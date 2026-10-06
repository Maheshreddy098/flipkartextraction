"""
Post SAP B1 AR Credit Notes for Amazon US refunds, sourced from a manually
downloaded Seller Central "Custom Unified Transaction" report (the same
report referred to as the MTR-equivalent for Amazon US).

This is a bridge for backfilling refunds that predate the automated
Lambda/SP-API Finances pipeline (Phase 4 of the AWS migration already does
this properly via the live Finances API) -- ponytail: CSV backfill only,
not a permanent ingestion path. Once the Lambda stack is live, refunds flow
through post_credit_notes.py there instead.

Flow per refund event (one order_id + one date/time = one event, since
Amazon groups all SKU adjustments of one return together on one row-block):
  1. Parse "Refund" type rows, group by (order id, date/time).
  2. Duplicate guard: NumAtCard = refund_id (order_id + compact timestamp);
     skip if already in SAP -- safe to re-run any number of times.
  3. Find the staged order + its posted invoice (sap_doc_entry). No invoice
     means nothing to BaseEntry-link against -- skipped for manual follow-up.
  4. Read DocumentLines straight from the order's own stored payload_json
     (the exact payload that was POSTed for the invoice) -- LineNum is the
     line's position in that array, matching what SAP assigned.
  5. Build + post the credit note. Returned stock receives into the SAME
     batches the invoice line shipped from (spillover onto the last batch
     if the refunded qty exceeds what that line's batches recorded) --
     the same rule proven for the Amazon Flex and AWS Lambda credit notes.
  6. Mark the order's cn_doc_entry/cn_doc_num/refunded_at.

dry_run=True: computes the same payload and duplicate-checks against SAP,
never posts, never mutates order state.
"""
import csv
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import frappe
from frappe.utils import now_datetime

from khanal_tech_integrations.amazon_us import ORDER_DOCTYPE, enforce_posting_cutoff
from khanal_tech_integrations.amazon_us.client.sap import (
    find_credit_note_by_ref,
    find_invoice_by_order_id,
    get_credit_note_lines,
    post_credit_note,
)
from khanal_tech_integrations.amazon_us.mappers.payload import (
    _FALLBACK_TAX_CODE,
    _SHIPPING_GL_ACCOUNT,
    _SHIPPING_ITEM_CODE,
    _TAX_GL_ACCOUNT,
    _TAX_ITEM_CODE,
    build_line_udfs,
    get_item_mapping,
)

_DT_FORMAT = "%b %d, %Y %I:%M:%S %p"  # "Jun 1, 2026 12:21:48 PM" (trailing tz abbrev stripped)

# Same rationale as invoice.py's pool: SAP license has no concurrent-session
# ceiling, so 8 is a server-capacity choice, not a license one.
_POOL_SIZE = 8


# ─── Cache helpers (same pattern as invoice.py / settlement.py) ──────────────
# _progress_lock guards the Redis read-modify-write below against the
# _POOL_SIZE workers in _run_refund_events emitting concurrently.
_progress_lock = threading.Lock()


def _cache_key(job_id):
    return f"amz_us_creditnote_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[amz_creditnote] {msg}")
        return
    with _progress_lock:
        raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        log = data.get("log", [])
        log.append({"msg": msg, "level": level, "at": str(now_datetime())})
        data["log"] = log[-200:]
        frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


def _set(job_id, updates):
    if not job_id:
        return
    with _progress_lock:
        raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        data.update(updates)
        frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


# ─── CSV parsing ──────────────────────────────────────────────────────────────

def _parse_dt(raw):
    """'Jun 1, 2026 12:21:48 PM PDT' -> datetime (tz abbreviation dropped, not needed for grouping)."""
    parts = raw.strip().rsplit(" ", 1)
    body = parts[0] if len(parts) == 2 else raw.strip()
    return datetime.strptime(body, _DT_FORMAT)


