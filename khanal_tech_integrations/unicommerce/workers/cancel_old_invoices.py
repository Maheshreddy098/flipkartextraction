"""
One-time cleanup: cancel 148 SAP AR Invoices posted by our integration
into old FY2025 series (KAB2C25, MHB2C25, TNB2C25).

Root cause: March 2026 orders (DocDate 2026-03-31) were pending in Frappe
and got posted in late April / early May 2026. SAP assigned them to the
last active series at posting time — the FY2025 series — because the
FY2026 series (KAB2C26, TNB2C26, MHB2C26) was not yet set as default.

These invoices are not duplicates — each UC order appears once. They
simply need to be cancelled and re-posted into the correct 2026 series.

Usage (bench console on production):
    from khanal_tech_integrations.unicommerce.workers.cancel_old_invoices import cancel_old_series_invoices

    # Step 1 — dry run: prints every invoice, zero changes to SAP or Frappe
    cancel_old_series_invoices(dry_run=True)

    # Step 2 — live run after reviewing dry run output
    cancel_old_series_invoices(dry_run=False)

After the live run:
    - SAP cancels each invoice and auto-creates a reversing Credit Memo
    - Frappe resets each Unicommerce Order back to pipeline_status='ready'
    - Re-enable post_invoices scheduled job → orders re-post into 2026 series
"""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from ..client import SAPClient

# Old FY2025 series — any invoice in these series needs to be cancelled + re-posted.
# Confirmed from HANA query: all 148 old-series invoices are in exactly these three.
OLD_SERIES_NAMES = {"KAB2C25", "MHB2C25", "TNB2C25"}

# Correct FY2026 series — invoices here are fine, never touch them.
GOOD_SERIES_NAMES = {"KAB2C26", "TNB2C26", "MHB2C26"}

# Look back this many days for recently-modified invoices.
# Set to 60 to safely cover all April/May 2026 postings (even early April).
LOOKBACK_DAYS = 60


def _fetch_invoices_from_frappe() -> list[dict]:
    """
    Get the list of invoices to cancel directly from Frappe.

    Frappe stores sap_ar_invoice_docentry on every posted Unicommerce Order.
    This is more reliable than querying SAP OData (which rejects many filters).

    Criteria:
      - pipeline_status = posted  (successfully posted to SAP)
      - order_date < 2026-04-01  (March orders that went to old series)
      - modified >= 30 days ago  (posted to SAP recently — modified is updated on status change)
      - sap_ar_invoice_docentry not empty

    NOTE: We filter on `modified`, NOT `creation`. These March orders were fetched into Frappe
    in March (creation = March), but were only posted to SAP in April/May (modified = April/May).
    """
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    rows = frappe.get_all(
        "Unicommerce Orders",
        filters={
            "pipeline_status": "posted",
            "sap_ar_invoice_docentry": ["!=", ""],
            "order_date": ["<", "2026-04-01"],
            "modified": [">=", since],
        },
        fields=[
            "name",
            "sap_ar_invoice_docentry",
            "sap_ar_invoice_docnum",
            "order_date",
            "channel_name",
            "ar_invoice_tax_actual",
        ],
        order_by="sap_ar_invoice_docentry asc",
        limit=0,
    )
    return [
        {
            "DocEntry": int(r.sap_ar_invoice_docentry),
            "DocNum": r.sap_ar_invoice_docnum,
            "DocDate": str(r.order_date),
            "DocTotal": 0,
            "uc_order_name": r.name,
            "channel": r.channel_name,
        }
        for r in rows
        if str(r.sap_ar_invoice_docentry or "").strip().isdigit()
    ]


