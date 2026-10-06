"""
POD repair and monitoring utilities.

-- One-time re-patch --
Re-patches SAP B1 U_Pod_Link for invoices that are already Completed in Frappe
but are missing the POD link in SAP (caused by the old code clearing the link
when Get_Single_Pod failed on the first run).

Usage:
    # Dry run first — see what will be patched without touching SAP
    bench --site khanaltech.com execute \
        khanal_tech_integrations.utils.repatch_pod.run \
        --kwargs "{'from_date': '2025-04-01', 'to_date': '2026-03-31', 'dry_run': True}"

    # Live run
    bench --site khanaltech.com execute \
        khanal_tech_integrations.utils.repatch_pod.run \
        --kwargs "{'from_date': '2025-04-01', 'to_date': '2026-03-31', 'dry_run': False}"

-- Monthly POD pending report --
Runs automatically on the 1st of every month (wired into hooks.py cron).
Can also be triggered manually:
    bench --site khanaltech.com execute \
        khanal_tech_integrations.utils.repatch_pod.monthly_pod_pending_report
"""

import calendar
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Optional
import frappe
from frappe.utils import add_days, add_to_date, nowdate, getdate

# Pause between SAP PATCH calls to avoid flooding Service Layer
SAP_CALL_DELAY = 0.3

SAFEXPRESS_SERIES = [
    "KAIN24", "KAIN25", "AR2024", "AR2025",
    "HRIN24", "HRIN25", "MHIN24", "MHIN25",
    "KAIN23", "AR2023", "HRIN23", "MHIN23", "Manual",
]

