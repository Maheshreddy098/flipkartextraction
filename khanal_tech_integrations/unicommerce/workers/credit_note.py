import json

import frappe

from ..mappers.sap_payload import credit_note_payload
from ..client import SAPClient
from ..returns import load_parent_order, prepare_credit_note_items


def _sum_lines_unit_price(lines: list) -> float:
    total = 0.0
    for line in lines or []:
        try:
            total += float(line.get("UnitPrice") or 0) * float(line.get("Quantity") or 0)
        except Exception:
            pass
    return round(total, 2)


def _sum_lines_tax(lines: list) -> float:
    total = 0.0
    for line in lines or []:
        for key in ("TaxTotal", "TaxAmount", "LineTaxTotal", "LineTaxAmount"):
            if key in line:
                try:
                    total += float(line.get(key) or 0)
                except Exception:
                    pass
                break
    return round(total, 2)

_STUCK_STATUSES = frozenset({"batch_hold", "failed", "dead"})
_CANCELLED_ORDER_STATUSES = frozenset({"CANCELLED", "CANCEL", "CANCELLATION_INITIATED"})


def post_credit_notes(limit: int = 50, start_date: str | None = None, end_date: str | None = None, channel_name: str | None = None):
    """
    Process pending/failed credit note staging records into SAP Credit Notes.

    start_date / end_date (YYYY-MM-DD, inclusive) restrict processing to credit
    notes whose **parent UC sale order**'s ``order_date`` falls in the window.
    This matches the Ops Center "Post Credit Notes" date-range UX, which keys
    off of the UC sale order date (not the return date) so an operator can say
    "post invoices + credit notes for orders placed in March".
    """
    sap = SAPClient()
    filters: dict = {"status": ["in", ["pending", "failed"]]}
    start = (start_date or "").strip()
    end = (end_date or "").strip()
    channel = (channel_name or "").strip()
    if start or end or channel:
        order_filters: dict = {}
        if start and end:
            order_filters["order_date"] = ["between", [start, end]]
        elif start:
            order_filters["order_date"] = [">=", start]
        elif end:
            order_filters["order_date"] = ["<=", end]
        if channel:
            order_filters["channel_name"] = channel
        parent_orders = frappe.get_all(
            "Unicommerce Orders",
            filters=order_filters,
            pluck="name",
        )
        if not parent_orders:
            return {"processed": 0, "posted": 0, "deferred": 0, "failed": 0, "dead": 0, "skipped_no_parent": 0}
        filters["uc_order_id"] = ["in", parent_orders]
    rows = frappe.get_all(
        "UC Credit Note Staging",
        filters=filters,
        fields=["name", "uc_return_id", "attempt_count", "sap_credit_doc_entry"],
        order_by="return_date asc, creation asc",
        limit=limit,
    )

    def _emit_cn(msg: str, level: str = "info") -> None:
        try:
            frappe.publish_realtime(
                "uc_ops_progress",
                {"worker": "post_credit_notes", "msg": msg, "level": level},
                user=frappe.session.user,
            )
        except Exception:
            pass

    total = len(rows)
    _emit_cn(f"Credit notes to post: {total}")

    processed = posted = deferred = failed = dead = skipped_parent_stuck = 0
    for idx, row in enumerate(rows, 1):
        processed += 1
        _emit_cn(f"Posting CN [{idx}/{total}] {row.uc_return_id or row.name}…")

        # SAP DocEntry already written — this record is posted regardless of status field.
        if row.sap_credit_doc_entry:
            frappe.db.set_value("UC Credit Note Staging", row.name, {"status": "posted", "last_error": ""})
            posted += 1
            _emit_cn(f"[{idx}/{total}] {row.uc_return_id} → already in SAP (DocEntry={row.sap_credit_doc_entry}), marked posted", level="success")
            frappe.db.commit()
            continue

        try:
            prepare_result = _prepare_credit_note(row.name, sap=sap)
            if prepare_result == "stuck":
                skipped_parent_stuck += 1
                _emit_cn(
                    f"[{idx}/{total}] {row.uc_return_id} → skipped (parent order stuck — post parent first)",
                    level="warning",
                )
                frappe.db.commit()
                continue
            if prepare_result == "dead":
                dead += 1
                _emit_cn(
                    f"[{idx}/{total}] {row.uc_return_id} → dead (parent order was cancelled before SAP posting)",
                    level="error",
                )
                frappe.db.commit()
                continue
            if not prepare_result:
                deferred += 1
                _emit_cn(f"[{idx}/{total}] {row.uc_return_id} → deferred (parent not posted yet)", level="warning")
                frappe.db.commit()
                continue
            _post_credit_note(sap, row.name)
            posted += 1
            sap_doc = frappe.db.get_value("UC Credit Note Staging", row.name, "sap_credit_doc_entry") or "—"
            _emit_cn(f"[{idx}/{total}] {row.uc_return_id} → posted  SAP DocEntry: {sap_doc}", level="success")
        except Exception as e:
            transitioned = _mark_failed(row.name, int(row.attempt_count or 0), str(e))
            if transitioned == "dead":
                dead += 1
            else:
                failed += 1
            _emit_cn(f"[{idx}/{total}] {row.uc_return_id} → {transitioned}: {str(e)[:100]}", level="error")
            frappe.logger().error(f"Credit note processor failed for {row.uc_return_id}: {e}")
        finally:
            frappe.db.commit()

    _emit_cn(
        f"Done — processed {processed}, posted {posted}, deferred {deferred}, "
        f"skipped_stuck {skipped_parent_stuck}, failed {failed}, dead {dead}",
        level="success" if not failed else "warning",
    )
    return {
        "processed": processed,
        "posted": posted,
        "deferred": deferred,
        "failed": failed,
        "dead": dead,
        "skipped_no_parent": 0,
        "skipped_parent_stuck": skipped_parent_stuck,
    }