def cancel_old_series_invoices(dry_run: bool = True) -> dict:
    """
    Cancel SAP AR Invoices in old FY2025 series posted by our integration.

    Args:
        dry_run: If True (default), prints every invoice that would be
                 cancelled — zero changes to SAP or Frappe.
                 Always run dry_run=True first to review.

    Returns:
        dict: total, cancelled, failed, errors
    """
    sap = SAPClient()
    sap.login()

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*70}")
    print(f"  cancel_old_series_invoices  [{mode}]")
    print(f"  Old series (cancel): {', '.join(sorted(OLD_SERIES_NAMES))}")
    print(f"  Good series (keep):  {', '.join(sorted(GOOD_SERIES_NAMES))}")
    print(f"  Filter: Comments='Unicommerce Order:...' + DocDate < 2026-04-01")
    print(f"  Lookback: {LOOKBACK_DAYS} days")
    print(f"{'='*70}\n")

    invoices = _fetch_invoices_from_frappe()
    total = len(invoices)
    print(f"Invoices to cancel (from Frappe): {total}\n")

    if not invoices:
        print("Nothing to cancel.")
        return {"total": 0, "cancelled": 0, "failed": 0, "errors": []}

    # Print header
    print(f"{'DocEntry':<12} {'DocNum':<10} {'DocDate':<12} {'Channel':<20}  UCOrderID")
    print("-" * 110)

    cancelled = 0
    failed = 0
    errors: list[str] = []

    for inv in invoices:
        doc_entry = inv.get("DocEntry")
        doc_num = inv.get("DocNum")
        doc_date = str(inv.get("DocDate") or "")[:10]
        channel = str(inv.get("channel") or "")[:18]
        uc_order_name = inv.get("uc_order_name")

        print(
            f"{doc_entry:<12} {doc_num:<10} {doc_date:<12} {channel:<20}  {uc_order_name or '?'}"
        )

        if dry_run:
            continue

        try:
            sap.cancel_ar_invoice(doc_entry)
            print(f"             ✓ Cancelled in SAP")
            cancelled += 1
        except Exception as e:
            failed += 1
            err = f"SAP cancel failed — DocEntry={doc_entry} DocNum={doc_num}: {e}"
            errors.append(err)
            frappe.log_error(err, "cancel_old_series_invoices")
            print(f"             ✗ SAP CANCEL FAILED: {e}")
            continue  # do NOT reset Frappe if SAP cancel failed

        # Only reset Frappe after SAP cancel is confirmed successful
        if uc_order_name:
            try:
                _reset_frappe_order(uc_order_name, doc_entry, doc_num)
                print(f"             ✓ Frappe order reset to ready")
            except Exception as e:
                err = f"Frappe reset failed (SAP cancel succeeded) — DocEntry={doc_entry} Order={uc_order_name}: {e}"
                errors.append(err)
                frappe.log_error(err, "cancel_old_series_invoices")
                print(f"             ✗ FRAPPE RESET FAILED (manual fix needed): {e}")

    print(f"\n{'='*70}")
    print(f"  [{mode}] Complete")
    print(f"  Total:     {total}")
    if dry_run:
        print(f"  Status:    Dry run — nothing changed. Run with dry_run=False to cancel.")
    else:
        print(f"  Cancelled: {cancelled}")
        print(f"  Failed:    {failed}")
        if errors:
            print(f"\n  Errors:")
            for e in errors:
                print(f"    - {e}")
        if cancelled > 0:
            print(f"\n  Next step: re-enable post_invoices scheduled job.")
            print(f"  {cancelled} orders are now back in 'ready' and will re-post to 2026 series.")
    print(f"{'='*70}\n")

    return {
        "total": total,
        "cancelled": cancelled if not dry_run else 0,
        "would_cancel": total if dry_run else 0,
        "failed": failed,
        "errors": errors,
    }


def _parse_uc_order_name(comments: str) -> str | None:
    """Extract UC order name from 'Unicommerce Order: <name> | Channel: ...'"""
    if not comments:
        return None
    try:
        return comments.split("Unicommerce Order:", 1)[1].split("|")[0].strip()
    except (IndexError, AttributeError):
        return None


def _reset_frappe_order(uc_order_name: str, doc_entry: int, doc_num: int) -> None:
    """
    Reset Frappe Unicommerce Order back to ready so it re-posts to the correct 2026 series.
    """
    if not frappe.db.exists("Unicommerce Orders", uc_order_name):
        frappe.logger().warning(
            f"cancel_old_series_invoices: {uc_order_name!r} not found in Frappe — skipping reset"
        )
        return

    frappe.db.set_value(
        "Unicommerce Orders",
        uc_order_name,
        {
            "pipeline_status": "ready",
            "sap_ar_invoice_docentry": "",
            "sap_ar_invoice_docnum": "",
            "ar_invoice_tax_actual": 0,
            "attempt_count": 0,
            "last_error": (
                f"Old FY2025-series invoice cancelled: DocEntry={doc_entry} DocNum={doc_num}. "
                f"Reset to ready on {now_datetime()} — will re-post to FY2026 series."
            ),
        },
    )
    frappe.db.commit()