MONTH_NAMES = [
    "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "January", "February", "March",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_fy_dates():
    """Return (fy_start, fy_end) for the Indian financial year that contains today."""
    today = getdate(nowdate())
    if today.month >= 4:
        fy_start = date(today.year, 4, 1)
        fy_end   = date(today.year + 1, 3, 31)
    else:
        fy_start = date(today.year - 1, 4, 1)
        fy_end   = date(today.year, 3, 31)
    return str(fy_start), str(fy_end)


def _get_recipients():
    """Read notification recipients from DSR Settings (comma-separated)."""
    try:
        doc = frappe.get_doc("DSR Settings")
        raw = getattr(doc, "notification_recipients", None) or ""
        recipients = [r.strip() for r in raw.split(",") if r.strip()]
        if recipients:
            return recipients
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Re-patch script
# ---------------------------------------------------------------------------

def run(
    from_date: str = None,
    to_date: str = None,
    days: int = None,
    dry_run: bool = True,
):
    """
    Re-patch SAP B1 U_Pod_Link for SafeExpress and DSR invoices that are
    Completed in Frappe but may be missing the link in SAP.

    Supply either (from_date + to_date) or days; from_date/to_date take priority.

    Args:
        from_date: Start date string 'YYYY-MM-DD'  (e.g. '2025-04-01')
        to_date:   End date string   'YYYY-MM-DD'  (e.g. '2026-03-31')
        days:      Lookback days from today (used only when from_date is not given)
        dry_run:   True = list records only, no SAP calls (default True — always dry-run first)
    """
    if from_date and to_date:
        fd, td = str(from_date), str(to_date)
    elif days:
        fd = str(add_to_date(nowdate(), days=-int(days)))
        td = str(nowdate())
    else:
        fd, td = _current_fy_dates()

    stats = {
        "safexpress": {"found": 0, "patched": 0, "skipped": 0, "failed": 0},
        "dsr":        {"found": 0, "patched": 0, "skipped": 0, "failed": 0},
    }

    print("=" * 70)
    print(f"POD Re-Patch  |  {fd} → {td}  |  dry_run={dry_run}")
    print("=" * 70)

    # Query HANA once — reused by both transporters to avoid duplicate queries
    print("\nQuerying HANA DB for invoices missing U_Pod_Link in date range...")
    sap_broken = _fetch_sap_docentries_missing_pod(fd, td)
    if sap_broken is None:
        print("HANA query failed — cannot continue. Check Frappe Error Log.")
        return stats
    print(f"SAP reports {len(sap_broken)} invoice(s) with empty U_Pod_Link\n")

    _repatch_safexpress(fd, td, dry_run, stats["safexpress"], sap_broken)
    _repatch_dsr(fd, td, dry_run, stats["dsr"], sap_broken)

    sx  = stats["safexpress"]
    dsr = stats["dsr"]
    print("\n" + "=" * 70)
    print("SUMMARY")
    print(f"  SafeExpress  — found:{sx['found']:>5}  patched:{sx['patched']:>5}  "
          f"skipped:{sx['skipped']:>5}  failed:{sx['failed']:>5}")
    print(f"  DSR Logistics— found:{dsr['found']:>5}  patched:{dsr['patched']:>5}  "
          f"skipped:{dsr['skipped']:>5}  failed:{dsr['failed']:>5}")
    if dry_run:
        print("\n  *** DRY RUN — no SAP changes were made ***")
        print("  Re-run with dry_run=False to apply.")
    print("=" * 70)
    return stats


NON_SAFEXPRESS_TRANSPORTERS = [
    "DP World", "Delhivery", "Local delivery partner",
    "Platform Fulfilled", "DSR Logistics",
]


def _fetch_sap_docentries_missing_pod(from_date, to_date):
    """
    Query HANA DB directly for AR invoices where U_Pod_Link is NULL or empty.
    Uses the existing read-only HANA connection — faster than OData and avoids
    SAP Service Layer HTTP 500 errors when filtering on UDF null values.

    Returns a set of DocEntry strings, or None if the query fails.
    """
    try:
        import hdbcli.dbapi as hana_dbapi
    except ImportError:
        print("  hdbcli not available — cannot query HANA directly")
        frappe.log_error("hdbcli not installed", "POD Re-Patch HANA Fetch")
        return None

    # Read credentials from SAP Settings (same source used by hana_query_engine.py)
    try:
        sap_settings = frappe.get_single("SAP Settings")
        hana_host     = sap_settings.hana_host
        hana_port     = int(sap_settings.hana_port)
        hana_user     = sap_settings.hana_user
        hana_password = sap_settings.get_password("hana_password")
        hana_schema   = sap_settings.hana_schema
    except Exception as exc:
        print(f"  Could not read HANA credentials from SAP Settings: {exc}")
        frappe.log_error(str(exc), "POD Re-Patch HANA Config")
        return None

    # Schema name comes from SAP Settings — safe to embed.
    # from_date / to_date are user-supplied — use ? placeholders to prevent SQL injection.
    # U_Pod_Link is a LOB column in HANA — = '' raises "inconsistent datatype".
    # Use LENGTH() = 0 for the empty-string check instead.
    sql = (
        'SELECT "DocEntry" FROM "{schema}"."OINV" '
        'WHERE "DocDate" BETWEEN ? AND ? '
        'AND ("U_Pod_Link" IS NULL OR LENGTH("U_Pod_Link") = 0)'
    ).format(schema=hana_schema)

    conn = None
    try:
        conn = hana_dbapi.connect(
            address=hana_host,
            port=hana_port,
            user=hana_user,
            password=hana_password,
        )
        cursor = conn.cursor()
        cursor.execute(sql, (from_date, to_date))
        rows = cursor.fetchall()
        broken = {str(row[0]) for row in rows}
        print(f"  HANA query returned {len(broken)} invoices with empty U_Pod_Link")
        return broken

    except Exception as exc:
        print(f"  HANA query failed: {exc}")
        frappe.log_error(str(exc), "POD Re-Patch HANA Fetch")
        return None

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _repatch_safexpress(from_date, to_date, dry_run, stats, sap_broken):
    from khanal_tech_integrations.utils.safexpress.attachpod_to_sap import PATCH_POD_AR_invoice

    base_filters = {
        "pod_status": "Completed",
        "pod_url":    ["!=", ""],
        "doc_date":   ["between", [from_date, to_date]],
    }

    # Group A: explicitly marked SafeExpress via transporter_type
    by_transporter = frappe.get_all(
        "SAP AR Invoice Detail",
        filters={**base_filters, "transporter_type": "SafeExpress"},
        fields=["name", "docnum", "pod_url", "pod_date", "way_bill_number"],
        order_by="doc_date asc",
    )

    # Group B: known SafeExpress series where transporter_type isn't explicitly set
    # (exclude confirmed non-SafeExpress transporters to avoid overlap with DSR etc.)
    by_series = frappe.get_all(
        "SAP AR Invoice Detail",
        filters={
            **base_filters,
            "series_name":      ["in", SAFEXPRESS_SERIES],
            "transporter_type": ["not in", NON_SAFEXPRESS_TRANSPORTERS + ["SafeExpress"]],
        },
        fields=["name", "docnum", "pod_url", "pod_date", "way_bill_number"],
        order_by="doc_date asc",
    )

    seen = set()
    all_records = []
    for r in by_transporter + by_series:
        if r["name"] not in seen:
            seen.add(r["name"])
            all_records.append(r)

    records = [r for r in all_records if str(r["name"]) in sap_broken]
    stats["found"] = len(records)
    print(f"\n[SafeExpress] {len(records)} invoice(s) broken in SAP and have pod_url in Frappe → will re-patch")

    for idx, rec in enumerate(records, 1):
        docentry = rec["name"]
        label = f"  [{idx}/{len(records)}] DocEntry={docentry}  DocNum={rec['docnum']}"

        if not rec["pod_url"]:
            print(f"{label}  SKIP — no pod_url")
            stats["skipped"] += 1
            continue

        if not rec["pod_date"]:
            print(f"{label}  SKIP — no pod_date (cannot build valid SAP payload)")
            stats["skipped"] += 1
            frappe.log_error(
                f"Skipped re-patch for SafeExpress docentry {docentry}: pod_date missing.",
                "POD Re-Patch SafeExpress",
            )
            continue

        if dry_run:
            print(f"{label}  DRY-RUN  pod_url={rec['pod_url'][:55]}…")
            stats["patched"] += 1
            continue

        try:
            response = PATCH_POD_AR_invoice(docentry)
            if response and response.status_code in (200, 204):
                print(f"{label}  OK ({response.status_code})")
                stats["patched"] += 1
            else:
                status = response.status_code if response else "no response"
                print(f"{label}  FAILED ({status})")
                stats["failed"] += 1
                frappe.log_error(
                    f"Re-patch failed for SafeExpress docentry {docentry}: HTTP {status}",
                    "POD Re-Patch SafeExpress",
                )
        except Exception as exc:
            print(f"{label}  ERROR: {exc}")
            stats["failed"] += 1
            frappe.log_error(
                f"Re-patch exception for SafeExpress docentry {docentry}: {exc}",
                "POD Re-Patch SafeExpress",
            )

        time.sleep(SAP_CALL_DELAY)


def _repatch_dsr(from_date, to_date, dry_run, stats, sap_broken):
    from khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION import _patch_sap_invoice

    all_records = frappe.get_all(
        "SAP AR Invoice Detail",
        filters={
            "pod_status":       ["in", ["Completed", "Pending_SAP"]],
            "pod_url":          ["!=", ""],
            "transporter_type": "DSR Logistics",
            "doc_date":         ["between", [from_date, to_date]],
        },
        fields=["name", "docnum", "pod_url", "pod_date", "pod_status", "way_bill_number"],
        order_by="doc_date asc",
    )

    records = [r for r in all_records if str(r["name"]) in sap_broken]
    stats["found"] = len(records)
    print(f"\n[DSR Logistics] {len(records)} invoice(s) broken in SAP and have pod_url in Frappe → will re-patch")

    for idx, rec in enumerate(records, 1):
        docentry = rec["name"]
        label = (
            f"  [{idx}/{len(records)}] DocEntry={docentry}  "
            f"DocNum={rec['docnum']}  status={rec['pod_status']}"
        )

        if not rec["pod_url"]:
            print(f"{label}  SKIP — no pod_url")
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"{label}  DRY-RUN  pod_url={rec['pod_url'][:55]}…")
            stats["patched"] += 1
            continue

        try:
            response = _patch_sap_invoice(docentry)
            if response:
                if rec["pod_status"] == "Pending_SAP":
                    frappe.db.set_value(
                        "SAP AR Invoice Detail", rec["name"], {"pod_status": "Completed"}
                    )
                    frappe.db.commit()
                print(f"{label}  OK")
                stats["patched"] += 1
            else:
                print(f"{label}  SKIPPED by _patch_sap_invoice (pod_url missing in DB?)")
                stats["skipped"] += 1
        except Exception as exc:
            print(f"{label}  FAILED: {exc}")
            stats["failed"] += 1
            frappe.log_error(
                f"Re-patch exception for DSR docentry {docentry}: {exc}",
                "POD Re-Patch DSR",
            )

        time.sleep(SAP_CALL_DELAY)


