import frappe

from ..workers.invoice import _update_reconciliation_diffs
from ..workers.credit_note import _sum_lines_unit_price, _sum_lines_tax
from ..client import SAPClient


def run_reconciliation_refresh(limit: int = 200) -> dict:
    """Wrapper kept for scheduler and API backwards-compatibility.

    Delegates to refresh_recon which uses per-order U_Order filtering (correct
    for batched invoices) and prioritises unreconciled rows first.
    """
    return refresh_recon(limit=limit)


def _run_reconciliation_refresh_legacy(limit: int = 200):
    """Original per-row refresh kept for reference — no longer called by the scheduler."""
    sap = SAPClient()

    # ── AR Invoice refresh ───────────────────────────────────────────────────
    inv_rows = frappe.get_all(
        "Unicommerce Orders",
        filters={"pipeline_status": "posted", "sap_ar_invoice_docentry": ["!=", ""]},
        fields=["name", "sap_ar_invoice_docentry"],
        order_by="modified desc",
        limit=limit,
    )
    inv_refreshed = inv_failed = 0
    for row in inv_rows:
        try:
            invoice = None
            try:
                invoice = sap.get_invoice_by_doc_entry(row.sap_ar_invoice_docentry)
            except Exception as fetch_err:
                frappe.logger().warning(
                    "run_reconciliation_refresh: invoice SAP fetch failed for %s (DocEntry=%s): %s",
                    row.name, row.sap_ar_invoice_docentry, fetch_err,
                )
            _update_reconciliation_diffs(row.name, invoice=invoice)
            inv_refreshed += 1
        except Exception:
            inv_failed += 1
        finally:
            frappe.db.commit()

    # ── Credit Note refresh ──────────────────────────────────────────────────
    cn_rows = frappe.get_all(
        "Unicommerce Orders",
        filters={"sap_ar_creditnote_docentry": ["!=", ""]},
        fields=["name", "sap_ar_creditnote_docentry",
                "ar_creditnote_unit_price_actual", "ar_creditnote_tax_actual"],
        order_by="modified desc",
        limit=limit,
    )
    cn_refreshed = cn_failed = 0
    for row in cn_rows:
        try:
            sap_doc = {}
            sap_fetch_ok = False
            try:
                sap_doc = sap.get_credit_note_by_doc_entry(row.sap_ar_creditnote_docentry) or {}
                sap_fetch_ok = bool(sap_doc)
            except Exception as fetch_err:
                frappe.logger().warning(
                    "run_reconciliation_refresh: CN SAP fetch failed for %s (DocEntry=%s): %s",
                    row.name, row.sap_ar_creditnote_docentry, fetch_err,
                )
            sap_lines   = sap_doc.get("DocumentLines") or []
            if sap_fetch_ok and sap_lines:
                actual_unit = _sum_lines_unit_price(sap_lines)
            else:
                actual_unit = float(row.ar_creditnote_unit_price_actual or 0)
            if sap_fetch_ok:
                actual_tax = float(sap_doc.get("DocTaxAmount") or 0) or _sum_lines_tax(sap_lines)
            else:
                actual_tax = float(row.ar_creditnote_tax_actual or 0)
            expected_unit = float(row.ar_creditnote_unit_price_expected or actual_unit)
            expected_tax  = float(row.ar_creditnote_tax_expected or actual_tax)
            unit_diff = round(abs(expected_unit - actual_unit), 2)
            tax_diff  = round(abs(expected_tax - actual_tax), 2)
            is_matched = unit_diff <= 1.0 and tax_diff <= 1.0
            frappe.db.set_value(
                "Unicommerce Orders",
                row.name,
                {
                    "ar_creditnote_unit_price_expected":   expected_unit,
                    "ar_creditnote_unit_price_actual":     actual_unit,
                    "ar_creditnote_unit_price_diff":       unit_diff,
                    "ar_creditnote_tax_expected":          expected_tax,
                    "ar_creditnote_tax_actual":            actual_tax,
                    "ar_creditnote_tax_diff":              tax_diff,
                    "ar_creditnote_reconciled":            int(is_matched),
                    "ar_creditnote_reconciliation_status": "Reconciled and matched with SAP" if is_matched else "Mismatch (SAP vs expected)",
                },
            )
            frappe.db.commit()
            cn_refreshed += 1
        except Exception:
            cn_failed += 1
            frappe.db.commit()

    return {
        "inv_selected": len(inv_rows), "inv_refreshed": inv_refreshed, "inv_failed": inv_failed,
        "cn_selected":  len(cn_rows),  "cn_refreshed":  cn_refreshed,  "cn_failed":  cn_failed,
    }


