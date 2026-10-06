"""
Build a downloadable MTR-vs-SAP reconciliation workbook -- the same kind of
cross-check Finance built by hand in Excel (June_MTR_vs_SAP_Reconciliation.xlsx,
XLOOKUP against SAP DocNum) after every backfill, now generated from the
dashboard instead.

Ground truth for "what's in SAP" is pulled live from SAP (Invoices/CreditNotes
OData, filtered by CardCode + DocDate window), not from this app's own
sap_doc_entry/cn_doc_entry bookkeeping -- those fields only describe whichever
SAP company DB this pipeline last posted to, so after a DB swap (new test DB,
eventual live cutover) they can't be trusted as "does SAP have this" on their
own. Querying SAP directly is what actually answers that question.

MTR side reuses the same "Custom Unified Transaction" CSV format as
workers/credit_note.py's CSV path: "Order" rows grouped by order id (one
invoice per order, matched to SAP by NumAtCard = order id). Refund rows are
aggregated PER ORDER, not per refund event: the MTR's refund timestamp
(Seller Central, PST) and the Finances API's PostedDate (UTC, often days
later -- June-MTR refunds carry July event dates) never agree, and each side
bakes its own timestamp into the refund_id/NumAtCard, so event-level ids can
never string-match across the two systems. Summing both sides per order and
comparing totals sidesteps the timestamp entirely -- and also folds the
"-SHIP" supplement CNs (whose NumAtCard is refund_id+"-SHIP") into the same
order bucket, which is exactly right: original CN + supplement together are
what must equal the MTR refund amount.
"""
import csv
import io
import os
import re

from datetime import datetime, timedelta

import frappe
from frappe.utils import now_datetime

from khanal_tech_integrations.amazon_us.workers.credit_note import _parse_refund_events

_AMOUNT_TOLERANCE = 0.02  # SAP rounds to 2dp per line; a few paisa of float drift is not a real mismatch


def _cache_key(job_id):
    return f"amz_us_recon_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[amz_recon] {msg}")
        return
    import json
    raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    log = data.get("log", [])
    log.append({"msg": msg, "level": level, "at": str(now_datetime())})
    data["log"] = log[-100:]
    frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


def _set(job_id, updates):
    import json
    if not job_id:
        return
    raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    data.update(updates)
    frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


# What the buyer actually paid, per MTR row. Deliberately NOT the CSV's own
# "total" column -- that nets Amazon's selling/FBA fees into the figure (it is
# the seller's payout impact), while the SAP invoice carries the buyer-facing
# charge. Verified empirically against 60 posted invoices: these columns match
# SAP DocTotal to the cent; the "total" column matches none of them.
_BUYER_COLUMNS = (
    "product sales", "product sales tax",
    "shipping credits", "shipping credits tax",
    "gift wrap credits", "giftwrap credits tax",
    "Regulatory Fee", "Tax On Regulatory Fee",
    "promotional rebates", "promotional rebates tax",
)


def _parse_order_rows(csv_path):
    """Group 'Order' type rows by order id.
    Returns ({order_id: buyer_paid_total}, {order_id: mtr_unit_qty})."""
    with open(csv_path, encoding="utf-8-sig") as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('"date/time"'):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError('Could not find the column header row (expected a line starting with "date/time")')

    reader = csv.DictReader(io.StringIO("".join(lines[header_idx:])))
    totals = {}
    qtys = {}
    for row in reader:
        if (row.get("type") or "").strip() != "Order":
            continue
        order_id = (row.get("order id") or "").strip()
        if not order_id:
            continue
        buyer_paid = sum(float(row.get(col) or 0) for col in _BUYER_COLUMNS)
        totals[order_id] = totals.get(order_id, 0.0) + buyer_paid
        try:
            qtys[order_id] = qtys.get(order_id, 0.0) + float(row.get("quantity") or 0)
        except ValueError:
            pass
    return {k: round(v, 2) for k, v in totals.items()}, qtys