def _parse_refund_events(csv_path):
    """
    Read a Seller Central "Custom (Unified) Transaction" CSV and group all
    "Refund" type rows by (order id, date/time) into refund events.

    Returns a list of dicts:
      {refund_id, amazon_order_id, posted_date, item_adjustments: [
          {seller_sku, principal_amount, tax_amount,
           shipping_amount, shipping_tax_amount}, ...
      ]}
    """
    with open(csv_path, encoding="utf-8-sig") as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('"date/time"'):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find the column header row (expected a line starting with \"date/time\")")

    reader = csv.DictReader(io.StringIO("".join(lines[header_idx:])))

    groups = {}  # (order_id, compact_dt) -> event dict, insertion-ordered
    for row in reader:
        if (row.get("type") or "").strip() != "Refund":
            continue
        order_id = (row.get("order id") or "").strip()
        raw_dt = (row.get("date/time") or "").strip()
        if not order_id or not raw_dt:
            continue

        dt = _parse_dt(raw_dt)
        key = (order_id, dt.strftime("%Y%m%d%H%M%S"))

        if key not in groups:
            groups[key] = {
                "refund_id": f"{order_id}-{key[1]}",
                "amazon_order_id": order_id,
                "posted_date": dt.strftime("%Y-%m-%d"),
                "item_adjustments": [],
            }

        groups[key]["item_adjustments"].append({
            "seller_sku": (row.get("sku") or "").strip(),
            "principal_amount": float(row.get("product sales") or 0),
            "tax_amount": float(row.get("product sales tax") or 0),
            "shipping_amount": float(row.get("shipping credits") or 0),
            "shipping_tax_amount": float(row.get("shipping credits tax") or 0),
        })

    return list(groups.values())


# ─── Payload building (same shape as domain/credit_note_builder.py in the AWS package) ───

def _pop_matching_invoice_line(lines_by_item_code, item_code):
    lines = lines_by_item_code.get(item_code)
    return lines.pop(0) if lines else None


def _receiving_batches(invoice_line, qty):
    """Fill the invoice line's own shipped batches in order until qty is covered,
    spilling remainder onto the last one used."""
    shipped_batches = invoice_line.get("BatchNumbers") or []
    if not shipped_batches:
        return None

    allocation = []
    remaining = qty
    for batch in shipped_batches:
        if remaining <= 0:
            break
        shipped_qty = float(batch.get("Quantity") or 0)
        take = min(remaining, shipped_qty)
        if take <= 0:
            continue
        allocation.append({"BatchNumber": batch.get("BatchNumber"), "Quantity": round(take, 6)})
        remaining = round(remaining - take, 6)

    if remaining > 0:
        if allocation:
            allocation[-1]["Quantity"] = round(allocation[-1]["Quantity"] + remaining, 6)
        else:
            allocation = [{"BatchNumber": shipped_batches[0].get("BatchNumber"), "Quantity": round(qty, 6)}]

    return allocation


