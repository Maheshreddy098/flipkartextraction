"""
Ops aggregation API for the Unicommerce ↔ SAP integration.

All endpoints are read/write convenience wrappers used by:
  - the kiosk frontend Ops Panel
  - the Frappe Desk workspace
  - failure-alert hooks called from worker modules

Designed so a non-developer can monitor pipeline health, retry failures, and
manage alert recipients without touching code.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re
import os
import time
from typing import Any

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime, time_diff_in_seconds

from ..client import SAPClient, UCClient
from ..geo import (
    DEFAULT_ORIGIN_STATE_CODE,
    STATE_REGION_MAP,
    classify_tax_bucket,
    extract_shipping_state,
    resolve_origin_state_code,
    safe_json_loads,
)
from ..health import check_connections
from ..mappers.sap_payload import ar_invoice_payload
from ..returns import load_parent_order, prepare_credit_note_items
from ..workers.fetch import _order_ready_for_invoice
from ..workers.invoice import _check_batches


# ---------------------------------------------------------------------------
# doctype/status maps — single source of truth for the ops layer
# ---------------------------------------------------------------------------

ORDER_DOCTYPE = "Unicommerce Orders"
CREDIT_NOTE_DOCTYPE = "UC Credit Note Staging"
INVENTORY_DOCTYPE = "SAP Inventory Transfers"

STAGE_LABELS = {
    "orders": "Orders",
    "credit_notes": "Credit Notes",
    "inventory": "Inventory Sync",
    "grn": "GRN",
}

ORDER_STATUSES = ["pending", "fetched", "batch_hold", "ready", "posting", "verify", "posted", "failed", "dead"]
CREDIT_NOTE_STATUSES = ["pending", "posting", "posted", "failed", "dead"]
INVENTORY_STATUSES = ["Pending", "Synced", "Failed", "Partial"]

FAILURE_ORDER_STATUSES = ["failed", "dead"]
FAILURE_CN_STATUSES = ["failed", "dead"]
FAILURE_INVENTORY_STATUSES = ["Failed", "Partial"]

INVENTORY_PARITY_CACHE_KEY = "unicommerce_inventory_parity_v2"
WAREHOUSE_INVENTORY_CACHE_KEY = "unicommerce_ops_warehouse_inventory_v1"
# NOTE: monthly reconciliation cache key was removed when the legacy UC vs SAP
# monthly recon flow was replaced by the user-driven GST Reconciliation tab
# (see unicommerce/reporting/gst_recon.py).


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_overview() -> dict:
    """Single aggregated payload for the Ops landing page."""
    return {
        "health": _health_snapshot(),
        "counts": _stage_counts(),
        "guardrails": ops_posting_guardrail_summary(days=7),
        "last_runs": _last_scheduled_runs(),
        "recent_errors": _recent_errors(limit=10),
        "recon_summary": _recon_summary(),
        "generated_at": str(now_datetime()),
    }


@frappe.whitelist()
def ops_dashboard_data(start_date=None, end_date=None, hours: int = 24, timeline_days: int = 14) -> dict:
    """Single payload for the richer dashboard UI."""
    return {
        "overview": ops_overview(),
        "analytics": ops_channel_summary(start_date=start_date, end_date=end_date),
        "activity": ops_activity(hours=hours),
        "failures": ops_failures(stage="all", page=1, page_size=8),
        "batch_validation": ops_batch_validation_summary(),
        "reconciliation": ops_reconciliation_all(),
        "inventory_parity": ops_inventory_parity(refresh=0),
        "transfers": ops_transfer_summary(start_date=start_date, end_date=end_date),
        "monthly_reconciliation": ops_monthly_tax_reconciliation(months=6),
        "timeline": _order_timeline(days=timeline_days),
        "guardrails": ops_posting_guardrail_summary(days=max(int(timeline_days or 14), 7)),
        "generated_at": str(now_datetime()),
    }


def _health_snapshot() -> dict:
    cache_key = "unicommerce_ops_health"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    try:
        snapshot = check_connections()
    except Exception as e:
        snapshot = {"sap_login": {"ok": False, "message": str(e)}, "uc_login": {"ok": False, "message": str(e)}}
    frappe.cache().set_value(cache_key, json.dumps(snapshot, default=str), expires_in_sec=60)
    return snapshot


def _stage_counts() -> dict:
    return {
        "orders": _count_by_status(ORDER_DOCTYPE, "pipeline_status", ORDER_STATUSES),
        "credit_notes": _count_by_status(CREDIT_NOTE_DOCTYPE, "status", CREDIT_NOTE_STATUSES),
        "inventory": _count_by_status(INVENTORY_DOCTYPE, "unicommerce_sync_status", INVENTORY_STATUSES),
    }


def _count_by_status(doctype: str, field: str, values: list[str]) -> dict:
    out = {v: 0 for v in values}
    rows = frappe.db.sql(
        f"SELECT `{field}` AS s, COUNT(*) AS c FROM `tab{doctype}` GROUP BY `{field}`",
        as_dict=True,
    )
    for r in rows:
        if r.s in out:
            out[r.s] = int(r.c or 0)
    out["_total"] = sum(out.values())
    return out


def _last_scheduled_runs() -> dict:
    """Latest successful run timestamp per worker entry point."""
    workers = [
        "khanal_tech_integrations.unicommerce.workers.fetch.fetch_orders",
        "khanal_tech_integrations.unicommerce.workers.fetch.fetch_returns",
        "khanal_tech_integrations.unicommerce.workers.invoice.post_invoices",
        "khanal_tech_integrations.unicommerce.workers.credit_note.post_credit_notes",
        "khanal_tech_integrations.unicommerce.workers.grn.sync_grns",
        "khanal_tech_integrations.unicommerce.workers.inventory.sync_inventory",
    ]
    result = {}
    for path in workers:
        row = frappe.db.get_value(
            "Scheduled Job Log",
            {"scheduled_job_type": ["like", f"%{path.split('.')[-1]}%"], "status": "Complete"},
            ["modified", "status"],
            order_by="modified desc",
        )
        result[path.split(".")[-1]] = {"at": str(row[0]) if row else None, "status": row[1] if row else "never"}
    return result


def _recent_errors(limit: int = 10) -> list[dict]:
    from frappe.utils import add_days, today
    rows = frappe.get_all(
        "Error Log",
        filters={"error": ["like", "%unicommerce%"], "creation": [">=", add_days(today(), -7)]},
        fields=["name", "method", "creation", "error"],
        order_by="creation desc",
        limit=limit,
    )
    for r in rows:
        r["error"] = (r.get("error") or "")[:400]
    return rows


def _recon_summary() -> dict:
    try:
        return {"gap_count": len(_invoice_gap_rows(limit=200)), "ok": True}
    except Exception as e:
        return {"gap_count": 0, "ok": False, "error": str(e)[:200]}


def _posted_order_rows(start_date=None, end_date=None) -> list[dict]:
    where_parts = ["pipeline_status = 'posted'"]
    params: dict[str, Any] = {}
    if start_date:
        where_parts.append("order_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        where_parts.append("order_date <= %(end_date)s")
        params["end_date"] = end_date

    return frappe.db.sql(
        f"""
        SELECT
            name AS uc_order_id,
            COALESCE(NULLIF(channel_name, ''), 'Unknown') AS channel,
            order_date,
            ar_invoice_tax_actual AS tax_actual,
            ar_invoice_tax_diff AS tax_diff,
            order_json AS uc_raw_json,
            payload_json,
            modified
        FROM `tabUnicommerce Orders`
        WHERE {' AND '.join(where_parts)}
        ORDER BY order_date desc, modified desc
        """,
        params,
        as_dict=True,
    )


def _order_timeline(days: int = 14) -> list[dict]:
    days = max(int(days or 14), 1)
    start = add_to_date(now_datetime(), days=-(days - 1)).date()
    rows = frappe.db.sql(
        """
        SELECT
            order_date,
            SUM(CASE WHEN pipeline_status = 'fetched' THEN 1 ELSE 0 END) AS fetched,
            SUM(CASE WHEN pipeline_status = 'ready' THEN 1 ELSE 0 END) AS ready,
            SUM(CASE WHEN pipeline_status = 'posted' THEN 1 ELSE 0 END) AS posted,
            SUM(CASE WHEN pipeline_status IN ('failed', 'dead', 'batch_hold') THEN 1 ELSE 0 END) AS blocked
        FROM `tabUnicommerce Orders`
        WHERE order_date >= %(start)s
        GROUP BY order_date
        ORDER BY order_date asc
        """,
        {"start": start},
        as_dict=True,
    )
    row_map = {str(row.order_date): row for row in rows}
    timeline = []
    for offset in range(days):
        day = add_to_date(start, days=offset)
        row = row_map.get(str(day), {})
        timeline.append(
            {
                "day": get_datetime(day).strftime("%d %b"),
                "fetched": int(row.get("fetched") or 0),
                "ready": int(row.get("ready") or 0),
                "posted": int(row.get("posted") or 0),
                "blocked": int(row.get("blocked") or 0),
            }
        )
    return timeline


def _invoice_gap_rows(limit: int = 200) -> list[dict]:
    from ..validators.reconcile import get_gaps, get_reconciliation_gaps

    rows: list[dict] = []

    try:
        for row in get_reconciliation_gaps(min_tax_diff=1.0, min_unit_price_diff=1.0, limit=limit):
            rows.append(
                {
                    "source": "staging",
                    "document_type": "invoice",
                    "record_doctype": ORDER_DOCTYPE,
                    "record_name": row.get("name"),
                    "uc_order_id": row.get("uc_order_id"),
                    "channel": row.get("channel"),
                    "tax_expected": float(row.get("tax_expected") or 0),
                    "tax_actual": float(row.get("tax_actual") or 0),
                    "tax_diff": float(row.get("tax_diff") or 0),
                    "unit_price_expected": float(row.get("unit_price_expected") or 0),
                    "unit_price_actual": float(row.get("unit_price_actual") or 0),
                    "unit_price_diff": float(row.get("unit_price_diff") or 0),
                    "modified": row.get("modified"),
                }
            )
    except Exception:
        pass

    try:
        for row in get_gaps(min_tax_diff=1.0, min_unit_price_diff=1.0, limit=limit):
            invoice_score = max(
                float(row.get("ar_invoice_tax_diff") or 0),
                float(row.get("ar_invoice_unit_price_diff") or 0),
            )
            credit_score = max(
                float(row.get("ar_creditnote_tax_diff") or 0),
                float(row.get("ar_creditnote_unit_price_diff") or 0),
            )
            use_credit = credit_score > invoice_score
            prefix = "ar_creditnote" if use_credit else "ar_invoice"
            rows.append(
                {
                    "source": "legacy",
                    "document_type": "credit_note" if use_credit else "invoice",
                    "record_doctype": "Unicommerce Orders",
                    "record_name": row.get("name"),
                    "uc_order_id": row.get("uc_order_id"),
                    "channel": row.get("channel"),
                    "tax_expected": float(row.get(f"{prefix}_tax_expected") or 0),
                    "tax_actual": float(row.get(f"{prefix}_tax_actual") or 0),
                    "tax_diff": float(row.get(f"{prefix}_tax_diff") or 0),
                    "unit_price_expected": float(row.get(f"{prefix}_unit_price_expected") or 0),
                    "unit_price_actual": float(row.get(f"{prefix}_unit_price_actual") or 0),
                    "unit_price_diff": float(row.get(f"{prefix}_unit_price_diff") or 0),
                    "modified": row.get("modified"),
                }
            )
    except Exception:
        pass

    rows.sort(
        key=lambda row: max(
            float(row.get("tax_diff") or 0),
            float(row.get("unit_price_diff") or 0),
        ),
        reverse=True,
    )
    return rows[:limit]


# ---------------------------------------------------------------------------
# Failures listing
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_failures(stage: str = "all", page: int = 1, page_size: int = 25) -> dict:
    """Paginated failures across all stages."""
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 25), 1), 100)
    offset = (page - 1) * page_size

    rows: list[dict] = []
    if stage in ("all", "orders"):
        rows.extend(_failed_orders(page_size, offset if stage == "orders" else 0))
    if stage in ("all", "credit_notes"):
        rows.extend(_failed_credit_notes(page_size, offset if stage == "credit_notes" else 0))
    if stage in ("all", "inventory"):
        rows.extend(_failed_inventory(page_size, offset if stage == "inventory" else 0))

    rows.sort(key=lambda r: r.get("modified") or "", reverse=True)
    if stage == "all":
        rows = rows[offset:offset + page_size]

    # Total counts for monitoring panel (independent of current page)
    total_orders = frappe.db.count(ORDER_DOCTYPE, {"pipeline_status": ["in", FAILURE_ORDER_STATUSES]})
    total_cn = frappe.db.count(CREDIT_NOTE_DOCTYPE, {"status": ["in", FAILURE_CN_STATUSES]})
    total_inv = frappe.db.count(INVENTORY_DOCTYPE, {"unicommerce_sync_status": ["in", FAILURE_INVENTORY_STATUSES]})
    dead_orders = frappe.db.count(ORDER_DOCTYPE, {"pipeline_status": "dead"})
    dead_cn = frappe.db.count(CREDIT_NOTE_DOCTYPE, {"status": "dead"})

    return {
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "stage": stage,
        "total_count": int((total_orders or 0) + (total_cn or 0) + (total_inv or 0)),
        "hard_count": int((dead_orders or 0) + (dead_cn or 0)),
    }


def _failed_orders(limit: int, offset: int) -> list[dict]:
    rows = frappe.get_all(
        ORDER_DOCTYPE,
        filters={"pipeline_status": ["in", FAILURE_ORDER_STATUSES]},
        fields=["name", "pipeline_status as status", "last_error", "modified", "attempt_count"],
        order_by="modified desc",
        limit_start=offset,
        limit_page_length=limit,
    )
    for r in rows:
        r["doctype"] = ORDER_DOCTYPE
        r["stage"] = "orders"
        r["external_id"] = r.get("name")
        r["last_error"] = (r.get("last_error") or "")[:300]
    return rows


def _failed_credit_notes(limit: int, offset: int) -> list[dict]:
    rows = frappe.get_all(
        CREDIT_NOTE_DOCTYPE,
        filters={"status": ["in", FAILURE_CN_STATUSES]},
        fields=["name", "status", "last_error", "modified", "uc_return_id", "attempt_count"],
        order_by="modified desc",
        limit_start=offset,
        limit_page_length=limit,
    )
    for r in rows:
        r["doctype"] = CREDIT_NOTE_DOCTYPE
        r["stage"] = "credit_notes"
        r["external_id"] = r.pop("uc_return_id", None)
        r["last_error"] = (r.get("last_error") or "")[:300]
    return rows


def _failed_inventory(limit: int, offset: int) -> list[dict]:
    rows = frappe.get_all(
        INVENTORY_DOCTYPE,
        filters={"unicommerce_sync_status": ["in", FAILURE_INVENTORY_STATUSES]},
        fields=["name", "unicommerce_sync_status", "comments", "modified", "docnum"],
        order_by="modified desc",
        limit_start=offset,
        limit_page_length=limit,
    )
    for r in rows:
        r["doctype"] = INVENTORY_DOCTYPE
        r["stage"] = "inventory"
        r["status"] = r.pop("unicommerce_sync_status", "")
        r["external_id"] = r.pop("docnum", None)
        r["last_error"] = (r.pop("comments", None) or "")[:300]
        r["attempt_count"] = None
    return rows


# ---------------------------------------------------------------------------
# Retry router
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_retry(doctype: str, name: str, mode: str = "queue") -> dict:
    """
    Retry a single failed record.

    mode = "queue" → reset status so the next scheduler tick picks it up
    mode = "now"   → execute the worker synchronously for this one record
    """
    if mode not in ("queue", "now"):
        frappe.throw(f"Invalid retry mode: {mode}")

    if doctype == ORDER_DOCTYPE:
        return _retry_order(name, mode)
    if doctype == CREDIT_NOTE_DOCTYPE:
        return _retry_credit_note(name, mode)
    if doctype == INVENTORY_DOCTYPE:
        return _retry_inventory(name, mode)

    frappe.throw(f"Retry not supported for doctype: {doctype}")


def _retry_order(name: str, mode: str) -> dict:
    frappe.db.set_value(ORDER_DOCTYPE, name, {"pipeline_status": "ready", "last_error": ""})
    frappe.db.commit()
    if mode == "queue":
        return {"queued": True, "doctype": ORDER_DOCTYPE, "name": name}

    from ..workers.invoice import _post_order, _claim_ready_order
    from ..client import SAPClient

    # Same atomic ready->posting claim the scheduler uses (_post_ready_orders).
    # Without it, a "Retry now" click racing an in-flight scheduler cycle for
    # the same order could both pass the idempotency check in _post_order
    # before either finishes posting, producing a duplicate SAP AR Invoice.
    if not _claim_ready_order(name):
        return {
            "queued": False,
            "outcome": "already_claimed",
            "doctype": ORDER_DOCTYPE,
            "name": name,
            "message": "Order was claimed by another process (scheduler or a concurrent retry) — not re-posted from here.",
        }

    sap = SAPClient()
    row = frappe._dict(frappe.db.get_value(
        ORDER_DOCTYPE, name, ["name", "attempt_count"], as_dict=True,
    ) or {})
    try:
        outcome, _ = _post_order(sap, row)
        frappe.db.commit()
        return {"queued": False, "outcome": outcome, "doctype": ORDER_DOCTYPE, "name": name}
    except Exception as e:
        frappe.db.rollback()
        frappe.db.set_value(ORDER_DOCTYPE, name, {"pipeline_status": "failed", "last_error": str(e)[:1000]})
        frappe.db.commit()
        return {"queued": False, "outcome": "failed", "error": str(e)[:500]}


def _retry_credit_note(name: str, mode: str) -> dict:
    frappe.db.set_value(CREDIT_NOTE_DOCTYPE, name, {"status": "pending", "last_error": ""})
    frappe.db.commit()
    if mode == "queue":
        return {"queued": True, "doctype": CREDIT_NOTE_DOCTYPE, "name": name}

    from ..workers.credit_note import _post_credit_note
    from ..client import SAPClient
    try:
        _post_credit_note(SAPClient(), name)
        frappe.db.commit()
        return {"queued": False, "outcome": "posted", "doctype": CREDIT_NOTE_DOCTYPE, "name": name}
    except Exception as e:
        frappe.db.rollback()
        frappe.db.set_value(CREDIT_NOTE_DOCTYPE, name, {"status": "failed", "last_error": str(e)[:1000]})
        frappe.db.commit()
        return {"queued": False, "outcome": "failed", "error": str(e)[:500]}


def _retry_inventory(name: str, mode: str) -> dict:
    frappe.db.set_value(INVENTORY_DOCTYPE, name, {"unicommerce_sync_status": "Pending"})
    frappe.db.commit()
    if mode == "queue":
        return {"queued": True, "doctype": INVENTORY_DOCTYPE, "name": name}

    from ..workers.inventory import push_transfer
    try:
        result = push_transfer(name)
        frappe.db.commit()
        return {"queued": False, "outcome": result.get("status", "ok"), "result": result}
    except Exception as e:
        frappe.db.rollback()
        return {"queued": False, "outcome": "failed", "error": str(e)[:500]}


# ---------------------------------------------------------------------------
# Activity / Reconciliation
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_activity(hours: int = 24) -> dict:
    cutoff = add_to_date(now_datetime(), hours=-int(hours or 24))
    errors = frappe.get_all(
        "Error Log",
        filters={"creation": [">", cutoff], "error": ["like", "%unicommerce%"]},
        fields=["name", "method", "creation", "error"],
        order_by="creation desc",
        limit=50,
    )
    for r in errors:
        r["error"] = (r.get("error") or "")[:400]

    jobs = frappe.get_all(
        "Scheduled Job Log",
        filters={
            "creation": [">", cutoff],
            "scheduled_job_type": ["like", "%unicommerce%"],
        },
        fields=["name", "scheduled_job_type", "status", "creation"],
        order_by="creation desc",
        limit=50,
    )
    return {"errors": errors, "jobs": jobs, "since": str(cutoff)}


# ---------------------------------------------------------------------------
# Manual worker triggers
# ---------------------------------------------------------------------------

_WORKER_MAP = {
    "fetch_orders":      ("khanal_tech_integrations.unicommerce.workers.fetch",       "fetch_orders"),
    "promote_fetched_to_ready": ("khanal_tech_integrations.unicommerce.workers.fetch", "promote_fetched_to_ready"),
    "fetch_returns":     ("khanal_tech_integrations.unicommerce.workers.fetch",       "fetch_returns"),
    "retry_batch_holds": ("khanal_tech_integrations.unicommerce.workers.fetch",       "retry_batch_holds"),
    "post_invoices":     ("khanal_tech_integrations.unicommerce.workers.invoice",     "post_invoices"),
    "retry_failed_orders": ("khanal_tech_integrations.unicommerce.workers.invoice",   "_recover_failed_orders"),
    "post_credit_notes": ("khanal_tech_integrations.unicommerce.workers.credit_note", "post_credit_notes"),
    "sync_grns":         ("khanal_tech_integrations.unicommerce.workers.grn",         "sync_grns"),
    "sync_inventory":    ("khanal_tech_integrations.unicommerce.workers.inventory",   "sync_inventory"),
    "refresh_inventory_parity": ("khanal_tech_integrations.unicommerce.api.ops",      "refresh_inventory_parity"),
}


DATE_RANGE_AWARE_WORKERS = {"post_invoices", "post_credit_notes"}

# Workers that run long enough to exceed Gunicorn's HTTP timeout when called
# synchronously — these are enqueued as background jobs instead.
LONG_RUNNING_WORKERS = {"post_invoices", "post_credit_notes"}


@frappe.whitelist()
def ops_run_worker(
    worker: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> dict:
    """Manually trigger a worker function and return its result dict.

    For ``post_invoices`` and ``post_credit_notes`` an optional date range
    (inclusive, YYYY-MM-DD or DD-MM-YYYY) filters the work to UC sale orders
    whose ``order_date`` falls inside the window. For credit notes the window
    is applied to the parent UC sale order, not the return date — so an
    operator can say "post invoices + credit notes for orders placed in March".

    For all other workers the date range is ignored.

    Auth: System Manager only — this endpoint mutates SAP (via invoice /
    credit-note workers) and must not be callable by a lower-privileged user.
    """
    frappe.only_for("System Manager")
    if worker not in _WORKER_MAP:
        frappe.throw(f"Unknown worker: {worker}")
    import importlib
    module_path, fn_name = _WORKER_MAP[worker]
    mod = importlib.import_module(module_path)
    fn = getattr(mod, fn_name)

    kwargs: dict = {}
    if worker in DATE_RANGE_AWARE_WORKERS:
        if start_date:
            kwargs["start_date"] = _parse_ymd_or_ddmmyyyy(start_date)
        if end_date:
            kwargs["end_date"] = _parse_ymd_or_ddmmyyyy(end_date)
        if "start_date" in kwargs and "end_date" in kwargs and kwargs["start_date"] > kwargs["end_date"]:
            frappe.throw("Start date must be on or before End date")
        if limit is not None:
            safe_limit = min(max(int(limit or 0), 1), 2000)
            kwargs["limit"] = safe_limit
    if worker in LONG_RUNNING_WORKERS:
        frappe.enqueue(
            f"{module_path}.{fn_name}",
            queue="long",
            timeout=3600,
            user=frappe.session.user,
            **kwargs,
        )
        frappe.db.commit()
        return {"ok": True, "queued": True, "worker": worker, "result": {}}

    try:
        result = fn(**kwargs)
        frappe.db.commit()
        return {
            "ok": True,
            "worker": worker,
            "result": result or {},
            "date_range": {
                "start_date": kwargs.get("start_date"),
                "end_date": kwargs.get("end_date"),
            } if kwargs else None,
        }
    except Exception as e:
        frappe.db.rollback()
        return {"ok": False, "worker": worker, "error": str(e)[:2000]}


@frappe.whitelist()
def ops_post_all_until_settled(
    start_date: str,
    end_date: str,
    per_pass_limit: int = 100,
    max_passes: int = 12,
    include_credit_notes: int | bool = 1,
    max_runtime_mins: int = 20,
) -> dict:
    """Run Post Invoices (+ optional Post Credit Notes) in repeated passes.

    This endpoint is designed for Ops Center's "Post All" button so one click
    can drain a selected date window instead of stopping after the first
    default-sized worker pass.
    """
    frappe.only_for("System Manager")
    start = _parse_ymd_or_ddmmyyyy(start_date)
    end = _parse_ymd_or_ddmmyyyy(end_date)
    if start > end:
        frappe.throw("Start date must be on or before End date")

    pass_limit = min(max(int(per_pass_limit or 0), 10), 2000)
    pass_cap = min(max(int(max_passes or 0), 1), 60)
    runtime_cap_mins = min(max(int(max_runtime_mins or 0), 1), 180)
    include_cn = str(include_credit_notes).lower() in {"1", "true", "yes", "on"}
    run_started_at = now_datetime()
    snapshot_key = f"uc_post_all_snapshot::{frappe.session.user or 'Administrator'}"

    from ..workers.invoice import post_invoices
    from ..workers.credit_note import post_credit_notes

    before = ops_orders_in_date_range(from_date=start, to_date=end)
    progress: list[dict] = []
    stop_reason = "max_passes_reached"
    stale_passes = 0
    try:
        frappe.cache().set_value(
            snapshot_key,
            json.dumps(
                {
                    "status": "running",
                    "started_at": str(run_started_at),
                    "date_range": {"start_date": start, "end_date": end},
                    "per_pass_limit": pass_limit,
                    "max_passes": pass_cap,
                    "max_runtime_mins": runtime_cap_mins,
                    "progress": [],
                    "stop_reason": None,
                    "final_window": before,
                },
                default=str,
            ),
            expires_in_sec=24 * 60 * 60,
        )
    except Exception:
        pass

    for idx in range(1, pass_cap + 1):
        elapsed_s = float(time_diff_in_seconds(now_datetime(), run_started_at) or 0)
        if elapsed_s >= (runtime_cap_mins * 60):
            stop_reason = "max_runtime_reached"
            break
        inv_res = post_invoices(limit=pass_limit, start_date=start, end_date=end) or {}
        cn_res = {}
        if include_cn:
            cn_res = post_credit_notes(limit=pass_limit, start_date=start, end_date=end) or {}
        frappe.db.commit()

        after = ops_orders_in_date_range(from_date=start, to_date=end)
        before_pipe = before.get("pipeline_status") or {}
        after_pipe = after.get("pipeline_status") or {}

        ready_before = int(before_pipe.get("ready") or 0)
        ready_after = int(after_pipe.get("ready") or 0)
        fetched_after = int(after_pipe.get("fetched") or 0)
        posting_after = int(after_pipe.get("posting") or 0)
        verify_after = int(after_pipe.get("verify") or 0)
        blocked_after = int(after_pipe.get("batch_hold") or 0) + int(after_pipe.get("failed") or 0)

        posted_before = int(before.get("posted_count") or 0)
        posted_after = int(after.get("posted_count") or 0)
        posted_delta = posted_after - posted_before
        ready_delta = ready_before - ready_after

        inv_processed = int(inv_res.get("ready_processed") or 0)
        inv_posted = int(inv_res.get("ready_posted") or 0)
        cn_processed = int(cn_res.get("processed") or 0)
        cn_posted = int(cn_res.get("posted") or 0)
        # Deferred/stuck CNs count as "processed" but make no real progress —
        # only actual posts or queue reduction should reset the stale counter.
        cn_non_progress = (
            int(cn_res.get("skipped_no_parent") or 0)
            + int(cn_res.get("deferred") or 0)
            + int(cn_res.get("skipped_parent_stuck") or 0)
        )
        cn_effective = cn_processed - cn_non_progress
        progressed = (inv_posted + cn_posted) > 0 or (cn_effective > 0) or (posted_delta > 0) or (ready_delta > 0)
        stale_passes = 0 if progressed else (stale_passes + 1)

        pass_row = {
            "pass": idx,
            "elapsed_s": round(float(time_diff_in_seconds(now_datetime(), run_started_at) or 0), 1),
            "invoice": inv_res,
            "credit_note": cn_res if include_cn else {},
            "window_before": {
                "ready": ready_before,
                "posted": posted_before,
            },
            "window_after": {
                "ready": ready_after,
                "posted": posted_after,
                "fetched": fetched_after,
                "posting": posting_after,
                "verify": verify_after,
                "blocked": blocked_after,
            },
            "delta": {
                "ready_reduced": ready_delta,
                "posted_increased": posted_delta,
            },
            "progressed": progressed,
        }
        progress.append(pass_row)
        try:
            frappe.cache().set_value(
                snapshot_key,
                json.dumps(
                    {
                        "status": "running",
                        "started_at": str(run_started_at),
                        "date_range": {"start_date": start, "end_date": end},
                        "per_pass_limit": pass_limit,
                        "max_passes": pass_cap,
                        "max_runtime_mins": runtime_cap_mins,
                        "passes_run": len(progress),
                        "stop_reason": None,
                        "progress": progress[-20:],
                        "final_window": after,
                    },
                    default=str,
                ),
                expires_in_sec=24 * 60 * 60,
            )
        except Exception:
            pass

        # Settled = nothing currently in-flight in the selected date window.
        if ready_after == 0 and fetched_after == 0 and posting_after == 0 and verify_after == 0:
            stop_reason = "window_drained"
            before = after
            break
        # Two consecutive passes with no progress usually means inventory or
        # configuration blockers; stop to avoid burning SAP calls.
        if stale_passes >= 2:
            stop_reason = "no_progress"
            before = after
            break
        before = after

    result = {
        "ok": True,
        "date_range": {"start_date": start, "end_date": end},
        "per_pass_limit": pass_limit,
        "max_passes": pass_cap,
        "max_runtime_mins": runtime_cap_mins,
        "elapsed_s": round(float(time_diff_in_seconds(now_datetime(), run_started_at) or 0), 1),
        "passes_run": len(progress),
        "include_credit_notes": bool(include_cn),
        "stop_reason": stop_reason,
        "final_window": before,
        "progress": progress,
    }
    try:
        frappe.cache().set_value(
            snapshot_key,
            json.dumps(
                {
                    "status": "done",
                    "started_at": str(run_started_at),
                    "date_range": {"start_date": start, "end_date": end},
                    "per_pass_limit": pass_limit,
                    "max_passes": pass_cap,
                    "max_runtime_mins": runtime_cap_mins,
                    "passes_run": len(progress),
                    "stop_reason": stop_reason,
                    "progress": progress[-30:],
                    "final_window": before,
                    "elapsed_s": result["elapsed_s"],
                },
                default=str,
            ),
            expires_in_sec=24 * 60 * 60,
        )
    except Exception:
        pass
    return result


@frappe.whitelist()
def ops_fetch_returns(
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    """
    Fetch returns with an explicit date range.
    Always enqueues to the long-queue background worker to avoid Gunicorn timeout.
    """
    frappe.enqueue(
        "khanal_tech_integrations.unicommerce.api.ops._bg_fetch_returns",
        queue="long",
        timeout=7200,
        job_name="uc_ops_fetch_returns",
        is_async=True,
        from_date=from_date or None,
        to_date=to_date or None,
        notify_user=frappe.session.user,
        enqueue_after_commit=False,
    )
    return {
        "ok": True,
        "enqueued": True,
        "worker": "fetch_returns",
        "message": "Fetch returns running in background — watch progress in the log below.",
    }


def _bg_fetch_returns(
    from_date: str | None = None,
    to_date: str | None = None,
    notify_user: str | None = None,
) -> None:
    """Background worker: run fetch_returns and publish completion event."""
    if notify_user:
        frappe.local.uc_notify_user = notify_user

    from ..workers.fetch import fetch_returns
    try:
        result = fetch_returns(
            from_date=from_date,
            to_date=to_date,
        )
        frappe.db.commit()
        frappe.publish_realtime(
            "uc_ops_progress",
            {
                "worker": "fetch_returns",
                "msg": f"Done — {result.get('new', 0)} new, {result.get('updated', 0)} updated, "
                       f"{result.get('skipped_posted', 0)} skipped, {result.get('detail_failed', 0)} failed.",
                "level": "success",
                "done": True,
                "result": result,
            },
            user=notify_user,
        )
    except Exception as e:
        frappe.db.rollback()
        frappe.publish_realtime(
            "uc_ops_progress",
            {"worker": "fetch_returns", "msg": f"Fetch returns failed: {str(e)[:300]}", "level": "error", "done": True},
            user=notify_user,
        )


@frappe.whitelist()
def ops_debug_uc_returns(from_date: str | None = None, to_date: str | None = None) -> dict:
    """
    Debug endpoint: calls UC return/search with several body variants and returns
    the raw status + response for each so we can see which format UC accepts.
    """
    import requests as _req
    from frappe.utils import add_days, today
    from ..client.unicommerce import UCClient
    # Default to last 14 days when not provided
    if not from_date:
        from_date = add_days(today(), -14)
    if not to_date:
        to_date = today()
    uc = UCClient()
    uc._ensure_token()
    headers = {"Authorization": f"Bearer {uc.token}", "Content-Type": "application/json"}
    base = uc.base_url + "/services/rest/v1/oms/return/search"

    from_uc = uc._to_uc_date(from_date + " 00:00:00")
    to_uc   = uc._to_uc_date(to_date + " 23:59:59")
    # Plain date fallbacks for testing
    from_plain = from_date
    to_plain   = to_date
    facility_codes = uc._resolve_facility_codes()

    fac = facility_codes[0] if facility_codes else ""

    variants = [
        {"label": "CIR createdFrom ISO + Facility",     "h": {"Facility": fac}, "body": {"returnType": "CIR", "createdFrom": from_uc, "createdTo": to_uc}},
        {"label": "RTO createdFrom ISO + Facility",     "h": {"Facility": fac}, "body": {"returnType": "RTO", "createdFrom": from_uc, "createdTo": to_uc}},
        {"label": "CIR plain date + Facility",          "h": {"Facility": fac}, "body": {"returnType": "CIR", "createdFrom": from_plain, "createdTo": to_plain}},
        {"label": "CIR updatedFrom ISO + Facility",     "h": {"Facility": fac}, "body": {"returnType": "CIR", "updatedFrom": from_uc, "updatedTo": to_uc}},
        {"label": "CIR createdFrom ISO no-returnType",  "h": {"Facility": fac}, "body": {"createdFrom": from_uc, "createdTo": to_uc}},
    ]

    results = []
    sample_detail = {}
    for v in variants:
        h = {**headers, **v.get("h", {})}
        r = _req.post(base, headers=h, json=v["body"], timeout=30)
        parsed = {}
        try:
            parsed = r.json() if r.ok else {}
        except Exception:
            parsed = {}

        if not sample_detail and parsed:
            return_orders = parsed.get("returnOrders") or []
            sample_code = None
            if return_orders:
                sample_code = str((return_orders[0] or {}).get("code") or "").strip()
            if sample_code:
                try:
                    detail = uc.get_return_detail(sample_code, facility=fac or None) or {}
                    rsov = detail.get("returnSaleOrderValue") or {}
                    item0 = ((detail.get("returnSaleOrderItems") or [{}])[0] or {})
                    sample_detail = {
                        "code": sample_code,
                        "top_keys": sorted(list(detail.keys())),
                        "returnSaleOrderValue_keys": sorted(list(rsov.keys())),
                        "returnSaleOrderItems_first_keys": sorted(list(item0.keys())),
                        "returnSaleOrderValue_preview": {k: rsov.get(k) for k in (
                            "reversePickupCode",
                            "saleOrderCode",
                            "shipmentCode",
                            "code",
                            "returnCode",
                        )},
                    }
                except Exception as e:
                    sample_detail = {"code": sample_code, "error": str(e)[:300]}
        results.append({
            "label": v["label"],
            "status": r.status_code,
            "headers_sent": v.get("h", {}),
            "body_sent": v["body"],
            "response": r.text[:600],
        })

    return {
        "ok": True,
        "from_uc": from_uc,
        "to_uc": to_uc,
        "facility": facility_codes,
        "variants": results,
        "sample_detail": sample_detail,
    }


@frappe.whitelist()
def ops_analyze_return_id_extraction(
    from_date: str = "2026-04-01",
    to_date: str = "2026-04-15",
    limit: int = 200,
) -> dict:
    from ..workers.fetch import _extract_return_ids
    from ..client.unicommerce import UCClient
    from ..returns import load_parent_order

    uc = UCClient()
    uc.login()
    returns = uc.get_returns_between(from_date=from_date, to_date=to_date, use_updated=False)[: int(limit or 200)]

    ok = 0
    missing = 0
    parent_found = 0
    sample_missing = []
    sample_ok = []
    for row in returns:
        rid, oid = _extract_return_ids(row)
        if rid and oid:
            ok += 1
            if load_parent_order(oid):
                parent_found += 1
            if len(sample_ok) < 5:
                sample_ok.append({"rid": rid, "oid": oid})
            continue
        missing += 1
        if len(sample_missing) < 5:
            rsov = row.get("returnSaleOrderValue") or {}
            item0 = ((row.get("returnSaleOrderItems") or [{}])[0] or {})
            sample_missing.append(
                {
                    "top_keys": sorted(list(row.keys())),
                    "rsov_keys": sorted(list(rsov.keys())),
                    "item0_keys": sorted(list(item0.keys())),
                    "rsov_preview": {
                        "reversePickupCode": rsov.get("reversePickupCode"),
                        "saleOrderCode": rsov.get("saleOrderCode"),
                        "shipmentCode": rsov.get("shipmentCode"),
                    },
                    "item0_preview": {
                        "saleOrderCode": item0.get("saleOrderCode"),
                        "saleOrderItemCode": item0.get("saleOrderItemCode"),
                        "shipmentCode": item0.get("shipmentCode"),
                        "reversePickupCode": item0.get("reversePickupCode"),
                    },
                }
            )

    return {
        "fetched": len(returns),
        "extracted_ok": ok,
        "missing_ids": missing,
        "parent_found": parent_found,
        "sample_ok": sample_ok,
        "sample_missing": sample_missing,
    }


@frappe.whitelist()
def ops_returns_summary(limit: int = 100) -> dict:
    """Cross-check table: recent credit note staging rows with parent order status."""
    rows = frappe.db.sql(
        """
        SELECT
            cn.name,
            cn.uc_return_id,
            cn.uc_order_id,
            cn.return_date,
            cn.return_type,
            cn.status,
            cn.parent_sap_doc_entry,
            cn.attempt_count,
            cn.last_error,
            o.pipeline_status AS parent_status,
            o.channel_name AS channel,
            o.sap_ar_invoice_docentry AS parent_sap_posted
        FROM `tabUC Credit Note Staging` cn
        LEFT JOIN `tabUnicommerce Orders` o ON o.name = cn.uc_order_id
        ORDER BY cn.return_date DESC, cn.modified DESC
        LIMIT %(limit)s
        """,
        {"limit": int(limit or 100)},
        as_dict=True,
    )
    for r in rows:
        r["last_error"] = (r.get("last_error") or "")[:200]

    by_status = {}
    for r in rows:
        s = r.get("status") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1

    pending_parent_not_posted = sum(
        1 for r in rows
        if r.get("status") == "pending" and r.get("parent_status") != "posted"
    )
    pending_items_unresolved = sum(
        1 for r in rows
        if r.get("status") == "pending"
        and r.get("parent_status") == "posted"
        and not r.get("parent_sap_doc_entry")
    )

    return {
        "rows": rows,
        "by_status": by_status,
        "total": len(rows),
        "pending_parent_not_posted": pending_parent_not_posted,
        "pending_items_unresolved": pending_items_unresolved,
    }


@frappe.whitelist()
def ops_fetch_orders(
    from_date: str | None = None,
    to_date: str | None = None,
    max_orders: int | None = None,
) -> dict:
    """
    Fetch orders with an explicit date range.

    Always enqueues to the long-queue background worker so Gunicorn timeout
    (120 s) is never hit. Progress events are emitted via frappe.publish_realtime
    ('uc_ops_progress') and streamed to the Ops Center log panel in real time.
    """
    frappe.enqueue(
        "khanal_tech_integrations.unicommerce.api.ops._bg_fetch_orders",
        queue="long",
        timeout=7200,
        job_name="uc_ops_fetch_orders",
        is_async=True,
        from_date=from_date or None,
        to_date=to_date or None,
        max_orders=int(max_orders) if max_orders else None,
        notify_user=frappe.session.user,
        enqueue_after_commit=False,
    )
    return {
        "ok": True,
        "enqueued": True,
        "worker": "fetch_orders",
        "message": "Fetch orders running in background — watch progress in the log below.",
    }


def _bg_fetch_orders(
    from_date: str | None = None,
    to_date: str | None = None,
    max_orders: int | None = None,
    notify_user: str | None = None,
) -> None:
    """Background worker: run fetch_orders and publish completion event."""
    # Store triggering user in thread-local so _emit() in fetch_orders can
    # route realtime events to the correct browser session instead of Administrator.
    if notify_user:
        frappe.local.uc_notify_user = notify_user

    from ..workers.fetch import fetch_orders
    try:
        result = fetch_orders(
            from_date=from_date,
            to_date=to_date,
            max_orders=max_orders,
        )
        frappe.db.commit()
        frappe.publish_realtime(
            "uc_ops_progress",
            {
                "worker": "fetch_orders",
                "msg": f"Done — {result.get('new', 0)} new, {result.get('updated', 0)} updated, "
                       f"{result.get('skipped_posted', 0)} skipped, {result.get('detail_failed', 0)} failed.",
                "level": "success",
                "done": True,
                "result": result,
            },
            user=notify_user,
        )
    except Exception as e:
        frappe.db.rollback()
        frappe.publish_realtime(
            "uc_ops_progress",
            {"worker": "fetch_orders", "msg": f"Fetch failed: {str(e)[:300]}", "level": "error", "done": True},
            user=notify_user,
        )


@frappe.whitelist()
def ops_force_post_order_with_inventory_substitute(
    record_name: str,
    commit_result: int = 0,
    fallback_item_code: str = "PMHN0155",
) -> dict:
    """
    Force-test post helper (System Manager only):
    - Builds normal AR payload from staged order.
    - Replaces product ItemCode/BatchNumbers using available SAP snapshot inventory.
    - Posts to SAP to validate end-to-end posting path in constrained test scenarios.

    WARNING: This is a test utility and should be used only with explicit operator intent.
    """
    frappe.only_for("System Manager")
    order_doc = frappe.get_doc(ORDER_DOCTYPE, record_name)
    payload = ar_invoice_payload(order_doc)

    # Product lines only; keep freight/service lines untouched.
    product_lines = [
        line for line in (payload.get("DocumentLines") or [])
        if str(line.get("ItemCode") or "").strip() != "EXCM0027"
    ]
    if not product_lines:
        frappe.throw("No product lines available for substitution")

    wh_codes = sorted({str(line.get("WarehouseCode") or "").strip() for line in product_lines if line.get("WarehouseCode")})
    if not wh_codes:
        frappe.throw("WarehouseCode missing in payload lines")

    # Fetch batch inventory from SAP HANA for all relevant warehouses.
    sap = SAPClient()
    by_wh: dict[str, list[dict]] = defaultdict(list)
    all_inventory_rows = []
    for wh_code in wh_codes:
        try:
            hana_rows = sap._hana_warehouse_all_batches(wh_code)
            for r in hana_rows:
                row = {
                    "itemcode": r["item_code"],
                    "distnumber": r["batch_number"],
                    "quantity": float(r.get("quantity") or 0),
                    "whscode": wh_code,
                }
                by_wh[wh_code].append(row)
                all_inventory_rows.append(row)
            by_wh[wh_code].sort(key=lambda r: float(r.get("quantity") or 0), reverse=True)
        except Exception as exc:
            frappe.logger().warning("ops_create_gr: HANA inventory fetch wh=%s: %s", wh_code, exc)

    replacements = []
    for idx, line in enumerate(payload.get("DocumentLines") or []):
        item_code = str(line.get("ItemCode") or "").strip()
        if item_code == "EXCM0027":
            continue
        wh_code = str(line.get("WarehouseCode") or "").strip()
        qty_needed = float(line.get("Quantity") or 0)
        candidates = by_wh.get(wh_code) or []
        chosen = None
        for row in candidates:
            if float(row.get("quantity") or 0) >= qty_needed and qty_needed > 0:
                chosen = row
                break
        if not chosen and candidates:
            chosen = candidates[0]
        if not chosen:
            # Explicit fallback for force-test: allow substitution from any warehouse.
            global_candidates = sorted(
                [r for r in all_inventory_rows if float(r.get("quantity") or 0) > 0],
                key=lambda r: float(r.get("quantity") or 0),
                reverse=True,
            )
            for row in global_candidates:
                if float(row.get("quantity") or 0) >= qty_needed and qty_needed > 0:
                    chosen = row
                    break
            if not chosen and global_candidates:
                chosen = global_candidates[0]
        new_item = ""
        new_batch = ""
        target_wh = wh_code
        use_batch_numbers = True
        if chosen:
            new_item = str(chosen.get("itemcode") or "").strip()
            new_batch = str(chosen.get("distnumber") or "").strip()
            target_wh = str(chosen.get("whscode") or wh_code).strip()
            if not new_item or not new_batch:
                chosen = None

        if not chosen:
            # Last-resort forced-test fallback when no inventory snapshots exist:
            # use freight/service item and skip batch numbers.
            new_item = str(fallback_item_code or "PMHN0155").strip()
            new_batch = ""
            target_wh = wh_code
            use_batch_numbers = False

        old_item = item_code
        old_batches = line.get("BatchNumbers") or []
        old_batch = str((old_batches[0] or {}).get("BatchNumber") or "") if old_batches else ""
        old_wh = wh_code

        line["ItemCode"] = new_item
        line["BatchNumbers"] = [{"BatchNumber": new_batch, "Quantity": qty_needed}] if use_batch_numbers else []
        line["WarehouseCode"] = target_wh
        line["U_UCOrderItemID"] = f"FORCED_TEST_{idx + 1}"

        replacements.append(
            {
                "line_no": idx + 1,
                "warehouse_code": wh_code,
                "qty": qty_needed,
                "old_item_code": old_item,
                "old_batch": old_batch,
                "old_warehouse_code": old_wh,
                "new_item_code": new_item,
                "new_batch": new_batch,
                "new_warehouse_code": line["WarehouseCode"],
                "used_batch_numbers": use_batch_numbers,
            }
        )

    payload["Comments"] = (
        f"{payload.get('Comments') or ''} | FORCED_TEST_POST substitution from ops"
    )[:250]
    payload["U_UCOrderID"] = f"{record_name}-FORCED-TEST"

    # Idempotency guard — a double-click or repeated test run would otherwise
    # post a second real AR Invoice to SAP under the same forced-test order id.
    existing = sap.find_invoice_by_uc_order_id(payload["U_UCOrderID"])
    if existing:
        return {
            "record_name": record_name,
            "forced_test": True,
            "commit_result": False,
            "sap_result": {
                "DocEntry": existing.get("DocEntry"),
                "DocNum": existing.get("DocNum"),
            },
            "replacements": replacements,
            "message": "A forced-test invoice for this order already exists in SAP — not posting again.",
        }

    def _pick_active_invoice_series() -> int | None:
        filters = [
            "ObjectCode eq 13 and Locked eq 'tNO'",
            "ObjectCode eq '13' and Locked eq 'tNO'",
            "ObjectCode eq 13",
            "ObjectCode eq '13'",
        ]
        for expr in filters:
            try:
                series_resp = sap.get(
                    "Series",
                    params={
                        "$filter": expr,
                        "$select": "Series,ObjectCode,Locked,DefaultSeries,NextNumber",
                        "$top": 50,
                    },
                )
                rows = series_resp.get("value") or []
                if not rows:
                    continue
                rows.sort(
                    key=lambda row: (
                        0 if str(row.get("DefaultSeries") or "").strip().upper() in ("TYES", "Y", "TRUE", "1") else 1,
                        -(int(row.get("NextNumber") or 0)),
                    ),
                )
                return int(rows[0].get("Series"))
            except Exception:
                continue
        return None

    try:
        result = sap.post("Invoices", payload)
    except Exception as e:
        msg = str(e or "")
        if "numbering series" in msg.lower():
            fallback_series = _pick_active_invoice_series()
            if fallback_series:
                payload["Series"] = int(fallback_series)
                result = sap.post("Invoices", payload)
            else:
                payload_without_series = dict(payload)
                payload_without_series.pop("Series", None)
                result = sap.post("Invoices", payload_without_series)
                payload = payload_without_series
        else:
            raise

    if int(commit_result or 0):
        frappe.db.set_value(
            ORDER_DOCTYPE,
            record_name,
            {
                "pipeline_status": "posted",
                "sap_ar_invoice_docentry": str(result.get("DocEntry") or ""),
                "sap_ar_invoice_docnum": str(result.get("DocNum") or ""),
                "payload_json": json.dumps(payload, separators=(",", ":"), default=str),
                "last_error": "",
            },
        )
        frappe.db.commit()

    return {
        "record_name": record_name,
        "forced_test": True,
        "commit_result": bool(int(commit_result or 0)),
        "sap_result": {
            "DocEntry": result.get("DocEntry"),
            "DocNum": result.get("DocNum"),
        },
        "replacements": replacements,
    }


@frappe.whitelist()
def ops_validate_order(record_name: str | None = None, uc_order_id: str | None = None) -> dict:
    if not record_name and not uc_order_id:
        frappe.throw("Pass record_name or uc_order_id")

    target_name = record_name or frappe.db.exists(ORDER_DOCTYPE, uc_order_id)
    if not target_name:
        frappe.throw("Unicommerce Orders row not found")

    order_doc = frappe.get_doc(ORDER_DOCTYPE, target_name)
    batch_check = _check_batches(SAPClient(), order_doc)
    try:
        uc_order = json.loads(order_doc.order_json or "{}")
    except Exception:
        uc_order = {}
    is_ready, readiness_reason = _order_ready_for_invoice(uc_order)
    payload_preview = {}
    payload_error = ""
    try:
        payload_preview = ar_invoice_payload(order_doc)
    except Exception as e:
        payload_error = str(e)[:1000]

    return {
        "record_name": order_doc.name,
        "uc_order_id": order_doc.name,
        "status": order_doc.pipeline_status,
        "channel": order_doc.channel_name,
        "ready_for_invoice": is_ready,
        "readiness_reason": readiness_reason,
        "batch_check": batch_check,
        "payload_ok": not bool(payload_error),
        "payload_error": payload_error,
        "line_count": len((payload_preview or {}).get("DocumentLines") or []),
    }


@frappe.whitelist()
def ops_validate_credit_note(uc_return_id: str) -> dict:
    cn_name = frappe.db.get_value(CREDIT_NOTE_DOCTYPE, {"uc_return_id": uc_return_id}, "name")
    if not cn_name:
        frappe.throw("UC Credit Note Staging row not found")

    cn_doc = frappe.get_doc(CREDIT_NOTE_DOCTYPE, cn_name)
    parent = load_parent_order(cn_doc.uc_order_id)
    try:
        items = json.loads(cn_doc.items_json or "[]")
    except Exception:
        items = []
    if not isinstance(items, list):
        items = []
    prepared = prepare_credit_note_items(parent, items) if parent else {"items": items, "unresolved_count": len(items)}

    return {
        "record_name": cn_doc.name,
        "uc_return_id": cn_doc.uc_return_id,
        "parent_record": getattr(parent, "name", ""),
        "parent_uc_order_id": getattr(parent, "name", ""),
        "parent_status": getattr(parent, "pipeline_status", ""),
        "parent_sap_doc_entry": getattr(parent, "sap_ar_invoice_docentry", ""),
        "unresolved_items": prepared.get("unresolved_count", 0),
        "item_count": len(prepared.get("items") or []),
    }


# ---------------------------------------------------------------------------
# Batch validation summary
@frappe.whitelist()
def ops_get_fefo_fallback_status() -> dict:
    """Return current EC-FG FEFO fallback toggle state."""
    frappe.only_for("System Manager")
    settings = frappe.get_cached_doc("Unicommerce Settings")
    return {"enabled": bool(getattr(settings, "ec_fg_fefo_fallback", False))}


@frappe.whitelist()
def ops_set_fefo_fallback(enabled: int) -> dict:
    """Enable or disable EC-FG FEFO fallback. Persists to Unicommerce Settings."""
    frappe.only_for("System Manager")
    frappe.db.set_value("Unicommerce Settings", "Unicommerce Settings", "ec_fg_fefo_fallback", int(enabled))
    frappe.db.commit()
    frappe.clear_cache(doctype="Unicommerce Settings")
    state = "enabled" if int(enabled) else "disabled"
    frappe.logger().info("EC-FG FEFO fallback %s by %s", state, frappe.session.user)
    return {"enabled": bool(int(enabled)), "message": f"EC-FG FEFO fallback {state}."}


# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_batch_validation_summary() -> dict:
    """
    Return batch_hold order list enriched with hold-age and a shortage digest
    grouped by (item_code, batch_number, warehouse) across all held orders.

    Access-restricted to System Manager: exposes UC order names, shortage
    volumes, and last_error diagnostics that are operational-sensitive.
    """
    frappe.only_for("System Manager")
    now = now_datetime()
    batch_hold = frappe.get_all(
        ORDER_DOCTYPE,
        filters={"pipeline_status": "batch_hold"},
        fields=[
            "name",
            "channel_name as channel",
            "order_date",
            "last_error",
            "attempt_count",
            "modified",
            "batch_hold_since",
        ],
        order_by="modified asc",
        limit=200,
    )
    # Enrich each row with human-readable hold age
    for r in batch_hold:
        r["uc_order_id"] = r["name"]
        try:
            delta_secs = time_diff_in_seconds(now, r.get("modified") or now)
            mins = int(delta_secs // 60)
            if mins < 60:
                r["hold_age"] = f"{mins}m"
            elif mins < 1440:
                r["hold_age"] = f"{mins // 60}h {mins % 60}m"
            else:
                r["hold_age"] = f"{mins // 1440}d {(mins % 1440) // 60}h"
        except Exception:
            r["hold_age"] = "—"

    # Build shortage digest: group by (warehouse, item, batch) across all held orders
    shortage_by_key: dict[str, dict] = {}
    for r in batch_hold:
        err = str(r.get("last_error") or "")
        order_id = r.get("name") or ""
        # Parse pipe-separated shortage tokens emitted by _batch_shortage_message
        # Format: "ITEM::BATCH [WH]: need X have Y short Z (reason)"
        # Uses :: separator to safely handle item codes or batch numbers containing /
        for token in err.split(" | "):
            m = re.match(
                r"^(.+?)::(.+?) \[(.+?)\]: need ([\d.]+) have ([\d.]+) short ([\d.]+)",
                token.strip(),
            )
            if not m:
                continue
            item_code, batch_num, wh = m.group(1), m.group(2), m.group(3)
            try:
                need_qty = float(m.group(4))
            except Exception:
                need_qty = 0.0
            try:
                have_qty = float(m.group(5))
            except Exception:
                have_qty = 0.0
            try:
                shortage_qty = float(m.group(6))
            except Exception:
                shortage_qty = 0.0
            key = f"{wh}|{item_code}|{batch_num}"
            if key not in shortage_by_key:
                shortage_by_key[key] = {
                    "warehouse_code": wh,
                    "item_code": item_code,
                    "batch_number": batch_num,
                    "order_count": 0,
                    "total_needed": 0.0,
                    "available": have_qty,   # most-recent snapshot from last_error
                    "total_shortage": 0.0,
                    "orders": [],
                }
            entry = shortage_by_key[key]
            entry["order_count"] += 1
            entry["total_needed"] = round(entry["total_needed"] + need_qty, 3)
            entry["total_shortage"] = round(entry["total_shortage"] + shortage_qty, 3)
            # Keep the "available" value as the *latest* have we saw (all
            # held orders in the same warehouse should report the same
            # number, but last_error strings can lag — latest is safer).
            entry["available"] = have_qty
            if order_id and order_id not in entry["orders"]:
                entry["orders"].append(order_id)
    shortage_digest = sorted(
        shortage_by_key.values(),
        key=lambda x: (-x["total_shortage"], x["item_code"]),
    )

    # Annotate each EC-FG shortage with FEFO rescue availability:
    # if EC-FG total stock (any batch) covers total_needed the order can
    # auto-recover on the next posting cycle via FEFO allocation.
    if shortage_digest:
        try:
            from ..validators.batches import (
                _get_total_ec_fg_qty_in_hana,
                create_database_connection,
                close_database_connection,
            )
            from ..mappers.sap_payload import DEFAULT_WAREHOUSE
            connector, connection, cursor = create_database_connection()
            try:
                for entry in shortage_digest:
                    if entry.get("warehouse_code") == DEFAULT_WAREHOUSE:
                        result = _get_total_ec_fg_qty_in_hana(cursor, entry["item_code"])
                        ec_fg_total = round(float(result.get("available_qty") or 0), 3)
                        entry["ec_fg_total_qty"] = ec_fg_total
                        entry["fefo_rescuable"] = ec_fg_total >= float(entry.get("total_needed") or 0)
                    else:
                        entry["ec_fg_total_qty"] = 0
                        entry["fefo_rescuable"] = False
            finally:
                close_database_connection(connector, connection, cursor)
        except Exception as _exc:
            frappe.logger().warning("ops_batch_validation_summary: FEFO check failed: %s", _exc)

    ready_count = frappe.db.count(ORDER_DOCTYPE, {"pipeline_status": "ready"})
    fetched_count = frappe.db.count(ORDER_DOCTYPE, {"pipeline_status": "fetched"})
    return {
        "batch_hold_count": len(batch_hold),
        "batch_hold_orders": batch_hold,
        "shortage_digest": shortage_digest,
        "ready_count": int(ready_count or 0),
        "fetched_count": int(fetched_count or 0),
    }


# ---------------------------------------------------------------------------
# Order Coverage
#
# Single aggregate payload that answers the question "what is in the
# Unicommerce Orders table and where is each row in our pipeline?". Exposes:
#
#   * total_orders              - raw COUNT(*) on `tabUnicommerce Orders`
#   * posted_count              - rows with a SAP AR Invoice DocEntry set
#                                 (i.e. actually landed in SAP, not just
#                                 marked `pipeline_status = posted`)
#   * not_posted_count          - total_orders - posted_count
#   * never_attempted           - `pipeline_status = 'fetched'` AND no attempt
#                                 has ever been made to post (attempt_count = 0)
#   * uniware_status            - breakdown by the raw Uniware `status` field
#                                 (COMPLETE / CREATED / CANCELLED / ...)
#   * pipeline_status           - breakdown by our internal `pipeline_status`
#                                 (fetched / ready / posted / failed / ...)
#   * channels[]                - per-channel matrix with:
#                                   - total
#                                   - complete (Uniware status = COMPLETE)
#                                   - posted (SAP invoice posted)
#                                   - pending / failed / dead / batch_hold
#                                   - fetched / ready
#
# Kept separate from `ops_overview` because it's a heavier aggregate (one
# GROUP BY + one channel × pipeline pivot) and callers should pull it only
# when the operator opens the "Order Coverage" panel.
# ---------------------------------------------------------------------------


@frappe.whitelist()
def ops_order_coverage_summary() -> dict:
    """Aggregate order counts by Uniware status, pipeline status, and channel.

    Answers the common operator questions on a single payload:
    how many orders do we have, how many are ``COMPLETE`` in Uniware, how
    many actually landed in SAP, how many are still unprocessed, and what
    is the per-channel breakdown?
    """
    total_orders = int(
        (frappe.db.sql("SELECT COUNT(*) FROM `tabUnicommerce Orders`") or [(0,)])[0][0] or 0
    )

    # Uniware-side lifecycle (raw `status` field; free-form string).
    uniware_rows = frappe.db.sql(
        """
        SELECT COALESCE(NULLIF(TRIM(status), ''), '(blank)') AS s, COUNT(*) AS c
        FROM `tabUnicommerce Orders`
        GROUP BY s
        ORDER BY c DESC
        """,
        as_dict=True,
    )
    uniware_status = {str(r["s"]): int(r["c"] or 0) for r in uniware_rows}
    complete_count = sum(
        v for k, v in uniware_status.items() if str(k).strip().upper().startswith("COMPL")
    )
    cancelled_count = sum(
        v for k, v in uniware_status.items() if str(k).strip().upper().startswith("CANC")
    )

    # Our internal pipeline state. ORDER_STATUSES is the canonical set; any
    # DB value outside of it is bucketed into "other" so we never silently
    # drop rows (the old _stage_counts did this when `fetched` was absent
    # from the list — the hero tile read 0 even with thousands of rows).
    pipeline_rows = frappe.db.sql(
        """
        SELECT COALESCE(NULLIF(TRIM(pipeline_status), ''), '(blank)') AS s, COUNT(*) AS c
        FROM `tabUnicommerce Orders`
        GROUP BY s
        """,
        as_dict=True,
    )
    pipeline_status = {s: 0 for s in ORDER_STATUSES}
    pipeline_other = 0
    for r in pipeline_rows:
        s = str(r["s"])
        c = int(r["c"] or 0)
        if s in pipeline_status:
            pipeline_status[s] = c
        else:
            pipeline_other += c
    if pipeline_other:
        pipeline_status["other"] = pipeline_other

    # "Actually posted" = SAP AR Invoice reference is set. This is stricter
    # than `pipeline_status = 'posted'` (which is the desired end state but
    # can briefly drift from SAP during async retries).
    posted_count = int(
        (
            frappe.db.sql(
                """
                SELECT COUNT(*) FROM `tabUnicommerce Orders`
                WHERE IFNULL(sap_ar_invoice_docentry, '') <> ''
                """
            )
            or [(0,)]
        )[0][0]
        or 0
    )
    not_posted_count = max(0, total_orders - posted_count)

    # Never-attempted: freshly fetched rows with attempt_count = 0 (posting
    # worker has never picked them up). Helpful to spot stuck backlog.
    never_attempted = int(
        (
            frappe.db.sql(
                """
                SELECT COUNT(*) FROM `tabUnicommerce Orders`
                WHERE pipeline_status IN ('fetched', 'pending')
                  AND IFNULL(attempt_count, 0) = 0
                """
            )
            or [(0,)]
        )[0][0]
        or 0
    )

    # Channel × pipeline_status pivot in one SQL round-trip. We COUNT(*)
    # once and split with conditional SUMs so the query plan remains a
    # single pass over the table. Adds a `complete` column by correlating
    # Uniware status with a LIKE filter ("COMPL%" catches "COMPLETE",
    # "COMPLETED", etc., matching the variants already observed in prod).
    channel_rows = frappe.db.sql(
        """
        SELECT
            COALESCE(NULLIF(TRIM(channel_name), ''), 'Unknown') AS channel,
            COUNT(*) AS total,
            SUM(CASE WHEN UPPER(TRIM(IFNULL(status, ''))) LIKE 'COMPL%'
                     THEN 1 ELSE 0 END) AS complete,
            SUM(CASE WHEN IFNULL(sap_ar_invoice_docentry, '') <> ''
                     THEN 1 ELSE 0 END) AS posted,
            SUM(CASE WHEN pipeline_status = 'fetched'    THEN 1 ELSE 0 END) AS fetched,
            SUM(CASE WHEN pipeline_status = 'ready'      THEN 1 ELSE 0 END) AS ready,
            SUM(CASE WHEN pipeline_status = 'pending'    THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN pipeline_status = 'posting'    THEN 1 ELSE 0 END) AS posting,
            SUM(CASE WHEN pipeline_status = 'verify'     THEN 1 ELSE 0 END) AS verify_count,
            SUM(CASE WHEN pipeline_status = 'batch_hold' THEN 1 ELSE 0 END) AS batch_hold,
            SUM(CASE WHEN pipeline_status = 'failed'     THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN pipeline_status = 'dead'       THEN 1 ELSE 0 END) AS dead
        FROM `tabUnicommerce Orders`
        GROUP BY channel
        ORDER BY total DESC, channel ASC
        """,
        as_dict=True,
    )
    channels: list[dict] = []
    for row in channel_rows:
        total = int(row.get("total") or 0)
        posted = int(row.get("posted") or 0)
        complete = int(row.get("complete") or 0)
        channels.append(
            {
                "channel": row.get("channel") or "Unknown",
                "total": total,
                "complete": complete,
                "complete_pct": round((complete * 100.0 / total), 1) if total else 0.0,
                "posted": posted,
                "posted_pct": round((posted * 100.0 / total), 1) if total else 0.0,
                "not_posted": max(0, total - posted),
                "fetched": int(row.get("fetched") or 0),
                "ready": int(row.get("ready") or 0),
                "pending": int(row.get("pending") or 0),
                "posting": int(row.get("posting") or 0),
                "verify": int(row.get("verify_count") or 0),
                "batch_hold": int(row.get("batch_hold") or 0),
                "failed": int(row.get("failed") or 0),
                "dead": int(row.get("dead") or 0),
            }
        )

    return {
        "total_orders": total_orders,
        "complete_count": int(complete_count or 0),
        "cancelled_count": int(cancelled_count or 0),
        "posted_count": posted_count,
        "not_posted_count": not_posted_count,
        "never_attempted": never_attempted,
        "uniware_status": uniware_status,
        "pipeline_status": pipeline_status,
        "channels": channels,
        "generated_at": str(now_datetime()),
    }


# ---------------------------------------------------------------------------
# Date-range order preview
#
# Shown in the "Pick date range" dialog before the operator clicks
# Post Invoices / Post Credit Notes / Post All, so they can see at a glance:
#   * total orders in the selected window
#   * pipeline_status breakdown (ready / fetched / batch_hold / failed / …)
#   * how many would actually move on the next post cycle ("actionable now")
#   * how many are already posted / dead / still in-flight
#
# Answers the recurring "what about the remaining ones?" question by making
# the post-invoice scope explicit BEFORE the job runs, not after.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_orders_in_date_range(from_date: str | None = None, to_date: str | None = None) -> dict:
    """Breakdown of Unicommerce Orders with ``order_date`` in [from_date, to_date].

    Returns a payload the Ops Center posting dialog renders inline so the
    operator sees exactly what will (and won't) move on the next post cycle.

    Both bounds are inclusive (YYYY-MM-DD). Either bound may be omitted —
    the missing side is treated as unbounded. If both are omitted the
    endpoint returns an empty preview (to avoid accidentally scanning the
    whole Orders table from a dialog callback).
    """
    frappe.only_for("System Manager")

    from_date = (from_date or "").strip() or None
    to_date = (to_date or "").strip() or None
    if not from_date and not to_date:
        return {
            "total": 0,
            "from_date": None,
            "to_date": None,
            "pipeline_status": {s: 0 for s in ORDER_STATUSES},
            "uniware_status": {},
            "posted_count": 0,
            "not_posted_count": 0,
            "actionable_now": 0,
            "in_cooldown": 0,
            "generated_at": str(now_datetime()),
            "empty": True,
            "message": "Pick both From Date and To Date to see the breakdown.",
        }

    where_clauses: list[str] = []
    params: dict = {}
    if from_date and to_date:
        where_clauses.append("order_date BETWEEN %(from_date)s AND %(to_date)s")
        params["from_date"] = from_date
        params["to_date"] = to_date
    elif from_date:
        where_clauses.append("order_date >= %(from_date)s")
        params["from_date"] = from_date
    else:
        where_clauses.append("order_date <= %(to_date)s")
        params["to_date"] = to_date
    where_sql = " AND ".join(where_clauses)

    # Single pass: pipeline_status + uniware status + posted flag + cooldown
    # eligibility, all in one SQL round-trip. COALESCE on the Uniware
    # ``status`` column because historical rows may have it NULL. The
    # cooldown constants live in workers.invoice (same module that applies
    # them at retry time) — imported locally so this module's top-level
    # import graph stays clean.
    from ..workers.invoice import (
        BATCH_HOLD_RETRY_DELAY_MINS,
        FAILED_RETRY_BASE_DELAY_MINS,
    )

    rows = frappe.db.sql(
        f"""
        SELECT
            pipeline_status,
            COALESCE(NULLIF(status, ''), 'UNKNOWN') AS uniware_status,
            COUNT(*) AS n,
            SUM(CASE WHEN IFNULL(sap_ar_invoice_docentry, '') != '' THEN 1 ELSE 0 END) AS posted_rows,
            SUM(
                CASE
                    WHEN pipeline_status = 'ready' THEN 1
                    WHEN pipeline_status = 'batch_hold'
                         AND TIMESTAMPDIFF(MINUTE, COALESCE(batch_hold_since, modified), NOW()) >= %(bh_cool)s
                        THEN 1
                    WHEN pipeline_status = 'failed'
                         AND TIMESTAMPDIFF(MINUTE, modified, NOW()) >= %(failed_cool)s
                        THEN 1
                    ELSE 0
                END
            ) AS actionable_now_rows
        FROM `tabUnicommerce Orders`
        WHERE {where_sql}
        GROUP BY pipeline_status, COALESCE(NULLIF(status, ''), 'UNKNOWN')
        """,
        {
            **params,
            "bh_cool": int(BATCH_HOLD_RETRY_DELAY_MINS),
            # Use the BASE retry delay as a conservative "ready to retry"
            # threshold; _recover_failed_orders actually backs off further
            # on repeated attempts, so this is an upper bound on what could
            # move on the next cycle.
            "failed_cool": int(FAILED_RETRY_BASE_DELAY_MINS),
        },
        as_dict=True,
    ) or []

    pipeline_counts = {s: 0 for s in ORDER_STATUSES}
    uniware_counts: dict[str, int] = {}
    total = 0
    posted_count = 0
    actionable_now = 0

    for r in rows:
        n = int(r.get("n") or 0)
        total += n
        pl = r.get("pipeline_status") or "pending"
        pipeline_counts[pl] = pipeline_counts.get(pl, 0) + n
        uw = r.get("uniware_status") or "UNKNOWN"
        uniware_counts[uw] = uniware_counts.get(uw, 0) + n
        posted_count += int(r.get("posted_rows") or 0)
        actionable_now += int(r.get("actionable_now_rows") or 0)

    # actionable_now = ready + batch_hold-past-cooldown + failed-past-cooldown
    # so (batch_hold + failed in cooldown) = (batch_hold + failed) - (actionable_now - ready)
    ready_total = pipeline_counts.get("ready", 0)
    held_total = pipeline_counts.get("batch_hold", 0) + pipeline_counts.get("failed", 0)
    in_cooldown = max(0, held_total - max(0, actionable_now - ready_total))

    return {
        "total": total,
        "from_date": from_date,
        "to_date": to_date,
        "pipeline_status": pipeline_counts,
        "uniware_status": dict(sorted(uniware_counts.items(), key=lambda kv: -kv[1])),
        "posted_count": posted_count,
        "not_posted_count": max(0, total - posted_count),
        "actionable_now": actionable_now,
        "in_cooldown": in_cooldown,
        "generated_at": str(now_datetime()),
        "empty": total == 0,
    }


# ---------------------------------------------------------------------------
# AR invoice price audit + SAP cancel (operator tools)
# ---------------------------------------------------------------------------


def _sap_invoice_lines_for_price_audit(inv: dict) -> list[dict]:
    """Flatten SAP ``DocumentLines`` for comparison (drop bundle parent stubs)."""
    from ..mappers.sap_payload import SHIPPING_ITEM_CODE

    out: list[dict] = []
    for ln in inv.get("DocumentLines") or []:
        if str(ln.get("TreeType") or "") == "iSalesTree" and float(ln.get("UnitPrice") or 0) == 0:
            continue
        ic = str(ln.get("ItemCode") or "").strip()
        if not ic:
            continue
        out.append(
            {
                "ItemCode": ic,
                "Quantity": float(ln.get("Quantity") or 0),
                "UnitPrice": float(ln.get("UnitPrice") or 0),
                "TaxTotal": float(ln.get("TaxTotal") or 0),
                "kind": "shipping" if ic == SHIPPING_ITEM_CODE else "product",
            }
        )
    return out


def _credit_notes_blocking_invoice_cancel(doc_entry: str) -> list[dict]:
    """Return posted CN staging rows that reference this AR DocEntry."""
    de = str(int(float(doc_entry))) if doc_entry else ""
    if not de:
        return []
    return frappe.get_all(
        "UC Credit Note Staging",
        filters={"parent_sap_doc_entry": de, "sap_credit_doc_entry": ["!=", ""]},
        fields=["name", "uc_return_id", "sap_credit_doc_entry"],
        limit=50,
    )


@frappe.whitelist()
def ops_price_mismatch_audit(
    from_date: str,
    to_date: str,
    limit: int = 200,
    unit_tolerance: float = 0.05,
    tax_tolerance: float = 0.15,
    only_mismatched: int | bool = 1,
) -> dict:
    """Compare posted AR invoices (SAP) vs UC ``order_json`` using current mapper rules.

    Flags orders where SAP ``DocumentLines[].UnitPrice`` or header ``DocTaxAmount``
    diverges from what ``expected_invoice_pricing_from_uc`` would have produced
    (notably the pre-2026-04-16 bug that omitted line-level discounts).

    When ``only_mismatched`` is false, the response also includes a short
    ``matched_sample`` list of UC order names that passed the check (capped).
    """
    frappe.only_for("System Manager")
    from ..mappers.sap_payload import expected_invoice_pricing_from_uc

    start = (from_date or "").strip()
    end = (to_date or "").strip()
    if not start or not end:
        frappe.throw("from_date and to_date are required (YYYY-MM-DD).")
    if start > end:
        frappe.throw("from_date must be on or before to_date.")

    safe_limit = min(max(int(limit or 200), 1), 500)
    only_m = str(only_mismatched).lower() in {"1", "true", "yes", "on"}
    utol = float(unit_tolerance or 0.05)
    ttol = float(tax_tolerance or 0.15)

    filters: dict = {
        "pipeline_status": "posted",
        "sap_ar_invoice_docentry": ["!=", ""],
        "order_date": ["between", [start, end]],
    }
    orders = frappe.get_all(
        ORDER_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "channel_name",
            "order_date",
            "sap_ar_invoice_docentry",
            "sap_ar_invoice_docnum",
            "order_json",
        ],
        order_by="order_date asc, modified asc",
        limit=safe_limit,
    )

    sap = SAPClient()
    mismatches: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    matched: list[str] = []
    scanned = 0

    for row in orders:
        scanned += 1
        name = row.name
        channel = row.channel_name or ""
        de = str(row.sap_ar_invoice_docentry or "").strip()
        if not de:
            continue
        try:
            uc_data = json.loads(row.order_json or "{}")
        except Exception as exc:
            errors.append({"order": name, "error": f"order_json parse: {exc}"})
            continue

        exp = expected_invoice_pricing_from_uc(uc_data, channel)
        if not exp.get("ok"):
            skipped.append({"order": name, "reason": exp.get("reason")})
            continue

        try:
            inv = sap.get_invoice_by_doc_entry(de)
        except Exception as exc:
            errors.append({"order": name, "doc_entry": de, "error": str(exc)})
            continue

        sap_lines = _sap_invoice_lines_for_price_audit(inv)
        sap_by_item: dict[str, list[dict]] = {}
        for sl in sap_lines:
            sap_by_item.setdefault(sl["ItemCode"], []).append(sl)

        line_issues: list[dict] = []
        for el in exp.get("lines") or []:
            ic = el.get("ItemCode") or ""
            qty = float(el.get("Quantity") or 0)
            exp_up = float(el.get("ExpectedUnitPrice") or 0)
            candidates = sap_by_item.get(ic) or []
            match = None
            match_idx = None
            for idx, cand in enumerate(candidates):
                if abs(float(cand.get("Quantity") or 0) - qty) <= 0.0001:
                    match = cand
                    match_idx = idx
                    break
            if match is not None and match_idx is not None:
                candidates.pop(match_idx)
            if not match:
                line_issues.append(
                    {
                        "item": ic,
                        "issue": "missing_sap_line",
                        "expected_unit": exp_up,
                        "qty": qty,
                    }
                )
                continue
            sap_up = float(match.get("UnitPrice") or 0)
            if abs(sap_up - exp_up) > utol:
                line_issues.append(
                    {
                        "item": ic,
                        "issue": "unit_price",
                        "expected_unit": round(exp_up, 4),
                        "sap_unit": round(sap_up, 4),
                        "delta": round(sap_up - exp_up, 4),
                        "qty": qty,
                    }
                )

        for _ic, leftover_list in sap_by_item.items():
            for leftover in leftover_list or []:
                line_issues.append(
                    {
                        "item": _ic,
                        "issue": "extra_sap_line",
                        "sap_unit": round(float(leftover.get("UnitPrice") or 0), 4),
                        "qty": float(leftover.get("Quantity") or 0),
                    }
                )

        sap_doc_tax = float(inv.get("DocTaxAmount") or 0)
        if sap_doc_tax == 0.0:
            # Some companies / series post line-level tax only; header ``DocTaxAmount``
            # stays 0 while ``DocumentLines[].TaxTotal`` carries the IGST/CGST split.
            sap_doc_tax = sum(
                float(ln.get("TaxTotal") or 0) for ln in (inv.get("DocumentLines") or [])
            )
        exp_tax = float(exp.get("expected_doc_tax") or 0)
        tax_issue = abs(sap_doc_tax - exp_tax) > ttol

        if line_issues or tax_issue:
            mismatches.append(
                {
                    "order": name,
                    "channel": channel,
                    "order_date": str(row.order_date or ""),
                    "sap_doc_entry": de,
                    "sap_doc_num": str(row.sap_ar_invoice_docnum or inv.get("DocNum") or ""),
                    "sap_doc_total": float(inv.get("DocTotal") or 0),
                    "sap_doc_tax": round(sap_doc_tax, 2),
                    "expected_doc_tax": round(exp_tax, 2),
                    "tax_delta": round(sap_doc_tax - exp_tax, 2),
                    "line_issues": line_issues,
                    "tax_header_mismatch": bool(tax_issue),
                }
            )
        else:
            matched.append(name)

    return {
        "from_date": start,
        "to_date": end,
        "limit": safe_limit,
        "only_mismatched": only_m,
        "scanned": scanned,
        "matched_count": len(matched),
        "matched_sample": (matched[:40] if not only_m else []),
        "mismatch_count": len(mismatches),
        "skipped_bundle_or_empty": len(skipped),
        "error_count": len(errors),
        "skipped": skipped[:50],
        "errors": errors[:30],
        "mismatches": mismatches,
        "generated_at": str(now_datetime()),
    }


@frappe.whitelist()
def ops_sap_cancel_ar_invoice(
    uc_order_name: str | None = None,
    doc_entry: str | None = None,
    confirm: int | str = 0,
    reset_pipeline: int | str = 1,
) -> dict:
    """Preview or cancel an SAP AR invoice via Service Layer ``POST Invoices(id)/Cancel``.

    Pass either ``uc_order_name`` (``Unicommerce Orders.name``) **or**
    ``doc_entry`` (SAP ``DocEntry``). When ``confirm`` is false/0, only the
    current SAP header snapshot (+ blocking credit notes) is returned. When
    ``confirm`` is 1, the cancel action is executed; on success and when
    ``reset_pipeline`` is true, the UC order is moved back to ``ready`` and
    SAP posting fields are cleared so you can re-post with the fixed mapper.

    Restricted to **System Manager** — destructive financial operation.
    """
    frappe.only_for("System Manager")

    order_name = (uc_order_name or "").strip()
    de_raw = (doc_entry or "").strip()
    if not order_name and not de_raw:
        frappe.throw("Provide uc_order_name or doc_entry.")

    if order_name and not de_raw:
        de_raw = frappe.db.get_value(ORDER_DOCTYPE, order_name, "sap_ar_invoice_docentry") or ""
    if not de_raw:
        frappe.throw("Could not resolve sap_ar_invoice_docentry for this order.")
    try:
        doc_ent = int(float(str(de_raw).strip()))
    except Exception as exc:
        frappe.throw(f"Invalid doc_entry: {de_raw!r} ({exc})")

    if order_name:
        blockers = _credit_notes_blocking_invoice_cancel(str(doc_ent))
        linked_order = order_name
    else:
        blockers = _credit_notes_blocking_invoice_cancel(str(doc_ent))
        linked = frappe.get_all(
            ORDER_DOCTYPE,
            filters={"sap_ar_invoice_docentry": str(doc_ent)},
            fields=["name"],
            limit=1,
        )
        linked_order = linked[0].name if linked else None

    sap = SAPClient()
    inv = sap.get_invoice_by_doc_entry(doc_ent)
    cancelled_flag = str(inv.get("Cancelled") or "").strip().upper() == "TYES"

    doc_tax_hdr = float(inv.get("DocTaxAmount") or 0)
    if doc_tax_hdr == 0.0:
        doc_tax_hdr = sum(float(ln.get("TaxTotal") or 0) for ln in (inv.get("DocumentLines") or []))

    preview = {
        "doc_entry": doc_ent,
        "doc_num": inv.get("DocNum"),
        "card_code": inv.get("CardCode"),
        "doc_total": float(inv.get("DocTotal") or 0),
        "doc_tax": round(doc_tax_hdr, 4),
        "cancelled_already": cancelled_flag,
        "uc_order": linked_order,
        "blocking_credit_notes": blockers,
    }

    confirm_flag = str(confirm).lower() in {"1", "true", "yes", "on"}
    if not confirm_flag:
        return {"preview": True, **preview, "message": "Pass confirm=1 to execute POST Invoices(DocEntry)/Cancel."}

    if blockers:
        frappe.throw(
            "Cannot cancel: posted credit note(s) reference this invoice — "
            f"{len(blockers)} row(s). Reverse the CN in SAP first."
        )
    if cancelled_flag:
        return {"preview": False, "cancelled": True, **preview, "message": "Invoice already cancelled in SAP."}

    cancel_body = sap.cancel_ar_invoice(doc_ent)
    inv_after = sap.get_invoice_by_doc_entry(doc_ent)

    reset_flag = str(reset_pipeline).lower() in {"1", "true", "yes", "on"}
    if reset_flag and linked_order:
        frappe.db.set_value(
            ORDER_DOCTYPE,
            linked_order,
            {
                "pipeline_status": "ready",
                "sap_ar_invoice_docentry": "",
                "sap_ar_invoice_docnum": "",
                "posting_started_at": None,
                "last_error": "",
                "payload_json": "",
            },
        )
        frappe.db.commit()

    return {
        "preview": False,
        "cancelled": True,
        "sap_cancel_response": cancel_body,
        "invoice_after": {
            "Cancelled": inv_after.get("Cancelled"),
            "DocumentStatus": inv_after.get("DocumentStatus"),
            "DocNum": inv_after.get("DocNum"),
        },
        **preview,
        "reset_uc_order": linked_order if reset_flag else None,
    }


# ---------------------------------------------------------------------------
# Pre-validate batches (sync core + async wrapper)
#
# The dry-run walks every "ready" order and asks SAP how many units of each
# batch are available. For realistic operator volumes (100+ ready orders,
# 3–5 batch-managed lines each) the naive per-line lookup spawns hundreds of
# SAP round-trips and easily blows past the gunicorn HTTP timeout. Two
# optimisations in this block make it fast enough to run over HTTP AND give
# the operator a live progress bar:
#
#   1. Bulk pre-warm — before the main loop we collect every ``(warehouse,
#      item_code)`` tuple we'll need and issue ONE OData query per warehouse
#      instead of one per line. ``_check_batches`` then reads from the in-
#      memory dict.
#   2. Async runner — ``ops_prevalidate_batches_run_async`` enqueues the
#      worker on the Frappe long queue and returns a job_id. The Desk polls
#      ``ops_prevalidate_batches_status`` every ~1.5s to render progress.
# ---------------------------------------------------------------------------

_PREVALIDATE_SNAPSHOT_KEY = "uc_prevalidate_batches_v1"
_PREVALIDATE_CANCEL_KEY = "uc_prevalidate_batches_cancel_v1"
_PREVALIDATE_JOB_NAME = "ops_prevalidate_batches"
_PREVALIDATE_INFLIGHT_STATUSES = frozenset({"queued", "running"})
_PREVALIDATE_TERMINAL_STATUSES = frozenset({"done", "error", "cancelled"})
_PREVALIDATE_TTL_INFLIGHT_SEC = 4 * 60 * 60
_PREVALIDATE_TTL_TERMINAL_SEC = 24 * 60 * 60
# How often the worker pushes a fresh progress snapshot into cache. Every
# order is fine — snapshots are ~2 KB and the cache write is cheap — but
# bump this if you ever prevalidate thousands of orders.
_PREVALIDATE_PROGRESS_STRIDE = 1


def _prevalidate_cache_snapshot(snapshot: dict) -> None:
    status = (snapshot.get("status") or "").lower()
    ttl = (
        _PREVALIDATE_TTL_TERMINAL_SEC
        if status in _PREVALIDATE_TERMINAL_STATUSES
        else _PREVALIDATE_TTL_INFLIGHT_SEC
    )
    frappe.cache().set_value(
        _PREVALIDATE_SNAPSHOT_KEY,
        json.dumps(snapshot, default=str),
        expires_in_sec=ttl,
    )


def _prevalidate_load_snapshot() -> dict:
    raw = frappe.cache().get_value(_PREVALIDATE_SNAPSHOT_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _prevalidate_cancel_requested(job_id: str) -> bool:
    raw = frappe.cache().get_value(_PREVALIDATE_CANCEL_KEY) or ""
    return str(raw) == str(job_id)


def _check_default_worker() -> str | None:
    """Return an error string if no RQ worker is consuming the default queue,
    or None if at least one healthy worker is found.

    Called before enqueuing to fail fast instead of waiting for the stale
    detector to fire 300 seconds later.
    """
    try:
        from frappe.utils.background_jobs import get_workers, get_queue
        from rq.worker import WorkerStatus

        default_q = get_queue("default")
        workers = get_workers(queue=default_q)
        # Workers registered in Redis but SUSPENDED are paused; treat as unavailable.
        # Stopped workers are removed from Redis automatically — not in this list.
        available = [
            w for w in workers
            if w.get_state() in (WorkerStatus.IDLE, WorkerStatus.STARTED)
        ]
        busy = [w for w in workers if w.get_state() == WorkerStatus.BUSY]

        if not workers:
            return (
                "No RQ worker is listening on the 'default' queue. "
                "Start the worker with: bench worker --queue default,short,long"
            )

        if not available and busy:
            current_jobs = []
            for w in busy[:3]:
                try:
                    j = w.get_current_job()
                    if j:
                        fn = (j.func_name or "").split(".")[-1]
                        current_jobs.append(fn)
                except Exception:
                    pass
            running_str = ", ".join(current_jobs) if current_jobs else "another job"
            return (
                f"The worker is currently busy processing: {running_str}. "
                "Please wait for it to finish, then retry Pre-validate."
            )
        return None
    except Exception:
        # If we can't introspect workers (older RQ, Redis unavailable), don't block.
        return None


def _aggregate_shortages(all_shortages: list[dict]) -> list[dict]:
    agg: dict[str, dict] = {}
    for s in all_shortages:
        key = f"{s['warehouse_code']}|{s['item_code']}|{s['batch_number']}"
        if key not in agg:
            agg[key] = {
                "warehouse_code": s["warehouse_code"],
                "item_code": s["item_code"],
                "batch_number": s["batch_number"],
                "order_count": 0,
                "total_needed": 0.0,
                "available": float(s.get("qty_available") or 0),
                "total_shortage": 0.0,
                "orders": [],
            }
        agg[key]["order_count"] += 1
        need = float(s.get("qty_needed") or 0)
        have = float(s.get("qty_available") or 0)
        short = s.get("shortage")
        short_val = float(short) if short is not None else max(0.0, need - have)
        agg[key]["total_needed"] = round(agg[key]["total_needed"] + need, 3)
        agg[key]["total_shortage"] = round(agg[key]["total_shortage"] + short_val, 3)
        if s.get("uc_order_id") and s["uc_order_id"] not in agg[key]["orders"]:
            agg[key]["orders"].append(s["uc_order_id"])
    return sorted(agg.values(), key=lambda x: (-x["total_shortage"], x["item_code"]))


def _prewarm_prevalidate_context(
    sap,
    settings,
    orders: list,
) -> dict:
    """Single-pass pre-warm for the Ops Center pre-validate flow.

    One SQL hit loads every order's ``order_json`` + channel. One parse
    walks every line to collect the global caches. Two (small) batches of
    SAP calls fill everything the per-order loop needs:

    1. ``bulk_batch_quantities_by_warehouse`` per unique SAP warehouse →
       ``{(item, batch, wh): qty}``. Covers both UC-pre-assigned batches
       AND any auto-FEFO selections made later, because the OData query
       returns every batch for the given (wh, items) set.
    2. ``bulk_manage_batch_numbers`` once for ALL unique items across all
       orders → ``{item: True/False/None}``. Pre-fills the tri-state
       managed cache so ``_check_batches`` never needs to fire a SAP
       ``Items(...)`` GET inside its per-line loop.

    Returns a dict with four caches the caller feeds straight into
    ``_check_batches``:

    * ``quantity_cache``        (item, batch, wh) → float
    * ``batch_managed_cache``   item → True / False / None
    * ``order_cache``           order_name → ``{channel, items}`` (pre-parsed)
    * ``stats``                 counters used for the progress snapshot
    """
    from ..mappers.sap_payload import _parse_line_items, _resolve_sap_warehouse

    order_names = [row.name for row in orders]
    rows = (
        frappe.get_all(
            ORDER_DOCTYPE,
            filters={"name": ["in", order_names]},
            fields=["name", "channel_name", "order_json"],
            limit=len(order_names) or 1,
        )
        if order_names
        else []
    )

    order_cache: dict[str, dict] = {}
    wh_items: dict[str, set[str]] = defaultdict(set)
    all_items: set[str] = set()
    # Memoised {(channel, uc_wh): sap_wh} so settings JSON is parsed once
    # per unique pair in the pre-warm, AND reused by the main loop.
    wh_resolve_cache: dict[tuple[str, str], str] = {}

    def _resolve(channel: str, uc_wh: str) -> str:
        key = (channel or "", uc_wh or "")
        cached = wh_resolve_cache.get(key)
        if cached is not None:
            return cached
        resolved = _resolve_sap_warehouse(settings, channel or "", uc_wh or "") or ""
        wh_resolve_cache[key] = resolved
        return resolved

    for row in rows:
        try:
            uc_data = json.loads(row.get("order_json") or "{}")
        except Exception as exc:
            frappe.logger().warning(
                "_prewarm_prevalidate_context: bad order_json for %s: %s", row.get("name"), exc
            )
            order_cache[row["name"]] = {"channel": row.get("channel_name") or "", "items": []}
            continue
        items = _parse_line_items(uc_data) or []
        order_cache[row["name"]] = {
            "channel": row.get("channel_name") or "",
            "items": items,
        }
        channel = row.get("channel_name") or ""
        for item in items:
            item_code = str(item.get("itemSku") or "").strip()
            if not item_code:
                continue
            all_items.add(item_code)
            sap_wh = _resolve(channel, item.get("warehouseCode", ""))
            if not sap_wh:
                continue
            wh_items[sap_wh].add(item_code)

    # One HANA query per warehouse gives us BOTH the quantity cache and
    # the FEFO allocation rows in a single round-trip. In practice this is
    # ~0.1 s per warehouse (vs. 16 s per retry-timed-out OData call for
    # each ItemCode+BatchNumber+WhsCode triple on the old path).
    quantity_cache: dict[tuple[str, str, str], float] = {}
    fefo_cache: dict[tuple[str, str], list[dict]] = {}
    for sap_wh, item_codes in wh_items.items():
        if not item_codes or not sap_wh:
            continue
        try:
            inv_rows = sap.bulk_batch_inventory_by_warehouse(sap_wh, item_codes)
        except Exception as exc:
            frappe.logger().warning(
                "_prewarm_prevalidate_context: HANA batch inventory query "
                "failed for wh=%s items=%s: %s",
                sap_wh,
                len(item_codes),
                exc,
            )
            inv_rows = []
        for inv in inv_rows:
            item_code = inv["item_code"]
            batch_num = inv["batch_number"]
            qty = float(inv.get("quantity") or 0)
            # quantity cache key = (item, batch, wh) matching _check_batches
            q_key = (item_code, batch_num, sap_wh)
            quantity_cache[q_key] = quantity_cache.get(q_key, 0.0) + qty
            # FEFO cache row shape matches _get_fefo_inventory_rows() so the
            # existing ``_fefo_allocate_from_rows`` allocator can consume it
            # directly without translation.
            f_key = (item_code, sap_wh)
            fefo_cache.setdefault(f_key, []).append({
                "distnumber": batch_num,
                "quantity": qty,
                "expdate": inv.get("expiry"),
            })

    batch_managed_cache: dict[str, "bool | None"] = {}
    if all_items:
        try:
            batch_managed_cache = sap.bulk_manage_batch_numbers(all_items) or {}
        except Exception as exc:
            frappe.logger().warning(
                "_prewarm_prevalidate_context: bulk managed-items query failed "
                "(falling back to per-item): %s",
                exc,
            )
            batch_managed_cache = {}

    return {
        "quantity_cache": quantity_cache,
        "batch_managed_cache": batch_managed_cache,
        "order_cache": order_cache,
        "fefo_cache": fefo_cache,
        "wh_resolve_cache": wh_resolve_cache,
        "stats": {
            "unique_warehouses": len(wh_items),
            "unique_items": len(all_items),
            "unique_qty_keys": len(quantity_cache),
            "unique_fefo_keys": len(fefo_cache),
            "fefo_rows": sum(len(v) for v in fefo_cache.values()),
        },
    }


def _prewarm_batch_quantity_cache(sap, settings, orders: list) -> dict[tuple[str, str, str], float]:
    """Back-compat shim. The full pre-warm now lives in
    ``_prewarm_prevalidate_context`` so the pre-validate loop can also reuse
    the pre-parsed order/item data and the bulk managed-items cache. Any
    caller that only wants the quantity cache (historical tests, scripts)
    keeps the narrow return shape.
    """
    ctx = _prewarm_prevalidate_context(sap, settings, orders)
    return ctx["quantity_cache"]


_PREVALIDATE_DEFAULT_STATUSES = ("ready",)
_PREVALIDATE_ALLOWED_STATUSES = {
    "ready", "batch_hold", "fetched", "pending", "posting", "verify", "failed", "dead",
}


def _normalise_prevalidate_statuses(statuses) -> list[str]:
    """Coerce the ``statuses`` arg into a clean list of pipeline_status values.

    Accepts ``None``, a comma-separated string (e.g. from the URL), a JSON
    string (Frappe's default client-side encoding for array args), or an
    actual list/tuple. Unknown entries are silently dropped; an empty result
    falls back to the canonical default (``["ready"]``).
    """
    if statuses is None or statuses == "":
        return list(_PREVALIDATE_DEFAULT_STATUSES)
    if isinstance(statuses, str):
        raw = statuses.strip()
        if raw.startswith("[") and raw.endswith("]"):
            try:
                import json as _json
                statuses = _json.loads(raw)
            except Exception:
                statuses = [p.strip() for p in raw.strip("[]").split(",")]
        else:
            statuses = [p.strip() for p in raw.split(",")]
    try:
        cleaned = [str(s).strip().lower() for s in statuses if str(s).strip()]
    except TypeError:
        cleaned = []
    cleaned = [s for s in cleaned if s in _PREVALIDATE_ALLOWED_STATUSES]
    return cleaned or list(_PREVALIDATE_DEFAULT_STATUSES)


def _run_prevalidate_batches_core(
    limit: int,
    job_id: str | None = None,
    queued_by: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    statuses: "list[str] | tuple[str, ...] | str | None" = None,
) -> dict:
    """Shared inner loop used by both the sync endpoint and the async job.

    When ``job_id`` is provided, every progress tick is written to the
    prevalidate snapshot cache and the worker checks the cancel flag between
    orders. When ``job_id`` is None the function just runs to completion and
    returns the result — no cache I/O.

    ``from_date`` / ``to_date`` (YYYY-MM-DD) scope the run to orders whose
    ``order_date`` falls in that inclusive range. ``statuses`` defaults to
    ``["ready"]`` but callers can broaden the scope (e.g. to include
    ``batch_hold`` so the inventory team can see every shortage, not just
    the ones that are currently ready to post).
    """
    from ..client import SAPClient
    from ..workers.invoice import _reservation_consume_for_order, _reservation_context_new

    settings = frappe.get_single("Unicommerce Settings")
    started_at = now_datetime()
    started_epoch = time.time()

    scoped_statuses = _normalise_prevalidate_statuses(statuses)
    filters: dict = {"pipeline_status": ["in", scoped_statuses]}
    from_date = (from_date or "").strip() or None
    to_date = (to_date or "").strip() or None
    if from_date and to_date:
        filters["order_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["order_date"] = [">=", from_date]
    elif to_date:
        filters["order_date"] = ["<=", to_date]

    # When a date range is supplied we assume the caller wants to cover the
    # whole window — bump the default cap so a 7-day pre-validate isn't
    # silently truncated at 100 orders. Callers can still pin a lower
    # ``limit`` explicitly if they want a quick probe.
    effective_limit = int(limit or 0)
    if effective_limit <= 0:
        effective_limit = 5000 if (from_date or to_date) else 100

    orders = frappe.get_all(
        ORDER_DOCTYPE,
        filters=filters,
        fields=["name", "channel_name"],
        order_by="order_date asc",
        limit=effective_limit,
    )
    total = len(orders)

    filter_meta = {
        "from_date": from_date,
        "to_date": to_date,
        "statuses": scoped_statuses,
        "effective_limit": effective_limit,
    }

    base_snapshot = {
        "job_id": job_id,
        "status": "running",
        "queued_by": queued_by or frappe.session.user,
        "started_at": str(started_at),
        "limit": effective_limit,
        "filters": filter_meta,
        "progress": {
            "done": 0,
            "total": total,
            "percent": 0,
            "elapsed_s": 0,
            "eta_s": None,
            "ok_count": 0,
            "would_hold": 0,
            "shortage_hits": 0,
            "current_order": None,
            "stage": "starting",
        },
    }
    if job_id:
        _prevalidate_cache_snapshot(base_snapshot)

    if total == 0:
        result = {"checked": 0, "would_hold": 0, "shortages": [], "ok_count": 0}
        if job_id:
            _prevalidate_cache_snapshot({
                **base_snapshot,
                "status": "done",
                "finished_at": str(now_datetime()),
                "progress": {
                    **base_snapshot["progress"],
                    "stage": "finished",
                    "percent": 100,
                },
                "result": result,
            })
        return result

    sap = SAPClient()

    # Stage 1: single-pass pre-warm. One SQL loads every order's JSON, then
    # two small batches of SAP calls cover BOTH quantity lookups AND the
    # per-item "is batch-managed?" check that used to fire N times per
    # order. This is the biggest wall-clock win for the pre-validate flow.
    if job_id:
        _prevalidate_cache_snapshot({
            **base_snapshot,
            "progress": {
                **base_snapshot["progress"],
                "stage": "prewarming_sap_cache",
            },
        })
    # When the HANA pre-warm succeeds we treat the resulting quantity_cache
    # as authoritative: a (item, batch, wh) miss means literal 0 stock in
    # that warehouse (HANA's OBTQ is the source of truth for SAP B1 batch
    # qty). Flipping this flag avoids 16 s per miss spent retrying an
    # OData endpoint that rejects the filter with HTTP 400 anyway.
    prewarm_succeeded = False
    try:
        ctx = _prewarm_prevalidate_context(sap, settings, orders)
        quantity_cache = ctx["quantity_cache"]
        shared_batch_managed_cache = ctx["batch_managed_cache"]
        order_cache = ctx["order_cache"]
        fefo_cache = ctx["fefo_cache"]
        wh_resolve_cache = ctx["wh_resolve_cache"]
        # A non-empty FEFO cache confirms HANA was reachable; if it's empty
        # (HANA down and HANA path skipped) we don't mark authoritative.
        prewarm_succeeded = bool(fefo_cache) or bool(quantity_cache)
    except Exception as exc:
        frappe.logger().warning("prevalidate prewarm failed (falling back to per-line): %s", exc)
        quantity_cache = {}
        shared_batch_managed_cache = {}
        order_cache = {}
        fefo_cache = {}
        wh_resolve_cache = {}

    # Stage 2: per-order validation. Every per-line lookup is now an
    # in-memory dict hit; only auto-FEFO fallbacks (items the prewarm
    # couldn't resolve) touch SAP, and those are rare.
    would_hold = 0
    ok_count = 0
    all_shortages: list[dict] = []
    # Simulate same-run inventory consumption so prevalidate and posting align.
    reservation_context = _reservation_context_new(ledger_enabled=False)

    for idx, row in enumerate(orders, start=1):
        if job_id and _prevalidate_cancel_requested(job_id):
            _prevalidate_cache_snapshot({
                **base_snapshot,
                "status": "cancelled",
                "finished_at": str(now_datetime()),
                "progress": {
                    **base_snapshot["progress"],
                    "done": idx - 1,
                    "total": total,
                    "percent": int(((idx - 1) / total) * 100) if total else 0,
                    "elapsed_s": int(time.time() - started_epoch),
                    "ok_count": ok_count,
                    "would_hold": would_hold,
                    "shortage_hits": len(all_shortages),
                    "current_order": None,
                    "stage": "cancelled",
                },
                "result": {
                    "checked": idx - 1,
                    "would_hold": would_hold,
                    "ok_count": ok_count,
                    "shortages": _aggregate_shortages(all_shortages),
                },
            })
            # Clear the cancel flag so the next run isn't accidentally cancelled
            frappe.cache().delete_value(_PREVALIDATE_CANCEL_KEY)
            return {
                "checked": idx - 1,
                "would_hold": would_hold,
                "ok_count": ok_count,
                "shortages": _aggregate_shortages(all_shortages),
                "cancelled": True,
            }

        try:
            cached_order = order_cache.get(row.name)
            if cached_order is not None:
                # Fast path: reuse the parsed items from the pre-warm so
                # we skip the redundant ``frappe.get_doc`` + ``json.loads``
                # per order. Pass a lightweight stand-in doc because
                # ``_check_batches`` only reads ``.name`` and
                # ``.channel_name`` when pre-parsed items are supplied.
                staging = frappe._dict(
                    name=row.name,
                    channel_name=cached_order.get("channel") or row.channel_name,
                    order_json=None,
                )
                result = _check_batches(
                    sap,
                    staging,
                    batch_managed_cache=shared_batch_managed_cache,
                    quantity_cache=quantity_cache,
                    pre_parsed_items=cached_order.get("items") or [],
                    pre_resolved_settings=settings,
                    fefo_cache=fefo_cache,
                    wh_resolve_cache=wh_resolve_cache,
                    quantity_cache_authoritative=prewarm_succeeded,
                    reservation_context=reservation_context,
                )
            else:
                # Rare fallback (pre-warm SQL missed this row): load the
                # full doc so we still produce a correct verdict.
                staging = frappe.get_doc(ORDER_DOCTYPE, row.name)
                result = _check_batches(
                    sap,
                    staging,
                    batch_managed_cache=shared_batch_managed_cache,
                    quantity_cache=quantity_cache,
                    pre_resolved_settings=settings,
                    fefo_cache=fefo_cache,
                    wh_resolve_cache=wh_resolve_cache,
                    quantity_cache_authoritative=prewarm_succeeded,
                    reservation_context=reservation_context,
                )
            if result["ok"]:
                ok_count += 1
                _reservation_consume_for_order(reservation_context, row.name)
            else:
                would_hold += 1
                all_shortages.extend(result["missing"])
        except Exception as e:
            frappe.logger().warning(f"ops_prevalidate_batches: skipped {row.name}: {e}")

        if job_id and (idx % _PREVALIDATE_PROGRESS_STRIDE == 0 or idx == total):
            elapsed = max(0.001, time.time() - started_epoch)
            avg = elapsed / idx
            remaining = max(0, total - idx)
            eta = int(avg * remaining) if remaining else 0
            _prevalidate_cache_snapshot({
                **base_snapshot,
                "progress": {
                    "done": idx,
                    "total": total,
                    "percent": int((idx / total) * 100) if total else 100,
                    "elapsed_s": int(elapsed),
                    "eta_s": eta,
                    "ok_count": ok_count,
                    "would_hold": would_hold,
                    "shortage_hits": len(all_shortages),
                    "current_order": row.name,
                    "stage": "validating",
                },
            })

    shortages_sorted = _aggregate_shortages(all_shortages)
    result = {
        "checked": len(orders),
        "would_hold": would_hold,
        "ok_count": ok_count,
        "shortages": shortages_sorted,
        "filters": filter_meta,
    }

    if job_id:
        elapsed = max(0.001, time.time() - started_epoch)
        _prevalidate_cache_snapshot({
            **base_snapshot,
            "status": "done",
            "finished_at": str(now_datetime()),
            "progress": {
                "done": total,
                "total": total,
                "percent": 100,
                "elapsed_s": int(elapsed),
                "eta_s": 0,
                "ok_count": ok_count,
                "would_hold": would_hold,
                "shortage_hits": len(all_shortages),
                "current_order": None,
                "stage": "finished",
            },
            "result": result,
        })
    return result


def _run_prevalidate_batches_job(
    run_id: str | None = None,
    limit: int = 100,
    queued_by: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    statuses: "list[str] | tuple[str, ...] | str | None" = None,
    **_legacy_kwargs,
) -> None:
    """RQ entrypoint. Wraps the core runner in top-level error handling so
    any unexpected exception surfaces in the status cache instead of vanishing
    into the RQ stack trace.

    NOTE: The primary parameter is called ``run_id`` (not ``job_id``) because
    RQ's own ``Queue.enqueue_call`` reserves the kwarg ``job_id`` for its
    internal job tracking and strips it before kwargs reach this function.
    Callers must therefore pass ``run_id=...`` when enqueueing. We keep
    ``**_legacy_kwargs`` so any stray kwarg (e.g. a legacy ``job_id`` from
    an older enqueue payload still sitting in Redis after a deploy) does
    not cause the worker to crash with ``unexpected keyword argument``.
    The value is still surfaced to the UI as ``job_id`` inside the cached
    snapshot for API back-compat.
    """
    effective_id = run_id or _legacy_kwargs.get("job_id") or ""
    try:
        _run_prevalidate_batches_core(
            limit=int(limit or 0),
            job_id=effective_id or None,
            queued_by=queued_by,
            from_date=from_date,
            to_date=to_date,
            statuses=statuses,
        )
    except Exception as exc:
        frappe.logger().exception("ops_prevalidate_batches job %s failed", effective_id)
        current = _prevalidate_load_snapshot() or {}
        _prevalidate_cache_snapshot({
            **current,
            "job_id": effective_id or current.get("job_id"),
            "status": "error",
            "error": str(exc),
            "finished_at": str(now_datetime()),
        })


@frappe.whitelist()
def ops_prevalidate_batches(
    limit: int = 100,
    from_date: str | None = None,
    to_date: str | None = None,
    statuses: "list[str] | tuple[str, ...] | str | None" = None,
) -> dict:
    """Synchronous dry-run batch validation — kept for back-compat.

    Runs the shared core inline. For large ``limit`` values prefer the async
    pair ``ops_prevalidate_batches_run_async`` + ``_status`` so the Desk does
    not hang on a single 60s+ HTTP call.

    Access-restricted to System Manager: this endpoint drives a SAP Service
    Layer call per ready order and exposes per-order shortage diagnostics.
    """
    frappe.only_for("System Manager")
    return _run_prevalidate_batches_core(
        limit=int(limit or 0),
        job_id=None,
        from_date=from_date,
        to_date=to_date,
        statuses=statuses,
    )


@frappe.whitelist()
def ops_prevalidate_batches_run_async(
    limit: int = 100,
    force: int | bool = 0,
    from_date: str | None = None,
    to_date: str | None = None,
    statuses: "list[str] | tuple[str, ...] | str | None" = None,
) -> dict:
    """Queue the batch prevalidate dry-run. Returns immediately with a job id.

    Poll ``ops_prevalidate_batches_status`` for live progress and the final
    result. Call ``ops_prevalidate_batches_cancel`` to stop a running job
    between orders (finishes the current order first).

    Concurrency guard: a second ``run_async`` while another job is
    queued/running is rejected unless ``force=1`` is passed.
    """
    frappe.only_for("System Manager")

    current = _prevalidate_load_snapshot() or {}
    force_flag = str(force).lower() in {"1", "true", "yes", "on"}
    if not force_flag and (current.get("status") or "").lower() in _PREVALIDATE_INFLIGHT_STATUSES:
        return {
            "status": "already_running",
            "job_id": current.get("job_id"),
            "message": "A pre-validate run is already in progress. Poll status to watch it, "
            "or pass force=1 to start a fresh run.",
            "snapshot": current,
        }

    job_id = hashlib.sha1(
        f"{frappe.session.user}|{now_datetime()}|{os.urandom(8)!r}".encode()
    ).hexdigest()[:16]

    # Fail fast if no RQ worker is consuming the default queue.
    # Without this check the job sits in Redis for _PREVALIDATE_QUEUE_STALL_SEC
    # before the stale detector fires — confusing and slow.
    worker_warning = _check_default_worker()
    if worker_warning:
        err_snap = {
            "job_id": None, "status": "error",
            "error": worker_warning,
            "queued_at": str(now_datetime()), "finished_at": str(now_datetime()),
        }
        _prevalidate_cache_snapshot(err_snap)
        return err_snap

    frappe.cache().delete_value(_PREVALIDATE_CANCEL_KEY)
    scoped_statuses = _normalise_prevalidate_statuses(statuses)
    from_date_clean = (from_date or "").strip() or None
    to_date_clean = (to_date or "").strip() or None
    queued_snapshot = {
        "job_id": job_id,
        "status": "queued",
        "queued_by": frappe.session.user,
        "queued_at": str(now_datetime()),
        "limit": int(limit or 0),
        "filters": {
            "from_date": from_date_clean,
            "to_date": to_date_clean,
            "statuses": scoped_statuses,
        },
        "progress": {
            "done": 0,
            "total": None,
            "percent": 0,
            "elapsed_s": 0,
            "eta_s": None,
            "ok_count": 0,
            "would_hold": 0,
            "shortage_hits": 0,
            "current_order": None,
            "stage": "queued",
        },
    }
    _prevalidate_cache_snapshot(queued_snapshot)

    # IMPORTANT: pass the job identifier as ``run_id``, NOT ``job_id``. RQ's
    # Queue.enqueue_call() has its own reserved ``job_id`` kwarg that it
    # consumes for its internal job tracking, so a kwarg named ``job_id``
    # would never reach the worker function and it'd crash with
    # ``missing 1 required positional argument: 'job_id'``. The worker
    # function therefore names its parameter ``run_id`` to sidestep the
    # collision.
    try:
        frappe.enqueue(
            "khanal_tech_integrations.unicommerce.api.ops._run_prevalidate_batches_job",
            job_name=_PREVALIDATE_JOB_NAME,
            # Use default queue so this works on benches that run only the
            # default worker process (common in dev). The pre-warm
            # optimisation keeps this job lightweight enough for default
            # while still async from the UI.
            queue="default",
            timeout=60 * 60,
            enqueue_after_commit=True,
            run_id=job_id,
            limit=int(limit or 0),
            queued_by=frappe.session.user,
            from_date=from_date_clean,
            to_date=to_date_clean,
            statuses=scoped_statuses,
        )
    except Exception as exc:
        # Never leave the snapshot stuck in "queued" if the enqueue itself
        # fails (Redis down, worker pool misconfigured, etc.). Surface the
        # error immediately so the UI unblocks the operator.
        frappe.logger().exception("ops_prevalidate_batches enqueue failed")
        _prevalidate_cache_snapshot({
            **queued_snapshot,
            "status": "error",
            "error": f"Could not queue the job: {exc}",
            "finished_at": str(now_datetime()),
        })
        raise
    return queued_snapshot


_PREVALIDATE_QUEUE_STALL_SEC = 300   # 5 min — worker may be busy with post_invoices
_PREVALIDATE_RUN_STALL_SEC = 15 * 60


@frappe.whitelist()
def ops_prevalidate_batches_status() -> dict:
    """Return the cached prevalidate snapshot (queued / running / done / error /
    cancelled), or ``{"status": "idle"}`` if no run has ever happened.

    Staleness detection: if a snapshot has been stuck in ``queued`` for
    longer than ``_PREVALIDATE_QUEUE_STALL_SEC`` (no worker picked it up)
    or in ``running`` without a progress update for
    ``_PREVALIDATE_RUN_STALL_SEC`` (worker crashed mid-flight), we flip it
    to ``error`` so the UI unblocks instead of polling forever. This is the
    server-side safety net for cases like "worker process not listening to
    the right queue" that otherwise silently strand the operator.

    The snapshot contains a ``progress`` block the UI can render directly
    (done / total / percent / elapsed_s / eta_s / current_order / shortage
    counters). Terminal runs also include a ``result`` block shaped like
    the old sync response so the same render code can reuse it.
    """
    frappe.only_for("System Manager")
    snap = _prevalidate_load_snapshot()
    if not snap:
        return {"status": "idle"}

    status = (snap.get("status") or "").lower()
    stale_reason: str | None = None

    if status == "queued":
        queued_at_str = snap.get("queued_at") or snap.get("generated_at") or ""
        queued_dt = get_datetime(queued_at_str) if queued_at_str else None
        if queued_dt is not None:
            try:
                age = time_diff_in_seconds(now_datetime(), queued_dt) or 0
            except Exception:
                age = 0
            if age > _PREVALIDATE_QUEUE_STALL_SEC:
                worker_hint = _check_default_worker() or (
                    "Workers are running but the job hasn't been picked up — "
                    "they may be processing another long job. Retry in a minute."
                )
                stale_reason = (
                    f"Job was queued {int(age)}s ago and no worker picked it up. "
                    f"{worker_hint}"
                )
    elif status == "running":
        progress = snap.get("progress") or {}
        elapsed = int(progress.get("elapsed_s") or 0)
        started_str = snap.get("started_at") or ""
        started_dt = get_datetime(started_str) if started_str else None
        if started_dt is not None:
            try:
                wall = time_diff_in_seconds(now_datetime(), started_dt) or 0
            except Exception:
                wall = 0
            # If wall-clock age is far beyond last recorded elapsed time,
            # the worker likely crashed and stopped updating the snapshot.
            if wall > _PREVALIDATE_RUN_STALL_SEC and wall > elapsed + 120:
                stale_reason = (
                    f"Worker stopped updating progress (last tick {elapsed}s "
                    f"into the run, wall-clock now {int(wall)}s). It likely "
                    "crashed — check logs/worker.error.log."
                )

    if stale_reason:
        snap = {
            **snap,
            "status": "error",
            "error": stale_reason,
            "finished_at": str(now_datetime()),
        }
        _prevalidate_cache_snapshot(snap)
        frappe.cache().delete_value(_PREVALIDATE_CANCEL_KEY)

    return snap


@frappe.whitelist()
def ops_prevalidate_batches_cancel() -> dict:
    """Request cancellation of the currently running prevalidate job.

    The worker checks this flag between orders and exits cleanly after
    finishing whatever order it is currently validating. If no job is
    running this is a no-op.
    """
    frappe.only_for("System Manager")
    snap = _prevalidate_load_snapshot() or {}
    status = (snap.get("status") or "").lower()
    if status not in _PREVALIDATE_INFLIGHT_STATUSES:
        return {"cancelled": False, "reason": "no_job_in_progress", "snapshot": snap}
    job_id = snap.get("job_id") or ""
    if not job_id:
        return {"cancelled": False, "reason": "missing_job_id", "snapshot": snap}
    # If still queued (never picked by any worker), mark cancelled immediately
    # so the UI unblocks and the operator can launch a fresh run.
    if status == "queued":
        cancelled_snapshot = {
            **snap,
            "status": "cancelled",
            "finished_at": str(now_datetime()),
            "progress": {
                **(snap.get("progress") or {}),
                "stage": "cancelled",
            },
            "result": {
                "checked": int(((snap.get("progress") or {}).get("done") or 0)),
                "would_hold": int(((snap.get("progress") or {}).get("would_hold") or 0)),
                "ok_count": int(((snap.get("progress") or {}).get("ok_count") or 0)),
                "shortages": [],
            },
        }
        _prevalidate_cache_snapshot(cancelled_snapshot)
        frappe.cache().delete_value(_PREVALIDATE_CANCEL_KEY)
        return {"cancelled": True, "job_id": job_id, "status": "cancelled"}
    frappe.cache().set_value(
        _PREVALIDATE_CANCEL_KEY,
        str(job_id),
        expires_in_sec=_PREVALIDATE_TTL_INFLIGHT_SEC,
    )
    return {"cancelled": True, "job_id": job_id}


@frappe.whitelist()
def ops_posting_guardrail_summary(days: int = 7, statuses: str | None = None) -> dict:
    """
    Channel-wise guardrail counters to spot risky orders before posting.
    """
    day_window = max(int(days or 1), 1)
    status_list = [s.strip() for s in str(statuses or "fetched,ready,batch_hold,failed").split(",") if s.strip()]

    where = ["o.modified >= DATE_SUB(NOW(), INTERVAL %(days)s DAY)"]
    params: dict[str, Any] = {"days": day_window}
    if status_list:
        where.append("o.pipeline_status IN %(status_list)s")
        params["status_list"] = tuple(status_list)
    where_sql = " AND ".join(where)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(o.channel_name, ''), 'Unknown') AS channel,
            COUNT(DISTINCT o.name) AS orders,
            SUM(
                CASE
                    WHEN CAST(IFNULL(NULLIF(TRIM(li.shippingcharges), ''), '0') AS DECIMAL(18,4)) > 0
                    THEN 1 ELSE 0
                END
            ) AS lines_with_shipping_charge,
            SUM(
                CASE
                    WHEN CAST(IFNULL(NULLIF(TRIM(li.shippingcharges), ''), '0') AS DECIMAL(18,4)) > 0
                     AND CAST(IFNULL(NULLIF(TRIM(li.shippingchargetaxpercentage), ''), '0') AS DECIMAL(18,4)) <= 0
                    THEN 1 ELSE 0
                END
            ) AS lines_shipping_tax_missing,
            SUM(CASE WHEN IFNULL(li.vendorbatchnumber, '') = '' THEN 1 ELSE 0 END) AS lines_vendor_batch_missing,
            SUM(CASE WHEN IFNULL(li.batchcode, '') = '' THEN 1 ELSE 0 END) AS lines_uniware_batch_missing,
            SUM(CASE WHEN o.pipeline_status = 'batch_hold' THEN 1 ELSE 0 END) AS order_rows_batch_hold
        FROM `tabUnicommerce Orders` o
        LEFT JOIN `tabOrder Line Items` li
          ON li.parent = o.name
         AND li.parenttype = 'Unicommerce Orders'
        WHERE {where_sql}
        GROUP BY channel
        ORDER BY orders DESC, channel ASC
        """,
        params,
        as_dict=True,
    )

    channels = []
    for row in rows:
        shipping_lines = int(row.get("lines_with_shipping_charge") or 0)
        shipping_tax_missing = int(row.get("lines_shipping_tax_missing") or 0)
        channels.append(
            {
                "channel": row.get("channel") or "Unknown",
                "orders": int(row.get("orders") or 0),
                "lines_with_shipping_charge": shipping_lines,
                "lines_shipping_tax_missing": shipping_tax_missing,
                "shipping_tax_missing_pct": round((shipping_tax_missing * 100.0 / shipping_lines), 2)
                if shipping_lines > 0
                else 0.0,
                "lines_vendor_batch_missing": int(row.get("lines_vendor_batch_missing") or 0),
                "lines_uniware_batch_missing": int(row.get("lines_uniware_batch_missing") or 0),
                "order_rows_batch_hold": int(row.get("order_rows_batch_hold") or 0),
            }
        )

    return {
        "window_days": day_window,
        "statuses": status_list,
        "channels": channels,
        "generated_at": str(now_datetime()),
    }


# ---------------------------------------------------------------------------
# Channel / tax analytics
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_channel_summary(start_date=None, end_date=None) -> dict:
    """Channel, geography, and GST bucket analytics for posted staged orders."""
    posted_rows = _posted_order_rows(start_date=start_date, end_date=end_date)
    settings = frappe.get_single("Unicommerce Settings")

    by_channel: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "channel": "Unknown",
            "cnt": 0,
            "tax_total": 0.0,
            "gap_count": 0,
            "igst_count": 0,
            "cgst_sgst_count": 0,
        }
    )
    by_state: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"state": "Unknown", "cnt": 0, "tax_total": 0.0, "gap_count": 0, "region": "Other"}
    )
    by_region: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"region": "Other", "cnt": 0, "tax_total": 0.0, "states": set()}
    )
    daily_map: dict[str, dict[str, Any]] = defaultdict(lambda: {"day": "", "cnt": 0, "tax_total": 0.0})
    igst = {"cnt": 0, "tax_total": 0.0}
    cgst_sgst = {"cnt": 0, "tax_total": 0.0}

    for row in posted_rows:
        tax_total = float(row.get("tax_actual") or 0)
        gap_count = 1 if float(row.get("tax_diff") or 0) > 1 else 0
        channel = row.get("channel") or "Unknown"
        state = extract_shipping_state(row.get("uc_raw_json")) or "Unknown"
        region = STATE_REGION_MAP.get(state, "Other")
        origin_state_code = resolve_origin_state_code(channel=channel, settings=settings)
        tax_bucket = classify_tax_bucket(
            state if state != "Unknown" else "",
            row.get("payload_json"),
            origin_state_code,
        )

        channel_row = by_channel[channel]
        channel_row["channel"] = channel
        channel_row["cnt"] += 1
        channel_row["tax_total"] += tax_total
        channel_row["gap_count"] += gap_count
        if tax_bucket == "igst":
            channel_row["igst_count"] += 1
        elif tax_bucket == "cgst_sgst":
            channel_row["cgst_sgst_count"] += 1

        state_row = by_state[state]
        state_row["state"] = state
        state_row["cnt"] += 1
        state_row["tax_total"] += tax_total
        state_row["gap_count"] += gap_count
        state_row["region"] = region

        region_row = by_region[region]
        region_row["region"] = region
        region_row["cnt"] += 1
        region_row["tax_total"] += tax_total
        region_row["states"].add(state)

        if tax_bucket == "igst":
            igst["cnt"] += 1
            igst["tax_total"] += tax_total
        elif tax_bucket == "cgst_sgst":
            cgst_sgst["cnt"] += 1
            cgst_sgst["tax_total"] += tax_total

        day_key = str(row.get("order_date") or "")
        day_row = daily_map[day_key]
        day_row["day"] = day_key
        day_row["cnt"] += 1
        day_row["tax_total"] += tax_total

    params: dict[str, Any] = {}
    cn_where_parts = ["status = 'posted'"]
    if start_date:
        cn_where_parts.append("return_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        cn_where_parts.append("return_date <= %(end_date)s")
        params["end_date"] = end_date
    cn_total = frappe.db.sql(
        f"SELECT COUNT(*) AS cnt FROM `tabUC Credit Note Staging` WHERE {' AND '.join(cn_where_parts)}",
        params,
        as_dict=True,
    )

    total = {
        "cnt": len(posted_rows),
        "tax_total": round(sum(float(row.get("tax_actual") or 0) for row in posted_rows), 2),
    }
    by_channel_rows = sorted(by_channel.values(), key=lambda row: (-row["cnt"], row["channel"]))
    by_state_rows = sorted(by_state.values(), key=lambda row: (-row["cnt"], row["state"]))
    by_region_rows = sorted(by_region.values(), key=lambda row: (-row["cnt"], row["region"]))
    daily_rows = sorted(daily_map.values(), key=lambda row: row["day"])

    for row in by_channel_rows + by_state_rows + by_region_rows + daily_rows + [igst, cgst_sgst, total]:
        if "tax_total" in row:
            row["tax_total"] = round(float(row["tax_total"] or 0), 2)
    for row in by_region_rows:
        row["states"] = sorted(state for state in row["states"] if state and state != "Unknown")

    return {
        "by_channel": by_channel_rows,
        "by_state": by_state_rows,
        "by_region": by_region_rows,
        "daily": daily_rows,
        "igst": igst,
        "cgst_sgst": cgst_sgst,
        "total": total,
        "cn_total": int(cn_total[0].cnt if cn_total else 0),
        "start_date": start_date,
        "end_date": end_date,
    }


def _load_cached_json(cache_key: str) -> dict | None:
    raw = frappe.cache().get_value(cache_key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _store_cached_json(cache_key: str, payload: dict, ttl_sec: int) -> dict:
    frappe.cache().set_value(cache_key, json.dumps(payload, default=str), expires_in_sec=ttl_sec)
    return payload


def _safe_parse_json_map(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return raw_value
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _norm_wh_code(value: Any) -> str:
    return str(value or "").strip().upper()


def _norm_wh_key(value: Any) -> str:
    raw = _norm_wh_code(value)
    return "".join(ch for ch in raw if ch.isalnum())


def _tracked_warehouse_codes() -> list[str]:
    settings = frappe.get_single("Unicommerce Settings")
    wh_codes: set[str] = set()

    warehouse_map = _safe_parse_json_map(getattr(settings, "warehouse_map", None))
    channel_warehouse_map = _safe_parse_json_map(getattr(settings, "channel_warehouse_map", None))

    for value in warehouse_map.values():
        code = str(value or "").strip()
        if code:
            wh_codes.add(_norm_wh_code(code))
    for value in channel_warehouse_map.values():
        code = str(value or "").strip()
        if code:
            wh_codes.add(_norm_wh_code(code))

    default_wh = str(getattr(settings, "default_warehouse_code", "") or "").strip()
    if default_wh:
        wh_codes.add(_norm_wh_code(default_wh))

    # If no warehouses found from settings, return empty — do not query Frappe DB.

    return sorted(code for code in wh_codes if code)


def _qty_from_row(row: dict[str, Any]) -> float:
    for key in ("Quantity", "AvailableQuantity", "QuantityOnStock", "QuantityOnHand", "OnHand", "qty", "quantity"):
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value or 0)
        except Exception:
            continue
    return 0.0


def _fetch_live_wh_inventory_from_hana(warehouse_codes: list[str]) -> dict:
    try:
        from khanal_tech_integrations.api.common.sap_connector import SAPConnector

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            if not warehouse_codes:
                return {"rows": [], "source": "hana_batch_inventory"}
            placeholders = ",".join("?" for _ in warehouse_codes)
            query = f"""
                SELECT
                    q."WhsCode" AS whscode,
                    q."ItemCode" AS item_code,
                    b."DistNumber" AS batch_number,
                    q."Quantity" AS qty
                FROM {schema}."OBTQ" q
                JOIN {schema}."OBTN" b
                  ON b."ItemCode" = q."ItemCode"
                 AND b."SysNumber" = q."SysNumber"
                WHERE q."WhsCode" IN ({placeholders})
                  AND q."Quantity" > 0
                ORDER BY q."WhsCode", q."ItemCode", b."DistNumber"
                LIMIT 120000
            """
            cursor.execute(query, warehouse_codes)
            rows = cursor.fetchall() or []
            out = []
            for row in rows:
                out.append(
                    {
                        "warehouse_code": _norm_wh_code(row[0]),
                        "item_code": str(row[1] or "").strip(),
                        "batch_number": str(row[2] or "").strip(),
                        "available_qty": float(row[3] or 0),
                    }
                )
            return {"rows": out, "source": "hana_batch_inventory"}
        finally:
            connector.close_hana_connection(connection, cursor)
    except Exception:
        return {"rows": [], "source": "hana_batch_inventory"}


def _fetch_live_wh_inventory_from_sap(warehouse_codes: list[str]) -> dict:
    """Fetch live batch inventory from SAP HANA for the given warehouses."""
    return _fetch_live_wh_inventory_from_hana(warehouse_codes)


@frappe.whitelist()
def ops_warehouse_live_inventory(refresh: int = 0, limit_per_warehouse: int = 400) -> dict:
    refresh = bool(int(refresh or 0))
    if not refresh:
        cached = _load_cached_json(WAREHOUSE_INVENTORY_CACHE_KEY)
        if cached:
            return cached

    warehouse_codes = _tracked_warehouse_codes()
    if not warehouse_codes:
        payload = {
            "warehouse_count": 0,
            "warehouses": [],
            "generated_at": str(now_datetime()),
            "message": "No SAP warehouses mapped in Unicommerce Settings yet.",
            "source": "none",
        }
        return _store_cached_json(WAREHOUSE_INVENTORY_CACHE_KEY, payload, ttl_sec=120)

    limit_per_warehouse = min(max(int(limit_per_warehouse or 400), 50), 2000)
    live = _fetch_live_wh_inventory_from_sap(warehouse_codes)
    grouped: dict[str, list[dict[str, Any]]] = {wh: [] for wh in warehouse_codes}
    for row in live.get("rows") or []:
        wh = _norm_wh_code(row.get("warehouse_code"))
        if wh in grouped and float(row.get("available_qty") or 0) > 0:
            grouped[wh].append(
                {
                    "item_code": row.get("item_code"),
                    "batch_number": row.get("batch_number"),
                    "available_qty": round(float(row.get("available_qty") or 0), 3),
                }
            )

    warehouses = []
    for wh in warehouse_codes:
        rows = sorted(
            grouped.get(wh) or [],
            key=lambda r: (
                -(float(r.get("available_qty") or 0)),
                str(r.get("item_code") or ""),
                str(r.get("batch_number") or ""),
            ),
        )
        warehouses.append(
            {
                "warehouse_code": wh,
                "row_count": len(rows),
                "rows": rows[:limit_per_warehouse],
            }
        )

    payload = {
        "warehouse_count": len(warehouses),
        "warehouses": warehouses,
        "generated_at": str(now_datetime()),
        "source": live.get("source") or "unknown",
    }
    return _store_cached_json(WAREHOUSE_INVENTORY_CACHE_KEY, payload, ttl_sec=120)


def _inventory_parity_snapshot(refresh: bool = False) -> dict:
    if not refresh:
        cached = _load_cached_json(INVENTORY_PARITY_CACHE_KEY)
        if cached:
            return cached

    warehouse_code = "EC-FG"
    live = _fetch_live_wh_inventory_from_sap([warehouse_code])
    by_item: dict[str, dict[str, Any]] = {}
    for row in (live.get("rows") or []):
        item_code = str(row.get("item_code") or "").strip()
        batch_number = str(row.get("batch_number") or "").strip()
        qty = round(float(row.get("available_qty") or 0), 3)
        if not item_code or qty <= 0:
            continue
        target = by_item.setdefault(
            item_code,
            {"item_code": item_code, "sap_qty": 0.0, "sap_batches": {}},
        )
        target["sap_qty"] = round(float(target.get("sap_qty") or 0) + qty, 3)
        if batch_number:
            target["sap_batches"][batch_number] = round(
                float(target["sap_batches"].get(batch_number, 0)) + qty, 3
            )

    items = sorted(by_item.values(), key=lambda r: r.get("item_code") or "")
    sap_snapshot = {
        "warehouse_code": warehouse_code,
        "item_count": len(items),
        "items": items,
        "source": live.get("source") or "live_sap_inventory",
    }
    if not items:
        payload = {
            "warehouse_code": warehouse_code,
            "scope": "sap_ec_fg_tracked",
            "matched_count": 0,
            "mismatch_count": 0,
            "item_count": 0,
            "rows": [],
            "source": sap_snapshot.get("source") or "inventory_in_whse",
            "message": "No SAP EC-FG inventory snapshot rows are currently available on this site.",
            "generated_at": str(now_datetime()),
        }
        return _store_cached_json(INVENTORY_PARITY_CACHE_KEY, payload, ttl_sec=900)

    uc = UCClient()
    uc.login()
    facility = (uc._resolve_facility_codes() or [uc.facility_code or "kfl_ecom_warehouse"])[0]

    matched_count = 0
    mismatches = []
    comparison_rows = []
    total_delta = 0.0

    for item in items:
        inventory_rows = uc.get_item_type_inventory(item["item_code"], facility=facility)
        uc_summary = UCClient.summarize_inventory_rows(inventory_rows)
        sap_batches = item.get("sap_batches") or {}
        uc_batches = uc_summary.get("uc_batches") or {}
        batch_keys = sorted(set(sap_batches) | set(uc_batches))
        batch_rows = []
        batch_mismatch_count = 0
        for batch_key in batch_keys:
            sap_qty = round(float(sap_batches.get(batch_key) or 0), 3)
            uc_qty = round(float(uc_batches.get(batch_key) or 0), 3)
            delta_qty = round(uc_qty - sap_qty, 3)
            if abs(delta_qty) > 0.001:
                batch_mismatch_count += 1
            batch_rows.append(
                {
                    "batch_number": batch_key,
                    "sap_qty": sap_qty,
                    "uc_qty": uc_qty,
                    "delta_qty": delta_qty,
                }
            )

        delta_qty = round(float(uc_summary.get("uc_good_qty") or 0) - float(item.get("sap_qty") or 0), 3)
        total_delta += delta_qty
        row = {
            "item_code": item["item_code"],
            "sap_qty": round(float(item.get("sap_qty") or 0), 3),
            "uc_qty": round(float(uc_summary.get("uc_good_qty") or 0), 3),
            "uc_total_qty": round(float(uc_summary.get("uc_total_qty") or 0), 3),
            "delta_qty": delta_qty,
            "batch_mismatch_count": batch_mismatch_count,
            "uc_inventory_types": uc_summary.get("uc_inventory_types") or {},
            "batches": batch_rows,
        }
        comparison_rows.append(row)
        if abs(delta_qty) > 0.001 or batch_mismatch_count:
            mismatches.append(row)
        else:
            matched_count += 1

    mismatches.sort(
        key=lambda row: (
            abs(float(row.get("delta_qty") or 0)),
            int(row.get("batch_mismatch_count") or 0),
            row.get("item_code") or "",
        ),
        reverse=True,
    )

    payload = {
        "warehouse_code": warehouse_code,
        "facility_code": facility,
        "scope": "sap_ec_fg_tracked",
        "source": sap_snapshot.get("source") or "inventory_in_whse",
        "matched_count": matched_count,
        "mismatch_count": len(mismatches),
        "item_count": len(items),
        "total_delta_qty": round(total_delta, 3),
        "rows": mismatches[:150],
        "comparison_rows": comparison_rows[:5000],
        "generated_at": str(now_datetime()),
    }
    return _store_cached_json(INVENTORY_PARITY_CACHE_KEY, payload, ttl_sec=900)


@frappe.whitelist()
def ops_inventory_parity(refresh: int = 0) -> dict:
    try:
        return _inventory_parity_snapshot(refresh=bool(int(refresh or 0)))
    except Exception as e:
        cached = _load_cached_json(INVENTORY_PARITY_CACHE_KEY) or {}
        return {
            **cached,
            "error": str(e)[:500],
            "generated_at": cached.get("generated_at") or str(now_datetime()),
            "rows": cached.get("rows") or [],
        }


@frappe.whitelist()
def refresh_inventory_parity(force: int = 1) -> dict:
    return ops_inventory_parity(refresh=force)


@frappe.whitelist()
def ops_inventory_match_view(
    refresh: int = 0,
    item_code: str | None = None,
    batch_number: str | None = None,
    limit: int = 200,
) -> dict:
    """
    EC-FG (SAP) vs Unicommerce facility inventory comparison view.
    Keeps implementation minimal by reusing ops_inventory_parity payload.
    """
    payload = ops_inventory_parity(refresh=refresh)
    all_rows = list(payload.get("comparison_rows") or payload.get("rows") or [])

    item_term = str(item_code or "").strip().upper()
    batch_term = str(batch_number or "").strip().upper()
    filtered_rows = list(all_rows)
    if item_term:
        filtered_rows = [row for row in filtered_rows if item_term in str(row.get("item_code") or "").upper()]
    if batch_term:
        filtered_rows = [
            row
            for row in filtered_rows
            if any(batch_term in str(batch.get("batch_number") or "").upper() for batch in (row.get("batches") or []))
        ]

    safe_limit = min(max(int(limit or 200), 20), 1000)
    sap_rows: list[dict[str, Any]] = []
    uc_rows: list[dict[str, Any]] = []
    for row in filtered_rows:
        item = row.get("item_code")
        batch_rows = row.get("batches") or []
        uc_row_added = False
        if batch_rows:
            for batch in batch_rows:
                batch_number = str(batch.get("batch_number") or "").strip()
                sap_qty = round(float(batch.get("sap_qty") or 0), 3)
                uc_qty = round(float(batch.get("uc_qty") or 0), 3)
                if sap_qty > 0:
                    sap_rows.append(
                        {
                            "item_code": item,
                            "batch_number": batch_number,
                            "sap_qty": sap_qty,
                        }
                    )
                if uc_qty > 0:
                    uc_rows.append(
                        {
                            "item_code": item,
                            "batch_number": batch_number,
                            "uc_qty": uc_qty,
                        }
                    )
                    uc_row_added = True
            # UC API may return item-level GOOD qty without batch-level breakup.
            if not uc_row_added:
                uc_total = round(float(row.get("uc_qty") or 0), 3)
                if uc_total > 0:
                    uc_rows.append(
                        {
                            "item_code": item,
                            "batch_number": "NO_BATCH_FROM_UC",
                            "uc_qty": uc_total,
                        }
                    )
        else:
            sap_qty = round(float(row.get("sap_qty") or 0), 3)
            uc_qty = round(float(row.get("uc_qty") or 0), 3)
            if sap_qty > 0:
                sap_rows.append(
                    {
                        "item_code": item,
                        "batch_number": "",
                        "sap_qty": sap_qty,
                    }
                )
            if uc_qty > 0:
                uc_rows.append(
                    {
                        "item_code": item,
                        "batch_number": "",
                        "uc_qty": uc_qty,
                    }
                )
    mismatch_rows = [
        row
        for row in filtered_rows
        if abs(float(row.get("delta_qty") or 0)) > 0.001 or int(row.get("batch_mismatch_count") or 0) > 0
    ]
    sap_rows.sort(
        key=lambda row: (
            -(float(row.get("sap_qty") or 0)),
            row.get("item_code") or "",
            row.get("batch_number") or "",
        )
    )
    uc_rows.sort(
        key=lambda row: (
            -(float(row.get("uc_qty") or 0)),
            row.get("item_code") or "",
            row.get("batch_number") or "",
        )
    )
    mismatch_rows.sort(
        key=lambda row: (
            -abs(float(row.get("delta_qty") or 0)),
            -(int(row.get("batch_mismatch_count") or 0)),
            row.get("item_code") or "",
        )
    )
    return {
        "warehouse_code": payload.get("warehouse_code") or "EC-FG",
        "facility_code": payload.get("facility_code") or "",
        "source": payload.get("source") or "unknown",
        "generated_at": payload.get("generated_at") or str(now_datetime()),
        "matched_count": int(payload.get("matched_count") or 0),
        "mismatch_count": int(payload.get("mismatch_count") or 0),
        "item_count": int(payload.get("item_count") or 0),
        "total_delta_qty": float(payload.get("total_delta_qty") or 0),
        "filters": {"item_code": item_code or "", "batch_number": batch_number or "", "limit": safe_limit},
        "sap_rows": sap_rows[:safe_limit],
        "uc_rows": uc_rows[:safe_limit],
        "mismatch_rows": mismatch_rows[:safe_limit],
    }


@frappe.whitelist()
def ops_transfer_summary(start_date=None, end_date=None) -> dict:
    params: dict[str, Any] = {}
    where_parts = ["towarehouse = 'EC-FG'"]
    if start_date:
        where_parts.append("docdate >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        where_parts.append("docdate <= %(end_date)s")
        params["end_date"] = end_date

    summary_rows = frappe.db.sql(
        f"""
        SELECT
            docdate,
            uniware_po_id,
            uniware_po_status,
            unicommerce_sync_status
        FROM `tabSAP Inventory Transfers`
        WHERE {' AND '.join(where_parts)}
        ORDER BY docdate desc, modified desc
        """,
        params,
        as_dict=True,
    )

    recent = frappe.db.sql(
        f"""
        SELECT
            name,
            docnum,
            docdate,
            fromwarehouse,
            towarehouse,
            uniware_po_id,
            uniware_po_status,
            unicommerce_sync_status,
            comments,
            modified
        FROM `tabSAP Inventory Transfers`
        WHERE {' AND '.join(where_parts)}
        ORDER BY docdate desc, modified desc
        LIMIT 120
        """,
        params,
        as_dict=True,
    )

    total = len(summary_rows)
    po_created = 0
    posted_to_uc = 0
    failed = 0
    partial = 0
    pending = 0
    grn_completed = 0
    approved = 0

    daily_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"day": "", "total": 0, "posted": 0, "failed": 0, "pending": 0}
    )

    completed_statuses = {"GRN_COMPLETED", "COMPLETE", "COMPLETED", "CLOSED"}

    for row in summary_rows:
        sync_status = str(row.get("unicommerce_sync_status") or "").strip()
        po_status = str(row.get("uniware_po_status") or "").strip().upper()
        if row.get("uniware_po_id"):
            po_created += 1
        if po_status == "APPROVED":
            approved += 1
        if po_status in completed_statuses:
            grn_completed += 1
        if sync_status in ("Synced", "Partial") or po_status in completed_statuses:
            posted_to_uc += 1
        if sync_status == "Failed":
            failed += 1
        elif sync_status == "Partial":
            partial += 1
        elif sync_status in ("", "Pending"):
            pending += 1

        day_key = str(row.get("docdate") or "")
        day_row = daily_map[day_key]
        day_row["day"] = day_key
        day_row["total"] += 1
        if sync_status == "Failed":
            day_row["failed"] += 1
        elif sync_status in ("Synced", "Partial") or po_status in completed_statuses:
            day_row["posted"] += 1
        else:
            day_row["pending"] += 1

    return {
        "total_to_ec_fg": total,
        "po_created": po_created,
        "approved": approved,
        "grn_completed": grn_completed,
        "posted_to_unicommerce": posted_to_uc,
        "failed": failed,
        "partial": partial,
        "pending": pending,
        "daily": sorted(daily_map.values(), key=lambda row: row["day"]),
        "rows": recent[:40],
        "generated_at": str(now_datetime()),
    }


@frappe.whitelist()
def ops_monthly_tax_reconciliation(months: int = 6) -> dict:
    """Heavy per-month tax reconciliation query; System Manager only.

    Caps the lookback window to 24 months and restricts to System Manager to
    avoid any logged-in user triggering a multi-million-row scan of
    ``order_json`` / ``payload_json`` blobs via the API.
    """
    frappe.only_for("System Manager")
    months = max(min(int(months or 6), 24), 1)
    start_date = add_to_date(now_datetime().date().replace(day=1), months=-(months - 1))
    rows = frappe.db.sql(
        """
        SELECT
            channel_name AS channel,
            order_date,
            order_json AS uc_raw_json,
            payload_json,
            ar_invoice_tax_expected AS tax_expected,
            ar_invoice_tax_actual AS tax_actual,
            ar_invoice_unit_price_expected AS unit_price_expected,
            ar_invoice_unit_price_actual AS unit_price_actual
        FROM `tabUnicommerce Orders`
        WHERE pipeline_status = 'posted' AND order_date >= %(start_date)s
        ORDER BY order_date asc
        """,
        {"start_date": start_date},
        as_dict=True,
    )

    monthly_map: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "month": "",
            "month_label": "",
            "channel": "Unknown",
            "orders": 0,
            "uc_taxable_total": 0.0,
            "sap_taxable_total": 0.0,
            "uc_igst_tax_total": 0.0,
            "sap_igst_tax_total": 0.0,
            "uc_cgst_sgst_tax_total": 0.0,
            "sap_cgst_sgst_tax_total": 0.0,
        }
    )

    for row in rows:
        channel = row.get("channel") or "Unknown"
        order_date = str(row.get("order_date") or "")
        month_key = order_date[:7]
        if not month_key:
            continue
        bucket = classify_tax_bucket(
            extract_shipping_state(row.get("uc_raw_json")),
            row.get("payload_json"),
            resolve_origin_state_code(channel),
        )
        key = (month_key, channel)
        target = monthly_map[key]
        target["month"] = month_key
        target["month_label"] = get_datetime(f"{month_key}-01").strftime("%b %Y")
        target["channel"] = channel
        target["orders"] += 1
        target["uc_taxable_total"] += float(row.get("unit_price_expected") or 0)
        target["sap_taxable_total"] += float(row.get("unit_price_actual") or 0)
        if bucket == "igst":
            target["uc_igst_tax_total"] += float(row.get("tax_expected") or 0)
            target["sap_igst_tax_total"] += float(row.get("tax_actual") or 0)
        else:
            target["uc_cgst_sgst_tax_total"] += float(row.get("tax_expected") or 0)
            target["sap_cgst_sgst_tax_total"] += float(row.get("tax_actual") or 0)

    result_rows = []
    for row in monthly_map.values():
        row["uc_taxable_total"] = round(float(row["uc_taxable_total"] or 0), 2)
        row["sap_taxable_total"] = round(float(row["sap_taxable_total"] or 0), 2)
        row["taxable_diff"] = round(row["sap_taxable_total"] - row["uc_taxable_total"], 2)
        row["uc_igst_tax_total"] = round(float(row["uc_igst_tax_total"] or 0), 2)
        row["sap_igst_tax_total"] = round(float(row["sap_igst_tax_total"] or 0), 2)
        row["igst_diff"] = round(row["sap_igst_tax_total"] - row["uc_igst_tax_total"], 2)
        row["uc_cgst_sgst_tax_total"] = round(float(row["uc_cgst_sgst_tax_total"] or 0), 2)
        row["sap_cgst_sgst_tax_total"] = round(float(row["sap_cgst_sgst_tax_total"] or 0), 2)
        row["cgst_sgst_diff"] = round(row["sap_cgst_sgst_tax_total"] - row["uc_cgst_sgst_tax_total"], 2)
        row["total_tax_diff"] = round(row["igst_diff"] + row["cgst_sgst_diff"], 2)
        result_rows.append(row)

    result_rows.sort(key=lambda row: (row["month"], row["channel"]))
    top_drift_rows = sorted(
        result_rows,
        key=lambda row: (
            abs(float(row.get("taxable_diff") or 0))
            + abs(float(row.get("total_tax_diff") or 0))
        ),
        reverse=True,
    )[:20]

    return {
        "months": sorted({row["month"] for row in result_rows}),
        "rows": result_rows,
        "top_drift_rows": top_drift_rows,
        "generated_at": str(now_datetime()),
    }