def get_reconciliation_gaps(
    min_tax_diff: float = 1.0,
    min_unit_price_diff: float = 1.0,
    limit: int = 200,
):
    """
    Return posted orders where either tax or unit-price total differs.
    """
    return frappe.db.sql(
        """
        SELECT
            name,
            name AS uc_order_id,
            channel_name AS channel,
            sap_ar_invoice_docentry AS sap_doc_entry,
            ar_invoice_tax_expected AS tax_expected,
            ar_invoice_tax_actual AS tax_actual,
            ar_invoice_tax_diff AS tax_diff,
            ar_invoice_unit_price_expected AS unit_price_expected,
            ar_invoice_unit_price_actual AS unit_price_actual,
            ar_invoice_unit_price_diff AS unit_price_diff,
            modified
        FROM `tabUnicommerce Orders`
        WHERE pipeline_status = 'posted'
          AND (
            IFNULL(ar_invoice_tax_diff, 0) >= %(min_tax_diff)s
            OR IFNULL(ar_invoice_unit_price_diff, 0) >= %(min_unit_price_diff)s
          )
        ORDER BY GREATEST(IFNULL(ar_invoice_tax_diff, 0), IFNULL(ar_invoice_unit_price_diff, 0)) DESC, modified DESC
        LIMIT %(limit)s
        """,
        {
            "min_tax_diff": float(min_tax_diff),
            "min_unit_price_diff": float(min_unit_price_diff),
            "limit": int(limit),
        },
        as_dict=True,
    )


def _to_float(x) -> float:
    try:
        return float(x or 0)
    except Exception:
        return 0.0


def _is_returned_line(line_item) -> bool:
    """
    Best-effort detection of which lines are part of a credit note.

    Legacy CreditNote2 payload is built from invoice lines that have batch numbers
    extracted from Uniware shipping packages/return items. In this doctype we only
    have the return status/items per line, so we include lines marked RETURNED /
    RETURN_EXPECTED (or with non-empty return items).
    """
    status = str(getattr(line_item, "uniware_return_status", "") or "").strip().upper()
    has_return_items = bool(getattr(line_item, "uniware_return_items", None))
    return ("RETURNED" in status) or ("RETURN_EXPECTED" in status) or has_return_items


def _expected_invoice_total(order_doc) -> tuple[float, float]:
    """
    Expected (ex-tax unit total, tax total) for AR Invoice.
    Mirrors the legacy taxable formulas:
    - item ex-tax = (sellingpricewithouttaxesanddiscount - discount) * qty
    - item tax = totalintegratedgst
    - shipping freight ex-tax derived using shippingcharges and shippingchargetaxpercentage
    """
    unit_total = 0.0
    tax_total = 0.0
    # Legacy posting sets TaxCode using `get_gst_code()` which derives uni_tax from:
    # state_gst_tax_percentage + central_gst_tax_percentage + integratedgstpercentage
    for oli in order_doc.line_items or []:
        qty = _to_float(getattr(oli, "quantity", 0))
        selling_wo_tax_disc = _to_float(getattr(oli, "sellingpricewithouttaxesanddiscount", 0))
        discount_total = _to_float(getattr(oli, "discount", 0))
        # UC discount is a line-level total amount (same as sap_payload._append_sales_line).
        # Convert to per-unit before computing line total so both sides agree.
        per_unit_discount = (discount_total / qty) if qty > 0 else 0.0
        item_unit_price = max(0.0, selling_wo_tax_disc - per_unit_discount)
        item_unit_ex_tax_total = item_unit_price * qty

        # Tax % — UC sends either IGST or CGST+SGST, never both non-zero simultaneously.
        # Take the larger of the two buckets to avoid doubling when both fields are populated.
        uni_igst = _to_float(getattr(oli, "integratedgstpercentage", 0))
        uni_cgst_sgst = _to_float(getattr(oli, "state_gst_tax_percentage", 0)) + _to_float(
            getattr(oli, "central_gst_tax_percentage", 0)
        )
        uni_tax_pct = int(max(uni_igst, uni_cgst_sgst))
        item_tax = item_unit_price * qty * (uni_tax_pct / 100.0)

        # Freight tax uses shippingchargetaxpercentage with allowed codes {0,5,12,18,24}.
        # When missing/zero, fall back to the item's tax % — same guardrail as sap_payload.py
        # _resolve_shipping_tax_percent — otherwise gross shipping is used as taxable, causing
        # a systematic diff equal to the GST on the shipping charge (e.g. ₹50*18%=₹7.63).
        shipping_gross = (
            _to_float(getattr(oli, "shippingcharges", 0))
            + _to_float(getattr(oli, "shippingmethodcharges", 0))
            + _to_float(getattr(oli, "cashondeliverycharges", 0))
        )
        shipping_tax_pct_raw = int(_to_float(getattr(oli, "shippingchargetaxpercentage", 0)))
        allowed_tax_codes = {0, 5, 12, 18, 24}
        shipping_tax_pct = shipping_tax_pct_raw if shipping_tax_pct_raw in allowed_tax_codes else 0
        if shipping_tax_pct == 0 and shipping_gross > 0:
            shipping_tax_pct = uni_tax_pct  # fallback: use item GST % (same logic as sap_payload)

        shipping_taxable = (
            (shipping_gross * 100.0 / (100.0 + shipping_tax_pct)) if shipping_tax_pct > 0 else shipping_gross
        )
        shipping_tax = shipping_gross - shipping_taxable

        unit_total += item_unit_ex_tax_total + shipping_taxable
        tax_total += item_tax + shipping_tax

    return round(unit_total, 2), round(tax_total, 2)