def _build_credit_note_payload(event, order_doc, settings, item_mapping, tax_code):
    """Returns (payload, skipped). payload is None if there is nothing postable."""
    if not order_doc.sap_doc_entry or not order_doc.payload_json:
        return None, [{"reason": "Order has no posted invoice to credit against"}]

    invoice_lines = json.loads(order_doc.payload_json).get("DocumentLines", [])
    for idx, line in enumerate(invoice_lines):
        line["LineNum"] = idx
    lines_by_item_code = {}
    for line in invoice_lines:
        lines_by_item_code.setdefault(line.get("ItemCode"), []).append(line)

    unit_price_by_sku = {row.seller_sku: float(row.unit_price or 0) for row in order_doc.items}
    line_udfs = build_line_udfs(order_doc)

    doc_lines = []
    skipped = []
    total_tax = 0.0
    total_shipping = 0.0
    line_num = 0

    for adj in event["item_adjustments"]:
        # Refunds return the shipping the buyer paid plus its tax, so the CN
        # must reverse the invoice's EXP000004 freight line and fold the
        # shipping tax into EXP000003 exactly like build_invoice_payload does.
        total_tax += adj["tax_amount"] + adj.get("shipping_tax_amount", 0)
        total_shipping += adj.get("shipping_amount", 0)
        unit_price = unit_price_by_sku.get(adj["seller_sku"])
        mapping = item_mapping.get(adj["seller_sku"])

        if not unit_price:
            skipped.append({"seller_sku": adj["seller_sku"], "reason": "No unit price on staged order"})
            continue

        # Find the base invoice line. The live SKU mapping can drift between
        # invoice-post time and refund time (the item master's U_Amz_SKU UDFs
        # get cleaned up continuously), so the current mapping is only the
        # first guess -- fall back to the item code the order was STAGED with,
        # since that's what the invoice was actually posted under. SAP rejects
        # any base-linked line whose ItemCode differs from the base line's.
        invoice_line = None
        if mapping:
            invoice_line = _pop_matching_invoice_line(lines_by_item_code, mapping["sap_item_code"])
        if invoice_line is None:
            staged_code = next(
                ((row.sap_item_code or "").strip() for row in order_doc.items
                 if row.seller_sku == adj["seller_sku"] and (row.sap_item_code or "").strip()),
                None,
            )
            if staged_code:
                invoice_line = _pop_matching_invoice_line(lines_by_item_code, staged_code)
        if invoice_line is None:
            skipped.append({"seller_sku": adj["seller_sku"], "reason": "No matching invoice line found"})
            continue

        qty = round(abs(adj["principal_amount"]) / unit_price, 6)
        if qty <= 0:
            continue

        line = {
            "LineNum": line_num,
            "BaseType": 13,  # AR Invoice
            "BaseEntry": int(order_doc.sap_doc_entry),
            "BaseLine": invoice_line.get("LineNum"),
            # Mirror the base line's code exactly -- see mapping-drift note above.
            "ItemCode": invoice_line.get("ItemCode"),
            "Quantity": qty,
            "UnitPrice": unit_price,
            "WarehouseCode": settings.sap_warehouse_code,
            "TaxCode": tax_code,
            **line_udfs,
        }
        batches = _receiving_batches(invoice_line, qty)
        if batches:
            line["BatchNumbers"] = batches
        doc_lines.append(line)
        line_num += 1

    if not doc_lines:
        return None, skipped

    if total_tax:
        doc_lines.append({
            "LineNum": line_num,
            "ItemCode": _TAX_ITEM_CODE,
            "Quantity": 1,
            "UnitPrice": round(abs(total_tax), 2),
            "WarehouseCode": settings.sap_warehouse_code,
            "TaxCode": tax_code,
            "AccountCode": _TAX_GL_ACCOUNT,
            **line_udfs,
        })
        line_num += 1

    if total_shipping:
        doc_lines.append({
            "LineNum": line_num,
            "ItemCode": _SHIPPING_ITEM_CODE,
            "Quantity": 1,
            "UnitPrice": round(abs(total_shipping), 2),
            "WarehouseCode": settings.sap_warehouse_code,
            "TaxCode": tax_code,
            "AccountCode": _SHIPPING_GL_ACCOUNT,
            **line_udfs,
        })

    # SAP's internal reconciliation refuses a CN dated before its base
    # invoice ("Reconciliation date must be on or after the last posting
    # date"), which happens when the refund event's PostedDate precedes the
    # invoice's ship-date DocDate. Clamp forward to the invoice date.
    doc_date = event["posted_date"]
    invoice_doc_date = (json.loads(order_doc.payload_json).get("DocDate") or "")[:10]
    if invoice_doc_date and doc_date < invoice_doc_date:
        doc_date = invoice_doc_date

    payload = {
        "CardCode": settings.sap_card_code,
        "DocDate": doc_date,
        "Series": int(settings.sap_credit_note_series),
        "NumAtCard": event["refund_id"],
        "PayToCode": settings.sap_pay_to_code,
        "DocumentLines": doc_lines,
    }
    return payload, skipped


# ─── Main worker ──────────────────────────────────────────────────────────────

def compare_csv_against_sap(csv_path, progress_id=None):
    """
    Parse a Custom Unified Transaction CSV and compute what each "Refund" row
    group WOULD look like as an AR Credit Note, purely to cross-check against
    what SAP already has (via post_refunds_from_finances_api). NEVER posts --
    no dry_run parameter exists here on purpose, so this can't accidentally
    become a second posting path.

    Why the CSV isn't a posting source: Amazon's own developer community has
    open, unresolved issues (selling-partner-api-models#2351,
    selling-partner-api-docs#2170) reporting that the Custom Unified
    Transaction Report (Seller Central UI, PST-based) and the Finances API
    (UTC, event-driven) do not reconcile 1:1 -- some refund events appear in
    one and not the other, and Amazon has not published a way to make them
    match exactly. Posting from both would double-post real money under two
    different NumAtCard values (see refund_id formats below) since SAP's
    dedup only catches exact-key repeats. The live Finances API
    (post_refunds_from_finances_api) is the single posting source; this
    function exists only so a human can eyeball "does SAP roughly match what
    Seller Central shows" -- not to drive automated posting.
    """
    _set(progress_id, {"status": "running"})
    _emit(progress_id, f"Parsing {csv_path}...")

    try:
        events = _parse_refund_events(csv_path)
    except Exception as e:
        _emit(progress_id, f"CSV parse failed: {e}", "error")
        result = {"status": "error", "message": str(e)}
        _set(progress_id, result)
        return result

    _emit(progress_id, f"Found {len(events)} refund events in CSV (comparison only, never posts)")
    return _run_refund_events(events, dry_run=True, progress_id=progress_id)


