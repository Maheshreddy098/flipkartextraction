"""
Daily proactive health check for the Amazon US pipeline.

Exists because of a real incident: the FBA shipment-date sync's fixed
7-day lookback silently lost coverage for 527 posted orders over several
weeks, and nobody found out until someone visually noticed a blank
"Shipped" column on the dashboard. frappe.log_error alone doesn't page
anyone -- this runs daily and actively emails Amazon US Settings.alert_email
(via notify_job_failure) when something that should be self-correcting
(see fba_shipments.py's watermark) isn't.

Checks:
  1. FBA shipment sync staleness -- fba_sync_watermark older than
     _STALE_DAYS behind today, or never set.
  2. Posted orders missing actual_ship_date exceeding
     _MISSING_SHIP_DATE_THRESHOLD -- the same canary that would have
     caught the original gap in real time instead of weeks later.

No-op (no email) if Amazon US Settings.alert_email is unset. Never raises.
"""
import frappe
from frappe.utils import date_diff, today

from khanal_tech_integrations.amazon_us import ORDER_DOCTYPE, notify_job_failure

_SETTINGS_DOCTYPE = "Amazon US Settings"
_STALE_DAYS = 2  # FBA watermark older than this = daily job hasn't succeeded recently
_MISSING_SHIP_DATE_THRESHOLD = 20  # posted orders missing actual_ship_date


def run_daily_health_check():
    """Scheduler entry point. Returns a summary dict; never raises."""
    issues = []

    watermark = frappe.db.get_single_value(_SETTINGS_DOCTYPE, "fba_sync_watermark")
    if not watermark or str(watermark) == "0001-01-01":
        issues.append("FBA shipment sync has never completed successfully (no watermark set).")
    else:
        stale_by = date_diff(today(), watermark)
        if stale_by > _STALE_DAYS:
            issues.append(
                f"FBA shipment sync is stale: last successful watermark is {watermark} "
                f"({stale_by} days behind today). Check the scheduler and worker logs."
            )

    missing_count = frappe.db.count(
        ORDER_DOCTYPE, {"stage": "posted", "actual_ship_date": ["is", "not set"]}
    )
    if missing_count > _MISSING_SHIP_DATE_THRESHOLD:
        issues.append(
            f"{missing_count} posted orders are missing actual_ship_date "
            f"(threshold {_MISSING_SHIP_DATE_THRESHOLD}). Likely a sync gap -- run "
            f"'Sync FBA ship dates' from the Actions tab for the affected window."
        )

    if issues:
        notify_job_failure("Daily health check found issues", "\n\n".join(issues))
        frappe.logger().warning(f"[amz_health_check] {len(issues)} issue(s): {issues}")
    else:
        frappe.logger().info("[amz_health_check] All checks passed")

    return {"status": "done", "issues": issues}