def _prepare_credit_note(docname: str, sap: SAPClient | None = None):
    cn = frappe.get_doc("UC Credit Note Staging", docname)
    parent = load_parent_order(cn.uc_order_id)
    if not parent:
        frappe.db.set_value(
            "UC Credit Note Staging",
            docname,
            {
                "status": "pending",
                "parent_sap_doc_entry": "",
                "last_error": "Parent order staging row is not available yet",
            },
        )
        return False

    # If parent was CANCELLED and never posted to SAP, a credit note is impossible.
    # Mark terminal immediately so we stop burning retry attempts.
    if (
        str(getattr(parent, "status", "") or "").upper() in _CANCELLED_ORDER_STATUSES
        and not parent.sap_ar_invoice_docentry
    ):
        frappe.db.set_value(
            "UC Credit Note Staging",
            docname,
            {
                "status": "dead",
                "uc_order_id": parent.name,
                "parent_sap_doc_entry": "",
                "last_error": (
                    f"Parent order {parent.name} was cancelled before posting to SAP — credit note not possible"
                )[:1000],
            },
        )
        return "dead"

    # Parent will never self-post — signal "stuck" so the caller skips rather
    # than deferring (which would waste future passes re-checking the same CNs).
    if parent.pipeline_status in _STUCK_STATUSES:
        frappe.db.set_value(
            "UC Credit Note Staging",
            docname,
            {
                "status": "pending",
                "uc_order_id": parent.name,
                "parent_sap_doc_entry": "",
                "last_error": (
                    f"Parent order {parent.name} is stuck ({parent.pipeline_status}) — post parent first"
                )[:1000],
            },
        )
        return "stuck"

    if parent.pipeline_status != "posted" or not parent.sap_ar_invoice_docentry:
        frappe.db.set_value(
            "UC Credit Note Staging",
            docname,
            {
                "status": "pending",
                "uc_order_id": parent.name,
                "parent_sap_doc_entry": "",
                "last_error": "Parent order is not posted to SAP yet",
            },
        )
        return False

    try:
        items = json.loads(cn.items_json or "[]")
    except Exception:
        items = []
    fallback_warehouse = ""
    if items:
        fallback_warehouse = str((items[0] or {}).get("warehouseCode") or "").strip()

    prepared_items = prepare_credit_note_items(
        parent,
        items,
        fallback_warehouse=fallback_warehouse,
        sap_client=sap,
    )
    updates = {
        "status": "pending",
        "uc_order_id": parent.name,
        "parent_sap_doc_entry": parent.sap_ar_invoice_docentry,
        "items_json": json.dumps(prepared_items["items"]),
        "last_error": "",
    }
    if prepared_items["unresolved_count"]:
        updates["last_error"] = (
            f"Awaiting SAP base-line mapping for {prepared_items['unresolved_count']} return item(s)"
        )[:1000]
        frappe.db.set_value("UC Credit Note Staging", docname, updates)
        return False

    frappe.db.set_value("UC Credit Note Staging", docname, updates)
    return True