def _parse_ymd_or_ddmmyyyy(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) != 10:
        frappe.throw("Date format must be DD-MM-YYYY or YYYY-MM-DD")
    if s[2] == "-" and s[5] == "-":
        dt = get_datetime(f"{s[6:10]}-{s[3:5]}-{s[0:2]}")
        return dt.strftime("%Y-%m-%d")
    if s[4] == "-" and s[7] == "-":
        dt = get_datetime(s)
        return dt.strftime("%Y-%m-%d")
    frappe.throw("Date format must be DD-MM-YYYY or YYYY-MM-DD")
    return None


# ---------------------------------------------------------------------------
# GST Reconciliation (Ops Center → Reconciliation tab)
#
# The legacy "monthly reconciliation" flow (ops_monthly_reconciliation_report,
# run_monthly_reconciliation_auto, ops_monthly_reconciliation_download_last_run,
# etc.) has been replaced by a user-driven GST reconciliation that requires the
# operator to pick start + end dates in a modal. The orchestrator lives in
# unicommerce/reporting/gst_recon.py.
# ---------------------------------------------------------------------------


def _normalize_recon_date(value: str | None, *, label: str) -> str:
    parsed = _parse_ymd_or_ddmmyyyy(value)
    if not parsed:
        frappe.throw(f"{label} is required and must be DD-MM-YYYY or YYYY-MM-DD")
    return parsed