# ---------------------------------------------------------------------------
# Monthly POD pending report  (runs 1st of every month via hooks.py)
# ---------------------------------------------------------------------------

def monthly_pod_pending_report(start_date=None, end_date=None):
    """
    Send a POD status report email for the given date range.

    When start_date/end_date are omitted, defaults to the current Indian
    financial year (April 1 – March 31).  Triggered automatically on the
    1st of each month at 09:00; can also be called manually with a custom
    range from the dashboard.

    Recipients are read from DSR Settings → notification_recipients.
    """
    if start_date and end_date:
        range_start  = str(start_date)
        range_end    = str(end_date)
        range_label  = f"{range_start} to {range_end}"
    else:
        range_start, range_end = _current_fy_dates()
        s = getdate(range_start)
        range_label = f"FY {s.year}–{s.year + 1}"

    today_str  = nowdate()
    recipients = _get_recipients()

    # ---- fetch records ----
    all_records = frappe.get_all(
        "SAP AR Invoice Detail",
        filters={"doc_date": ["between", [range_start, range_end]]},
        fields=["name", "docnum", "pod_status", "transporter_type",
                "series_name", "doc_date", "pod_url", "way_bill_number"],
        order_by="doc_date asc",
        limit_page_length=0,
    )

    def _is_sx(r):
        return r["series_name"] in SAFEXPRESS_SERIES

    def _is_dsr(r):
        return (r.get("transporter_type") or "").strip() == "DSR Logistics"

    def _pending(r):
        return r["pod_status"] in ("Pending", "Pending_SAP", "", None)

    def _completed(r):
        return r["pod_status"] == "Completed"

    sx_records  = [r for r in all_records if _is_sx(r)]
    dsr_records = [r for r in all_records if _is_dsr(r)]

    sx_total     = len(sx_records)
    sx_completed = len([r for r in sx_records if _completed(r)])
    sx_pending   = len([r for r in sx_records if _pending(r)])

    dsr_total     = len(dsr_records)
    dsr_completed = len([r for r in dsr_records if _completed(r)])
    dsr_pending   = len([r for r in dsr_records if _pending(r)])

    grand_total     = sx_total + dsr_total
    grand_completed = sx_completed + dsr_completed
    grand_pending   = sx_pending + dsr_pending

    # ---- month-wise pending breakdown ----
    # Build ordered list of (year, month) pairs covering the full range
    s_date = getdate(range_start)
    e_date = getdate(range_end)
    months_in_range = []
    y, m = s_date.year, s_date.month
    while (y, m) <= (e_date.year, e_date.month):
        months_in_range.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    sx_month_pending  = defaultdict(int)
    dsr_month_pending = defaultdict(int)

    for r in sx_records:
        if _pending(r) and r.get("doc_date"):
            d = getdate(r["doc_date"])
            sx_month_pending[(d.year, d.month)] += 1

    for r in dsr_records:
        if _pending(r) and r.get("doc_date"):
            d = getdate(r["doc_date"])
            dsr_month_pending[(d.year, d.month)] += 1

    # ---- build month table rows ----
    month_rows = ""
    for (yr, mo) in months_in_range:
        sx_p    = sx_month_pending[(yr, mo)]
        dsr_p   = dsr_month_pending[(yr, mo)]
        total_p = sx_p + dsr_p
        row_style   = 'background:#fff3cd' if total_p > 0 else ''
        month_label = f"{calendar.month_abbr[mo]} {yr}"
        month_rows += f"""
        <tr style="{row_style}">
            <td style="padding:6px 12px;border:1px solid #dee2e6">{month_label}</td>
            <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center">{sx_p}</td>
            <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center">{dsr_p}</td>
            <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;font-weight:bold">{total_p}</td>
        </tr>"""

    pending_color = "#dc3545" if grand_pending > 0 else "#28a745"

    body = f"""
<div style="font-family:Arial,sans-serif;font-size:14px;color:#333">

<h2 style="color:#343a40">POD Status Report — {range_label}</h2>
<p style="color:#6c757d">Generated on {today_str} &nbsp;|&nbsp; Period: {range_start} to {range_end}</p>

<h3 style="margin-top:24px">Overall Summary</h3>
<table style="border-collapse:collapse;min-width:380px">
  <thead>
    <tr style="background:#343a40;color:#fff">
      <th style="padding:8px 14px;border:1px solid #dee2e6;text-align:left">Transporter</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">Total Invoices</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">POD Completed</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">POD Pending</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:6px 12px;border:1px solid #dee2e6">SafeExpress</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center">{sx_total}</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;color:#28a745;font-weight:bold">{sx_completed}</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;color:{'#dc3545' if sx_pending else '#28a745'};font-weight:bold">{sx_pending}</td>
    </tr>
    <tr style="background:#f8f9fa">
      <td style="padding:6px 12px;border:1px solid #dee2e6">DSR Logistics</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center">{dsr_total}</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;color:#28a745;font-weight:bold">{dsr_completed}</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;color:{'#dc3545' if dsr_pending else '#28a745'};font-weight:bold">{dsr_pending}</td>
    </tr>
    <tr style="background:#e9ecef;font-weight:bold">
      <td style="padding:6px 12px;border:1px solid #dee2e6">Total</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center">{grand_total}</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;color:#28a745">{grand_completed}</td>
      <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;color:{pending_color}">{grand_pending}</td>
    </tr>
  </tbody>
</table>

<h3 style="margin-top:28px">Month-wise Pending PODs</h3>
<table style="border-collapse:collapse;min-width:380px">
  <thead>
    <tr style="background:#343a40;color:#fff">
      <th style="padding:8px 14px;border:1px solid #dee2e6;text-align:left">Month</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">SafeExpress Pending</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">DSR Pending</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">Total Pending</th>
    </tr>
  </thead>
  <tbody>
    {month_rows}
  </tbody>
</table>

<p style="margin-top:24px;color:#6c757d;font-size:12px">
  <b>Pending</b> includes pod_status = Pending and Pending_SAP.<br>
  This report covers invoices with doc_date between {range_start} and {range_end}.
</p>
</div>
"""

    overdue_section, overdue_total = _build_overdue_pod_section()
    body += overdue_section

    subject = (
        f"[POD Report] {range_label} — {grand_pending} pending"
        f" | {overdue_total} overdue >30d — {today_str}"
    )

    if not recipients:
        frappe.log_error("No recipients configured for POD report.", "POD Monthly Report")
        return {"status": "error", "error": "No recipients configured"}

    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=body,
        now=True,
    )
    frappe.logger().info(
        f"POD report sent to {recipients}. "
        f"Range: {range_start} to {range_end}. "
        f"Pending: {grand_pending} (SX={sx_pending}, DSR={dsr_pending}), "
        f"Overdue >30d: {overdue_total}"
    )
    return {
        "status": "sent",
        "recipients": recipients,
        "pending": grand_pending,
        "overdue": overdue_total,
    }