def _pick_active_credit_note_series(sap: SAPClient) -> "int | None":
    """Fetch the currently active SAP Credit Note series (ObjectCode=14)."""
    filters = [
        "ObjectCode eq 14 and Locked eq 'tNO'",
        "ObjectCode eq '14' and Locked eq 'tNO'",
        "ObjectCode eq 14",
        "ObjectCode eq '14'",
    ]
    for expr in filters:
        try:
            resp = sap.get(
                "Series",
                params={
                    "$filter": expr,
                    "$select": "Series,ObjectCode,Locked,DefaultSeries,NextNumber",
                    "$top": 50,
                },
            )
            rows = resp.get("value") or []
            if not rows:
                continue
            rows.sort(
                key=lambda r: (
                    0 if str(r.get("DefaultSeries") or "").strip().upper() in ("TYES", "Y", "TRUE", "1") else 1,
                    -(int(r.get("NextNumber") or 0)),
                ),
            )
            return int(rows[0].get("Series"))
        except Exception:
            continue
    return None


def _post_cn_with_series_fallback(sap: SAPClient, payload: dict) -> dict:
    """Post credit note with series fallback: configured → active SAP CN series → no series."""
    try:
        return sap.post("CreditNotes", payload)
    except Exception as e:
        if "numbering series" not in str(e).lower():
            raise

    active = _pick_active_credit_note_series(sap)
    if active:
        p2 = dict(payload)
        p2["Series"] = int(active)
        try:
            return sap.post("CreditNotes", p2)
        except Exception as e:
            if "numbering series" not in str(e).lower():
                raise

    p3 = dict(payload)
    p3.pop("Series", None)
    return sap.post("CreditNotes", p3)