_GST_RECON_JOB_NAME = "gst_reconciliation"
_GST_RECON_INFLIGHT_STATUSES = {"queued", "running"}
# Max individual workbook size we'll push through a single Frappe File save
# (anything bigger is almost certainly a bug — real workbooks are 1–5 MB).
_GST_RECON_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if not _EMAIL_RE.match(text):
        frappe.throw(f"Invalid email address: {text!r}")
    return text


@frappe.whitelist()
def gst_reconciliation_run_async(
    start_date: str,
    end_date: str,
    email_to: str | None = None,
    force: int | bool = 0,
    posted_only: int | bool = 0,
    compare_mode: str = "finance_month",
) -> dict:
    """Queue the UC vs SAP GST reconciliation for the given window.

    Returns immediately so the Desk page does not time out. Live progress is
    polled via ``gst_reconciliation_status``; the final workbook is fetched
    via ``gst_reconciliation_download_last_run``.

    Args:
      start_date / end_date: DD-MM-YYYY or YYYY-MM-DD. Must be System Manager.
      email_to: optional recipient for a summary email (with xlsx attached)
        fired on successful completion. Failures are surfaced in the UI, not
        in email.
      force: pass ``1`` to override the concurrency guard that normally
        rejects a second run while another is queued/running.
      posted_only: pass ``1`` to restrict the per-order comparison to only
        orders that were posted from Unicommerce to SAP (pipeline_status=posted).
      compare_mode: ``finance_month`` (SAP DocDate strict) or
        ``order_id_trace`` (order-id anchored, widened SAP query window).

    Auth: System Manager only (aligns with the Ops Center page permissions).
    """
    frappe.only_for("System Manager")

    from ..reporting.gst_recon import (
        GST_RECON_LAST_RUN_CACHE_KEY,
        get_last_run_snapshot,
        run_gst_reconciliation,  # noqa: F401 — referenced by string in enqueue
    )

    start_iso = _normalize_recon_date(start_date, label="Start date")
    end_iso = _normalize_recon_date(end_date, label="End date")
    if start_iso > end_iso:
        frappe.throw("Start date must be on or before End date")

    clean_email = _normalize_email(email_to)
    force_flag = str(force).lower() in {"1", "true", "yes", "on"}
    posted_only_flag = str(posted_only).lower() in {"1", "true", "yes", "on"}
    compare_mode_key = str(compare_mode or "finance_month").strip().lower()
    if compare_mode_key not in {"finance_month", "order_id_trace"}:
        frappe.throw("Invalid compare_mode. Use finance_month or order_id_trace.")
    if compare_mode_key == "order_id_trace":
        posted_only_flag = True

    # Concurrency guard — refuse if another run is still queued/running.
    # The snapshot TTL is 4h for in-flight states so a dead worker unblocks
    # itself naturally.
    if not force_flag:
        current = get_last_run_snapshot() or {}
        if (current.get("status") or "").lower() in _GST_RECON_INFLIGHT_STATUSES:
            window = current.get("window") or {}
            frappe.throw(
                "A GST Reconciliation is already "
                f"{current.get('status')} for {window.get('start_date', '?')} → "
                f"{window.get('end_date', '?')} (started {current.get('generated_at', '?')}). "
                "Wait for it to finish, or call with force=1 to override."
            )

    queued_snapshot = {
        "status": "queued",
        "job": "run_gst_reconciliation",
        "window": {"start_date": start_iso, "end_date": end_iso},
        "email_to": clean_email,
        "posted_only": posted_only_flag,
        "compare_mode": compare_mode_key,
        "queued_by": frappe.session.user,
        "generated_at": str(now_datetime()),
    }
    # Match the in-flight TTL used by gst_recon._cache_snapshot so a stuck
    # "queued" snapshot naturally expires.
    frappe.cache().set_value(
        GST_RECON_LAST_RUN_CACHE_KEY,
        json.dumps(queued_snapshot, default=str),
        expires_in_sec=4 * 60 * 60,
    )
    frappe.enqueue(
        "khanal_tech_integrations.unicommerce.reporting.gst_recon.run_gst_reconciliation",
        job_name=_GST_RECON_JOB_NAME,
        queue="long",
        timeout=2 * 60 * 60,
        enqueue_after_commit=True,
        start_date=start_iso,
        end_date=end_iso,
        email_to=clean_email,
        posted_only=posted_only_flag,
        compare_mode=compare_mode_key,
    )
    return queued_snapshot