def post_refunds_from_finances_api(from_date, to_date, dry_run=True, progress_id=None):
    """
    Fetch refund events live from SP-API Finances API for [from_date, to_date]
    (YYYY-MM-DD Pacific calendar dates) and post AR Credit Notes for each.
    This is the only function that actually posts to SAP.
    """
    from khanal_tech_integrations.amazon_us.client.finances import fetch_refund_events
    from khanal_tech_integrations.amazon_us.client.sp_api import _pacific_day_to_utc

    enforce_posting_cutoff(from_date)
    _set(progress_id, {"status": "running"})
    posted_after = _pacific_day_to_utc(from_date, end_of_day=False)
    posted_before = _pacific_day_to_utc(to_date, end_of_day=True)
    _emit(progress_id, f"Fetching refund events from SP-API Finances: {posted_after} -> {posted_before}...")

    try:
        events = fetch_refund_events(posted_after, posted_before)
    except Exception as e:
        _emit(progress_id, f"Finances API fetch failed: {e}", "error")
        result = {"status": "error", "message": str(e)}
        _set(progress_id, result)
        return result

    _emit(progress_id, f"Found {len(events)} refund events ({'DRY RUN' if dry_run else 'LIVE POST'})")
    return _run_refund_events(events, dry_run, progress_id)


