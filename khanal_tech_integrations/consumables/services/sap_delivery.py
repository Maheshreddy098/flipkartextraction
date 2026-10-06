import json
from collections import namedtuple

import frappe
from frappe.utils import today

from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
from khanal_tech_integrations.consumables.hana.inventory_queries import (
    get_batch_costs,
    get_item_current_cost,
)

# SAP G/L account consumption lines are booked to.
GL_ACCOUNT_CODE = "52112000"

# Items that book to a different G/L account than the default. Keys are item codes
# in upper case.
ITEM_GL_ACCOUNT_CODE = {
    "COCM0121": "51201510",
}

# One DocumentLine, plus what we need to price-check it before it is sent.
_Line = namedtuple("_Line", "payload item_code batch qty price")


# SAP rejects a whole document at once for this rule and never says which line
# caused it (confirmed: even a document where every line's UnitPrice already
# equals our own read of Batch Cost can still be refused). We price each line
# from that batch's own standing cost — the figure SAP's Batch Details window
# shows (OBTN.CostTotal / OBTN.Quantity) — but SAP's own DocAdd can still
# revalue the batch at post time to a number our last read didn't see — some
# items' costs move live, between our read and SAP's commit (confirmed: same
# item/batch/qty posted twice, seconds apart, accepted at two different
# prices). There is no query that predicts that in advance with certainty, so
# it cannot be pre-validated away.
_PRICE_ERROR_MARKERS = ("9876", "item cost", "unit price")


def post_delivery_note_to_sap(doc):
    """POST the delivery note to SAP.

    Returns ([(doc_entry, doc_num), ...], skipped_lines).

    Each allocated batch is its own DocumentLine, priced (see _price_lines) at
    that specific batch's own batch cost — the number SAP's Batch Details
    window shows (OBTN.CostTotal / OBTN.Quantity) — or OINM.CalcPrice as a
    fallback when the batch has no cost on record. Sending that number back
    to SAP is what guarantees the line is accepted.

    All priced lines are posted together as ONE document — always, unless SAP
    itself refuses it. That can still happen on rare, genuine data problems this
    file cannot see in advance (e.g. an item with no cost on record at all, or
    SAP's own live figure moving between our read and its write). SAP's
    rejection names no line, so the only way to find which is to ask SAP: the
    failed batch is split in half and each half is tried again, recursively,
    ONLY as a fallback and ONLY on that specific rejection — so a document only
    ever splits around the lines actually in question, staying consolidated
    everywhere else. Isolated lines are held back and reported to Super Admins
    with SAP's own wording. Any other failure (auth, network, an unrelated SAP
    error) is not treated as this case and is raised as before.
    """
    lines = _build_lines(doc)
    if not lines:
        return [], []

    to_post, skipped = _price_lines(doc, lines)
    if not to_post:
        frappe.logger().warning(
            f"SAP Delivery Note {doc.name}: no cost found in SAP for any line — nothing posted"
        )
        return [], skipped

    header = _build_header(doc)
    results = _post_bisecting(doc, header, to_post, skipped)

    if not results:
        frappe.logger().warning(f"SAP Delivery Note {doc.name}: every line was rejected by SAP")
    return results, skipped


def _post_bisecting(doc, header, lines, skipped):
    """POST `lines` as one document; on a price rejection, split in half and
    retry each half the same way, recursing until only the true outlier lines
    are isolated. Returns the (doc_entry, doc_num) of every document posted.

    Every retry re-reads its lines' prices right before attempting them (see
    _refresh_prices) — a rejection means real time has already passed since
    _price_lines ran (the failed attempt's own round-trip to SAP, plus any
    earlier retries), and for an item whose live cost is moving fast that gap
    is exactly what turns a correct price into a stale one. The first,
    top-level attempt does not re-read: it runs right after _price_lines and
    doing it again would just repeat the same query for no benefit.
    """
    try:
        return [_post_lines(header, lines)]
    except Exception as e:
        if not _is_price_rejection(e):
            raise
        error_text = str(e)

    if len(lines) == 1:
        skipped.append(f"{lines[0].item_code}: SAP rejected this line — {error_text}")
        return []

    frappe.logger().warning(
        f"SAP Delivery Note {doc.name}: a {len(lines)}-line document was rejected on price — "
        "splitting it in half to isolate which line(s)"
    )
    mid = len(lines) // 2
    first_half, second_half = lines[:mid], lines[mid:]
    _refresh_prices(doc, first_half)
    _refresh_prices(doc, second_half)
    return (
        _post_bisecting(doc, header, first_half, skipped)
        + _post_bisecting(doc, header, second_half, skipped)
    )