def _expected_credit_total(order_doc) -> tuple[float, float]:
    """
    Expected (ex-tax unit total, tax total) for AR Credit Note.

    Legacy CreditNote2 builds credit note lines only for invoice lines where
    Uniware returns/batches exist. We approximate that by including line items
    marked RETURNED / RETURN_EXPECTED (or with return items present).

    Note: We do NOT include freight lines here because CreditNote2 typically
    appends only product invoice lines that have batch numbers.
    """
    unit_total = 0.0
    tax_total = 0.0
    for oli in order_doc.line_items or []:
        if not _is_returned_line(oli):
            continue

        qty = _to_float(getattr(oli, "quantity", 0))
        selling_wo_tax_disc = _to_float(getattr(oli, "sellingpricewithouttaxesanddiscount", 0))
        discount_total = _to_float(getattr(oli, "discount", 0))
        per_unit_discount = (discount_total / qty) if qty > 0 else 0.0
        item_unit_price = max(0.0, selling_wo_tax_disc - per_unit_discount)

        unit_total += item_unit_price * qty

        uni_igst = _to_float(getattr(oli, "integratedgstpercentage", 0))
        uni_cgst_sgst = _to_float(getattr(oli, "state_gst_tax_percentage", 0)) + _to_float(
            getattr(oli, "central_gst_tax_percentage", 0)
        )
        uni_tax_pct = int(max(uni_igst, uni_cgst_sgst))
        tax_total += item_unit_price * qty * (uni_tax_pct / 100.0)

    return round(unit_total, 2), round(tax_total, 2)


def _sum_actual_unit_total(lines: list[dict], uc_order_id: str | None = None) -> float:
    """
    One SAP DocEntry can contain multiple UC orders (batch posting).
    Filter DocumentLines using U_Order so we compute totals per UC order.
    """
    total = 0.0
    order_id_norm = str(uc_order_id) if uc_order_id is not None else None
    for ln in lines or []:
        if order_id_norm is not None and str(ln.get("U_Order") or "") != order_id_norm:
            continue
        qty = _to_float(ln.get("Quantity"))
        unit_price = _to_float(ln.get("UnitPrice"))
        total += qty * unit_price
    return round(total, 2)


def _sum_actual_tax_total_from_lines(
    lines: list[dict], uc_order_id: str | None = None
) -> tuple[float, bool]:
    """
    Best-effort line-level tax sum.
    Returns: (tax_total, used_line_level_key)
    """
    tax_total = 0.0
    order_id_norm = str(uc_order_id) if uc_order_id is not None else None
    candidate_keys = [
        "TaxTotal",
        "TaxAmount",
        "LineTaxTotal",
        "LineTaxAmount",
        "TaxExpense",
        "TaxLineTotal",
    ]
    used_any = False
    for ln in lines or []:
        if order_id_norm is not None and str(ln.get("U_Order") or "") != order_id_norm:
            continue
        line_key = next((k for k in candidate_keys if k in ln), None)
        if not line_key:
            continue
        used_any = True
        tax_total += _to_float(ln.get(line_key))
    return round(tax_total, 2), used_any


