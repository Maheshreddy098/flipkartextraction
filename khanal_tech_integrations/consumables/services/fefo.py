import json

from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
from khanal_tech_integrations.consumables.hana.inventory_queries import (
    get_batch_costs,
    get_item_batch_detail,
    get_item_current_cost,
    get_item_valuation_info,
)

_PLANT_STATE = {
    'HN-STR': 'KT',
    'NH-STR': 'KT',
    'DC-STR': 'KT',
    'ATP-HO': 'KT',
    'KG-STR': 'TN',
}

# Same state as plant → CGST+SGST
_INTRASTATE_TAX_CODE = {'KT': 'KACS0', 'TN': 'TNCS0'}
# Different state from plant → IGST
_INTERSTATE_TAX_CODE = {'KT': 'KAIG0', 'TN': 'TNIG0'}


def _get_customer_state(client, card_code):
    if not card_code:
        return None
    rows = client.execute(
        f'SELECT "State1" AS state FROM {client.schema}."OCRD" WHERE "CardCode" = ?',
        [card_code],
    )
    return (rows[0].get('state') or '').strip() if rows else None


def _build_tax_code(plant_code, customer_state=None):
    plant_state = _PLANT_STATE.get(str(plant_code or ''))
    if not plant_state:
        return ''
    if customer_state and customer_state.upper() != plant_state.upper():
        return _INTERSTATE_TAX_CODE.get(plant_state, '')
    return _INTRASTATE_TAX_CODE.get(plant_state, '')


class InsufficientStockError(Exception):
    def __init__(self, item_code, item_name, requested, available):
        self.item_code = item_code
        self.item_name = item_name
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for {item_name} ({item_code}): "
            f"requested {requested}, available {available}"
        )


def run_fefo_for_delivery_note(doc):
    """Run FEFO allocation for every line item in a Delivery Note doc.

    Price source: there are no FIFO-valuated items in this SAP company, so
    every batch-managed item (ManBtchNum=Y) is priced the same way — each
    allocated batch at its OWN batch cost (get_batch_costs: the Batch
    Details figure, OBTN.CostTotal / OBTN.Quantity), kept separate per batch
    rather than blended into one line-level number. A batch with no cost on
    record falls back to the item's current SAP cost; a non-batch item has
    only one cost SAP holds for it: OINM.CalcPrice.

    Mutates doc.line_items in place.
    Raises InsufficientStockError on the first item with insufficient stock.
    """
    with ConsumablesHANAClient() as client:
        item_codes = [item.item_code for item in doc.line_items]
        valuation_info = get_item_valuation_info(client, item_codes)
        item_current_costs = get_item_current_cost(client, doc.warehouse, item_codes)
        batch_costs = get_batch_costs(client, item_codes)
        customer_state = _get_customer_state(client, getattr(doc, 'sap_customer_code', None))

        for item in doc.line_items:
            info = valuation_info.get(item.item_code, {})
            is_batch = info.get("is_batch", False)
            tax_code = _build_tax_code(doc.plant, customer_state)
            calc_price = item_current_costs.get(item.item_code, 0.0)

            if is_batch:
                batches = get_item_batch_detail(client, doc.warehouse, item.item_code)
                allocations, total = _allocate(batches, float(item.requested_quantity))
                if total < float(item.requested_quantity):
                    item.fefo_status = "Insufficient Stock"
                    item.fefo_batches = json.dumps([])
                    item.total_allocated_quantity = total
                    raise InsufficientStockError(
                        item.item_code,
                        item.item_name or item.item_code,
                        float(item.requested_quantity),
                        total,
                    )
                priced_allocations = _price_per_batch(
                    allocations, batch_costs, item.item_code, fallback_price=calc_price
                )
                total_value = sum(float(a["price"]) * float(a["qty"]) for a in priced_allocations)
                avg_price = round(total_value / total, 6) if total > 0 else calc_price
                item.fefo_batches = json.dumps(priced_allocations)
                item.total_allocated_quantity = total
                item.fefo_status = "Allocated"
                item.unit_price = avg_price
                item.reference_cost = avg_price

            else:
                # Non-batch: CalcPrice.
                qty = float(item.requested_quantity or 0)
                item.fefo_batches = json.dumps([{"batch": "", "qty": qty, "price": calc_price}])
                item.total_allocated_quantity = qty
                item.fefo_status = "Allocated"
                item.unit_price = calc_price
                item.reference_cost = calc_price

            if tax_code:
                item.tax_code = tax_code


def _allocate(batches: list, requested_qty: float) -> tuple:
    """Greedy FIFO allocation. Returns (allocations, total_allocated).

    batches must already be sorted by InDate ASC (get_item_batch_detail
    guarantees this via ORDER BY T0."InDate" ASC, SysNumber ASC).
    """
    remaining = requested_qty
    allocations = []

    for batch in batches:
        if remaining <= 0:
            break
        available = float(batch.get("quantity") or 0)
        if available <= 0:
            continue
        take = min(available, remaining)
        allocations.append({
            "batch": batch["batch_number"],
            "qty": round(take, 6),
        })
        remaining = round(remaining - take, 6)

    total_allocated = round(requested_qty - remaining, 6)
    return allocations, total_allocated


def _price_per_batch(allocations: list, batch_costs: dict, item_code: str,
                     fallback_price: float = 0.0) -> list:
    """Price each batch allocation at its OWN batch cost — the number SAP's
    Batch Details window shows for that lot (get_batch_costs: OBTN.CostTotal
    divided by OBTN.Quantity), kept separate per batch — no blending into one
    averaged number for the line. A batch with no cost on record (absent from
    batch_costs) is priced at fallback_price (this item's current SAP cost)
    rather than 0.

    Returns a new list of allocation dicts with a "price" key added to each
    — this is what actually gets posted to SAP, one DocumentLine per batch.
    """
    priced = []
    for a in allocations:
        price = batch_costs.get((item_code, a["batch"]), 0.0)
        if price <= 0:
            price = fallback_price
        priced.append({**a, "price": round(price, 6)})
    return priced
