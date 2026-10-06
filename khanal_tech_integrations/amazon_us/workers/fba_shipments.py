"""
Sync FBA shipment dates into Amazon US Order.actual_ship_date.

Source: GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL (SP-API Reports API).
  - Contains `shipment-date` — the actual date Amazon handed the package to the carrier.
  - This is the date Amazon uses in the MTR (Merchant Tax Report).
  - Report can cover up to 30 days per request. Do not request more than once/24h.

Flow:
  1. Request report for date range
  2. Poll until DONE (up to 10 min)
  3. Parse TSV, extract min(shipment-date) per amazon-order-id
  4. Convert shipment-date to Pacific Time (MTR-aligned)
  5. UPDATE actual_ship_date on matching Amazon US Order docs

Daily scheduler job (sync_fba_shipments_daily) covers last 7 days.
Manual trigger available via api/ops.py (enqueue_fba_shipments_sync).
"""
import csv
import io
import json
from datetime import datetime, timedelta, timezone

import frappe
from frappe.utils import now_datetime

from khanal_tech_integrations.amazon_us import (
    INCREMENTAL_LOOKBACK_DAYS,
    ORDER_DOCTYPE,
    notify_job_failure,
)
from khanal_tech_integrations.amazon_us.client.reports import (
    create_report,
    download_report,
    poll_report,
)
from khanal_tech_integrations.amazon_us.client.sp_api import _pacific_day_to_utc

_REPORT_TYPE = "GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL"
_SETTINGS_DOCTYPE = "Amazon US Settings"


# ─── Timezone helper ──────────────────────────────────────────────────────────

def _to_pacific_date(raw):
    """
    Convert a shipment-date value from the FBA report to a Pacific calendar date string.
    FBA report dates are UTC ISO 8601 (e.g. '2026-05-15T07:30:00+00:00').
    """
    if not raw:
        return None
    try:
        from zoneinfo import ZoneInfo
        pacific = ZoneInfo("America/Los_Angeles")
    except Exception:
        try:
            import pytz
            pacific = pytz.timezone("America/Los_Angeles")
        except Exception:
            pacific = None

    s = str(raw).strip()
    try:
        if "T" in s:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.fromisoformat(s + "T00:00:00+00:00")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        pacific_dt = dt.astimezone(pacific) if pacific else dt
        return pacific_dt.strftime("%Y-%m-%d")
    except Exception:
        return None


# ─── Cache helpers (for ops-center polling) ───────────────────────────────────

def _cache_key(job_id):
    return f"amz_us_fba_shipments_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[fba_shipments] {msg}")
        return
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
    if not job_id:
        return
    raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    data.update(updates)
    frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


# ─── Core sync ────────────────────────────────────────────────────────────────

def sync_fba_shipments_range(from_date, to_date, progress_id=None):
    """
    Request and process FBA Shipments report for from_date → to_date (YYYY-MM-DD Pacific).
    Updates actual_ship_date on matching Amazon US Order docs.
    Max date range: 30 days (SP-API limit). Returns summary dict.
    """
    _set(progress_id, {"status": "running"})
    settings = frappe.get_doc(_SETTINGS_DOCTYPE)
    marketplace_id = settings.marketplace_id

    data_start = _pacific_day_to_utc(from_date, end_of_day=False)
    data_end = _pacific_day_to_utc(to_date, end_of_day=True)

    _emit(progress_id, f"Requesting {_REPORT_TYPE}: {from_date} → {to_date} (UTC: {data_start} → {data_end})")

    try:
        report_id = create_report(_REPORT_TYPE, marketplace_id, data_start, data_end)
    except Exception as e:
        err = str(e)
        _emit(progress_id, f"create_report failed: {err}", "error")
        _set(progress_id, {"status": "error", "message": err})
        frappe.log_error(err, "Amazon US FBA Shipments — create_report")
        return {"status": "error", "message": err}

    _emit(progress_id, f"Report requested: {report_id}. Polling (max 10 min)...")

    try:
        doc_id = poll_report(report_id, poll_interval=30, max_wait=600)
    except Exception as e:
        err = str(e)
        _emit(progress_id, f"poll_report failed: {err}", "error")
        _set(progress_id, {"status": "error", "message": err})
        frappe.log_error(err, "Amazon US FBA Shipments — poll_report")
        return {"status": "error", "message": err}

    _emit(progress_id, f"Report ready ({doc_id}). Downloading...")

    try:
        content = download_report(doc_id)
    except Exception as e:
        err = str(e)
        _emit(progress_id, f"download_report failed: {err}", "error")
        _set(progress_id, {"status": "error", "message": err})
        frappe.log_error(err, "Amazon US FBA Shipments — download_report")
        return {"status": "error", "message": err}

    # Parse TSV — collect minimum (earliest) ship date per order
    ship_dates = {}  # {amazon_order_id: pacific_date_str}
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for row in reader:
        order_id = (row.get("amazon-order-id") or "").strip()
        raw_date = (row.get("shipment-date") or "").strip()
        if not order_id or not raw_date:
            continue
        pacific_date = _to_pacific_date(raw_date)
        if not pacific_date:
            continue
        if order_id not in ship_dates or pacific_date < ship_dates[order_id]:
            ship_dates[order_id] = pacific_date

    _emit(progress_id, f"Parsed {len(ship_dates)} unique order ship dates. Updating DB...")

    updated = skipped = 0
    for order_id, pacific_date in ship_dates.items():
        if not frappe.db.exists(ORDER_DOCTYPE, order_id):
            skipped += 1
            continue
        frappe.db.set_value(
            ORDER_DOCTYPE,
            order_id,
            "actual_ship_date",
            pacific_date,
            update_modified=False,
        )
        updated += 1

    frappe.db.commit()

    result = {
        "status": "done",
        "report_id": report_id,
        "parsed": len(ship_dates),
        "updated": updated,
        "skipped": skipped,
    }
    _emit(progress_id, f"Done. updated={updated} skipped={skipped} (orders not in staging)")
    _set(progress_id, result)
    return result