# ---------------------------------------------------------------------------
# Overdue POD section — appended to the monthly report email
# ---------------------------------------------------------------------------

def _build_overdue_pod_section():
    """
    Return an HTML string listing invoices with no POD after 30+ days.
    Returns an empty string if none are found.
    Excluded: Pending_SAP (pod_url already fetched, SAP PATCH being retried).
    """
    cutoff = add_days(nowdate(), -30)
    today_date = getdate(nowdate())

    overdue = frappe.get_all(
        "SAP AR Invoice Detail",
        filters=[
            ["doc_date", "<=", cutoff],
            ["pod_url", "in", ["", None]],
            ["pod_status", "in", ["Pending", "", None]],
        ],
        fields=[
            "docnum", "doc_date", "way_bill_number", "transporter_type", "customer_name",
        ],
        order_by="doc_date asc",
        limit_page_length=0,
    )

    if not overdue:
        return "", 0

    for r in overdue:
        inv_date = getdate(r["doc_date"]) if r.get("doc_date") else today_date
        r["days_overdue"] = (today_date - inv_date).days

    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)

    by_transporter = defaultdict(list)
    for r in overdue:
        tp = (r.get("transporter_type") or "Unknown").strip()
        by_transporter[tp].append(r)

    summary_rows = ""
    for tp, items in sorted(by_transporter.items()):
        summary_rows += f"""
        <tr>
          <td style="padding:6px 12px;border:1px solid #dee2e6">{tp}</td>
          <td style="padding:6px 12px;border:1px solid #dee2e6;text-align:center;
                     color:#dc3545;font-weight:bold">{len(items)}</td>
        </tr>"""

    detail_rows = ""
    for i, r in enumerate(overdue):
        row_bg = "background:#f8f9fa" if i % 2 else ""
        days = r["days_overdue"]
        day_color = "#dc3545" if days >= 60 else "#fd7e14"
        detail_rows += f"""
        <tr style="{row_bg}">
          <td style="padding:5px 10px;border:1px solid #dee2e6">{r.get('docnum') or ''}</td>
          <td style="padding:5px 10px;border:1px solid #dee2e6">{r.get('doc_date') or ''}</td>
          <td style="padding:5px 10px;border:1px solid #dee2e6;text-align:center;
                     color:{day_color};font-weight:bold">{days}</td>
          <td style="padding:5px 10px;border:1px solid #dee2e6">{r.get('transporter_type') or '—'}</td>
          <td style="padding:5px 10px;border:1px solid #dee2e6">{r.get('way_bill_number') or '—'}</td>
          <td style="padding:5px 10px;border:1px solid #dee2e6">{r.get('customer_name') or '—'}</td>
        </tr>"""

    total = len(overdue)
    html = f"""
<hr style="margin:32px 0;border:none;border-top:2px solid #dee2e6">

<h2 style="color:#dc3545">Overdue POD List — {total} Invoice(s) with No POD &gt; 30 Days</h2>
<p style="color:#6c757d">Invoices with no POD link and invoice date &le; {cutoff}.<br>
  <em>Pending_SAP invoices (POD fetched, SAP PATCH in progress) are excluded.</em></p>

<h3 style="margin-top:20px">By Transporter</h3>
<table style="border-collapse:collapse;min-width:280px">
  <thead>
    <tr style="background:#343a40;color:#fff">
      <th style="padding:8px 14px;border:1px solid #dee2e6;text-align:left">Transporter</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6">Count</th>
    </tr>
  </thead>
  <tbody>{summary_rows}</tbody>
</table>

<h3 style="margin-top:28px">Invoice Detail</h3>
<table style="border-collapse:collapse;min-width:680px">
  <thead>
    <tr style="background:#343a40;color:#fff">
      <th style="padding:8px 12px;border:1px solid #dee2e6;text-align:left">Invoice No.</th>
      <th style="padding:8px 12px;border:1px solid #dee2e6">Invoice Date</th>
      <th style="padding:8px 12px;border:1px solid #dee2e6">Days Overdue</th>
      <th style="padding:8px 12px;border:1px solid #dee2e6;text-align:left">Transporter</th>
      <th style="padding:8px 12px;border:1px solid #dee2e6;text-align:left">Waybill No.</th>
      <th style="padding:8px 12px;border:1px solid #dee2e6;text-align:left">Customer</th>
    </tr>
  </thead>
  <tbody>{detail_rows}</tbody>
</table>

<p style="margin-top:16px;color:#6c757d;font-size:12px">
  <span style="color:#fd7e14;font-weight:bold">Orange</span> = 30–59 days &nbsp;|&nbsp;
  <span style="color:#dc3545;font-weight:bold">Red</span> = 60+ days overdue.
</p>
"""
    return html, total