def _run_refund_events(events, dry_run, job_id):
    """
    Shared posting loop for both the CSV and live Finances API sources.
    Runs across a pool of _POOL_SIZE worker threads, each with its own SAP
    session (client.sap._get_session() already builds a fresh
    requests.Session() per call from a Redis-cached cookie, so this is
    thread-safe with no changes there) and its own frappe DB connection
    (frappe.init + frappe.connect per thread -- frappe.local is thread-local).
    No HANA connection needed here, unlike invoice.py's pool: credit notes
    reuse the base invoice's own stored batches (see _receiving_batches),
    never a fresh FEFO query.
    """
    settings = frappe.get_doc("Amazon US Settings")
    tax_code = settings.sap_tax_code or _FALLBACK_TAX_CODE
    item_mapping = get_item_mapping()

    site = frappe.local.site
    counts_lock = threading.Lock()
    counts = {"posted": 0, "skipped": 0, "failed": 0}
    details = []

    def _process_slice(slice_events):
        frappe.init(site=site)
        frappe.connect()
        try:
            for event in slice_events:
                refund_id = event["refund_id"]
                order_id = event["amazon_order_id"]
                try:
                    existing = find_credit_note_by_ref(refund_id)
                    if existing:
                        with counts_lock:
                            counts["skipped"] += 1
                        _emit(job_id, f"  SKIP {refund_id}: already in SAP DocNum={existing['doc_num']}")
                        continue

                    if not frappe.db.exists(ORDER_DOCTYPE, order_id):
                        with counts_lock:
                            counts["skipped"] += 1
                        _emit(job_id, f"  SKIP {refund_id}: order {order_id} not staged (fetch it first)", "warn")
                        continue

                    order_doc = frappe.get_doc(ORDER_DOCTYPE, order_id)
                    if order_doc.stage != "posted":
                        with counts_lock:
                            counts["skipped"] += 1
                        _emit(job_id, f"  SKIP {refund_id}: order {order_id} not posted yet (stage={order_doc.stage})", "warn")
                        continue

                    # Never trust the stored DocEntry blindly: after a company-DB
                    # swap, an order that wasn't reset still carries a pointer into
                    # the OLD DB, and the same DocEntry number in the new DB is some
                    # unrelated invoice -- base-linking against it produces
                    # "target item does not match base item" / wrong-date errors, or
                    # worst case silently credits a stranger's invoice. The invoice
                    # this pipeline posted always has NumAtCard = the Amazon order id,
                    # so that lookup is the authority on "does the base exist HERE".
                    base = find_invoice_by_order_id(order_id)
                    if not base:
                        with counts_lock:
                            counts["skipped"] += 1
                        _emit(job_id, f"  SKIP {refund_id}: base invoice not in connected SAP DB "
                                      f"(stale pointer DocEntry={order_doc.sap_doc_entry}; repost the order first)", "warn")
                        continue
                    if str(base["doc_entry"]) != str(order_doc.sap_doc_entry):
                        with counts_lock:
                            counts["skipped"] += 1
                        _emit(job_id, f"  SKIP {refund_id}: stored DocEntry={order_doc.sap_doc_entry} is stale "
                                      f"(SAP has DocEntry={base['doc_entry']} for this order; repost/reset first)", "warn")
                        continue

                    payload, line_skips = _build_credit_note_payload(event, order_doc, settings, item_mapping, tax_code)
                    if payload is None:
                        with counts_lock:
                            counts["skipped"] += 1
                        _emit(job_id, f"  SKIP {refund_id}: no postable lines ({line_skips})", "warn")
                        continue

                    if dry_run:
                        total = sum(float(l.get("Quantity", 0)) * float(l.get("UnitPrice", 0)) for l in payload["DocumentLines"])
                        with counts_lock:
                            details.append({"refund_id": refund_id, "order_id": order_id, "computed_total": round(total, 2)})
                            counts["posted"] += 1
                        _emit(job_id, f"  DRY_RUN {refund_id}: would post, computed_total={round(total, 2)}")
                        continue

                    sap_ref = post_credit_note(payload)
                    frappe.db.set_value(
                        ORDER_DOCTYPE, order_id,
                        {"cn_doc_entry": sap_ref["doc_entry"], "cn_doc_num": sap_ref["doc_num"], "refunded_at": str(now_datetime())},
                        update_modified=False,
                    )
                    frappe.db.commit()
                    with counts_lock:
                        counts["posted"] += 1
                    _emit(job_id, f"  OK {refund_id} -> DocEntry={sap_ref['doc_entry']} DocNum={sap_ref['doc_num']}")

                except Exception as e:
                    with counts_lock:
                        counts["failed"] += 1
                    _emit(job_id, f"  FAIL {refund_id}: {e}", "error")
        finally:
            frappe.destroy()

    slices = [events[i::_POOL_SIZE] for i in range(_POOL_SIZE)]
    with ThreadPoolExecutor(max_workers=_POOL_SIZE) as pool:
        futures = [pool.submit(_process_slice, s) for s in slices if s]
        for f in as_completed(futures):
            f.result()  # re-raise anything a worker didn't catch itself

    result = {
        "status": "dry_run" if dry_run else "done",
        "total": len(events),
        "posted": counts["posted"],
        "skipped": counts["skipped"],
        "failed": counts["failed"],
        "details": details[:200],
    }
    _emit(job_id, f"Done. Posted={counts['posted']} Skipped={counts['skipped']} Failed={counts['failed']}")
    _set(job_id, result)
    return result


# ─── One-off repair: shipping supplements for CNs posted before the shipping fix ───