def _load_local_orders(order_ids):
    """Bulk map {order_id: {stage, last_error, purchase_date, ship_date, qty, cn_doc_num, refunded_at}}
    from the staging doctype, for remark generation."""
    if not order_ids:
        return {}
    rows = frappe.db.sql(
        """SELECT o.name, o.stage, o.last_error, o.purchase_date, o.actual_ship_date,
                  o.sap_doc_num, o.cn_doc_num, o.refunded_at,
                  COALESCE(SUM(i.quantity), 0) AS qty
           FROM `tabAmazon US Order` o
           LEFT JOIN `tabAmazon US Order Item` i ON i.parent = o.name
           WHERE o.name IN %(ids)s
           GROUP BY o.name""",
        {"ids": tuple(order_ids)}, as_dict=True,
    )
    return {r.name: r for r in rows}


def _invoice_remark(status, diff, local, mtr_qty):
    """One finance-readable sentence explaining every non-MATCH invoice row."""
    if status == "MATCH":
        return ""
    if status == "AMOUNT MISMATCH":
        if local is not None and mtr_qty and float(local.qty or 0) > mtr_qty:
            return (
                f"Quantity split across MTR months: invoice covers {local.qty:g} unit(s), "
                f"June MTR shows {mtr_qty:g} — the rest settles in the next month's MTR "
                f"(MTR is settlement-date indexed; invoice is per order)."
            )
        return (
            f"Amount differs by {diff}: SAP invoice does not equal the buyer-paid MTR total "
            f"(check promotional rebates / partial settlement rows for this order)."
        )
    if status == "MISSING IN SAP":
        if local is None:
            return "Order was never staged from Amazon (outside every fetch window) — fetch and post it."
        if local.stage == "failed":
            return f"SAP rejected the invoice: {(local.last_error or 'unknown error').strip()}"
        if local.stage == "fetched":
            err = (local.last_error or "").strip()
            return f"Not postable yet: {err or 'awaiting SKU mapping'}"
        if local.stage == "ready":
            return "Staged and ready but not yet posted — run Post to SAP."
        if local.stage == "posted":
            return (
                "Marked posted locally but the invoice is not in this SAP DB "
                "(posted to a previously connected DB) — reset and repost this order."
            )
        return f"Order stage is '{local.stage}' — not posted."
    if status == "IN SAP, NOT IN MTR":
        return (
            "Invoice exists in SAP but the order has no June MTR row — it settles in an "
            "adjacent MTR month (MTR is settlement-date indexed, posting is ship-date based)."
        )
    return ""


def _cn_remark(status, diff, local, _mtr_qty=None):
    """Finance-readable remark for every non-MATCH credit-note row."""
    if status == "MATCH":
        return ""
    if status == "AMOUNT MISMATCH":
        return (
            f"Refund amount differs by {diff}: part of this order's refund was issued as a "
            f"separate event outside the June window (Finances API event dates lag the MTR) — "
            f"the remaining credit note lands with a later date."
        )
    if status == "MISSING IN SAP":
        if local is None:
            return "Order was never staged from Amazon — its base invoice does not exist here, so no credit note could be posted."
        if local.stage != "posted":
            err = (local.last_error or "").strip()
            return f"No credit note because the base invoice is not posted (order stage '{local.stage}'{': ' + err if err else ''})."
        if not (local.cn_doc_num or "").strip():
            return (
                "Base invoice belongs to a previous SAP DB (order predates this repost window) — "
                "repost the order's invoice here first, then re-run credit notes."
            )
        return "Credit note recorded locally but not found in this SAP DB — re-run credit notes."
    if status == "IN SAP, NOT IN MTR":
        return (
            "Credit note is dated after June (Finances API refund events lag the MTR month) — "
            "this refund appears in the following month's MTR."
        )
    return ""