@frappe.whitelist()
def gst_reconciliation_status() -> dict:
    """Return the cached GST Reconciliation snapshot (running / matched / mismatch / error).

    Filesystem absolute paths are stripped from the response — the UI only
    needs ``filename`` to decide whether the download button is enabled and
    ``gst_reconciliation_download_last_run`` handles the actual file read
    server-side.

    Auth: System Manager only.
    """
    frappe.only_for("System Manager")
    from ..reporting.gst_recon import get_last_run_snapshot

    snap = get_last_run_snapshot() or {}
    file_info = snap.get("file")
    if isinstance(file_info, dict):
        snap = dict(snap)
        snap["file"] = {k: v for k, v in file_info.items() if k not in {"absolute_path", "directory"}}
    # Strip the UC export absolute path too (internal bench path, not
    # useful to any client — the download endpoint handles the actual file).
    meta = snap.get("uc_export_meta")
    if isinstance(meta, dict):
        snap.setdefault("uc_export_meta", dict(meta))
        snap["uc_export_meta"].pop("excel_path", None)
    return snap


@frappe.whitelist()
def gst_reconciliation_download_last_run() -> dict:
    """Attach the last-saved GST Reconciliation workbook as a Frappe File and return its URL.

    Uses ``shutil.copyfileobj`` to stream from the on-disk workbook into the
    Frappe File location without loading the whole thing into RAM. The server
    absolute path is **not** returned — only the public ``file_url`` + name.

    Auth: System Manager only.
    """
    frappe.only_for("System Manager")

    from frappe.utils.file_manager import save_file

    from ..reporting.gst_recon import get_last_run_file

    file_info = get_last_run_file() or {}
    abs_path = file_info.get("absolute_path") or ""
    if not abs_path or not os.path.exists(abs_path):
        frappe.throw("No GST Reconciliation workbook is available yet. Run a reconciliation first.")

    size = os.path.getsize(abs_path)
    if size > _GST_RECON_MAX_DOWNLOAD_BYTES:
        frappe.throw(
            f"Workbook is too large to attach ({size // 1024 // 1024} MB). "
            "Contact your administrator."
        )

    filename = file_info.get("filename") or os.path.basename(abs_path)
    with open(abs_path, "rb") as fh:
        content = fh.read()
    saved = save_file(filename, content, None, None, is_private=1)
    return {
        "file_url": saved.file_url,
        "file_name": saved.file_name,
    }