def post_shipping_supplements(from_date, to_date, dry_run=True, progress_id=None):
    """
    Repair worker for credit notes posted before shipping charges were included
    in the CN payload (finance finding, 2026-07-09): those CNs reversed only the
    item principal and product tax, never the buyer's refunded shipping and its
    tax.

    For every refund event in [from_date, to_date] (Pacific calendar dates) that
    carries a shipping charge and/or shipping tax:
      - the original CN must already exist in SAP (NumAtCard = refund_id);
        events with no CN yet are skipped — the normal posting path now
        includes shipping, so they need no supplement.
      - CNs that already contain an EXP000004 freight line are skipped (posted
        after the fix), which makes re-runs of any window safe.
      - a service-only supplement CN is posted: EXP000004 for the shipping
        amount and EXP000003 for the shipping tax, same DocDate as the refund,
        NumAtCard = refund_id + "-SHIP" (its own duplicate guard).

    The supplement is deliberately NOT base-linked to the invoice: the freight
    line on the invoice is a GL service line, and the two-document total
    (original CN + supplement) is what must equal the MTR refund amount.
    """
    from khanal_tech_integrations.amazon_us.client.finances import fetch_refund_events
    from khanal_tech_integrations.amazon_us.client.sp_api import _pacific_day_to_utc

    enforce_posting_cutoff(from_date)
    _set(progress_id, {"status": "running"})
    posted_after = _pacific_day_to_utc(from_date, end_of_day=False)
    posted_before = _pacific_day_to_utc(to_date, end_of_day=True)
    _emit(progress_id, f"Fetching refund events for shipping supplements: {posted_after} -> {posted_before}...")

    try:
        events = fetch_refund_events(posted_after, posted_before)
    except Exception as e:
        _emit(progress_id, f"Finances API fetch failed: {e}", "error")
        result = {"status": "error", "message": str(e)}
        _set(progress_id, result)
        return result

    settings = frappe.get_doc("Amazon US Settings")
    tax_code = settings.sap_tax_code or _FALLBACK_TAX_CODE

    posted = skipped = failed = 0
    details = []

    for event in events:
        refund_id = event["refund_id"]
        order_id = event["amazon_order_id"]
        shipping = sum(adj.get("shipping_amount", 0) for adj in event["item_adjustments"])
        shipping_tax = sum(adj.get("shipping_tax_amount", 0) for adj in event["item_adjustments"])
        if not shipping and not shipping_tax:
            continue

        supplement_ref = f"{refund_id}-SHIP"
        try:
            original = find_credit_note_by_ref(refund_id)
            if not original:
                skipped += 1
                _emit(progress_id, f"  SKIP {refund_id}: no original CN in SAP (normal path will include shipping)")
                continue

            if find_credit_note_by_ref(supplement_ref):
                skipped += 1
                _emit(progress_id, f"  SKIP {refund_id}: supplement already posted")
                continue

            original_lines = get_credit_note_lines(original["doc_entry"])
            if any(line.get("ItemCode") == _SHIPPING_ITEM_CODE for line in original_lines):
                skipped += 1
                _emit(progress_id, f"  SKIP {refund_id}: original CN already carries shipping")
                continue

            line_udfs = {}
            if frappe.db.exists(ORDER_DOCTYPE, order_id):
                line_udfs = build_line_udfs(frappe.get_doc(ORDER_DOCTYPE, order_id))

            doc_lines = []
            if shipping:
                doc_lines.append({
                    "ItemCode": _SHIPPING_ITEM_CODE,
                    "Quantity": 1,
                    "UnitPrice": round(abs(shipping), 2),
                    "WarehouseCode": settings.sap_warehouse_code,
                    "TaxCode": tax_code,
                    "AccountCode": _SHIPPING_GL_ACCOUNT,
                    **line_udfs,
                })
            if shipping_tax:
                doc_lines.append({
                    "ItemCode": _TAX_ITEM_CODE,
                    "Quantity": 1,
                    "UnitPrice": round(abs(shipping_tax), 2),
                    "WarehouseCode": settings.sap_warehouse_code,
                    "TaxCode": tax_code,
                    "AccountCode": _TAX_GL_ACCOUNT,
                    **line_udfs,
                })

            payload = {
                "CardCode": settings.sap_card_code,
                "DocDate": event["posted_date"],
                "Series": int(settings.sap_credit_note_series),
                "NumAtCard": supplement_ref,
                "PayToCode": settings.sap_pay_to_code,
                "Comments": f"Shipping supplement to CN {original['doc_num']} (refund {refund_id})",
                "DocumentLines": doc_lines,
            }

            amount = round(abs(shipping) + abs(shipping_tax), 2)
            if dry_run:
                details.append({"refund_id": refund_id, "order_id": order_id,
                                "original_cn": original["doc_num"], "supplement_total": amount})
                _emit(progress_id, f"  DRY_RUN {refund_id}: would post supplement {amount} onto CN {original['doc_num']}")
                posted += 1
                continue

            sap_ref = post_credit_note(payload)
            posted += 1
            details.append({"refund_id": refund_id, "order_id": order_id,
                            "original_cn": original["doc_num"], "supplement_cn": sap_ref["doc_num"],
                            "supplement_total": amount})
            _emit(progress_id, f"  OK {refund_id}: supplement DocNum={sap_ref['doc_num']} total={amount}")

        except Exception as e:
            failed += 1
            _emit(progress_id, f"  FAIL {refund_id}: {e}", "error")

    result = {
        "status": "dry_run" if dry_run else "done",
        "total_events": len(events),
        "posted": posted,
        "skipped": skipped,
        "failed": failed,
        "details": details[:200],
    }
    _emit(progress_id, f"Done. Posted={posted} Skipped={skipped} Failed={failed}")
    _set(progress_id, result)
    return result