def _actual_invoice(
    sap: SAPClient,
    doc_entry: str | int,
    uc_order_id: str | None = None,
) -> tuple[float, float, dict]:
    """Returns (unit_total, tax_total, raw_sap_doc)."""
    inv = sap.get_invoice_by_doc_entry(doc_entry)
    doc_tax = _to_float(inv.get("DocTaxAmount"))
    lines = inv.get("DocumentLines") or []

    unit_total = _sum_actual_unit_total(lines, uc_order_id=uc_order_id)

    line_tax_total, used_line_level_key = _sum_actual_tax_total_from_lines(
        lines, uc_order_id=uc_order_id
    )
    if used_line_level_key:
        return unit_total, line_tax_total, inv

    # Fallback: allocate doc tax proportionally by unit total.
    total_unit_invoice = _sum_actual_unit_total(lines, uc_order_id=None)
    if total_unit_invoice <= 0:
        return unit_total, 0.0, inv
    alloc_tax = doc_tax * (unit_total / total_unit_invoice)
    return unit_total, round(alloc_tax, 2), inv


def _actual_credit_note(
    sap: SAPClient,
    doc_entry: str | int,
    uc_order_id: str | None = None,
) -> tuple[float, float, dict]:
    """Returns (unit_total, tax_total, raw_sap_doc)."""
    cn = sap.get_credit_note_by_doc_entry(doc_entry)
    doc_tax = _to_float(cn.get("DocTaxAmount"))
    lines = cn.get("DocumentLines") or []

    unit_total = _sum_actual_unit_total(lines, uc_order_id=uc_order_id)

    line_tax_total, used_line_level_key = _sum_actual_tax_total_from_lines(
        lines, uc_order_id=uc_order_id
    )
    if used_line_level_key:
        return unit_total, line_tax_total, cn

    total_unit_invoice = _sum_actual_unit_total(lines, uc_order_id=None)
    if total_unit_invoice <= 0:
        return unit_total, 0.0, cn
    alloc_tax = doc_tax * (unit_total / total_unit_invoice)
    return unit_total, round(alloc_tax, 2), cn


# ---------------------------------------------------------------------------
# Mismatch diagnosis
# ---------------------------------------------------------------------------