def _refresh_prices(doc, lines):
    """Re-read every line's cost basis right now and re-stamp its UnitPrice —
    the same logic _price_lines uses, run again immediately before a retry so
    the price sent is as current as SAP's own figure can be gotten."""
    item_codes = list({ln.item_code for ln in lines})
    with ConsumablesHANAClient() as hana:
        item_costs = get_item_current_cost(hana, doc.warehouse, item_codes)
        _price_lines_by_batch(hana, doc.warehouse, lines, item_costs)


def _price_lines_by_batch(hana, warehouse, lines, item_costs):
    """Price every line from its own named batch's batch cost — the single
    number SAP's Batch Details window shows for that lot
    (get_batch_costs: OBTN.CostTotal / OBTN.Quantity). A batch is a distinct
    physical lot with its own standing cost, independent of any other batch
    of the same item, so each batch is priced from ONLY its own cost — never
    blended with another batch's.

    Lines that share the SAME batch (FEFO normally allocates one line per
    batch, so this is rare) all get that same one batch cost — there is no
    layering to drain: the batch's cost is one number, not a stack of
    receipts.

    A line with no batch, or whose batch has no cost on record, falls back
    to OINM.CalcPrice (item-level).

    Mutates ln.payload["UnitPrice"] for every line with a computed cost.
    Returns the lines that could not be priced at all (no batch cost and
    no item-level cost either).
    """
    by_key = {}
    for ln in lines:
        by_key.setdefault((ln.item_code, ln.batch), []).append(ln)

    item_codes = list({item_code for item_code, _ in by_key})
    batch_costs = get_batch_costs(hana, item_codes)

    unpriced = []
    for (item_code, batch), key_lines in by_key.items():
        cost = batch_costs.get((item_code, batch), 0.0) if batch else 0.0
        if cost <= 0:
            cost = float(item_costs.get(item_code) or 0)
        if cost > 0:
            for ln in key_lines:
                ln.payload["UnitPrice"] = cost
        else:
            unpriced.extend(key_lines)
    return unpriced


def _is_price_rejection(e) -> bool:
    text = str(e).lower()
    return any(marker in text for marker in _PRICE_ERROR_MARKERS)


def _post_lines(header, lines):
    """POST one SAP Delivery Note document carrying exactly these lines."""
    from khanal_tech_integrations.unicommerce.client.sap import SAPClient

    payload = {**header, "DocumentLines": [ln.payload for ln in lines]}
    frappe.logger().info(f"SAP Delivery Note Payload: {frappe.as_json(payload)}")
    try:
        result = SAPClient(settings_doctype="Consumables SAP Settings").post("DeliveryNotes", payload)
    except Exception as e:
        frappe.logger().error(f"SAP Delivery Note Error: {str(e)}")
        raise
    frappe.logger().info(f"SAP Delivery Note Response: {frappe.as_json(result)}")
    if not result or "DocEntry" not in result:
        frappe.throw(frappe._("SAP returned an empty or unexpected response for DeliveryNotes — DocEntry missing."))
    return (result["DocEntry"], result["DocNum"])


def _build_header(doc):
    """Document-level fields of the SAP payload."""
    comments = [f"StoreOps Consumption: {doc.name}"]
    if doc.purpose:
        comments.append(str(doc.purpose))
    if getattr(doc, "remarks", None):
        comments.append(str(doc.remarks))

    payload = {
        "DocType": "dDocument_Items",
        "CardCode": doc.sap_customer_code,
        "DocDate": str(doc.doc_date or today()),
        "DocDueDate": str(doc.doc_due_date or doc.doc_date or today()),
        "Comments": " | ".join(comments),
    }
    if doc.card_name:
        payload["CardName"] = doc.card_name
    if doc.series not in (None, ""):
        try:
            payload["Series"] = int(doc.series)
        except (TypeError, ValueError):
            payload["Series"] = doc.series

    address_code = (
        (doc.ship_to_code or doc.bill_to_code or "").strip()
        or _shared_bp_address_code(doc.sap_customer_code)
    )
    if address_code:
        payload["ShipToCode"] = address_code
        payload["PayToCode"] = address_code
    if doc.address:
        payload["Address"] = doc.address

    return payload