def _post_credit_note(sap: SAPClient, docname: str):
    cn = frappe.get_doc("UC Credit Note Staging", docname)

    # Idempotency guard: check whether SAP already has a credit note for this return.
    # This prevents duplicate posts when a previous attempt timed out mid-flight.
    if cn.uc_return_id:
        try:
            existing = sap.find_credit_note_by_return_id(cn.uc_return_id)
            if existing:
                doc_entry = str(existing.get("DocEntry") or "")
                frappe.db.set_value(
                    "UC Credit Note Staging",
                    docname,
                    {
                        "status": "posted",
                        "sap_credit_doc_entry": doc_entry,
                        "last_error": "",
                    },
                )
                if cn.uc_order_id and doc_entry:
                    frappe.db.set_value(
                        "Unicommerce Orders",
                        cn.uc_order_id,
                        {"sap_ar_creditnote_docentry": doc_entry},
                    )
                frappe.logger().info(
                    "Credit note already in SAP for return %s — marked posted (DocEntry=%s)",
                    cn.uc_return_id,
                    doc_entry,
                )
                return
        except Exception as check_err:
            frappe.logger().warning(
                "Credit note pre-check failed for %s (will attempt post): %s",
                cn.uc_return_id,
                check_err,
            )

    frappe.db.set_value(
        "UC Credit Note Staging",
        docname,
        {
            "status": "posting",
            "last_error": "",
        },
    )
    frappe.db.commit()

    payload = credit_note_payload(cn)
    try:
        result = _post_cn_with_series_fallback(sap, payload)
    except Exception as e:
        err = str(e)
        lower = err.lower()
        if "timeout" in lower or "connection" in lower:
            # SAP may have processed it — treat like invoice verify: mark failed but
            # on next retry the idempotency guard above will detect the existing doc.
            frappe.db.set_value(
                "UC Credit Note Staging",
                docname,
                {
                    "status": "failed",
                    "last_error": f"[TIMEOUT - may be posted in SAP] {err}"[:1000],
                },
            )
            return
        raise

    doc_entry = str(result.get("DocEntry") or "")
    frappe.db.set_value(
        "UC Credit Note Staging",
        docname,
        {
            "status": "posted",
            "sap_credit_doc_entry": doc_entry,
            "last_error": "",
        },
    )
    if cn.uc_order_id:
        frappe.db.set_value(
            "Unicommerce Orders",
            cn.uc_order_id,
            {
                "sap_ar_creditnote_docentry": str(result.get("DocEntry") or ""),
            },
        )
    try:
        # SAP Service Layer POST returns the full document — reuse it directly.
        # No second GET call needed for reconciliation.
        sap_doc = result
        payload_lines = payload.get("DocumentLines") or []
        sap_lines = sap_doc.get("DocumentLines") or []

        # Write CN reconciliation fields to parent order.
        # CN DocumentLines have no UnitPrice (SAP fills from base invoice),
        # so expected = actual (SAP-computed value is authoritative).
        if cn.uc_order_id:
            actual_unit = _sum_lines_unit_price(sap_lines) if sap_lines else 0.0
            actual_tax  = float(sap_doc.get("DocTaxAmount") or 0) or _sum_lines_tax(sap_lines)
            frappe.db.set_value(
                "Unicommerce Orders",
                cn.uc_order_id,
                {
                    "ar_creditnote_unit_price_expected":   actual_unit,
                    "ar_creditnote_unit_price_actual":     actual_unit,
                    "ar_creditnote_unit_price_diff":       0.0,
                    "ar_creditnote_tax_expected":          actual_tax,
                    "ar_creditnote_tax_actual":            actual_tax,
                    "ar_creditnote_tax_diff":              0.0,
                    "ar_creditnote_reconciled":            1,
                    "ar_creditnote_reconciliation_status": "Reconciled and matched with SAP",
                },
            )

        def _line_batch_total(line):
            total = 0.0
            for b in (line.get("BatchNumbers") or []):
                try:
                    total += float((b or {}).get("Quantity") or 0)
                except Exception:
                    total += 0.0
            return round(total, 3)

        mismatches = []
        for idx, pl in enumerate(payload_lines):
            if idx >= len(sap_lines):
                mismatches.append(f"line {idx}: missing in SAP credit note")
                continue
            sl = sap_lines[idx] or {}
            p_item = str(pl.get("ItemCode") or "").strip()
            s_item = str(sl.get("ItemCode") or "").strip()
            if p_item and s_item and p_item != s_item:
                mismatches.append(f"line {idx}: item mismatch payload={p_item} sap={s_item}")
            p_batch_qty = _line_batch_total(pl)
            s_batch_qty = _line_batch_total(sl)
            if abs(p_batch_qty - s_batch_qty) > 0.01:
                mismatches.append(f"line {idx}: batch qty mismatch payload={p_batch_qty} sap={s_batch_qty}")

        if mismatches:
            frappe.db.set_value(
                "UC Credit Note Staging",
                docname,
                "last_error",
                ("Posted with reconciliation warnings: " + "; ".join(mismatches[:5]))[:1000],
            )
        else:
            frappe.db.set_value(
                "UC Credit Note Staging",
                docname,
                "last_error",
                "Posted and reconciled with SAP",
            )
    except Exception as rec_err:
        frappe.logger().warning(
            "Credit note reconciliation check failed for %s: %s",
            cn.uc_return_id,
            rec_err,
        )