def _match_lines_by_sku_qty(
    uc_lines: list,
    sap_lines: list[dict],
    uc_order_id: str | None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Match UC order lines to SAP DocumentLines by ItemCode + Quantity.

    Returns:
        matched   — list of {uc_line, sap_line} pairs
        uc_only   — UC lines with no SAP counterpart
        sap_only  — SAP lines with no UC counterpart
    """
    order_id_norm = str(uc_order_id) if uc_order_id else None
    filtered_sap = [
        ln for ln in sap_lines
        if order_id_norm is None or str(ln.get("U_Order") or "") == order_id_norm
    ] or list(sap_lines)

    sap_pool: list[dict] = list(filtered_sap)
    matched: list[dict] = []
    uc_only: list[dict] = []

    for oli in uc_lines:
        sku = str(getattr(oli, "itemcode", "") or "")
        qty = _to_float(getattr(oli, "quantity", 0))
        found = None
        # First pass: exact ItemCode + Quantity match
        for idx, sl in enumerate(sap_pool):
            if str(sl.get("ItemCode") or "") == sku and abs(_to_float(sl.get("Quantity")) - qty) <= 0.01:
                found = sap_pool.pop(idx)
                break
        # Second pass: ItemCode only — handles partial-quantity returns where
        # SAP credit note line carries the returned qty, not the original order qty.
        if not found:
            for idx, sl in enumerate(sap_pool):
                if str(sl.get("ItemCode") or "") == sku:
                    found = sap_pool.pop(idx)
                    break
        if found:
            matched.append({"uc": oli, "sap": found})
        else:
            uc_only.append(oli)

    return matched, uc_only, sap_pool  # sap_pool remainder = sap_only


def _diagnose_invoice_mismatch(
    order_doc,
    sap_doc: dict,
    expected_unit: float,
    actual_unit: float,
    expected_tax: float,
    actual_tax: float,
) -> str:
    """
    Produce a concise human-readable explanation for an invoice reconciliation mismatch.
    Stored in ar_invoice_mismatch_reason so operators can read it without re-fetching SAP.
    """
    unit_diff = round(abs(expected_unit - actual_unit), 2)
    tax_diff = round(abs(expected_tax - actual_tax), 2)
    parts: list[str] = []

    sap_lines = sap_doc.get("DocumentLines") or []
    uc_lines = list(order_doc.line_items or [])
    matched, uc_only, sap_only = _match_lines_by_sku_qty(uc_lines, sap_lines, uc_order_id=order_doc.name)

    # --- Unit price diagnosis ---
    if unit_diff > 1.0:
        line_issues: list[str] = []
        total_discount = 0.0

        for pair in matched:
            oli = pair["uc"]
            sl = pair["sap"]
            qty = _to_float(getattr(oli, "quantity", 0))
            selling = _to_float(getattr(oli, "sellingpricewithouttaxesanddiscount", 0))
            disc = _to_float(getattr(oli, "discount", 0))
            total_discount += disc
            per_unit_disc = (disc / qty) if qty > 0 else 0.0
            exp_up = max(0.0, selling - per_unit_disc)
            sap_up = _to_float(sl.get("UnitPrice"))
            diff = round(abs(exp_up - sap_up), 2)
            if diff > 0.05:
                sku = str(getattr(oli, "itemcode", "") or "")
                if abs(diff * qty - disc) <= 1.0:
                    line_issues.append(f"{sku}: discount ₹{disc:.2f} not applied (exp ₹{exp_up:.2f}, SAP ₹{sap_up:.2f})")
                else:
                    line_issues.append(f"{sku}: exp ₹{exp_up:.2f} SAP ₹{sap_up:.2f} (Δ₹{diff:.2f}×{qty:.0f})")

        for oli in uc_only:
            sku = str(getattr(oli, "itemcode", "") or "")
            line_issues.append(f"{sku}: missing in SAP")

        for sl in sap_only:
            sku = str(sl.get("ItemCode") or "")
            sap_up = _to_float(sl.get("UnitPrice"))
            qty = _to_float(sl.get("Quantity"))
            if sap_up > 0:
                line_issues.append(f"{sku}: extra SAP line ₹{sap_up:.2f}×{qty:.0f}")

        if line_issues:
            parts.append(f"unit Δ₹{unit_diff}: {'; '.join(line_issues[:3])}")
        elif abs(unit_diff - total_discount) <= 2.0 and total_discount > 0:
            parts.append(f"unit Δ₹{unit_diff}: discount ₹{total_discount:.2f} likely not reflected in SAP")
        else:
            parts.append(f"unit Δ₹{unit_diff}: SAP ₹{actual_unit:.2f} vs expected ₹{expected_unit:.2f}")

    # --- Tax diagnosis ---
    if tax_diff > 1.0:
        if expected_tax > 0:
            ratio = actual_tax / expected_tax
            if 1.85 <= ratio <= 2.15:
                parts.append(
                    f"tax Δ₹{tax_diff}: SAP ₹{actual_tax:.2f} ≈ 2×expected ₹{expected_tax:.2f} "
                    f"(IGST+CGST/SGST both summed?)"
                )
            elif actual_tax > expected_tax:
                parts.append(f"tax Δ₹{tax_diff}: SAP ₹{actual_tax:.2f} > expected ₹{expected_tax:.2f}")
            else:
                parts.append(f"tax Δ₹{tax_diff}: SAP ₹{actual_tax:.2f} < expected ₹{expected_tax:.2f}")
        else:
            parts.append(f"tax Δ₹{tax_diff}: expected ₹0 but SAP has ₹{actual_tax:.2f}")

    return " | ".join(parts)[:500] if parts else ""


def _diagnose_cn_mismatch(
    order_doc,
    sap_doc: dict,
    expected_unit: float,
    actual_unit: float,
    expected_tax: float,
    actual_tax: float,
) -> str:
    """
    Produce a concise explanation for a credit note reconciliation mismatch.
    Stored in ar_creditnote_mismatch_reason.
    """
    unit_diff = round(abs(expected_unit - actual_unit), 2)
    tax_diff = round(abs(expected_tax - actual_tax), 2)
    parts: list[str] = []

    sap_lines = sap_doc.get("DocumentLines") or []
    returned_uc_lines = [oli for oli in (order_doc.line_items or []) if _is_returned_line(oli)]
    matched, uc_only, sap_only = _match_lines_by_sku_qty(
        returned_uc_lines, sap_lines, uc_order_id=order_doc.name
    )

    if unit_diff > 1.0:
        line_issues: list[str] = []
        for pair in matched:
            oli = pair["uc"]
            sl = pair["sap"]
            qty = _to_float(getattr(oli, "quantity", 0))
            selling = _to_float(getattr(oli, "sellingpricewithouttaxesanddiscount", 0))
            disc = _to_float(getattr(oli, "discount", 0))
            per_unit_disc = (disc / qty) if qty > 0 else 0.0
            exp_up = max(0.0, selling - per_unit_disc)
            sap_up = _to_float(sl.get("UnitPrice"))
            diff = round(abs(exp_up - sap_up), 2)
            if diff > 0.05:
                sku = str(getattr(oli, "itemcode", "") or "")
                line_issues.append(f"{sku}: exp ₹{exp_up:.2f} SAP ₹{sap_up:.2f} (Δ₹{diff:.2f})")
        for oli in uc_only:
            sku = str(getattr(oli, "itemcode", "") or "")
            line_issues.append(f"{sku}: return line missing in SAP CN")
        for sl in sap_only:
            sku = str(sl.get("ItemCode") or "")
            if _to_float(sl.get("UnitPrice")) > 0:
                line_issues.append(f"{sku}: extra SAP CN line")

        if line_issues:
            parts.append(f"unit Δ₹{unit_diff}: {'; '.join(line_issues[:3])}")
        else:
            parts.append(f"unit Δ₹{unit_diff}: SAP ₹{actual_unit:.2f} vs expected ₹{expected_unit:.2f}")

    if tax_diff > 1.0:
        if expected_tax > 0:
            ratio = actual_tax / expected_tax
            if 1.85 <= ratio <= 2.15:
                parts.append(f"tax Δ₹{tax_diff}: SAP ₹{actual_tax:.2f} ≈ 2×expected (doubled?)")
            elif actual_tax > expected_tax:
                parts.append(f"tax Δ₹{tax_diff}: SAP ₹{actual_tax:.2f} > expected ₹{expected_tax:.2f}")
            else:
                parts.append(f"tax Δ₹{tax_diff}: SAP ₹{actual_tax:.2f} < expected ₹{expected_tax:.2f}")
        else:
            parts.append(f"tax Δ₹{tax_diff}: expected ₹0 but SAP has ₹{actual_tax:.2f}")

    return " | ".join(parts)[:500] if parts else ""


def refresh_recon(
    limit: int = 200,
    min_tax_diff: float = 1.0,
    min_unit_price_diff: float = 1.0,
):
    """
    Populate reconciliation fields on legacy `Unicommerce Orders` doctype:
    - AR invoice: expected vs actual (tax + ex-tax unit total)
    - AR credit note: expected vs actual (tax + ex-tax unit total)
    """
    sap = SAPClient()

    # Prefer rows that look mismatched (or never reconciled).
    rows = frappe.db.sql(
        """
        SELECT
            o.name,
            o.sap_ar_invoice_docentry,
            o.sap_ar_creditnote_docentry
        FROM `tabUnicommerce Orders` o
        WHERE o.pipeline_status = 'posted'
          AND (
              (
                 o.sap_ar_invoice_docentry IS NOT NULL AND o.sap_ar_invoice_docentry != '' AND
                 (
                    o.ar_invoice_reconciliation_status IS NULL OR o.ar_invoice_reconciliation_status = '' OR
                    IFNULL(o.ar_invoice_tax_diff, 0) >= %(min_tax_diff)s OR
                    IFNULL(o.ar_invoice_unit_price_diff, 0) >= %(min_unit_price_diff)s
                 )
              )
              OR
              (
                 o.sap_ar_creditnote_docentry IS NOT NULL AND o.sap_ar_creditnote_docentry != '' AND
                 (
                    o.ar_creditnote_reconciliation_status IS NULL OR o.ar_creditnote_reconciliation_status = '' OR
                    IFNULL(o.ar_creditnote_tax_diff, 0) >= %(min_tax_diff)s OR
                    IFNULL(o.ar_creditnote_unit_price_diff, 0) >= %(min_unit_price_diff)s
                 )
              )
          )
        ORDER BY
          -- Unreconciled rows first so the backlog clears before re-checking already-matched rows
          CASE WHEN (o.ar_invoice_reconciliation_status IS NULL OR o.ar_invoice_reconciliation_status = '')
                AND (o.ar_creditnote_reconciliation_status IS NULL OR o.ar_creditnote_reconciliation_status = '')
               THEN 0 ELSE 1 END ASC,
          -- Then largest diff first (highest-value mismatches get priority)
          GREATEST(
            IFNULL(o.ar_invoice_tax_diff, 0),
            IFNULL(o.ar_invoice_unit_price_diff, 0),
            IFNULL(o.ar_creditnote_tax_diff, 0),
            IFNULL(o.ar_creditnote_unit_price_diff, 0)
          ) DESC,
          o.modified DESC
        LIMIT %(limit)s
        """,
        {
            "min_tax_diff": float(min_tax_diff),
            "min_unit_price_diff": float(min_unit_price_diff),
            "limit": int(limit),
        },
        as_dict=True,
    )

    refreshed = 0
    failed = 0
    for r in rows:
        row_failed = False
        try:
            order_doc = frappe.get_doc("Unicommerce Orders", r.name)

            update = {}

            # Invoice reconciliation
            if r.sap_ar_invoice_docentry and str(r.sap_ar_invoice_docentry).strip():
                expected_unit, expected_tax = _expected_invoice_total(order_doc)
                actual_unit = 0.0
                actual_tax = 0.0
                raw_inv: dict = {}
                try:
                    # Use r.name (= Frappe order ID) to match U_Order set on SAP lines during posting.
                    # The SAP payload sets U_Order = staging_doc.name, not staging_doc.uniware_id.
                    actual_unit, actual_tax, raw_inv = _actual_invoice(
                        sap,
                        r.sap_ar_invoice_docentry,
                        uc_order_id=r.name,
                    )
                except Exception as e:
                    row_failed = True
                    frappe.log_error("Unicommerce Reconciliation", f"Invoice actual fetch failed for {r.name}: {e}")
                unit_diff = abs(expected_unit - actual_unit)
                tax_diff = abs(expected_tax - actual_tax)
                is_matched = unit_diff <= float(min_unit_price_diff) and tax_diff <= float(min_tax_diff)
                reason = (
                    ""
                    if is_matched
                    else _diagnose_invoice_mismatch(order_doc, raw_inv, expected_unit, actual_unit, expected_tax, actual_tax)
                )
                update.update(
                    {
                        "ar_invoice_unit_price_expected": expected_unit,
                        "ar_invoice_unit_price_actual": actual_unit,
                        "ar_invoice_unit_price_diff": round(unit_diff, 2),
                        "ar_invoice_tax_expected": expected_tax,
                        "ar_invoice_tax_actual": actual_tax,
                        "ar_invoice_tax_diff": round(tax_diff, 2),
                        "ar_invoice_reconciled": bool(is_matched),
                        "ar_invoice_reconciliation_status": "Reconciled and matched with SAP" if is_matched else "Mismatch (SAP vs expected)",
                        "ar_invoice_mismatch_reason": reason,
                    }
                )

            # Credit note reconciliation
            if r.sap_ar_creditnote_docentry and str(r.sap_ar_creditnote_docentry).strip():
                expected_unit, expected_tax = _expected_credit_total(order_doc)
                actual_unit = 0.0
                actual_tax = 0.0
                raw_cn: dict = {}
                try:
                    actual_unit, actual_tax, raw_cn = _actual_credit_note(
                        sap,
                        r.sap_ar_creditnote_docentry,
                        uc_order_id=r.name,
                    )
                except Exception as e:
                    row_failed = True
                    frappe.log_error("Unicommerce Reconciliation", f"Credit note actual fetch failed for {r.name}: {e}")
                unit_diff = abs(expected_unit - actual_unit)
                tax_diff = abs(expected_tax - actual_tax)
                is_matched = unit_diff <= float(min_unit_price_diff) and tax_diff <= float(min_tax_diff)
                cn_reason = (
                    ""
                    if is_matched
                    else _diagnose_cn_mismatch(order_doc, raw_cn, expected_unit, actual_unit, expected_tax, actual_tax)
                )
                update.update(
                    {
                        "ar_creditnote_unit_price_expected": expected_unit,
                        "ar_creditnote_unit_price_actual": actual_unit,
                        "ar_creditnote_unit_price_diff": round(unit_diff, 2),
                        "ar_creditnote_tax_expected": expected_tax,
                        "ar_creditnote_tax_actual": actual_tax,
                        "ar_creditnote_tax_diff": round(tax_diff, 2),
                        "ar_creditnote_reconciled": bool(is_matched),
                        "ar_creditnote_reconciliation_status": "Reconciled and matched with SAP" if is_matched else "Mismatch (SAP vs expected)",
                        "ar_creditnote_mismatch_reason": cn_reason,
                    }
                )

            if update:
                frappe.db.set_value("Unicommerce Orders", r.name, update)

            if row_failed:
                failed += 1
            else:
                refreshed += 1
            frappe.db.commit()
        except Exception as e:
            failed += 1
            frappe.log_error("Unicommerce Reconciliation", f"Reconciliation refresh failed for {r.name}: {e}")

    try:
        threshold = int(frappe.db.get_single_value("Unicommerce Settings", "recon_gap_alert_threshold") or 5)
        if failed >= threshold:
            from ..api.ops import send_failure_alert
            send_failure_alert(
                "recon_gap",
                "Unicommerce Orders",
                f"refresh_recon_{frappe.utils.now()}",
                f"Reconciliation refresh produced {failed} failures (threshold {threshold}).",
            )
    except Exception:
        pass

    return {"selected": len(rows), "refreshed": refreshed, "failed": failed}


def get_gaps(
    min_tax_diff: float = 1.0,
    min_unit_price_diff: float = 1.0,
    limit: int = 200,
):
    """
    Return legacy reconciliation gaps from `Unicommerce Orders`.
    """
    return frappe.db.sql(
        """
        SELECT
            o.name,
            o.uniware_id AS uc_order_id,
            o.channel_name AS channel,
            o.sap_ar_invoice_docentry,
            o.ar_invoice_tax_expected,
            o.ar_invoice_tax_actual,
            o.ar_invoice_tax_diff,
            o.ar_invoice_unit_price_expected,
            o.ar_invoice_unit_price_actual,
            o.ar_invoice_unit_price_diff,
            o.sap_ar_creditnote_docentry,
            o.ar_creditnote_tax_expected,
            o.ar_creditnote_tax_actual,
            o.ar_creditnote_tax_diff,
            o.ar_creditnote_unit_price_expected,
            o.ar_creditnote_unit_price_actual,
            o.ar_creditnote_unit_price_diff,
            o.modified
        FROM `tabUnicommerce Orders` o
        WHERE o.pipeline_status = 'posted'
          AND (
              (
                 o.sap_ar_invoice_docentry IS NOT NULL AND o.sap_ar_invoice_docentry != '' AND
                 (
                    o.ar_invoice_reconciliation_status IS NULL OR o.ar_invoice_reconciliation_status = '' OR
                    IFNULL(o.ar_invoice_tax_diff, 0) >= %(min_tax_diff)s OR
                    IFNULL(o.ar_invoice_unit_price_diff, 0) >= %(min_unit_price_diff)s
                 )
              )
              OR
              (
                 o.sap_ar_creditnote_docentry IS NOT NULL AND o.sap_ar_creditnote_docentry != '' AND
                 (
                    o.ar_creditnote_reconciliation_status IS NULL OR o.ar_creditnote_reconciliation_status = '' OR
                    IFNULL(o.ar_creditnote_tax_diff, 0) >= %(min_tax_diff)s OR
                    IFNULL(o.ar_creditnote_unit_price_diff, 0) >= %(min_unit_price_diff)s
                 )
              )
          )
        ORDER BY GREATEST(IFNULL(o.ar_invoice_tax_diff, 0), IFNULL(o.ar_invoice_unit_price_diff, 0),
                            IFNULL(o.ar_creditnote_tax_diff, 0), IFNULL(o.ar_creditnote_unit_price_diff, 0)) DESC,
                 o.modified desc
        LIMIT %(limit)s
        """,
        {
            "min_tax_diff": float(min_tax_diff),
            "min_unit_price_diff": float(min_unit_price_diff),
            "limit": int(limit),
        },
        as_dict=True,
    )