def _fetch_sap_docs(entity, from_date, to_date, card_code):
    """Bulk-pull {NumAtCard: {doc_num, doc_entry, doc_total, doc_date}} from SAP
    for the given entity ('Invoices' or 'CreditNotes'), CardCode and DocDate window."""
    from khanal_tech_integrations.amazon_us.client.sap import _get_session
    from khanal_tech_integrations.amazon_us import SAP_VERIFY_SSL

    session, b1_url = _get_session()
    select = "DocEntry,DocNum,NumAtCard,DocTotal,DocDate"
    # CancelStatus eq 'csNo' drops both cancelled originals (csCancelled) and
    # their cancellation documents (csCancellation) -- they share the
    # NumAtCard and would otherwise clobber the live document in the map.
    # (Cancellation docs do NOT carry Cancelled='tYES', so filtering on the
    # Cancelled flag alone lets them through.)
    url = (
        f"{b1_url}{entity}?$filter=CardCode eq '{card_code}' and DocDate ge '{from_date}' and DocDate le '{to_date}'"
        f" and CancelStatus eq 'csNo'&$select={select}&$orderby=DocDate"
    )
    docs = {}
    while url:
        resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=60, headers={"Prefer": "odata.maxpagesize=1000"})
        if resp.status_code == 401:
            frappe.cache().delete_value("amazon_us_sap_session")
            session, b1_url = _get_session()
            continue
        resp.raise_for_status()
        data = resp.json()
        for row in data.get("value", []):
            num_at_card = (row.get("NumAtCard") or "").strip()
            if num_at_card:
                docs[num_at_card] = {
                    "doc_num": row.get("DocNum"),
                    "doc_entry": row.get("DocEntry"),
                    "doc_total": round(float(row.get("DocTotal") or 0), 2),
                    "doc_date": row.get("DocDate"),
                }
        url = data.get("odata.nextLink") or ""
        if url and not url.startswith("http"):
            url = b1_url + url
    return docs


def _build_rows(mtr_totals, sap_docs, id_label, locals_map=None, mtr_qtys=None, remark_fn=None):
    """Cross-match one MTR total-map against one SAP doc-map. Returns list of row
    dicts enriched with local staging state and a finance-readable remark."""
    locals_map = locals_map or {}
    mtr_qtys = mtr_qtys or {}
    rows = []
    all_ids = set(mtr_totals) | set(sap_docs)
    for doc_id in sorted(all_ids):
        mtr_total = mtr_totals.get(doc_id)
        sap = sap_docs.get(doc_id)
        if mtr_total is not None and sap is not None:
            diff = round(mtr_total - sap["doc_total"], 2)
            status = "MATCH" if abs(diff) <= _AMOUNT_TOLERANCE else "AMOUNT MISMATCH"
        elif mtr_total is not None:
            diff = None
            status = "MISSING IN SAP"
        else:
            diff = None
            status = "IN SAP, NOT IN MTR"
        local = locals_map.get(doc_id)
        rows.append({
            id_label: doc_id,
            "purchase_date": str(local.purchase_date)[:10] if local and local.purchase_date else None,
            "ship_date": str(local.actual_ship_date)[:10] if local and local.actual_ship_date else None,
            "stage": local.stage if local else "not staged",
            "mtr_total": mtr_total,
            "sap_doc_num": sap["doc_num"] if sap else None,
            "sap_total": sap["doc_total"] if sap else None,
            "diff": diff,
            "status": status,
            "remarks": remark_fn(status, diff, local, mtr_qtys.get(doc_id)) if remark_fn else "",
        })
    return rows


_ORDER_ID_RE = re.compile(r"^(\d{3}-\d{7}-\d{7})")