def _build_lines(doc):
    """One _Line per FEFO allocation, at the price FEFO gave that allocation."""
    lines = []

    for item in doc.line_items:
        item_price = float(item.unit_price or 0)
        allocations = [
            a for a in json.loads(item.fefo_batches or "[]") if _alloc_qty(a) > 0
        ]
        if not allocations:
            # Nothing allocated per batch — post the item as a single line.
            qty = float(
                item.total_allocated_quantity if item.total_allocated_quantity is not None
                else (item.requested_quantity or 0)
            )
            if qty <= 0:
                continue
            allocations = [{"batch": "", "qty": qty, "price": item_price}]

        for alloc in allocations:
            batch = (alloc.get("batch") or alloc.get("batch_code") or "").strip()
            qty = _alloc_qty(alloc)
            price = float(alloc["price"]) if alloc.get("price") is not None else item_price

            payload = {
                "ItemCode": item.item_code,
                "Quantity": qty,
                "WarehouseCode": doc.warehouse,
                "UnitPrice": price,
                "AccountCode": _gl_account_code(item.item_code),
            }
            if batch:
                payload["BatchNumbers"] = [{"BatchNumber": batch, "Quantity": qty}]
            if item.uom:
                payload["UnitOfMeasure"] = item.uom
            if item.tax_code:
                payload["TaxCode"] = item.tax_code

            lines.append(_Line(payload, item.item_code, batch, qty, price))

    return lines


def _gl_account_code(item_code):
    """G/L account for this item — the default, unless the item is one of the few
    that book somewhere else."""
    return ITEM_GL_ACCOUNT_CODE.get((item_code or "").strip().upper(), GL_ACCOUNT_CODE)


def _alloc_qty(alloc):
    return float(alloc.get("qty") or alloc.get("quantity") or 0)


def _price_lines(doc, lines):
    """Price every line from the cost basis SAP itself will book it at: a
    batch-managed item is priced from that SPECIFIC BATCH's own batch cost
    (get_batch_costs — the Batch Details figure, OBTN.CostTotal / OBTN.
    Quantity), not blended with any other batch of the same item. See
    _price_lines_by_batch for how a batch with no cost on record falls back
    to OINM.CalcPrice (item-level).

    Every line gets a price and is sent — nothing is proactively held back
    over a mismatch. A price this file cannot compute from any source at all
    (no batch receipt and no item cost either) is the only case left
    unpriced, and that is a genuine data gap, not a mismatch to police.
    """
    item_codes = list({ln.item_code for ln in lines})

    with ConsumablesHANAClient() as hana:
        item_costs = get_item_current_cost(hana, doc.warehouse, item_codes)
        unpriced = _price_lines_by_batch(hana, doc.warehouse, lines, item_costs)

    unpriced_set = set(id(ln) for ln in unpriced)
    priced = [ln for ln in lines if id(ln) not in unpriced_set]
    skipped = [
        f"{ln.item_code}: no cost found in SAP for this item or its batch "
        f"— not posted (qty {ln.qty:.3f})"
        for ln in unpriced
    ]
    return priced, skipped


def _shared_bp_address_code(card_code):
    """Return an address code that SAP has as both Ship-To and Bill-To for this BP."""
    card_code = (card_code or "").strip()
    if not card_code:
        return ""

    try:
        from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient

        with ConsumablesHANAClient() as client:
            rows = client.execute(
                f"""
SELECT T0."Address" AS address_code
FROM {client.schema}."CRD1" T0
WHERE T0."CardCode" = ?
  AND T0."Address" IS NOT NULL
  AND T0."Address" <> ''
  AND UPPER(T0."AdresType") IN ('S', 'B')
GROUP BY T0."Address"
HAVING COUNT(DISTINCT UPPER(T0."AdresType")) = 2
ORDER BY T0."Address"
""",
                [card_code],
            )
    except Exception:
        return ""

    return (rows[0].get("address_code") or "").strip() if rows else ""