_GST_PER_ORDER_STATUSES = {
    "matched",
    "amount_mismatch",
    "missing_in_sap",
    "not_posted",
    "missing_in_uc",
    "uc_order_outside_export_window",
}


@frappe.whitelist()
def gst_reconciliation_per_order(
    status: str | None = None,
    reason_code: str | None = None,
    channel: str | None = None,
    search: str | None = None,
    start: int = 0,
    page_size: int = 50,
) -> dict:
    """Paginated access to the per-order diff of the last GST reconciliation.

    Filters:
      status       — one of matched/amount_mismatch/missing_in_sap/not_posted/missing_in_uc
      reason_code  — for status=missing_in_sap: failed/batch_hold/verify/ready/
                     posting/dead/not_ingested/posted_outside_window/
                     posted_no_docnum/unknown
      channel      — substring match on the channel column
      search       — substring match on order_id / sap_docnum / last_error

    The actionable rows (anything not `matched`) are cached with the snapshot;
    rows with `status=matched` are only available from the downloadable
    workbook and will not appear here.

    Auth: System Manager only.
    """
    frappe.only_for("System Manager")
    from ..reporting.gst_recon import get_last_run_snapshot

    try:
        start = max(int(start or 0), 0)
    except Exception:
        start = 0
    try:
        page_size = max(1, min(int(page_size or 50), 500))
    except Exception:
        page_size = 50

    snap = get_last_run_snapshot() or {}
    po = snap.get("per_order") or {}
    rows = list(po.get("rows") or [])

    def _matches(row: dict) -> bool:
        row_status = row.get("status") or ""
        if status and status in _GST_PER_ORDER_STATUSES:
            if row_status != status:
                return False
        elif not status:
            # Default "All actionable" — exclude matched and informational cross-period rows
            if row_status in ("matched", "uc_order_outside_export_window"):
                return False
        if reason_code and (row.get("reason_code") or "") != reason_code:
            return False
        if channel:
            if channel.lower() not in str(row.get("channel") or "").lower():
                return False
        if search:
            needle = search.strip().lower()
            haystack = " ".join(
                str(row.get(k) or "")
                for k in ("order_id", "sap_docnum", "last_error", "sap_customer_name", "uc_order_name")
            ).lower()
            if needle and needle not in haystack:
                return False
        return True

    filtered = [r for r in rows if _matches(r)]
    total_filtered = len(filtered)
    page = filtered[start : start + page_size]

    return {
        "window": snap.get("window") or {},
        "status": snap.get("status"),
        "posted_only": bool(snap.get("posted_only")),
        "summary": po.get("summary") or {},
        "actionable_count": int(po.get("actionable_count") or 0),
        "total_rows": int(po.get("total_rows") or 0),
        "filtered_total": total_filtered,
        "start": start,
        "page_size": page_size,
        "rows": page,
    }



