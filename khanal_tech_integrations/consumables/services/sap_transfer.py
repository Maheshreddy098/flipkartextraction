import frappe
from frappe.utils import today

_INTRANSIT_WAREHOUSE = {
    "DC-STR": "DC-IT",
    "KG-STR": "KG-IT",
    "NH-STR": "NH-IT",
    "HN-STR": "HN-IT",
    "ATP-HO": "ATP-IT",
}


def get_intransit_warehouse(to_plant: str) -> str | None:
    """Return the in-transit warehouse code for a destination plant, or None if not applicable."""
    return _INTRANSIT_WAREHOUSE.get(str(to_plant or "").strip())


def _get_live_batches(warehouse_code: str, item_code: str, quantity: float) -> list[dict]:
    """Fetch current FEFO batches from HANA for one item. Returns list of
    {BatchNumber, Quantity} dicts ready for SAP Service Layer."""
    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    from khanal_tech_integrations.consumables.hana.inventory_queries import get_item_batch_detail

    with ConsumablesHANAClient() as client:
        batches = get_item_batch_detail(client, warehouse_code, item_code)

    remaining = quantity
    result = []
    for b in batches:
        if remaining <= 0:
            break
        avail = float(b.get("quantity") or 0)
        if avail <= 0:
            continue
        take = min(avail, remaining)
        result.append({"BatchNumber": b["batch_number"], "Quantity": round(take, 6)})
        remaining = round(remaining - take, 6)

    return result


def _build_batch_lines(warehouse_code: str, item_code: str, quantity: float) -> list[dict] | None:
    """Resolve the BatchNumbers array for a line item using live HANA data.

    Always fetches current FEFO batches at posting time — never uses the
    batch_number stored on the transfer line, which may be stale (consumed
    or moved by the time the transfer is approved/dispatched).

    Returns None for non-batch-managed items (no batches in HANA) — caller
    must omit the BatchNumbers key entirely.
    """
    live = _get_live_batches(warehouse_code, item_code, quantity)
    return live if live else None




def post_stock_transfer_to_intransit(doc, batch_splits: dict | None = None):
    """First StockTransfer on dispatch: source warehouse → destination's in-transit warehouse.

    batch_splits: {item_code: [{batch_number, quantity}]} from dispatch dialog.
    For ATP-HO as destination (no in-transit), posts directly source → destination warehouse.

    Returns (doc_entry, doc_num, dest_warehouse).
    """
    from khanal_tech_integrations.unicommerce.client.sap import SAPClient

    intransit = get_intransit_warehouse(doc.to_plant)
    dest_warehouse = intransit or doc.to_warehouse

    lines = []
    for item in doc.line_items:
        actual_qty = float(item.quantity or 0)
        if actual_qty <= 0:
            continue
        line = {
            "ItemCode": item.item_code,
            "Quantity": actual_qty,
            "FromWarehouseCode": doc.from_warehouse,
            "WarehouseCode": dest_warehouse,
        }
        if batch_splits and item.item_code in batch_splits:
            splits = batch_splits[item.item_code]
            if splits:
                line["BatchNumbers"] = [
                    {"BatchNumber": s["batch_number"], "Quantity": float(s["quantity"])}
                    for s in splits
                    if s.get("batch_number") and float(s.get("quantity") or 0) > 0
                ]
        else:
            batch_lines = _build_batch_lines(doc.from_warehouse, item.item_code, actual_qty)
            if batch_lines:
                line["BatchNumbers"] = batch_lines
        lines.append(line)

    payload = {
        "DocDate": today(),
        "FromWarehouse": doc.from_warehouse,
        "ToWarehouse": dest_warehouse,
        "Comments": f"StoreOps Dispatch: {doc.name}",
        "StockTransferLines": lines,
    }
    client = SAPClient(settings_doctype="Consumables SAP Settings")
    result = client.post("StockTransfers", payload)
    if not result or "DocEntry" not in result:
        frappe.throw(frappe._("SAP returned empty response for dispatch StockTransfer — DocEntry missing."))
    return result["DocEntry"], result["DocNum"], dest_warehouse


def post_intransit_to_final_transfer(doc):
    """Second StockTransfer on receipt confirmation: destination's in-transit warehouse → destination warehouse.

    Only runs when the destination plant has an in-transit warehouse.
    For ATP-HO as destination (no in-transit), the first transfer already went source → destination; returns None.

    Returns (doc_entry, doc_num) or (None, None) if not applicable.
    """
    intransit = get_intransit_warehouse(doc.to_plant)
    if not intransit:
        return None, None

    from khanal_tech_integrations.unicommerce.client.sap import SAPClient

    lines = []
    for item in doc.line_items:
        received_qty = float(item.quantity_received or item.quantity or 0)
        if received_qty <= 0:
            continue
        line = {
            "ItemCode": item.item_code,
            "Quantity": received_qty,
            "FromWarehouseCode": intransit,
            "WarehouseCode": doc.to_warehouse,
        }
        batch_lines = _build_batch_lines(intransit, item.item_code, received_qty)
        if batch_lines:
            line["BatchNumbers"] = batch_lines
        lines.append(line)

    if not lines:
        return None, None

    payload = {
        "DocDate": today(),
        "FromWarehouse": intransit,
        "ToWarehouse": doc.to_warehouse,
        "Comments": f"StoreOps Receipt: {doc.name}",
        "StockTransferLines": lines,
    }
    client = SAPClient(settings_doctype="Consumables SAP Settings")
    result = client.post("StockTransfers", payload)
    if not result or "DocEntry" not in result:
        frappe.throw(frappe._("SAP returned empty response for final StockTransfer — DocEntry missing."))
    return result["DocEntry"], result["DocNum"]