# ─── Scheduler entry point ────────────────────────────────────────────────────

_MAX_REPORT_SPAN_DAYS = 29  # SP-API Reports API caps a request at 30 days; stay one under


def sync_fba_shipments_daily():
    """
    Daily background job: watermark-based sync of FBA shipment dates.

    Self-healing by design: resumes from Amazon US Settings.fba_sync_watermark
    (the last date this job *successfully* completed through) instead of a
    blind fixed lookback. If the scheduler misses days -- server restart,
    worker crash, bench down -- the next successful run automatically covers
    the whole gap (capped at the SP-API's ~30-day report window) instead of
    silently losing anything older than a fixed window. The old fixed
    7-day-lookback version could never recover a gap wider than 7 days on
    its own; this replaces it.

    The watermark only advances on success -- a failed run leaves it where
    it was, so the next scheduled run retries the exact same window rather
    than skipping past it.
    """
    settings = frappe.get_doc(_SETTINGS_DOCTYPE)
    today = datetime.now(timezone.utc).date()
    to_date = today - timedelta(days=1)

    raw_watermark = getattr(settings, "fba_sync_watermark", None)
    if raw_watermark:
        watermark_date = raw_watermark if hasattr(raw_watermark, "strftime") else \
            datetime.strptime(str(raw_watermark)[:10], "%Y-%m-%d").date()
        from_date = watermark_date + timedelta(days=1)
    else:
        from_date = today - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)
        frappe.logger().info("[fba_shipments_daily] No watermark found — starting from INCREMENTAL_LOOKBACK_DAYS")

    if to_date - from_date > timedelta(days=_MAX_REPORT_SPAN_DAYS):
        from_date = to_date - timedelta(days=_MAX_REPORT_SPAN_DAYS)

    if from_date > to_date:
        frappe.logger().info("[fba_shipments_daily] Watermark already caught up, nothing to sync")
        return {"status": "done", "message": "Already up to date"}

    from_str, to_str = from_date.strftime("%Y-%m-%d"), to_date.strftime("%Y-%m-%d")
    frappe.logger().info(f"[fba_shipments_daily] {from_str} → {to_str} (watermark-based)")

    try:
        result = sync_fba_shipments_range(from_str, to_str)
    except Exception as e:
        err = str(e)
        frappe.log_error(err, "Amazon US FBA Shipments Daily")
        notify_job_failure("FBA shipments daily sync crashed", err)
        return {"status": "error", "message": err}

    if result.get("status") == "done":
        frappe.db.set_value(_SETTINGS_DOCTYPE, _SETTINGS_DOCTYPE, "fba_sync_watermark", to_str, update_modified=False)
        frappe.db.commit()
    else:
        notify_job_failure(
            "FBA shipments daily sync failed",
            f"Window {from_str} → {to_str} did not complete: {result.get('message')}. "
            f"Watermark left at previous value -- next run retries this window.",
        )

    return result