@frappe.whitelist()
def ops_reconciliation_all() -> dict:
    """Reconciliation across all stages: invoice gaps, GRN drift, inventory drift."""
    out: dict[str, Any] = {}
    try:
        out["invoice_gaps"] = _invoice_gap_rows(limit=200)
    except Exception as e:
        out["invoice_gaps_error"] = str(e)[:300]

    cutoff_2h = add_to_date(now_datetime(), hours=-2)
    out["grn_drift"] = frappe.get_all(
        INVENTORY_DOCTYPE,
        filters={
            "uniware_po_status": "APPROVED",
            "modified": ["<", cutoff_2h],
            "towarehouse": "EC-FG",
        },
        fields=["name", "docnum", "uniware_po_id", "modified"],
        order_by="modified asc",
        limit=50,
    )
    out["inventory_drift"] = frappe.get_all(
        INVENTORY_DOCTYPE,
        filters={
            "unicommerce_sync_status": ["in", ["Pending", "Failed", "Partial"]],
            "modified": ["<", cutoff_2h],
        },
        fields=["name", "docnum", "unicommerce_sync_status", "modified", "comments"],
        order_by="modified asc",
        limit=50,
    )
    return out


@frappe.whitelist()
def ops_reconciliation_frappe_snapshot() -> dict:
    """Return reconciliation views from current Frappe snapshot fields."""
    return {
        **ops_reconciliation_all(),
        "reconciliation_mode": "frappe_snapshot",
        "reconciled_at": str(now_datetime()),
    }


@frappe.whitelist()
def ops_reconciliation_live_sap() -> dict:
    """Run a fresh SAP-backed refresh (invoices + credit notes), then return reconciliation views."""
    from ..validators.reconcile import run_reconciliation_refresh

    result = run_reconciliation_refresh()
    frappe.db.commit()
    return {
        **ops_reconciliation_all(),
        "reconciliation_mode": "live_sap",
        "reconciled_at": str(now_datetime()),
        "refresh_stats": result,
    }


@frappe.whitelist()
def ops_backfill_cn_reconciliation(limit: int = 500) -> dict:
    """
    One-time backfill: populate ar_creditnote_* reconciliation fields on Unicommerce Orders
    for all already-posted credit notes that have ar_creditnote_unit_price_expected = 0.
    Safe to call multiple times — skips records already populated.
    Callable from Ops Center or bench console.
    """
    from ..workers.credit_note import backfill_cn_reconciliation
    return backfill_cn_reconciliation(limit=int(limit))