def _aggregate_by_order(doc_map):
    """Collapse {NumAtCard: doc} into {order_id: {doc_num: "123, 124", doc_total: sum}}.
    NumAtCard formats seen: '<order_id>' (invoices), '<order_id>-<timestamp>' (CNs),
    '<order_id>-<timestamp>-SHIP' (shipping supplement CNs) -- all share the
    Amazon order-id prefix."""
    by_order = {}
    for num_at_card, doc in doc_map.items():
        m = _ORDER_ID_RE.match(num_at_card)
        if not m:
            continue
        order_id = m.group(1)
        agg = by_order.setdefault(order_id, {"doc_num": [], "doc_total": 0.0, "doc_entry": None, "doc_date": doc["doc_date"]})
        agg["doc_num"].append(str(doc["doc_num"]))
        agg["doc_total"] = round(agg["doc_total"] + doc["doc_total"], 2)
    return {
        oid: {"doc_num": ", ".join(a["doc_num"]), "doc_total": a["doc_total"], "doc_entry": a["doc_entry"], "doc_date": a["doc_date"]}
        for oid, a in by_order.items()
    }


def _write_workbook(invoice_rows, cn_rows, out_path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    bad_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    header_font = Font(bold=True)

    def _sheet(ws, rows, id_label):
        headers = [
            "Amazon Order ID", "Purchase Date", "Ship Date", "Stage",
            "MTR Amount (USD)", "SAP Doc Num", "SAP Amount (USD)",
            "Difference (USD)", "Status", "Remarks",
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = header_font
        for r in rows:
            ws.append([
                r[id_label], r["purchase_date"], r["ship_date"], r["stage"],
                r["mtr_total"], r["sap_doc_num"], r["sap_total"],
                r["diff"], r["status"], r["remarks"],
            ])
            if r["status"] != "MATCH":
                for cell in ws[ws.max_row]:
                    cell.fill = bad_fill
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(width + 2, 70)

    ws_inv = wb.active
    ws_inv.title = "Invoices"
    _sheet(ws_inv, invoice_rows, "order_id")

    ws_cn = wb.create_sheet("Credit Notes")
    _sheet(ws_cn, cn_rows, "order_id")

    ws_sum = wb.create_sheet("Summary")
    ws_sum.append(["Sheet", "Matched", "Amount Mismatch", "Missing in SAP", "In SAP, Not in MTR", "Total"])
    for cell in ws_sum[1]:
        cell.font = header_font
    for label, rows in (("Invoices", invoice_rows), ("Credit Notes", cn_rows)):
        counts = {"MATCH": 0, "AMOUNT MISMATCH": 0, "MISSING IN SAP": 0, "IN SAP, NOT IN MTR": 0}
        for r in rows:
            counts[r["status"]] += 1
        ws_sum.append([label, counts["MATCH"], counts["AMOUNT MISMATCH"], counts["MISSING IN SAP"], counts["IN SAP, NOT IN MTR"], len(rows)])
    for col in ws_sum.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws_sum.column_dimensions[col[0].column_letter].width = min(width + 2, 30)

    wb.save(out_path)


def build_reconciliation_file(csv_path, from_date, to_date, progress_id=None):
    """
    Parse the MTR CSV, pull SAP Invoices + CreditNotes for [from_date, to_date]
    live, cross-match by order id / refund id, and save a downloadable XLSX
    (Invoices sheet, Credit Notes sheet, Summary sheet) as a private File.

    Returns {"status": "done", "file_url": ..., "summary": {...}} or
    {"status": "error", "message": ...}.
    """
    _set(progress_id, {"status": "running"})

    if not os.path.isfile(csv_path):
        result = {"status": "error", "message": f"File not found: {csv_path}"}
        _set(progress_id, result)
        return result

    settings = frappe.get_doc("Amazon US Settings")
    card_code = settings.sap_card_code

    try:
        _emit(progress_id, f"Parsing {csv_path}...")
        mtr_orders, mtr_qtys = _parse_order_rows(csv_path)
        refund_events = _parse_refund_events(csv_path)
        # Aggregate refunds per ORDER, not per event -- see module docstring for
        # why event-level ids can never match across MTR and Finances API.
        # MTR refund amounts are negative (money back); SAP CN DocTotals are
        # positive, so compare absolute values.
        mtr_refunds = {}
        for ev in refund_events:
            total = sum(
                adj["principal_amount"] + adj["tax_amount"] + adj.get("shipping_amount", 0) + adj.get("shipping_tax_amount", 0)
                for adj in ev["item_adjustments"]
            )
            oid = ev["amazon_order_id"]
            mtr_refunds[oid] = round(mtr_refunds.get(oid, 0.0) + abs(total), 2)
        _emit(progress_id, f"MTR: {len(mtr_orders)} orders, {len(mtr_refunds)} refunded orders")

        _emit(progress_id, "Pulling SAP Invoices...")
        sap_invoices = _fetch_sap_docs("Invoices", from_date, to_date, card_code)
        _emit(progress_id, f"SAP: {len(sap_invoices)} invoices")

        # CN DocDates carry the Finances API PostedDate, which lags the MTR's
        # refund date by up to weeks (June-MTR refunds get July DocDates), so
        # the CN pull window extends past to_date to catch them.
        cn_to_date = (datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=45)).strftime("%Y-%m-%d")
        _emit(progress_id, f"Pulling SAP Credit Notes (DocDate window extended to {cn_to_date})...")
        sap_credit_notes = _fetch_sap_docs("CreditNotes", from_date, cn_to_date, card_code)
        _emit(progress_id, f"SAP: {len(sap_credit_notes)} credit notes")

        sap_cns_by_order = _aggregate_by_order(sap_credit_notes)
        all_order_ids = set(mtr_orders) | set(sap_invoices) | set(mtr_refunds) | set(sap_cns_by_order)
        _emit(progress_id, f"Loading local staging state for {len(all_order_ids)} orders...")
        locals_map = _load_local_orders(list(all_order_ids))

        invoice_rows = _build_rows(mtr_orders, sap_invoices, "order_id",
                                   locals_map=locals_map, mtr_qtys=mtr_qtys, remark_fn=_invoice_remark)
        cn_rows = _build_rows(mtr_refunds, sap_cns_by_order, "order_id",
                              locals_map=locals_map, remark_fn=_cn_remark)

        file_name = f"amazon_us_recon_{from_date}_to_{to_date}_{now_datetime().strftime('%Y%m%d%H%M%S')}.xlsx"
        site_path = frappe.get_site_path("private", "files", file_name)
        _write_workbook(invoice_rows, cn_rows, site_path)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "file_url": f"/private/files/{file_name}",
            "is_private": 1,
        })
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        summary = {
            "invoices": {
                "matched": sum(1 for r in invoice_rows if r["status"] == "MATCH"),
                "mismatched": sum(1 for r in invoice_rows if r["status"] == "AMOUNT MISMATCH"),
                "missing_in_sap": sum(1 for r in invoice_rows if r["status"] == "MISSING IN SAP"),
                "extra_in_sap": sum(1 for r in invoice_rows if r["status"] == "IN SAP, NOT IN MTR"),
            },
            "credit_notes": {
                "matched": sum(1 for r in cn_rows if r["status"] == "MATCH"),
                "mismatched": sum(1 for r in cn_rows if r["status"] == "AMOUNT MISMATCH"),
                "missing_in_sap": sum(1 for r in cn_rows if r["status"] == "MISSING IN SAP"),
                "extra_in_sap": sum(1 for r in cn_rows if r["status"] == "IN SAP, NOT IN MTR"),
            },
        }
        result = {"status": "done", "file_url": file_doc.file_url, "summary": summary}
        _emit(progress_id, f"Done. {file_doc.file_url}")
        _set(progress_id, result)
        return result

    except Exception as e:
        frappe.log_error(f"Reconciliation build failed: {e}", "Amazon US Reconciliation")
        result = {"status": "error", "message": str(e)}
        _emit(progress_id, f"FAILED: {e}", "error")
        _set(progress_id, result)
        return result