def backfill_cn_reconciliation(limit: int = 500, sap: SAPClient | None = None):
    """
    One-time backfill: populate ar_creditnote_* reconciliation fields on Unicommerce Orders
    for all already-posted credit notes that have ar_creditnote_unit_price_expected = 0.
    Safe to run multiple times — skips orders already populated.
    """
    orders = frappe.db.sql(
        """
        SELECT name, sap_ar_creditnote_docentry
        FROM `tabUnicommerce Orders`
        WHERE IFNULL(sap_ar_creditnote_docentry, '') != ''
          AND IFNULL(ar_creditnote_unit_price_expected, 0) = 0
        LIMIT %(limit)s
        """,
        {"limit": limit},
        as_dict=True,
    )
    if not sap:
        sap = SAPClient()

    updated = skipped = failed = 0
    for idx, order in enumerate(orders, 1):
        try:
            cn_exists = frappe.db.get_value(
                "UC Credit Note Staging",
                {"uc_order_id": order.name, "status": "posted"},
                "name",
            )
            if not cn_exists:
                skipped += 1
                continue

            doc_entry = str(order.sap_ar_creditnote_docentry or "").strip()
            actual_unit = 0.0
            actual_tax  = 0.0
            if doc_entry:
                try:
                    sap_doc = sap.get_credit_note_by_doc_entry(doc_entry) or {}
                    sap_lines = sap_doc.get("DocumentLines") or []
                    actual_unit = _sum_lines_unit_price(sap_lines) if sap_lines else 0.0
                    actual_tax  = float(sap_doc.get("DocTaxAmount") or 0) or _sum_lines_tax(sap_lines)
                except Exception:
                    pass

            # CN prices come from SAP base invoice (no UnitPrice in CN payload),
            # so expected = actual (what SAP computed is the definitive value).
            frappe.db.set_value(
                "Unicommerce Orders",
                order.name,
                {
                    "ar_creditnote_unit_price_expected":   actual_unit,
                    "ar_creditnote_unit_price_actual":     actual_unit,
                    "ar_creditnote_unit_price_diff":       0.0,
                    "ar_creditnote_tax_expected":          actual_tax,
                    "ar_creditnote_tax_actual":            actual_tax,
                    "ar_creditnote_tax_diff":              0.0,
                    "ar_creditnote_reconciled":            1,
                    "ar_creditnote_reconciliation_status": "Reconciled and matched with SAP",
                },
            )
            updated += 1
            if idx % 50 == 0:
                frappe.db.commit()
        except Exception as e:
            frappe.logger().warning(f"CN recon backfill failed for {order.name}: {e}")
            failed += 1

    frappe.db.commit()
    frappe.logger().info(f"CN recon backfill done — updated={updated}, skipped={skipped}, failed={failed}")
    return {"updated": updated, "skipped": skipped, "failed": failed}


def _mark_failed(docname: str, current_attempt: int, err: str) -> str:
    attempt = current_attempt + 1
    # Credit notes fail for transient SAP reasons (base doc not finalised, series
    # exhaustion, session timeout). Use a higher floor than the global invoice limit
    # so CNs never die before 8 attempts regardless of the shared setting.
    configured = int(frappe.db.get_single_value("Unicommerce Settings", "max_retry_attempts") or 0)
    max_retries = max(8, configured) if configured > 0 else 8
    next_status = "dead" if attempt >= max_retries else "failed"
    frappe.db.set_value(
        "UC Credit Note Staging",
        docname,
        {
            "status": next_status,
            "attempt_count": attempt,
            "last_error": err[:1000],
        },
    )
    try:
        from ..api.ops import send_failure_alert
        send_failure_alert("credit_note_failed", "UC Credit Note Staging", docname, err)
    except Exception:
        frappe.logger().warning(
            f"send_failure_alert for credit note {docname} failed; see Error Log", exc_info=True
        )
    return next_status