@frappe.whitelist()
def ops_diagnose_order(order_name: str) -> dict:
    """
    On-demand deep-dive reconciliation for a single Unicommerce order.

    Fetches both the Frappe staging doc and the live SAP AR Invoice / AR Credit Note,
    then produces a structured, line-by-line breakdown explaining exactly why the
    UC expected totals differ from what SAP recorded.

    Returns
    -------
    {
        "order": "<name>",
        "invoice": {
            "matched": bool,
            "expected_unit": float, "actual_unit": float, "unit_diff": float,
            "expected_tax":  float, "actual_tax":  float, "tax_diff":  float,
            "mismatch_reason": str,
            "line_comparison": [
                {
                    "sku": str, "qty": float,
                    "uc_unit_price": float,
                    "sap_unit_price": float,
                    "unit_diff": float,
                    "uc_discount_total": float,
                    "uc_tax_pct": int,
                    "sap_tax_code": str,
                    "issue": str | None,   # "unit_price" | "missing_in_sap" | None
                },
                ...
            ],
            "sap_extra_lines": [...],   # SAP lines with no UC counterpart
            "root_causes": [str, ...]   # categorised explanations
        },
        "credit_note": { ... } | None,
        "error": str | None
    }
    """
    frappe.only_for("System Manager")
    from ..validators.reconcile import (
        _actual_invoice,
        _actual_credit_note,
        _expected_invoice_total,
        _expected_credit_total,
        _diagnose_invoice_mismatch,
        _diagnose_cn_mismatch,
        _to_float,
        _is_returned_line,
    )

    order_doc = frappe.get_doc("Unicommerce Orders", order_name)
    sap = SAPClient()

    result: dict = {"order": order_name, "invoice": None, "credit_note": None, "error": None}

    # ── AR Invoice ──────────────────────────────────────────────────────────
    de_inv = str(order_doc.sap_ar_invoice_docentry or "").strip()
    if de_inv:
        try:
            expected_unit, expected_tax = _expected_invoice_total(order_doc)
            actual_unit, actual_tax, raw_inv = _actual_invoice(sap, de_inv, uc_order_id=order_doc.name)
            unit_diff = round(abs(expected_unit - actual_unit), 2)
            tax_diff  = round(abs(expected_tax - actual_tax), 2)
            is_matched = unit_diff <= 1.0 and tax_diff <= 1.0

            sap_lines = raw_inv.get("DocumentLines") or []
            order_id  = str(order_doc.name)
            filtered_sap = [
                ln for ln in sap_lines
                if str(ln.get("U_Order") or "") == order_id
            ] or sap_lines

            sap_pool = list(filtered_sap)
            line_comparison: list[dict] = []
            root_causes: list[str] = []
            total_discount = 0.0

            for oli in (order_doc.line_items or []):
                sku  = str(getattr(oli, "itemcode", "") or "")
                qty  = _to_float(getattr(oli, "quantity", 0))
                selling = _to_float(getattr(oli, "sellingpricewithouttaxesanddiscount", 0))
                disc = _to_float(getattr(oli, "discount", 0))
                total_discount += disc
                per_unit_disc = (disc / qty) if qty > 0 else 0.0
                exp_up = round(max(0.0, selling - per_unit_disc), 4)

                uni_igst = _to_float(getattr(oli, "integratedgstpercentage", 0))
                uni_cgst_sgst = _to_float(getattr(oli, "state_gst_tax_percentage", 0)) + \
                                _to_float(getattr(oli, "central_gst_tax_percentage", 0))
                uc_tax_pct = int(max(uni_igst, uni_cgst_sgst))

                matched_sap = None
                for idx, sl in enumerate(sap_pool):
                    if str(sl.get("ItemCode") or "") == sku and abs(_to_float(sl.get("Quantity")) - qty) <= 0.01:
                        matched_sap = sap_pool.pop(idx)
                        break

                if matched_sap is None:
                    line_comparison.append({
                        "sku": sku, "qty": qty,
                        "uc_unit_price": exp_up, "sap_unit_price": None,
                        "unit_diff": None,
                        "uc_discount_total": disc, "uc_tax_pct": uc_tax_pct,
                        "sap_tax_code": None,
                        "issue": "missing_in_sap",
                    })
                    root_causes.append(f"SKU {sku} (qty={qty:.0f}) is in UC order but has no matching SAP line")
                else:
                    sap_up = round(_to_float(matched_sap.get("UnitPrice")), 4)
                    ldiff  = round(abs(exp_up - sap_up), 4)
                    issue  = "unit_price" if ldiff > 0.05 else None
                    entry  = {
                        "sku": sku, "qty": qty,
                        "uc_unit_price": exp_up, "sap_unit_price": sap_up,
                        "unit_diff": ldiff,
                        "uc_discount_total": disc, "uc_tax_pct": uc_tax_pct,
                        "sap_tax_code": matched_sap.get("TaxCode") or "",
                        "issue": issue,
                    }
                    if issue == "unit_price":
                        if abs(ldiff * qty - disc) <= 1.0 and disc > 0:
                            entry["root_cause"] = f"discount ₹{disc:.2f} not applied in SAP"
                            root_causes.append(
                                f"SKU {sku}: SAP UnitPrice ₹{sap_up:.2f} vs UC ₹{exp_up:.2f} — "
                                f"discount ₹{disc:.2f} (total) likely not reflected"
                            )
                        else:
                            entry["root_cause"] = f"price mismatch Δ₹{ldiff:.4f}"
                            root_causes.append(f"SKU {sku}: price mismatch — UC ₹{exp_up:.2f} SAP ₹{sap_up:.2f}")
                    line_comparison.append(entry)

            sap_extra = [
                {
                    "sku": sl.get("ItemCode"), "qty": _to_float(sl.get("Quantity")),
                    "sap_unit_price": round(_to_float(sl.get("UnitPrice")), 4),
                    "sap_tax_code": sl.get("TaxCode") or "",
                    "issue": "extra_in_sap",
                }
                for sl in sap_pool
            ]
            if sap_extra:
                root_causes.append(
                    f"{len(sap_extra)} SAP line(s) have no UC counterpart: "
                    + ", ".join(x["sku"] for x in sap_extra if x.get("sku"))
                )

            if tax_diff > 1.0:
                if expected_tax > 0:
                    ratio = actual_tax / expected_tax
                    if 1.85 <= ratio <= 2.15:
                        root_causes.append(
                            f"Tax doubled: SAP ₹{actual_tax:.2f} ≈ 2×UC expected ₹{expected_tax:.2f}. "
                            "Likely IGST and CGST+SGST both summed — check tax mapping for this channel/state."
                        )
                    elif actual_tax > expected_tax:
                        root_causes.append(
                            f"Tax over-stated in SAP by ₹{tax_diff:.2f} "
                            f"(SAP ₹{actual_tax:.2f} > expected ₹{expected_tax:.2f})"
                        )
                    else:
                        root_causes.append(
                            f"Tax under-stated in SAP by ₹{tax_diff:.2f} "
                            f"(SAP ₹{actual_tax:.2f} < expected ₹{expected_tax:.2f})"
                        )

            if not root_causes and not is_matched:
                root_causes.append(
                    f"unit Δ₹{unit_diff} / tax Δ₹{tax_diff} — may be rounding across many lines"
                )

            mismatch_reason = _diagnose_invoice_mismatch(
                order_doc, raw_inv, expected_unit, actual_unit, expected_tax, actual_tax
            )
            result["invoice"] = {
                "sap_doc_entry": de_inv,
                "sap_doc_num": str(order_doc.sap_ar_invoice_docnum or raw_inv.get("DocNum") or ""),
                "matched": is_matched,
                "expected_unit": expected_unit, "actual_unit": actual_unit, "unit_diff": unit_diff,
                "expected_tax":  expected_tax,  "actual_tax":  actual_tax,  "tax_diff":  tax_diff,
                "mismatch_reason": mismatch_reason,
                "line_comparison": line_comparison,
                "sap_extra_lines": sap_extra,
                "root_causes": root_causes,
                "total_uc_discount": round(total_discount, 2),
                "sap_doc_tax": round(_to_float(raw_inv.get("DocTaxAmount")), 2),
                "sap_doc_total": round(_to_float(raw_inv.get("DocTotal")), 2),
            }
        except Exception as exc:
            result["invoice"] = {"error": str(exc)}
            frappe.log_error(f"ops_diagnose_order invoice for {order_name}: {exc}", "Recon Diagnose")

    # ── AR Credit Note ───────────────────────────────────────────────────────
    de_cn = str(order_doc.sap_ar_creditnote_docentry or "").strip()
    if de_cn:
        try:
            expected_unit, expected_tax = _expected_credit_total(order_doc)
            actual_unit, actual_tax, raw_cn = _actual_credit_note(sap, de_cn, uc_order_id=order_doc.name)
            unit_diff = round(abs(expected_unit - actual_unit), 2)
            tax_diff  = round(abs(expected_tax - actual_tax), 2)
            is_matched = unit_diff <= 1.0 and tax_diff <= 1.0

            sap_lines   = raw_cn.get("DocumentLines") or []
            returned_uc = [oli for oli in (order_doc.line_items or []) if _is_returned_line(oli)]
            order_id    = str(order_doc.name)
            filtered_sap = [
                ln for ln in sap_lines
                if str(ln.get("U_Order") or "") == order_id
            ] or sap_lines

            sap_pool = list(filtered_sap)
            cn_line_comparison: list[dict] = []
            cn_root_causes: list[str] = []

            for oli in returned_uc:
                sku  = str(getattr(oli, "itemcode", "") or "")
                qty  = _to_float(getattr(oli, "quantity", 0))
                selling = _to_float(getattr(oli, "sellingpricewithouttaxesanddiscount", 0))
                disc = _to_float(getattr(oli, "discount", 0))
                per_unit_disc = (disc / qty) if qty > 0 else 0.0
                exp_up = round(max(0.0, selling - per_unit_disc), 4)

                uni_igst = _to_float(getattr(oli, "integratedgstpercentage", 0))
                uni_cgst_sgst = _to_float(getattr(oli, "state_gst_tax_percentage", 0)) + \
                                _to_float(getattr(oli, "central_gst_tax_percentage", 0))
                uc_tax_pct = int(max(uni_igst, uni_cgst_sgst))

                matched_sap = None
                for idx, sl in enumerate(sap_pool):
                    if str(sl.get("ItemCode") or "") == sku and abs(_to_float(sl.get("Quantity")) - qty) <= 0.01:
                        matched_sap = sap_pool.pop(idx)
                        break

                if matched_sap is None:
                    cn_line_comparison.append({
                        "sku": sku, "qty": qty,
                        "uc_unit_price": exp_up, "sap_unit_price": None,
                        "unit_diff": None, "uc_discount_total": disc,
                        "uc_tax_pct": uc_tax_pct, "sap_tax_code": None,
                        "issue": "missing_in_sap",
                    })
                    cn_root_causes.append(f"Returned SKU {sku} missing from SAP CN")
                else:
                    sap_up = round(_to_float(matched_sap.get("UnitPrice")), 4)
                    ldiff  = round(abs(exp_up - sap_up), 4)
                    issue  = "unit_price" if ldiff > 0.05 else None
                    cn_line_comparison.append({
                        "sku": sku, "qty": qty,
                        "uc_unit_price": exp_up, "sap_unit_price": sap_up,
                        "unit_diff": ldiff, "uc_discount_total": disc,
                        "uc_tax_pct": uc_tax_pct,
                        "sap_tax_code": matched_sap.get("TaxCode") or "",
                        "issue": issue,
                    })
                    if issue == "unit_price":
                        cn_root_causes.append(f"CN SKU {sku}: UC ₹{exp_up:.2f} SAP ₹{sap_up:.2f} Δ₹{ldiff:.4f}")

            cn_extra_sap = [
                {
                    "sku": sl.get("ItemCode"), "qty": _to_float(sl.get("Quantity")),
                    "sap_unit_price": round(_to_float(sl.get("UnitPrice")), 4),
                    "issue": "extra_in_sap",
                }
                for sl in sap_pool
            ]

            if tax_diff > 1.0:
                if expected_tax > 0:
                    ratio = actual_tax / expected_tax
                    if 1.85 <= ratio <= 2.15:
                        cn_root_causes.append(
                            f"CN tax doubled: SAP ₹{actual_tax:.2f} ≈ 2×expected ₹{expected_tax:.2f}"
                        )
                    elif actual_tax > expected_tax:
                        cn_root_causes.append(f"CN tax over-stated Δ₹{tax_diff:.2f}")
                    else:
                        cn_root_causes.append(f"CN tax under-stated Δ₹{tax_diff:.2f}")

            mismatch_reason = _diagnose_cn_mismatch(
                order_doc, raw_cn, expected_unit, actual_unit, expected_tax, actual_tax
            )
            result["credit_note"] = {
                "sap_doc_entry": de_cn,
                "matched": is_matched,
                "expected_unit": expected_unit, "actual_unit": actual_unit, "unit_diff": unit_diff,
                "expected_tax":  expected_tax,  "actual_tax":  actual_tax,  "tax_diff":  tax_diff,
                "mismatch_reason": mismatch_reason,
                "line_comparison": cn_line_comparison,
                "sap_extra_lines": cn_extra_sap,
                "root_causes": cn_root_causes,
                "returned_line_count": len(returned_uc),
            }
        except Exception as exc:
            result["credit_note"] = {"error": str(exc)}
            frappe.log_error(f"ops_diagnose_order CN for {order_name}: {exc}", "Recon Diagnose")

    if result["invoice"] is None and result["credit_note"] is None:
        result["error"] = "No SAP doc entry found on this order (not yet posted or different pipeline status)"

    return result


# ---------------------------------------------------------------------------
# Failure alerts
# ---------------------------------------------------------------------------

EVENT_FIELD_MAP = {
    "order_failed": "notify_orders",
    "credit_note_failed": "notify_credit_notes",
    "inventory_failed": "notify_inventory",
    "grn_failed": "notify_grn",
    "recon_gap": "notify_recon",
}


def send_failure_alert(event_type: str, doctype: str, name: str, error: str) -> bool:
    """
    Dispatch a failure alert via email to all enabled recipients subscribed to
    this event type. Respects the per-record debounce window.

    Safe to call from worker catch blocks — never raises.
    """
    try:
        if not _alerts_enabled():
            return False
        if not _should_send(event_type, doctype, name):
            return False
        recipients = _resolve_recipients(event_type)
        if not recipients:
            return False
        subject = f"[Unicommerce Ops] {event_type} — {doctype} {name}"
        body = (
            f"<p><strong>Event:</strong> {event_type}</p>"
            f"<p><strong>Doctype:</strong> {doctype}</p>"
            f"<p><strong>Record:</strong> {name}</p>"
            f"<p><strong>Error:</strong></p><pre>{frappe.utils.escape_html(error or '')[:2000]}</pre>"
        )
        frappe.sendmail(recipients=recipients, subject=subject, message=body, delayed=False)
        _mark_sent(event_type, doctype, name)
        return True
    except Exception as e:
        frappe.logger().error(f"send_failure_alert failed: {e}")
        return False


_BATCH_SHORTAGE_RATE_LIMIT_SECONDS = 30 * 60  # one digest per 30 min regardless of churn
_BATCH_SHORTAGE_DEDUPE_SECONDS = 4 * 60 * 60   # identical shortage set dedup window (4h)


def send_batch_shortage_digest(shortages: list[dict]) -> bool:
    """Email a batch-shortage digest. Two layers of suppression:

    1. **Content dedupe** (4h): identical normalized shortage multisets are
       collapsed to a single email in the window.
    2. **Rate limit** (30 min): even if the shortage set changes every cycle
       (e.g. one new order held every few minutes), we cap outgoing mail at
       one digest per 30 min per recipient list. Operators get a timely view
       without mailbox noise.
    """
    try:
        if not shortages or not _alerts_enabled():
            return False
        recipients = _resolve_recipients("order_failed")
        if not recipients:
            return False

        normalized = []
        for row in shortages:
            normalized.append(
                {
                    "uc_order_id": row.get("uc_order_id") or row.get("record_name") or "",
                    "channel": row.get("channel") or "",
                    "item_code": row.get("item_code") or "",
                    "batch_number": row.get("batch_number") or "",
                    "warehouse_code": row.get("warehouse_code") or "",
                    "qty_needed": float(row.get("qty_needed") or 0),
                    "qty_available": float(row.get("qty_available") or 0),
                }
            )
        normalized.sort(
            key=lambda row: (
                row["uc_order_id"],
                row["item_code"],
                row["batch_number"],
                row["warehouse_code"],
            )
        )

        recipients_key = hashlib.md5(
            ",".join(sorted(recipients)).encode()
        ).hexdigest()
        rate_key = f"uc_batch_shortage_rate:{recipients_key}"
        if frappe.cache().get_value(rate_key):
            return False

        digest_seed = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        digest_key = f"uc_batch_shortage_digest:{hashlib.md5(digest_seed.encode()).hexdigest()}"
        if frappe.cache().get_value(digest_key):
            return False

        preview_rows = normalized[:50]
        row_html = "".join(
            (
                "<tr>"
                f"<td>{frappe.utils.escape_html(row['uc_order_id'])}</td>"
                f"<td>{frappe.utils.escape_html(row['channel'])}</td>"
                f"<td>{frappe.utils.escape_html(row['item_code'])}</td>"
                f"<td>{frappe.utils.escape_html(row['batch_number'])}</td>"
                f"<td>{frappe.utils.escape_html(row['warehouse_code'])}</td>"
                f"<td style='text-align:right'>{row['qty_needed']:.3f}</td>"
                f"<td style='text-align:right'>{row['qty_available']:.3f}</td>"
                "</tr>"
            )
            for row in preview_rows
        )
        more_note = ""
        if len(normalized) > len(preview_rows):
            more_note = f"<p>Showing first {len(preview_rows)} shortages out of {len(normalized)}.</p>"

        body = (
            "<p><strong>Batch shortage summary</strong></p>"
            f"<p>{len(normalized)} item-level shortages were detected while preparing invoices.</p>"
            "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
            "<thead><tr>"
            "<th>Order</th><th>Channel</th><th>Item</th><th>Batch</th><th>Warehouse</th><th>Needed</th><th>Available</th>"
            "</tr></thead>"
            f"<tbody>{row_html}</tbody>"
            "</table>"
            f"{more_note}"
        )
        frappe.sendmail(
            recipients=recipients,
            subject=f"[Unicommerce Ops] Batch shortages detected ({len(normalized)})",
            message=body,
            delayed=False,
        )
        frappe.cache().set_value(
            digest_key, str(now_datetime()), expires_in_sec=_BATCH_SHORTAGE_DEDUPE_SECONDS
        )
        frappe.cache().set_value(
            rate_key, str(now_datetime()), expires_in_sec=_BATCH_SHORTAGE_RATE_LIMIT_SECONDS
        )
        return True
    except Exception as e:
        frappe.logger().error(f"send_batch_shortage_digest failed: {e}")
        return False


def _alerts_enabled() -> bool:
    return bool(int(frappe.db.get_single_value("Unicommerce Settings", "ops_enable_alerts") or 0))


def _resolve_recipients(event_type: str) -> list[str]:
    field = EVENT_FIELD_MAP.get(event_type)
    if not field:
        return []
    settings = frappe.get_single("Unicommerce Settings")
    out: list[str] = []
    for r in (settings.get("alert_recipients") or []):
        if not int(r.get("enabled") or 0):
            continue
        if not int(r.get(field) or 0):
            continue
        if r.get("email"):
            out.append(r.get("email"))
    return out


def _should_send(event_type: str, doctype: str, name: str) -> bool:
    debounce = int(frappe.db.get_single_value("Unicommerce Settings", "alert_debounce_minutes") or 15)
    key = f"uc_alert:{event_type}:{doctype}:{name}"
    last = frappe.cache().get_value(key)
    if not last:
        return True
    try:
        last_dt = get_datetime(last)
        if (now_datetime() - last_dt).total_seconds() < debounce * 60:
            return False
    except Exception:
        return True
    return True


def _mark_sent(event_type: str, doctype: str, name: str) -> None:
    key = f"uc_alert:{event_type}:{doctype}:{name}"
    debounce = int(frappe.db.get_single_value("Unicommerce Settings", "alert_debounce_minutes") or 15)
    frappe.cache().set_value(key, str(now_datetime()), expires_in_sec=max(debounce, 1) * 60)


# ---------------------------------------------------------------------------
# GR helpers — inactive item fallback
# ---------------------------------------------------------------------------

def _resolve_item_alternate(sap: "SAPClient", inactive_item: str) -> str | None:
    """
    Return the first active SubstituteItem configured in SAP B1 for `inactive_item`.

    SAP endpoint used: GET /b1s/v1/Items('{code}')?$select=Valid,SubstituteItems
    Returns None if no active substitute is found or if the lookup fails.
    """
    try:
        data = sap.get(f"Items('{inactive_item}')", params={"$select": "Valid,SubstituteItems"})
    except Exception as e:
        frappe.logger().warning("Could not fetch Item %s from SAP: %s", inactive_item, e)
        return None

    for sub in (data.get("SubstituteItems") or []):
        alt = str(sub.get("ItemCode") or "").strip()
        if not alt or alt == inactive_item:
            continue
        # Verify the substitute itself is active
        try:
            alt_data = sap.get(f"Items('{alt}')", params={"$select": "Valid"})
            if str(alt_data.get("Valid") or "").upper() != "TNO":
                return alt
        except Exception:
            pass  # If we can't verify, skip this candidate

    return None


def _post_gr_with_inactive_fallback(sap: "SAPClient", payload: dict) -> dict:
    """
    Post InventoryGenEntries to SAP, retrying once if an inactive-item error is raised.

    On the first attempt, if SAP returns error -10 "Item X is inactive":
      1. Look up X's SubstituteItems via the Items API.
      2. Replace every occurrence of X in DocumentLines with the active alternate.
      3. Retry the post exactly once.

    Raises on any other error, or if no alternate can be resolved.
    """
    import re

    try:
        return sap.post("InventoryGenEntries", payload)
    except Exception as first_err:
        err_str = str(first_err)
        # SAP B1 error -10: "Item FGDC0032 is inactive"
        match = re.search(r"Item\s+(\S+?)\s+is\s+inactive", err_str, re.IGNORECASE)
        if not match:
            raise  # unrelated error — propagate as-is

        inactive_item = match.group(1).strip()
        frappe.logger().warning(
            "GR post: item %s is inactive in SAP — looking up alternate", inactive_item
        )

        alternate = _resolve_item_alternate(sap, inactive_item)
        if not alternate:
            raise ValueError(
                f"Item {inactive_item} is inactive in SAP and no active substitute is "
                "configured on its Item Master (SubstituteItems). "
                "Please add an active substitute in SAP or use a different item code."
            ) from first_err

        frappe.logger().info(
            "GR post: replacing inactive item %s with alternate %s", inactive_item, alternate
        )

        # Swap the inactive item in every affected line
        substitutions: list[str] = []
        for line in (payload.get("DocumentLines") or []):
            if str(line.get("ItemCode") or "").strip() == inactive_item:
                line["ItemCode"] = alternate
                substitutions.append(f"{inactive_item} → {alternate}")

        if not substitutions:
            raise  # safety: nothing to swap, re-raise original

        # Annotate the comment so the operator knows a substitution was made
        orig_comment = str(payload.get("Comments") or "")
        payload["Comments"] = (orig_comment + f" [auto-sub: {', '.join(substitutions)}]")[:254]

        return sap.post("InventoryGenEntries", payload)


# ---------------------------------------------------------------------------
# Bulk Goods Receipt creation from shortage digest
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_create_gr_from_shortages(shortages_json: str) -> dict:
    """
    Create one Goods Receipt (InventoryGenEntries) in SAP B1 for ALL shorted
    item/batch/warehouse combos from the batch pre-validation shortage digest.

    shortages_json: JSON array of {item_code, batch_number, warehouse_code, quantity}

    Adds exactly the shorted quantity for each line so the inventory gap is
    covered. Multiple lines in the same warehouse are allowed in one document.
    System Manager only — FOR TESTING / EMERGENCY STOCK ADDITION ONLY.
    """
    frappe.only_for("System Manager")
    from frappe.utils import today as frappe_today

    try:
        shortages = json.loads(shortages_json or "[]")
    except Exception:
        return {"ok": False, "error": "Invalid shortages_json — must be a JSON array"}

    if not shortages:
        return {"ok": False, "error": "shortages list is empty"}

    gr_account = "52140200"

    lines = []
    skipped = []
    for row in shortages:
        item = str(row.get("item_code") or "").strip()
        batch = str(row.get("batch_number") or "").strip()
        wh = str(row.get("warehouse_code") or "").strip()
        qty = float(row.get("quantity") or 0)
        if not item or not batch or not wh or qty <= 0:
            skipped.append(row)
            continue
        lines.append({
            "ItemCode": item,
            "Quantity": qty,
            "WarehouseCode": wh,
            "AccountCode": "52140200",
            "BatchNumbers": [{"BatchNumber": batch, "Quantity": qty}],
        })

    if not lines:
        return {
            "ok": False,
            "error": f"No valid lines after filtering (skipped {len(skipped)} invalid rows). "
                     "Each row needs item_code, batch_number, warehouse_code, and quantity > 0.",
        }

    payload = {
        "DocDate": frappe_today(),
        "Comments": f"UC Ops emergency GR — batch shortage fix ({len(lines)} lines)",
        "DocumentLines": lines,
    }

    try:
        sap = SAPClient()
        sap.login()
        result = _post_gr_with_inactive_fallback(sap, payload)
        doc_entry = result.get("DocEntry") or result.get("docentry") or result.get("DocNum")
        frappe.logger().info(
            "ops_create_gr_from_shortages: %s lines, DocEntry=%s", len(lines), doc_entry
        )
        return {
            "ok": True,
            "doc_entry": doc_entry,
            "lines_created": len(lines),
            "lines_skipped": len(skipped),
            "message": f"GR created in SAP with {len(lines)} line(s). DocEntry: {doc_entry}",
        }
    except Exception as e:
        err = str(e)[:1000]
        frappe.logger().error(f"ops_create_gr_from_shortages failed: {err}")
        return {"ok": False, "error": err}


# ---------------------------------------------------------------------------
# Simplified reconciliation for a date range
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_recon_for_range(from_date: str, to_date: str) -> dict:
    """
    Simplified reconciliation view for a given UC order date range.

    Returns:
    - Total orders staged in the date range
    - Breakdown by pipeline status (how many posted, not posted, etc.)
    - Reasons why orders are not posted
    - Price / tax mismatch count for posted orders
    - Credit note stats
    """
    from_d = (from_date or "").strip()
    to_d = (to_date or "").strip()
    if not from_d or not to_d:
        return {"ok": False, "error": "from_date and to_date are required"}

    # Status counts across all orders in range
    status_rows = frappe.db.sql(
        """
        SELECT pipeline_status, COUNT(*) AS cnt
        FROM `tabUnicommerce Orders`
        WHERE order_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY pipeline_status
        """,
        {"from_date": from_d, "to_date": to_d},
        as_dict=True,
    )
    status_summary = {row.pipeline_status: int(row.cnt) for row in status_rows}
    total = sum(status_summary.values())
    posted_count = status_summary.get("posted", 0)
    not_posted_count = total - posted_count

    # Not-posted breakdown by status + most common last_error
    not_posted_rows = frappe.db.sql(
        """
        SELECT pipeline_status, last_error, COUNT(*) AS cnt
        FROM `tabUnicommerce Orders`
        WHERE order_date BETWEEN %(from_date)s AND %(to_date)s
          AND pipeline_status != 'posted'
        GROUP BY pipeline_status, last_error
        ORDER BY cnt DESC
        LIMIT 50
        """,
        {"from_date": from_d, "to_date": to_d},
        as_dict=True,
    )
    not_posted_reasons = [
        {"status": r.pipeline_status, "reason": (r.last_error or "")[:200], "count": int(r.cnt)}
        for r in not_posted_rows
    ]

    # Price / tax mismatches for posted orders — use fallback to avoid false mismatches
    # for orders where actual=0 (not yet reconciled with SAP live data).
    mismatch_rows = frappe.db.sql(
        """
        SELECT
            name,
            channel_name,
            sap_ar_invoice_docentry,
            CASE
                WHEN IFNULL(ar_invoice_unit_price_actual, 0) != 0
                THEN ABS(IFNULL(ar_invoice_unit_price_expected, 0) - IFNULL(ar_invoice_unit_price_actual, 0))
                ELSE 0
            END AS price_diff,
            CASE
                WHEN IFNULL(ar_invoice_tax_actual, 0) != 0
                THEN ABS(IFNULL(ar_invoice_tax_expected, 0) - IFNULL(ar_invoice_tax_actual, 0))
                ELSE 0
            END AS tax_diff
        FROM `tabUnicommerce Orders`
        WHERE order_date BETWEEN %(from_d)s AND %(to_d)s
          AND pipeline_status = 'posted'
          AND IFNULL(sap_ar_invoice_docentry, '') != ''
          AND ar_invoice_reconciled = 0
          AND (
              (IFNULL(ar_invoice_unit_price_actual, 0) != 0
               AND ABS(IFNULL(ar_invoice_unit_price_expected, 0) - IFNULL(ar_invoice_unit_price_actual, 0)) > 1)
              OR
              (IFNULL(ar_invoice_tax_actual, 0) != 0
               AND ABS(IFNULL(ar_invoice_tax_expected, 0) - IFNULL(ar_invoice_tax_actual, 0)) > 1)
          )
        ORDER BY tax_diff DESC
        LIMIT 50
        """,
        {"from_d": from_d, "to_d": to_d},
        as_dict=True,
    )

    # Credit note stats for orders in this date range
    cn_rows = frappe.db.sql(
        """
        SELECT cn.status, COUNT(*) AS cnt
        FROM `tabUC Credit Note Staging` cn
        INNER JOIN `tabUnicommerce Orders` o ON o.name = cn.uc_order_id
        WHERE o.order_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY cn.status
        """,
        {"from_date": from_d, "to_date": to_d},
        as_dict=True,
    )
    cn_summary = {row.status: int(row.cnt) for row in cn_rows}

    return {
        "ok": True,
        "from_date": from_d,
        "to_date": to_d,
        "total_orders": total,
        "posted_count": posted_count,
        "not_posted_count": not_posted_count,
        "status_summary": status_summary,
        "not_posted_reasons": not_posted_reasons,
        "price_mismatches": [
            {
                "order": r.name,
                "channel": r.channel_name,
                "sap_doc": r.sap_ar_invoice_docentry,
                "tax_diff": float(r.tax_diff or 0),
                "price_diff": float(r.price_diff or 0),
            }
            for r in mismatch_rows
        ],
        "price_mismatches_count": len(mismatch_rows),
        "credit_note_summary": cn_summary,
    }


# ---------------------------------------------------------------------------
# Test utility — create Goods Receipt in SAP B1 when batch validation fails
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_create_test_gr(
    item_code: str,
    batch_number: str,
    quantity: float,
    warehouse_code: str,
    doc_date: str | None = None,
    comments: str = "",
) -> dict:
    """
    Create a Goods Receipt (InventoryGenEntries) in SAP B1 via Service Layer.

    FOR TESTING ONLY — use when batch validation fails and you need to add stock.
    Restricted to System Manager.

    SAP B1 endpoint: POST /b1s/v1/InventoryGenEntries
    """
    frappe.only_for("System Manager")
    from frappe.utils import today as frappe_today

    item = (item_code or "").strip()
    batch = (batch_number or "").strip()
    wh = (warehouse_code or "").strip()
    qty = float(quantity or 0)

    if not item or not batch or not wh or qty <= 0:
        return {"ok": False, "error": "item_code, batch_number, warehouse_code, and quantity > 0 are required"}

    gr_account = "52140200"

    payload = {
        "DocDate": (doc_date or "").strip() or frappe_today(),
        "Comments": (comments or f"Test GR — UC Ops batch fix: {item} / {batch} / {wh}").strip()[:254],
        "DocumentLines": [
            {
                "ItemCode": item,
                "Quantity": qty,
                "WarehouseCode": wh,
                "AccountCode": gr_account,
                "BatchNumbers": [
                    {
                        "BatchNumber": batch,
                        "Quantity": qty,
                    }
                ],
            }
        ],
    }

    try:
        sap = SAPClient()
        sap.login()
        result = _post_gr_with_inactive_fallback(sap, payload)
        doc_entry = result.get("DocEntry") or result.get("docentry") or result.get("DocNum")
        frappe.logger().info(
            "ops_create_test_gr: item=%s batch=%s wh=%s qty=%s DocEntry=%s",
            item, batch, wh, qty, doc_entry,
        )
        return {
            "ok": True,
            "doc_entry": doc_entry,
            "message": f"Goods Receipt created in SAP. DocEntry: {doc_entry}",
        }
    except Exception as e:
        err = str(e)[:1000]
        frappe.logger().error(f"ops_create_test_gr failed: {err}")
        return {"ok": False, "error": err}


# ---------------------------------------------------------------------------
# Finance Reconciliation — UC vs SAP comparison with pivots + Excel download
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_finance_recon_data(from_date: str, to_date: str) -> dict:
    """
    Finance reconciliation for a date range.

    Reads staged order data (no external API calls — uses what's already in Frappe)
    and compares UC-expected values against SAP-actual values.

    Returns:
    - summary: totals (orders, posted, not-posted, total amounts)
    - channel_pivot: channel → {orders, uc_taxable, sap_taxable, uc_tax, sap_tax, diff_taxable, diff_tax, match}
    - customer_pivot: sap_customer_code → same shape
    - order_rows: per-order list for drill-down / Excel
    - not_posted: orders not yet in SAP with reason
    """
    from_d = (from_date or "").strip()
    to_d = (to_date or "").strip()
    if not from_d or not to_d:
        return {"ok": False, "error": "from_date and to_date are required"}

    rows = frappe.db.sql(
        """
        SELECT
            name                           AS uc_order_id,
            COALESCE(NULLIF(TRIM(channel_name), ''), 'Unknown')  AS channel,
            order_date,
            pipeline_status,
            status                                               AS uc_status,
            IFNULL(sap_ar_invoice_docentry, '')  AS sap_doc_entry,
            IFNULL(sap_ar_invoice_docnum,   '')  AS sap_doc_num,
            IFNULL(ar_invoice_unit_price_expected, 0) AS uc_taxable,
            -- For posted orders where actual has not been reconciled yet (=0/NULL),
            -- fall back to expected so SAP taxable ≠ 0 and diff stays near ₹0.
            CASE
                WHEN IFNULL(sap_ar_invoice_docentry, '') != ''
                 AND IFNULL(ar_invoice_unit_price_actual, 0) = 0
                THEN IFNULL(ar_invoice_unit_price_expected, 0)
                ELSE IFNULL(ar_invoice_unit_price_actual, 0)
            END                                                   AS sap_taxable,
            IFNULL(ar_invoice_tax_expected, 0)        AS uc_tax,
            CASE
                WHEN IFNULL(sap_ar_invoice_docentry, '') != ''
                 AND IFNULL(ar_invoice_tax_actual, 0) = 0
                THEN IFNULL(ar_invoice_tax_expected, 0)
                ELSE IFNULL(ar_invoice_tax_actual, 0)
            END                                                   AS sap_tax,
            IFNULL(ar_invoice_tax_diff,          0)   AS tax_diff,
            IFNULL(ar_invoice_unit_price_diff,   0)   AS price_diff,
            IFNULL(ar_invoice_reconciled,        0)   AS reconciled,
            last_error,
            -- Credit note fields
            IFNULL(sap_ar_creditnote_docentry, '')    AS cn_sap_doc_entry,
            IFNULL(sap_ar_creditnote_docentry, '')    AS cn_sap_doc_num,
            -- CN expected: use actual as fallback (CN prices come from SAP base invoice,
            -- so expected = what SAP computed; no separate UC-side expected exists).
            CASE
                WHEN IFNULL(ar_creditnote_unit_price_expected, 0) > 0
                THEN IFNULL(ar_creditnote_unit_price_expected, 0)
                ELSE IFNULL(ar_creditnote_unit_price_actual, 0)
            END                                           AS cn_uc_taxable,
            IFNULL(ar_creditnote_unit_price_actual, 0)    AS cn_sap_taxable,
            CASE
                WHEN IFNULL(ar_creditnote_tax_expected, 0) > 0
                THEN IFNULL(ar_creditnote_tax_expected, 0)
                ELSE IFNULL(ar_creditnote_tax_actual, 0)
            END                                           AS cn_uc_tax,
            IFNULL(ar_creditnote_tax_actual, 0)           AS cn_sap_tax
        FROM `tabUnicommerce Orders`
        WHERE order_date BETWEEN %(from_date)s AND %(to_date)s
          AND UPPER(TRIM(IFNULL(status, ''))) NOT IN ('CANCELLED', 'CANCEL', 'CANCELLATION_INITIATED', 'PROCESSING')
        ORDER BY order_date asc, name asc
        """,
        {"from_date": from_d, "to_date": to_d},
        as_dict=True,
    )

    # Fetch SAP customer code per channel from settings (channel_customer_map)
    channel_to_customer: dict[str, str] = {}
    try:
        settings = frappe.get_single("Unicommerce Settings")
        ccm = safe_json_loads(getattr(settings, "channel_customer_map", "") or "")
        if isinstance(ccm, dict):
            channel_to_customer = {str(k).strip(): str(v).strip() for k, v in ccm.items()}
    except Exception:
        pass

    THRESH = 1.0  # ₹1 mismatch threshold

    channel_pivot: dict[str, dict] = {}
    customer_pivot: dict[str, dict] = {}
    order_rows: list[dict] = []
    not_posted: list[dict] = []

    total_orders = len(rows)
    posted_count = 0
    total_uc_taxable = 0.0
    total_sap_taxable = 0.0
    total_uc_tax = 0.0
    total_sap_tax = 0.0
    total_cn_posted = 0
    total_cn_uc_taxable = 0.0
    total_cn_sap_taxable = 0.0
    total_cn_uc_tax = 0.0
    total_cn_sap_tax = 0.0
    mismatch_count = 0

    def _bucket(pivot: dict, key: str) -> dict:
        if key not in pivot:
            pivot[key] = {
                "orders": 0,
                "posted": 0,
                "uc_taxable": 0.0,
                "sap_taxable": 0.0,
                "uc_tax": 0.0,
                "sap_tax": 0.0,
                "diff_taxable": 0.0,
                "diff_tax": 0.0,
                "mismatches": 0,
                "cn_posted": 0,
                "cn_uc_taxable": 0.0,
                "cn_sap_taxable": 0.0,
                "cn_uc_tax": 0.0,
                "cn_sap_tax": 0.0,
                "cn_diff_taxable": 0.0,
                "cn_diff_tax": 0.0,
            }
        return pivot[key]

    for row in rows:
        channel = str(row.get("channel") or "Unknown")
        status = str(row.get("pipeline_status") or "")
        sap_doc = str(row.get("sap_doc_entry") or "").strip()
        is_posted = bool(sap_doc)

        uc_taxable = float(row.get("uc_taxable") or 0)
        sap_taxable = float(row.get("sap_taxable") or 0)
        uc_tax = float(row.get("uc_tax") or 0)
        sap_tax = float(row.get("sap_tax") or 0)
        # Compute diffs from displayed values (which already apply the fallback for
        # unreconciled orders). The stored ar_invoice_unit_price_diff reflects actual=0
        # for orders that haven't been through run_reconciliation_refresh yet, producing
        # false mismatches (price_diff = full expected amount even when UC == SAP).
        price_diff = round(abs(uc_taxable - sap_taxable), 2)
        tax_diff = round(abs(uc_tax - sap_tax), 2)
        has_mismatch = is_posted and (price_diff > THRESH or tax_diff > THRESH)

        if is_posted:
            posted_count += 1
        else:
            not_posted.append(
                {
                    "uc_order_id": row.get("uc_order_id"),
                    "channel": channel,
                    "order_date": str(row.get("order_date") or ""),
                    "status": status,
                    "reason": (str(row.get("last_error") or "") or status)[:200],
                }
            )

        # Credit note amounts for this order
        cn_sap_doc = str(row.get("cn_sap_doc_entry") or "").strip()
        is_cn_posted = bool(cn_sap_doc)
        cn_uc_taxable = float(row.get("cn_uc_taxable") or 0)
        cn_sap_taxable = float(row.get("cn_sap_taxable") or 0)
        cn_uc_tax = float(row.get("cn_uc_tax") or 0)
        cn_sap_tax = float(row.get("cn_sap_tax") or 0)
        cn_price_diff = round(abs(cn_uc_taxable - cn_sap_taxable), 2)
        cn_tax_diff = round(abs(cn_uc_tax - cn_sap_tax), 2)

        total_uc_taxable += uc_taxable
        total_sap_taxable += sap_taxable
        total_uc_tax += uc_tax
        total_sap_tax += sap_tax
        if is_cn_posted:
            total_cn_posted += 1
            total_cn_uc_taxable += cn_uc_taxable
            total_cn_sap_taxable += cn_sap_taxable
            total_cn_uc_tax += cn_uc_tax
            total_cn_sap_tax += cn_sap_tax
        if has_mismatch:
            mismatch_count += 1

        # Channel pivot
        cb = _bucket(channel_pivot, channel)
        cb["orders"] += 1
        if is_posted:
            cb["posted"] += 1
        cb["uc_taxable"] += uc_taxable
        cb["sap_taxable"] += sap_taxable
        cb["uc_tax"] += uc_tax
        cb["sap_tax"] += sap_tax
        if has_mismatch:
            cb["mismatches"] += 1
        if is_cn_posted:
            cb["cn_posted"] += 1
            cb["cn_uc_taxable"] += cn_uc_taxable
            cb["cn_sap_taxable"] += cn_sap_taxable
            cb["cn_uc_tax"] += cn_uc_tax
            cb["cn_sap_tax"] += cn_sap_tax

        # Customer pivot (keyed by SAP customer code via channel_customer_map)
        cust_key = channel_to_customer.get(channel) or channel_to_customer.get(channel.upper()) or f"({channel})"
        kb = _bucket(customer_pivot, cust_key)
        kb["orders"] += 1
        if is_posted:
            kb["posted"] += 1
        kb["uc_taxable"] += uc_taxable
        kb["sap_taxable"] += sap_taxable
        kb["uc_tax"] += uc_tax
        kb["sap_tax"] += sap_tax
        if has_mismatch:
            kb["mismatches"] += 1
        if is_cn_posted:
            kb["cn_posted"] += 1
            kb["cn_uc_taxable"] += cn_uc_taxable
            kb["cn_sap_taxable"] += cn_sap_taxable
            kb["cn_uc_tax"] += cn_uc_tax
            kb["cn_sap_tax"] += cn_sap_tax

        order_rows.append(
            {
                "uc_order_id": row.get("uc_order_id"),
                "channel": channel,
                "sap_customer": cust_key,
                "order_date": str(row.get("order_date") or ""),
                "status": status,
                "sap_doc_entry": sap_doc,
                "sap_doc_num": str(row.get("sap_doc_num") or ""),
                "uc_taxable": round(uc_taxable, 2),
                "sap_taxable": round(sap_taxable, 2),
                "uc_tax": round(uc_tax, 2),
                "sap_tax": round(sap_tax, 2),
                "price_diff": round(price_diff, 2),
                "tax_diff": round(tax_diff, 2),
                "match": not has_mismatch if is_posted else None,
                "reason": (str(row.get("last_error") or "") or "")[:200] if not is_posted else "",
                "cn_sap_doc_entry": cn_sap_doc,
                "cn_sap_doc_num": str(row.get("cn_sap_doc_num") or ""),
                "cn_uc_taxable": round(cn_uc_taxable, 2),
                "cn_sap_taxable": round(cn_sap_taxable, 2),
                "cn_uc_tax": round(cn_uc_tax, 2),
                "cn_sap_tax": round(cn_sap_tax, 2),
                "cn_price_diff": cn_price_diff,
                "cn_tax_diff": cn_tax_diff,
                "cn_match": (cn_price_diff <= THRESH and cn_tax_diff <= THRESH) if is_cn_posted else None,
            }
        )

    # ── GST split per order from line items (for GST Recon Excel sheet) ──────
    try:
        li_rows = frappe.db.sql(
            """
            SELECT
                li.parent                                                        AS order_name,
                ROUND(SUM(li.sellingpricewithouttaxesanddiscount * li.quantity), 2) AS subtotal,
                ROUND(SUM(li.discount * li.quantity), 2)                         AS discount_total,
                ROUND(SUM(li.totalintegratedgst * li.quantity), 2)               AS igst,
                ROUND(SUM(
                    CASE WHEN li.central_gst_tax_percentage > 0
                    THEN (li.sellingpricewithouttaxesanddiscount - li.discount)
                         * li.quantity * li.central_gst_tax_percentage / 100
                    ELSE 0 END), 2)                                              AS cgst,
                ROUND(SUM(
                    CASE WHEN li.state_gst_tax_percentage > 0
                    THEN (li.sellingpricewithouttaxesanddiscount - li.discount)
                         * li.quantity * li.state_gst_tax_percentage / 100
                    ELSE 0 END), 2)                                              AS sgst,
                ROUND(SUM(
                    CASE WHEN (IFNULL(li.shippingcharges, 0) + IFNULL(li.shippingmethodcharges, 0)) > 0
                    THEN
                        (IFNULL(li.shippingcharges, 0) + IFNULL(li.shippingmethodcharges, 0))
                        * COALESCE(
                            NULLIF(IFNULL(li.shippingchargetaxpercentage, 0), 0),
                            CASE WHEN IFNULL(li.integratedgstpercentage, 0) > 0
                                 THEN li.integratedgstpercentage
                                 WHEN IFNULL(li.central_gst_tax_percentage, 0) > 0
                                 THEN (li.central_gst_tax_percentage + li.state_gst_tax_percentage)
                                 ELSE 0 END
                          ) / (100.0 + COALESCE(
                            NULLIF(IFNULL(li.shippingchargetaxpercentage, 0), 0),
                            CASE WHEN IFNULL(li.integratedgstpercentage, 0) > 0
                                 THEN li.integratedgstpercentage
                                 WHEN IFNULL(li.central_gst_tax_percentage, 0) > 0
                                 THEN (li.central_gst_tax_percentage + li.state_gst_tax_percentage)
                                 ELSE 0 END
                          ))
                    ELSE 0 END), 2)                                              AS shipping_tax,
                MAX(CASE WHEN IFNULL(li.integratedgstpercentage, 0) > 0 THEN 1 ELSE 0 END) AS is_igst_order,
                MAX(CASE WHEN IFNULL(li.central_gst_tax_percentage, 0) > 0 THEN 1 ELSE 0 END) AS is_cgst_order
            FROM `tabOrder Line Items` li
            INNER JOIN `tabUnicommerce Orders` o ON o.name = li.parent
            WHERE o.order_date BETWEEN %(from_d)s AND %(to_d)s
            GROUP BY li.parent
            """,
            {"from_d": from_d, "to_d": to_d},
            as_dict=True,
        )
        li_map = {r.order_name: r for r in li_rows}
    except Exception:
        li_map = {}

    for row in order_rows:
        li = li_map.get(row["uc_order_id"]) or {}
        row["subtotal"]    = round(float(li.get("subtotal")       or 0), 2)
        row["uc_discount"] = round(float(li.get("discount_total") or 0), 2)
        uc_cgst = round(float(li.get("cgst") or 0), 2)
        uc_sgst = round(float(li.get("sgst") or 0), 2)
        uc_igst = round(float(li.get("igst") or 0), 2)
        shipping_tax = round(float(li.get("shipping_tax") or 0), 2)
        if shipping_tax:
            if int(li.get("is_igst_order") or 0):
                uc_igst = round(uc_igst + shipping_tax, 2)
            elif int(li.get("is_cgst_order") or 0):
                half = round(shipping_tax / 2, 2)
                uc_cgst = round(uc_cgst + half, 2)
                uc_sgst = round(uc_sgst + half, 2)
            else:
                uc_igst = round(uc_igst + shipping_tax, 2)
        row["uc_cgst"] = uc_cgst
        row["uc_sgst"] = uc_sgst
        row["uc_igst"] = uc_igst
        # SAP tax split mirrors UC rates applied to SAP taxable
        sap_t = row["sap_taxable"]
        uc_t  = row["uc_taxable"]
        if uc_t > 0 and sap_t > 0:
            ratio = sap_t / uc_t
            row["sap_cgst"] = round(row["uc_cgst"] * ratio, 2)
            row["sap_sgst"] = round(row["uc_sgst"] * ratio, 2)
            row["sap_igst"] = round(row["uc_igst"] * ratio, 2)
        else:
            row["sap_cgst"] = row["sap_sgst"] = row["sap_igst"] = 0.0

    # Finalise pivot diffs + match flag
    def _finalise(pivot: dict) -> list[dict]:
        out = []
        for key, b in sorted(pivot.items()):
            b["key"] = key
            b["uc_taxable"] = round(b["uc_taxable"], 2)
            b["sap_taxable"] = round(b["sap_taxable"], 2)
            b["uc_tax"] = round(b["uc_tax"], 2)
            b["sap_tax"] = round(b["sap_tax"], 2)
            b["diff_taxable"] = round(b["sap_taxable"] - b["uc_taxable"], 2)
            b["diff_tax"] = round(b["sap_tax"] - b["uc_tax"], 2)
            b["match"] = b["mismatches"] == 0
            b["cn_uc_taxable"] = round(b["cn_uc_taxable"], 2)
            b["cn_sap_taxable"] = round(b["cn_sap_taxable"], 2)
            b["cn_uc_tax"] = round(b["cn_uc_tax"], 2)
            b["cn_sap_tax"] = round(b["cn_sap_tax"], 2)
            b["cn_diff_taxable"] = round(b["cn_sap_taxable"] - b["cn_uc_taxable"], 2)
            b["cn_diff_tax"] = round(b["cn_sap_tax"] - b["cn_uc_tax"], 2)
            out.append(b)
        return out

    return {
        "ok": True,
        "from_date": from_d,
        "to_date": to_d,
        "generated_at": str(now_datetime()),
        "summary": {
            "total_orders": total_orders,
            "posted_count": posted_count,
            "not_posted_count": total_orders - posted_count,
            "mismatch_count": mismatch_count,
            "uc_taxable_total": round(total_uc_taxable, 2),
            "sap_taxable_total": round(total_sap_taxable, 2),
            "uc_tax_total": round(total_uc_tax, 2),
            "sap_tax_total": round(total_sap_tax, 2),
            "diff_taxable": round(total_sap_taxable - total_uc_taxable, 2),
            "cn_posted_count": total_cn_posted,
            "cn_uc_taxable_total": round(total_cn_uc_taxable, 2),
            "cn_sap_taxable_total": round(total_cn_sap_taxable, 2),
            "cn_uc_tax_total": round(total_cn_uc_tax, 2),
            "cn_sap_tax_total": round(total_cn_sap_tax, 2),
            "cn_diff_taxable": round(total_cn_sap_taxable - total_cn_uc_taxable, 2),
            "cn_diff_tax": round(total_cn_sap_tax - total_cn_uc_tax, 2),
            "diff_tax": round(total_sap_tax - total_uc_tax, 2),
        },
        "channel_pivot": _finalise(channel_pivot),
        "customer_pivot": _finalise(customer_pivot),
        "order_rows": order_rows,
        "not_posted": not_posted,
    }


# ---------------------------------------------------------------------------
# Tab 5 · Inward Inventory Flow (SAP → EC-FG → UC PO + GRN)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ops_inward_transfer_list(days: int = 30) -> dict:
    """
    Read-only list of SAP Inventory Transfers (towarehouse=EC-FG) with UC sync status.
    Safe to call at any time — no UC writes.
    """
    try:
        from ..workers.po_grn import get_inward_transfer_list
        rows = get_inward_transfer_list(days=int(days or 30))
        pending = sum(1 for r in rows if r["ui_status"] == "PENDING")
        po_created = sum(1 for r in rows if r["ui_status"] == "PO_CREATED")
        grn_done = sum(1 for r in rows if r["ui_status"] == "GRN_COMPLETED")
        grn_partial = sum(1 for r in rows if r["ui_status"] == "GRN_PARTIAL")
        return {
            "rows": rows,
            "summary": {
                "total": len(rows),
                "pending": pending,
                "po_created": po_created,
                "grn_completed": grn_done,
                "grn_partial": grn_partial,
            },
        }
    except Exception as exc:
        frappe.log_error(str(exc), "ops_inward_transfer_list")
        return {"error": str(exc)[:500], "rows": [], "summary": {}}


@frappe.whitelist()
def ops_process_inward_transfer(docname: str) -> dict:
    """
    Create UC PO + GRN(s) for a single SAP Inventory Transfer (towarehouse=EC-FG).
    Operator-triggered only. Idempotent — safe to retry on failure.
    """
    if not docname:
        return {"success": False, "message": "docname is required"}
    try:
        from ..workers.po_grn import process_inward_transfer
        return process_inward_transfer(str(docname))
    except Exception as exc:
        frappe.log_error(str(exc), "ops_process_inward_transfer")
        return {"success": False, "message": str(exc)[:500]}


@frappe.whitelist()
def ops_process_pending_inward_transfers(days: int = 30) -> dict:
    """
    Enqueue background job to process all pending SAP Inward Transfers.
    Operator-triggered only.
    """
    try:
        frappe.enqueue(
            "khanal_tech_integrations.unicommerce.workers.po_grn.process_pending_inward_transfers",
            queue="default",
            timeout=900,
            days=int(days or 30),
        )
        return {"queued": True, "message": f"Background job queued for last {days} days of transfers."}
    except Exception as exc:
        frappe.log_error(str(exc), "ops_process_pending_inward_transfers")
        return {"queued": False, "message": str(exc)[:500]}


@frappe.whitelist()
def ops_uc_po_details(po_code: str) -> dict:
    """
    Read-only: fetch a Unicommerce PO's details (items, status) by PO code.
    Safe to call at any time — no UC writes.
    """
    if not (po_code or "").strip():
        return {"success": False, "error": "po_code is required"}
    try:
        from ..workers.po_grn import get_uc_po_details
        return get_uc_po_details(str(po_code).strip())
    except Exception as exc:
        frappe.log_error(str(exc), "ops_uc_po_details")
        return {"success": False, "error": str(exc)[:500]}


@frappe.whitelist()
def ops_create_grn_for_manual_po(po_code: str) -> dict:
    """
    Create GRN(s) for a PO that was manually created in Unicommerce.
    Operator-triggered only — never scheduled.
    """
    if not (po_code or "").strip():
        return {"success": False, "message": "po_code is required"}
    try:
        from ..workers.po_grn import create_grn_for_manual_po
        return create_grn_for_manual_po(str(po_code).strip())
    except Exception as exc:
        frappe.log_error(str(exc), "ops_create_grn_for_manual_po")
        return {"success": False, "message": str(exc)[:500]}
