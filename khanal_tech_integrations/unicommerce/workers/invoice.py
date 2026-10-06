import json
import re
import uuid
from datetime import datetime

import frappe
from frappe.utils import now_datetime, time_diff_in_hours, time_diff_in_seconds

from ..mappers.sap_payload import (
    DEFAULT_WAREHOUSE,
    _fefo_allocate_from_rows,
    _parse_line_items,
    _resolve_sap_warehouse,
    ar_invoice_payload,
)
from ..client import SAPClient
from .fetch import promote_fetched_to_ready


FAILED_RETRY_BASE_DELAY_MINS = 10
FAILED_RETRY_MAX_DELAY_MINS = 180

# Batch-hold auto-recovery — retry every 30 min (flat, no exponential backoff because
# we're waiting for stock, not a transient service error).
BATCH_HOLD_RETRY_DELAY_MINS = 30

# Batch-hold escalation. Orders that can't clear batch validation within this budget
# are moved to `dead` with a clear `last_error` so an operator can intervene.
#   * max attempts = 10  → at 30-min intervals that's ≥ 5 h of clock time, typically
#     much longer because attempts only happen while a posting cycle is running.
#   * max hours    = 48  → wall-clock ceiling so even rarely-posting pipelines
#     don't silently keep a stale hold around for days.
# Whichever limit trips first, the order escalates.
BATCH_HOLD_MAX_ATTEMPTS = 10
BATCH_HOLD_MAX_HOURS = 48

# Float tolerance for batch qty comparison — avoids false holds from rounding
# (e.g. SAP returns 4.999 when 5.0 is actually available due to decimal precision).
BATCH_QTY_TOLERANCE = 0.01

# Tri-state batch-managed cache sentinel. The cache stores one of:
#   True  → SAP confirmed ManageBatchNumbers = tYES
#   False → SAP confirmed ManageBatchNumbers = tNO
#   None  → lookup failed (SL 5xx / timeout / auth) — caller must NOT allocate
#           batches for that item AND must NOT enforce shortage, so validation
#           and payload builders stay consistent.
BatchManagedCache = dict[str, "bool | None"]
ReservationContext = dict[str, object]


def _ensure_reservation_ledger_table() -> None:
    """Best-effort table for soft batch reservation audit trail."""
    try:
        frappe.db.sql(
            """
            CREATE TABLE IF NOT EXISTS `__uc_batch_reservation_ledger` (
                `name` VARCHAR(140) PRIMARY KEY,
                `run_id` VARCHAR(140) NOT NULL,
                `order_name` VARCHAR(140) NOT NULL,
                `item_code` VARCHAR(140) NOT NULL,
                `batch_number` VARCHAR(140) NOT NULL,
                `warehouse_code` VARCHAR(140) NOT NULL,
                `reserved_qty` DECIMAL(18,6) NOT NULL DEFAULT 0,
                `status` VARCHAR(32) NOT NULL DEFAULT 'held',
                `reason` TEXT NULL,
                `created_at` DATETIME NULL,
                `updated_at` DATETIME NULL,
                INDEX `idx_uc_batch_res_run` (`run_id`),
                INDEX `idx_uc_batch_res_order` (`order_name`),
                INDEX `idx_uc_batch_res_item_batch_wh` (`item_code`, `batch_number`, `warehouse_code`)
            )
            """
        )
    except Exception:
        # Reservation must never block posting when DDL fails.
        pass


def _reservation_context_new(ledger_enabled: bool = True) -> ReservationContext:
    return {
        "run_id": f"run-{uuid.uuid4().hex[:16]}",
        "reserved_by_key": {},
        "allocs_by_order": {},
        "ledger_enabled": bool(ledger_enabled),
    }


def _reservation_reserved_qty(ctx: ReservationContext | None, key: tuple[str, str, str]) -> float:
    if not ctx:
        return 0.0
    return float((ctx.get("reserved_by_key") or {}).get(key) or 0.0)


def _reservation_hold_for_order(
    ctx: ReservationContext | None,
    order_name: str,
    allocations: list[dict],
) -> None:
    if not ctx or not allocations:
        return
    reserved_by_key = ctx.setdefault("reserved_by_key", {})
    allocs_by_order = ctx.setdefault("allocs_by_order", {})
    allocs_by_order[order_name] = allocations
    now = now_datetime()
    run_id = str(ctx.get("run_id") or "")
    ledger_enabled = bool(ctx.get("ledger_enabled", True))

    for row in allocations:
        key = (
            str(row.get("item_code") or ""),
            str(row.get("batch_number") or ""),
            str(row.get("warehouse_code") or ""),
        )
        qty = float(row.get("qty") or 0)
        if qty <= 0:
            continue
        reserved_by_key[key] = float(reserved_by_key.get(key) or 0) + qty
        if ledger_enabled:
            try:
                frappe.db.sql(
                    """
                    INSERT INTO `__uc_batch_reservation_ledger`
                        (`name`, `run_id`, `order_name`, `item_code`, `batch_number`, `warehouse_code`,
                         `reserved_qty`, `status`, `reason`, `created_at`, `updated_at`)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'held','reservation_held',%s,%s)
                    """,
                    (
                        f"{run_id}-{order_name}-{uuid.uuid4().hex[:8]}",
                        run_id,
                        order_name,
                        key[0],
                        key[1],
                        key[2],
                        qty,
                        now,
                        now,
                    ),
                )
            except Exception:
                pass


def _reservation_release_for_order(ctx: ReservationContext | None, order_name: str, reason: str) -> None:
    if not ctx:
        return
    allocs_by_order = ctx.get("allocs_by_order") or {}
    rows = allocs_by_order.pop(order_name, [])
    if not rows:
        return
    reserved_by_key = ctx.get("reserved_by_key") or {}
    for row in rows:
        key = (
            str(row.get("item_code") or ""),
            str(row.get("batch_number") or ""),
            str(row.get("warehouse_code") or ""),
        )
        qty = float(row.get("qty") or 0)
        if qty <= 0:
            continue
        reserved_by_key[key] = max(0.0, float(reserved_by_key.get(key) or 0) - qty)
    if bool(ctx.get("ledger_enabled", True)):
        try:
            run_id = str(ctx.get("run_id") or "")
            frappe.db.sql(
                """
                UPDATE `__uc_batch_reservation_ledger`
                   SET status = 'released', reason = %s, updated_at = %s
                 WHERE run_id = %s AND order_name = %s AND status = 'held'
                """,
                (str(reason or "")[:255], now_datetime(), run_id, order_name),
            )
        except Exception:
            pass


def _reservation_consume_for_order(ctx: ReservationContext | None, order_name: str) -> None:
    if not ctx:
        return
    allocs_by_order = ctx.get("allocs_by_order") or {}
    rows = allocs_by_order.pop(order_name, [])
    if not rows:
        return
    if bool(ctx.get("ledger_enabled", True)):
        try:
            run_id = str(ctx.get("run_id") or "")
            frappe.db.sql(
                """
                UPDATE `__uc_batch_reservation_ledger`
                   SET status = 'consumed', reason = 'invoice_posted', updated_at = %s
                 WHERE run_id = %s AND order_name = %s AND status = 'held'
                """,
                (now_datetime(), run_id, order_name),
            )
        except Exception:
            pass


def post_invoices(limit: int = 50, start_date: str | None = None, end_date: str | None = None, channel_name: str | None = None):
    """
    Step-9 processor:
    - Recover stuck posting -> verify
    - Auto-recover batch_hold orders past cooldown -> ready
    - Process verify queue
    - Process ready queue (posting flow)

    start_date / end_date (YYYY-MM-DD) restrict the ready queue to UC sale orders
    whose ``order_date`` falls inside the window. They are propagated to the
    promote/verify/recovery sub-stages so a single Ops Center "Post Invoices"
    run only acts on the operator-selected date range.
    """
    cycle_started_at = now_datetime()
    promoted_stats = promote_fetched_to_ready(limit=limit, start_date=start_date, end_date=end_date)
    _recover_stuck(start_date=start_date, end_date=end_date)
    recovered_failed = _recover_failed_orders(limit=limit, start_date=start_date, end_date=end_date)
    batch_recovery = _recover_batch_hold_orders(limit=limit, start_date=start_date, end_date=end_date)
    verify_stats = _verify_posted_orders(limit=limit, start_date=start_date, end_date=end_date)
    ready_stats = _post_ready_orders(
        limit=limit,
        ready_before=cycle_started_at,
        start_date=start_date,
        end_date=end_date,
        channel_name=channel_name,
    )
    return {
        "promoted_to_ready": promoted_stats["moved_to_ready"],
        "deferred_fetched": promoted_stats.get("deferred", 0),
        "recovered_failed": recovered_failed,
        "recovered_batch_hold": batch_recovery.get("recovered", 0),
        "escalated_batch_hold": batch_recovery.get("escalated", 0),
        "verify_checked": verify_stats["checked"],
        "verify_posted": verify_stats["posted"],
        "verify_requeued": verify_stats["requeued"],
        "verify_dead": verify_stats["dead"],
        "ready_processed": ready_stats["processed"],
        "ready_posted": ready_stats["posted"],
        "ready_batch_hold": ready_stats["batch_hold"],
        "ready_failed": ready_stats["failed"],
        "reservation_conflicts": ready_stats.get("reservation_conflicts", 0),
    }


def _claim_ready_order(name: str) -> bool:
    """Atomically move an order from ``ready`` to ``posting``.

    Returns True if THIS worker owns the claim. Protects against two
    concurrent ``post_invoices`` cycles picking the same order (the old code
    read with ``frappe.get_all`` then wrote later, leaving a classic TOCTOU
    race window).

    The conditional ``UPDATE ... WHERE pipeline_status='ready'`` either
    transitions exactly one row (we got it) or zero rows (another worker
    already claimed it). The claim is committed immediately so other workers
    see the state change in their own transactions.
    """
    frappe.db.sql(
        """
        UPDATE `tabUnicommerce Orders`
           SET pipeline_status = 'posting',
               posting_started_at = %s,
               modified = %s,
               modified_by = %s
         WHERE name = %s AND pipeline_status = 'ready'
        """,
        (now_datetime(), now_datetime(), frappe.session.user or "Administrator", name),
    )
    affected = 0
    try:
        affected = frappe.db._cursor.rowcount
    except Exception:
        frappe.logger().warning(
            f"_claim_ready_order({name}): could not read cursor.rowcount; "
            "falling back to status check",
            exc_info=True,
        )
        state = frappe.db.get_value("Unicommerce Orders", name, "pipeline_status")
        affected = 1 if state == "posting" else 0
    frappe.db.commit()
    return affected == 1


def _emit_post(msg: str, level: str = "info") -> None:
    try:
        frappe.publish_realtime(
            "uc_ops_progress",
            {"worker": "post_invoices", "msg": msg, "level": level},
            user=frappe.session.user,
        )
    except Exception:
        pass


def _prewarm_fefo_cache(sap: SAPClient, orders: list) -> dict:
    """Bulk-fetch HANA batch inventory for all items across all orders in one pass.

    Returns {(item_code, wh_code): [fefo_rows]} shared across the posting run.
    On HANA failure returns an empty dict so _check_batches falls back to
    per-item HANA queries (still HANA, just one at a time).
    """
    from ..mappers.sap_payload import _parse_line_items, _resolve_sap_warehouse
    settings = frappe.get_single("Unicommerce Settings")
    wh_items: dict[str, set[str]] = {}
    for row in orders:
        try:
            doc = frappe.get_doc("Unicommerce Orders", row.name)
            uc_data = json.loads(doc.order_json or "{}")
            items = _parse_line_items(uc_data) or []
            channel = doc.channel_name or ""
            for item in items:
                item_code = str(item.get("itemSku") or "").strip()
                if not item_code:
                    continue
                sap_wh = _resolve_sap_warehouse(settings, channel, item.get("warehouseCode", ""))
                if sap_wh:
                    wh_items.setdefault(sap_wh, set()).add(item_code)
        except Exception:
            continue
    fefo_cache: dict = {}
    for wh, item_codes in wh_items.items():
        try:
            rows = sap.bulk_batch_inventory_by_warehouse(wh, list(item_codes))
            for r in rows:
                key = (r["item_code"], r["warehouse_code"])
                fefo_cache.setdefault(key, []).append(
                    {"distnumber": r["batch_number"], "quantity": r["quantity"], "expdate": r.get("expiry")}
                )
        except Exception as exc:
            frappe.logger().warning("_prewarm_fefo_cache wh=%s: %s", wh, exc)
    return fefo_cache


def _current_fy_end_suffix() -> str:
    """Return the 2-digit end-year suffix for the current Indian financial year.

    FY2025-26 → '26', FY2026-27 → '27', etc. Used to build expected series names
    like KAB2C26 / KAB2C27 dynamically so no code change is needed at FY rollover.
    Indian FY starts 1 April.
    """
    today = datetime.today()
    fy_start = today.year if today.month >= 4 else today.year - 1
    return str(fy_start + 1)[-2:]


def _validate_active_series(sap: SAPClient) -> tuple[bool, str]:
    """
    Fetch the currently active SAP AR Invoice series and verify it belongs to
    the current Indian financial year.

    Returns (ok, message).  ok=False aborts the entire posting run so that
    no invoices land in an old financial-year series.

    Series sets are derived from the current date so no code change is needed
    at annual FY rollover (April).
    """
    curr_suffix = _current_fy_end_suffix()
    prev_suffix = str(int(curr_suffix) - 1).zfill(2)
    _KNOWN_PREFIXES = {"KAB2C", "TNB2C", "MHB2C"}
    _GOOD_SERIES = {f"{p}{curr_suffix}" for p in _KNOWN_PREFIXES}
    _OLD_SERIES  = {f"{p}{prev_suffix}" for p in _KNOWN_PREFIXES}

    active_series_id = _pick_active_invoice_series(sap)
    if not active_series_id:
        # Could not determine series — warn but allow (SAP may not expose it via OData)
        frappe.logger().warning("_validate_active_series: could not resolve active series ID — proceeding")
        return True, "Series ID could not be resolved — proceeding without validation"

    try:
        resp = sap.post(
            "SeriesService_GetSeries",
            {"SeriesParams": {"Series": int(active_series_id)}},
        )
        series_name = str(resp.get("Name") or "").strip()
    except Exception as exc:
        frappe.logger().warning(f"_validate_active_series: could not fetch series name: {exc} — proceeding")
        return True, f"Series name lookup failed ({exc}) — proceeding without validation"

    if series_name in _GOOD_SERIES:
        return True, f"Active series '{series_name}' is a valid series for the current financial year"

    if series_name in _OLD_SERIES:
        msg = (
            f"POSTING BLOCKED — active SAP AR Invoice series is '{series_name}' (previous financial year series). "
            f"Update the default series to one of {sorted(_GOOD_SERIES)} in SAP B1 "
            f"(Administration → System Initialization → Document Numbering) and retry."
        )
        return False, msg

    # Unknown series — warn but allow (could be a non-B2C or test series)
    frappe.logger().warning(f"_validate_active_series: unrecognised series '{series_name}' — proceeding")
    return True, f"Series '{series_name}' is not in the known list — proceeding"


def _post_ready_orders(limit: int = 50, ready_before=None, start_date: str | None = None, end_date: str | None = None, channel_name: str | None = None):
    sap = SAPClient()

    # Guard: abort entire run if active SAP series is still an old FY2025 series.
    # Prevents re-posting of the 148 cancelled March orders into the wrong series.
    series_ok, series_msg = _validate_active_series(sap)
    if not series_ok:
        frappe.log_error(series_msg, "post_invoices series guard")
        _emit_post(f"ABORTED — {series_msg}", level="error")
        return {
            "processed": 0, "posted": 0, "batch_hold": 0,
            "verify": 0, "failed": 0, "skipped_claimed": 0,
            "reservation_conflicts": 0, "abort_reason": series_msg,
        }
    frappe.logger().info(f"post_invoices series guard: {series_msg}")

    _ensure_reservation_ledger_table()
    reservation_context: ReservationContext = _reservation_context_new()
    # Shared caches across the entire posting run:
    # - batch_managed_cache: item_code → True/False/None (static SAP item property)
    # - series_cache: (configured_series, fiscal_period) → resolved_series
    # - fefo_cache: (item_code, wh) → HANA FEFO rows — pre-warmed once for all orders
    batch_managed_cache: BatchManagedCache = {}
    series_cache: dict = {}
    filters: dict = {"pipeline_status": "ready"}
    if ready_before:
        filters["modified"] = ["<", ready_before]
    if channel_name:
        filters["channel_name"] = channel_name
    _apply_order_date_window(filters, start_date, end_date)
    orders = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=["name", "attempt_count"],
        order_by="order_date asc, creation asc",
        limit=limit,
    )
    fefo_cache: dict = _prewarm_fefo_cache(sap, orders)

    total = len(orders)
    _emit_post(f"Ready orders to post: {total}")

    processed = 0
    posted = 0
    batch_hold = 0
    verify = 0
    failed = 0
    skipped_claimed = 0
    batch_shortages = []

    for idx, row in enumerate(orders, 1):
        if not _claim_ready_order(row.name):
            skipped_claimed += 1
            continue
        processed += 1
        _emit_post(f"Posting [{idx}/{total}] {row.name}…", level="info")
        try:
            outcome, shortages = _post_order(
                sap, row,
                reservation_context=reservation_context,
                batch_managed_cache=batch_managed_cache,
                series_cache=series_cache,
                fefo_cache=fefo_cache,
            )
            if outcome == "posted":
                posted += 1
                sap_doc = frappe.db.get_value("Unicommerce Orders", row.name, "sap_ar_invoice_docentry") or "—"
                _emit_post(f"[{idx}/{total}] {row.name} → posted  SAP DocEntry: {sap_doc}", level="success")
                _reservation_consume_for_order(reservation_context, row.name)
            elif outcome == "batch_hold":
                batch_hold += 1
                batch_shortages.extend(shortages)
                shortage_summary = "; ".join(
                    f"{s.get('item_code','?')} batch {s.get('batch_number','?')}: need {s.get('required',0)} have {s.get('available',0)}"
                    for s in (shortages or [])[:3]
                )
                _emit_post(f"[{idx}/{total}] {row.name} → batch_hold  {shortage_summary}", level="warning")
                _reservation_release_for_order(reservation_context, row.name, "batch_hold")
            elif outcome == "verify":
                verify += 1
                _emit_post(f"[{idx}/{total}] {row.name} → verify (timeout — will confirm on next cycle)", level="warning")
                _reservation_release_for_order(reservation_context, row.name, "verify")
        except Exception as e:
            failed += 1
            _reservation_release_for_order(reservation_context, row.name, "failed")
            _mark_failed(row, str(e))
            _emit_post(f"[{idx}/{total}] {row.name} → failed: {str(e)[:120]}", level="error")
            frappe.logger().error(f"Order processor failed for {row.name}: {e}")
        finally:
            frappe.db.commit()

    if batch_shortages:
        try:
            from ..api.ops import send_batch_shortage_digest

            send_batch_shortage_digest(batch_shortages)
        except Exception:
            frappe.logger().warning(
                "send_batch_shortage_digest failed; skipping (see Error Log for details)",
                exc_info=True,
            )

    reservation_conflicts = 0
    for row in batch_shortages:
        if str((row or {}).get("reason") or "") == "reservation_conflict":
            reservation_conflicts += 1

    _emit_post(
        f"Pass complete — processed {processed}, posted {posted}, "
        f"batch_hold {batch_hold}, verify {verify}, failed {failed}",
        level="success" if not failed else "warning",
    )

    return {
        "processed": processed,
        "posted": posted,
        "batch_hold": batch_hold,
        "verify": verify,
        "failed": failed,
        "skipped_claimed": skipped_claimed,
        "reservation_conflicts": reservation_conflicts,
    }


def _apply_order_date_window(filters: dict, start_date: str | None, end_date: str | None) -> None:
    """Restrict an Unicommerce Orders frappe.get_all filter dict to an order_date window.

    Both endpoints are inclusive. Either bound may be omitted (one-sided range).
    Date strings are expected in YYYY-MM-DD; whitespace-only values are ignored.
    """
    start = (start_date or "").strip()
    end = (end_date or "").strip()
    if start and end:
        filters["order_date"] = ["between", [start, end]]
    elif start:
        filters["order_date"] = [">=", start]
    elif end:
        filters["order_date"] = ["<=", end]


def _recover_failed_orders(limit: int = 50, start_date: str | None = None, end_date: str | None = None) -> int:
    filters: dict = {"pipeline_status": "failed"}
    _apply_order_date_window(filters, start_date, end_date)
    rows = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=["name", "attempt_count", "modified"],
        order_by="modified asc",
        limit=max(int(limit or 0), 0) or 50,
    )
    recovered = 0
    for row in rows:
        attempt = max(int(row.attempt_count or 1), 1)
        cooldown_mins = min(
            FAILED_RETRY_MAX_DELAY_MINS,
            FAILED_RETRY_BASE_DELAY_MINS * (2 ** max(attempt - 1, 0)),
        )
        elapsed = time_diff_in_seconds(now_datetime(), row.modified)
        if elapsed is None or elapsed < (cooldown_mins * 60):
            continue
        frappe.db.set_value(
            "Unicommerce Orders",
            row.name,
            {
                "pipeline_status": "ready",
            },
        )
        recovered += 1
    if recovered:
        frappe.db.commit()
    return recovered


def _recover_batch_hold_orders(limit: int = 50, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Auto-requeue batch_hold orders back to ``ready`` after the cooldown.

    Behaviour:

    * Orders in ``batch_hold`` whose ``modified`` is older than
      ``BATCH_HOLD_RETRY_DELAY_MINS`` are transitioned back to ``ready`` and
      have ``attempt_count`` incremented by one.
    * Orders that have exceeded **either** ``BATCH_HOLD_MAX_ATTEMPTS`` (attempts)
      or ``BATCH_HOLD_MAX_HOURS`` (wall-clock time since ``batch_hold_since``)
      are escalated to ``dead`` with a clear ``last_error`` so an operator can
      act without the order silently cycling forever.
    * Orders still within cooldown are skipped untouched.

    Unlike failed orders (exponential backoff), batch holds use a flat cooldown
    because we're waiting for stock replenishment, not a transient error. Each
    posting cycle will re-validate the batch; if stock is still insufficient
    the order drops back to ``batch_hold`` and the clock resets — but the hold
    cap still trips via ``batch_hold_since`` (which is **not** reset on
    re-entry into the hold) and ``attempt_count`` (which is monotonic).

    Returns a dict with ``recovered`` (→ ``ready``) and ``escalated`` (→ ``dead``)
    so the caller can surface both numbers in the Ops Center summary.
    """
    filters: dict = {"pipeline_status": "batch_hold"}
    _apply_order_date_window(filters, start_date, end_date)
    rows = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=["name", "modified", "attempt_count", "batch_hold_since", "last_error"],
        order_by="modified asc",
        limit=max(int(limit or 0), 0) or 50,
    )
    recovered = 0
    escalated = 0
    now = now_datetime()
    for row in rows:
        attempt = int(row.attempt_count or 0)
        hold_since = row.batch_hold_since or row.modified
        hours_held = 0.0
        try:
            if hold_since:
                hours_held = float(time_diff_in_hours(now, hold_since) or 0)
        except Exception:
            hours_held = 0.0

        if attempt >= BATCH_HOLD_MAX_ATTEMPTS or hours_held >= BATCH_HOLD_MAX_HOURS:
            reason = (
                f"Batch hold exceeded cap (attempts={attempt}/{BATCH_HOLD_MAX_ATTEMPTS}, "
                f"hours={hours_held:.1f}/{BATCH_HOLD_MAX_HOURS}). Last shortage: "
                f"{(row.last_error or 'n/a')[:700]}"
            )
            frappe.db.set_value(
                "Unicommerce Orders",
                row.name,
                {
                    "pipeline_status": "dead",
                    "last_error": reason[:1000],
                },
            )
            try:
                from ..api.ops import send_failure_alert

                send_failure_alert("order_failed", "Unicommerce Orders", row.name, reason)
            except Exception:
                frappe.logger().warning(
                    f"send_failure_alert for escalated batch_hold {row.name} failed; see Error Log",
                    exc_info=True,
                )
            escalated += 1
            continue

        # Reservation conflicts clear the moment the earlier order's batch is
        # consumed — no point waiting the full cooldown; retry immediately.
        is_reservation_conflict = "reservation_conflict" in str(row.last_error or "").lower()
        elapsed = time_diff_in_seconds(now, row.modified)
        if not is_reservation_conflict and (elapsed is None or elapsed < (BATCH_HOLD_RETRY_DELAY_MINS * 60)):
            continue
        frappe.db.sql(
            """UPDATE `tabUnicommerce Orders`
               SET pipeline_status = 'ready',
                   attempt_count = attempt_count + 1
               WHERE name = %s AND pipeline_status = 'batch_hold'""",
            row.name,
        )
        recovered += 1

    if recovered or escalated:
        frappe.db.commit()
    return {"recovered": recovered, "escalated": escalated}


def _post_order(
    sap: SAPClient,
    row,
    reservation_context: ReservationContext | None = None,
    batch_managed_cache: "BatchManagedCache | None" = None,
    series_cache: "dict | None" = None,
    fefo_cache: "dict | None" = None,
) -> tuple[str, list]:
    """
    Returns (outcome, shortages) where outcome is "posted" | "batch_hold" | "verify".

    batch_managed_cache, series_cache, fefo_cache should be created once per
    posting run in _post_ready_orders and shared — eliminates O(orders × items)
    duplicate SAP/HANA round-trips.
    """
    staging = frappe.get_doc("Unicommerce Orders", row.name)
    if batch_managed_cache is None:
        batch_managed_cache = {}

    # Idempotency guard: if SAP already has an invoice for this order (from a
    # prior posting attempt that timed out before Frappe could write the docentry),
    # mark it posted immediately and skip re-posting to SAP.
    try:
        existing = sap.find_invoice_by_uc_order_id(row.name)
        if existing:
            frappe.db.set_value(
                "Unicommerce Orders",
                row.name,
                {
                    "pipeline_status": "posted",
                    "sap_ar_invoice_docentry": str(existing.get("DocEntry") or ""),
                    "sap_ar_invoice_docnum": str(existing.get("DocNum") or ""),
                    "ar_invoice_tax_actual": float(existing.get("DocTaxAmount") or 0),
                    "batch_hold_since": None,
                    "last_error": "",
                },
            )
            frappe.db.commit()
            frappe.logger().info(
                f"_post_order({row.name}): SAP invoice already exists "
                f"(DocEntry={existing.get('DocEntry')}); skipping re-post."
            )
            return "posted", []
    except Exception:
        # If the SAP lookup itself fails, proceed with posting — worst case is
        # _verify_posted_orders catches a duplicate on the next cycle. Suppressing
        # here avoids blocking the entire posting run on a transient SAP outage.
        frappe.logger().warning(
            f"_post_order({row.name}): idempotency check failed (SAP unreachable?); proceeding with post",
            exc_info=True,
        )

    batch_check = _check_batches(
        sap,
        staging,
        batch_managed_cache=batch_managed_cache,
        reservation_context=reservation_context,
        fefo_cache=fefo_cache,
        fast_mode=True,
    )
    if not batch_check["ok"]:
        last_error = _batch_shortage_message(batch_check["missing"])
        hold_updates = {
            "pipeline_status": "batch_hold",
            "last_error": last_error[:2000],
        }
        if not staging.get("batch_hold_since"):
            hold_updates["batch_hold_since"] = now_datetime()
        frappe.db.set_value("Unicommerce Orders", row.name, hold_updates)
        return "batch_hold", batch_check["missing"]

    payload = ar_invoice_payload(
        staging,
        batch_managed_cache=batch_managed_cache,
        fefo_rows_cache=batch_check.get("fefo_rows_cache") or {},
        fefo_overrides=batch_check.get("fefo_overrides") or {},
    )
    staging.payload_json = json.dumps(payload, separators=(",", ":"), default=str)
    staging.save(ignore_permissions=True)

    frappe.db.set_value(
        "Unicommerce Orders",
        row.name,
        {
            "pipeline_status": "posting",
            "posting_started_at": now_datetime(),
            "batch_hold_since": None,
            "last_error": "",
        },
    )
    frappe.db.commit()

    try:
        result, posted_payload = _post_invoice_with_series_fallback(sap, payload, series_cache=series_cache)
    except Exception as e:
        err = str(e)
        lower = err.lower()
        if "timeout" in lower or "connection" in lower:
            frappe.db.set_value(
                "Unicommerce Orders",
                row.name,
                {
                    "pipeline_status": "verify",
                    "last_error": err[:1000],
                },
            )
            return "verify", []
        raise

    try:
        # Use set_value (not staging.save) because an earlier frappe.db.set_value
        # already bumped the row's `modified` timestamp — staging's in-memory
        # copy is now stale, so calling .save() would raise TimestampMismatchError
        # and spam the operator's message log with scary "has been modified after
        # you have opened it" popups even though the invoice did post to SAP.
        frappe.db.set_value(
            "Unicommerce Orders",
            row.name,
            "payload_json",
            json.dumps(posted_payload, separators=(",", ":"), default=str),
            update_modified=False,
        )
    except Exception:
        frappe.logger().warning(
            f"_post_order({row.name}): could not persist posted payload_json "
            "(invoice was still posted to SAP)",
            exc_info=True,
        )

    doc_entry = result.get("DocEntry")
    doc_num = result.get("DocNum")
    tax_actual = float(result.get("DocTaxAmount") or 0)

    invoice_detail = {}
    if doc_entry:
        try:
            invoice_detail = sap.get_invoice_by_doc_entry(doc_entry)
        except Exception:
            frappe.logger().warning(
                f"_post_order({row.name}): could not fetch invoice detail after posting; "
                "recon diffs will be updated by the background reconciliation pass",
                exc_info=True,
            )

    frappe.db.set_value(
        "Unicommerce Orders",
        row.name,
        {
            "pipeline_status": "posted",
            "sap_ar_invoice_docentry": str(doc_entry) if doc_entry is not None else "",
            "sap_ar_invoice_docnum": str(doc_num) if doc_num is not None else "",
            "ar_invoice_tax_actual": float(tax_actual or 0),
            "batch_hold_since": None,
        },
    )
    _update_reconciliation_diffs(row.name, invoice=invoice_detail)
    _update_line_items_after_post(row.name, doc_num=doc_num, invoice_detail=invoice_detail)
    return "posted", []


def _pick_active_invoice_series(sap: SAPClient) -> int | None:
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
                key=lambda series_row: (
                    0 if str(series_row.get("DefaultSeries") or "").strip().upper() in ("TYES", "Y", "TRUE", "1") else 1,
                    -(int(series_row.get("NextNumber") or 0)),
                ),
            )
            return int(rows[0].get("Series"))
        except Exception:
            continue
    return None


def _fy_period_indicator_for_doc_date(doc_date: str | None) -> str | None:
    """Map YYYY-MM-DD to SAP period indicator format (e.g. FY2526)."""
    raw = str(doc_date or "").strip()[:10]
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except Exception:
        return None
    fy_start_year = dt.year if dt.month >= 4 else dt.year - 1
    fy_end_year = fy_start_year + 1
    return f"FY{str(fy_start_year)[-2:]}{str(fy_end_year)[-2:]}"


def _match_series_prefix(name: str) -> str:
    """Normalize series name for fiscal-year variant matching."""
    raw = str(name or "").strip().upper()
    if not raw:
        return ""
    return re.sub(r"\d{2}$", "", raw)


def _pick_series_for_doc_date(
    sap: SAPClient,
    configured_series: int | None,
    doc_date: str | None,
    series_cache: "dict | None" = None,
) -> int | None:
    """Resolve a period-correct SAP series for invoice DocDate.

    series_cache keyed by (configured_series, target_period) eliminates
    repeated SeriesService SAP calls when all orders in a run share the same
    fiscal period (which is the common case).
    """
    if not configured_series:
        return None
    target_period = _fy_period_indicator_for_doc_date(doc_date)
    if not target_period:
        return int(configured_series)

    cache_key = (int(configured_series), target_period)
    if series_cache is not None and cache_key in series_cache:
        return series_cache[cache_key]

    resolved = int(configured_series)  # default: return as-is on any error
    try:
        current = sap.post("SeriesService_GetSeries", {"SeriesParams": {"Series": int(configured_series)}}) or {}
        current_period = str(current.get("PeriodIndicator") or "").strip()
        if current_period == target_period:
            resolved = int(configured_series)
        else:
            doc_subtype = str(current.get("DocumentSubType") or "--").strip() or "--"
            current_prefix = _match_series_prefix(str(current.get("Name") or ""))
            desired_suffix = target_period[-2:]
            all_series = sap.post(
                "SeriesService_GetDocumentSeries",
                {"DocumentSeriesParams": {"Document": "13", "DocumentSubType": doc_subtype}},
            ) or {}
            candidates = [
                row for row in (all_series.get("value") or [])
                if str(row.get("Locked") or "").strip().upper() != "TYES"
                and str(row.get("PeriodIndicator") or "").strip() == target_period
            ]
            if candidates:
                if current_prefix:
                    family = [
                        row for row in candidates
                        if _match_series_prefix(str(row.get("Name") or "")) == current_prefix
                    ]
                    if family:
                        exact = [
                            row for row in family
                            if str(row.get("Name") or "").strip().upper().endswith(desired_suffix)
                        ]
                        resolved = int((exact or family)[0].get("Series"))
                    else:
                        candidates.sort(key=lambda r: int(r.get("NextNumber") or 0), reverse=True)
                        resolved = int(candidates[0].get("Series"))
                else:
                    candidates.sort(key=lambda r: int(r.get("NextNumber") or 0), reverse=True)
                    resolved = int(candidates[0].get("Series"))
    except Exception:
        resolved = int(configured_series)

    if series_cache is not None:
        series_cache[cache_key] = resolved
    return resolved


def _post_invoice_with_series_fallback(
    sap: SAPClient,
    payload: dict,
    series_cache: "dict | None" = None,
) -> tuple[dict, dict]:
    """
    Post invoice with resilient numbering series fallback:
    configured payload series -> active SAP series -> no series.
    Returns (sap_result, payload_used_for_post).
    """
    payload_to_post = dict(payload)
    resolved_series = _pick_series_for_doc_date(
        sap,
        payload_to_post.get("Series"),
        payload_to_post.get("DocDate"),
        series_cache=series_cache,
    )
    if resolved_series:
        payload_to_post["Series"] = int(resolved_series)
    try:
        result = sap.post("Invoices", payload_to_post)
        return result, payload_to_post
    except Exception as e:
        msg = str(e or "")
        if "numbering series" not in msg.lower():
            raise

    fallback_series = _pick_active_invoice_series(sap)
    if fallback_series:
        payload_with_fallback = dict(payload)
        payload_with_fallback["Series"] = int(fallback_series)
        try:
            result = sap.post("Invoices", payload_with_fallback)
            return result, payload_with_fallback
        except Exception as e:
            msg = str(e or "")
            if "numbering series" not in msg.lower():
                raise

    payload_without_series = dict(payload)
    payload_without_series.pop("Series", None)
    result = sap.post("Invoices", payload_without_series)
    return result, payload_without_series


def _update_line_items_after_post(doc_name: str, doc_num=None, invoice_detail: dict | None = None):
    """
    After an AR Invoice is posted to SAP, stamp the child line_items rows with:
      - sap_invoice_no  : SAP AR Invoice DocNum
      - sap_filled_status : "Invoice Posted"
      - delivery_linenum  : SAP DocumentLines[*].LineNum (matched by item code)

    Falls back gracefully if the invoice detail is missing or mapping fails.
    """
    if not doc_num:
        return

    sap_doc_num = str(doc_num)
    invoice_lines: list[dict] = (invoice_detail or {}).get("DocumentLines") or []

    # Build ItemCode → [LineNum, ...] map from the SAP invoice response
    # (an item may appear on multiple lines; keep a queue so we can pop one per UC row)
    from collections import defaultdict
    line_num_by_item: dict[str, list[int]] = defaultdict(list)
    for line in invoice_lines:
        item_code = str(line.get("ItemCode") or "").strip()
        line_num = line.get("LineNum")
        if item_code and line_num is not None:
            try:
                line_num_by_item[item_code].append(int(line_num))
            except Exception:
                pass

    # Load the child rows for this order
    child_rows = frappe.get_all(
        "Order Line Items",
        filters={"parent": doc_name, "parenttype": "Unicommerce Orders"},
        fields=["name", "itemsku"],
        order_by="idx asc",
    )

    for row in child_rows:
        item_code = str(row.itemsku or "").strip()
        # Pop the first matching SAP line number (FIFO — same order items appear)
        line_num_val = ""
        if item_code and line_num_by_item.get(item_code):
            line_num_val = str(line_num_by_item[item_code].pop(0))

        frappe.db.set_value(
            "Order Line Items",
            row.name,
            {
                "sap_invoice_no": sap_doc_num,
                "sap_filled_status": "Invoice Posted",
                "delivery_linenum": line_num_val,
            },
            update_modified=False,
        )


def _mark_failed(row, err: str):
    attempt = int(row.attempt_count or 0) + 1
    configured = int(frappe.db.get_single_value("Unicommerce Settings", "max_retry_attempts") or 0)
    max_retries = max(8, configured) if configured > 0 else 8
    new_status = "dead" if attempt >= max_retries else "failed"
    frappe.db.set_value(
        "Unicommerce Orders",
        row.name,
        {
            "pipeline_status": new_status,
            "attempt_count": attempt,
            "last_error": err[:1000],
            "batch_hold_since": None,
        },
    )
    try:
        from ..api.ops import send_failure_alert
        send_failure_alert("order_failed", "Unicommerce Orders", row.name, err)
    except Exception:
        frappe.logger().warning(
            f"send_failure_alert for {row.name} failed; see Error Log",
            exc_info=True,
        )


def _update_reconciliation_diffs(doc_name: str, invoice: dict | None = None):
    doc = frappe.db.get_value(
        "Unicommerce Orders",
        doc_name,
        ["ar_invoice_tax_expected", "ar_invoice_tax_actual", "payload_json", "sap_ar_invoice_docentry"],
        as_dict=True,
    )
    if not doc:
        return

    payload = {}
    if doc.payload_json:
        try:
            payload = json.loads(doc.payload_json)
        except Exception:
            payload = {}
    payload_lines = payload.get("DocumentLines", [])
    expected_unit_total = _sum_unit_price_total_from_lines(payload_lines)
    expected_tax_total = _sum_tax_total_from_lines(payload_lines)

    actual_tax = float(doc.ar_invoice_tax_actual or 0)
    actual_unit_total = 0.0
    actual_tax_from_lines = 0.0
    used_line_tax = False
    if invoice:
        invoice_lines = invoice.get("DocumentLines", [])
        actual_tax = float(invoice.get("DocTaxAmount") or actual_tax or 0)
        actual_unit_total = _sum_unit_price_total_from_lines(invoice_lines)
        actual_tax_from_lines, used_line_tax = _sum_tax_total_from_lines(invoice_lines, return_used=True)

    # If no invoice was provided and we have nothing to compare, skip updating reconciliation
    # to avoid falsely marking orders as "matched" when expected is also 0 (empty payload).
    if not invoice and expected_unit_total == 0.0 and expected_tax_total == 0.0:
        return

    # Prefer line-level tax when available. Some SAP tenants return empty/zero DocTaxAmount
    # even though DocumentLines carry tax values.
    if used_line_tax:
        actual_tax = actual_tax_from_lines
    elif actual_tax <= 0 and actual_unit_total > 0 and expected_unit_total > 0 and expected_tax_total > 0:
        # Last fallback: proportional allocation from expected ratio to avoid false large mismatches
        # when DocTaxAmount is unavailable and line-level tax keys are hidden.
        actual_tax = round((actual_unit_total / expected_unit_total) * expected_tax_total, 2)

    tax_expected = float(doc.ar_invoice_tax_expected or expected_tax_total or 0)
    tax_diff = abs(tax_expected - actual_tax)
    unit_diff = abs(expected_unit_total - actual_unit_total)
    is_matched = (tax_diff <= 1.0) and (unit_diff <= 1.0)
    frappe.db.set_value(
        "Unicommerce Orders",
        doc_name,
        {
            "ar_invoice_tax_actual": actual_tax,
            "ar_invoice_tax_expected": round(tax_expected, 2),
            "ar_invoice_tax_diff": tax_diff,
            "ar_invoice_unit_price_expected": expected_unit_total,
            "ar_invoice_unit_price_actual": actual_unit_total,
            "ar_invoice_unit_price_diff": unit_diff,
            "ar_invoice_reconciled": int(is_matched),
            "ar_invoice_reconciliation_status": (
                "Reconciled and matched with SAP" if is_matched else "Mismatch (SAP vs expected)"
            ),
        },
    )


def _sum_unit_price_total_from_lines(lines: list[dict]) -> float:
    total = 0.0
    for line in lines or []:
        try:
            qty = float(line.get("Quantity", 0) or 0)
            unit_price = float(line.get("UnitPrice", 0) or 0)
        except (TypeError, ValueError):
            continue
        total += qty * unit_price
    return round(total, 2)


def _sum_tax_total_from_lines(lines: list[dict], return_used: bool = False):
    total = 0.0
    used = False
    candidate_keys = (
        "TaxTotal",
        "TaxAmount",
        "LineTaxTotal",
        "LineTaxAmount",
        "TaxExpense",
        "TaxLineTotal",
    )
    for line in lines or []:
        for key in candidate_keys:
            if key not in line:
                continue
            try:
                total += float(line.get(key) or 0)
            except Exception:
                total += 0.0
            used = True
            break
    rounded = round(total, 2)
    if return_used:
        return rounded, used
    return rounded


def _recover_stuck(start_date: str | None = None, end_date: str | None = None):
    timeout_mins = int(frappe.db.get_single_value("Unicommerce Settings", "posting_timeout_mins") or 5)
    filters: dict = {"pipeline_status": "posting"}
    _apply_order_date_window(filters, start_date, end_date)
    posting_orders = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=["name", "posting_started_at"],
    )
    for row in posting_orders:
        if not row.posting_started_at:
            frappe.db.set_value("Unicommerce Orders", row.name, "pipeline_status", "verify")
            continue
        elapsed = time_diff_in_seconds(now_datetime(), row.posting_started_at)
        if elapsed is not None and elapsed > (timeout_mins * 60):
            frappe.db.set_value("Unicommerce Orders", row.name, "pipeline_status", "verify")


def _verify_posted_orders(limit: int = 50, start_date: str | None = None, end_date: str | None = None):
    sap = SAPClient()
    configured = int(frappe.db.get_single_value("Unicommerce Settings", "max_retry_attempts") or 0)
    max_retries = max(8, configured) if configured > 0 else 8
    filters: dict = {"pipeline_status": "verify"}
    _apply_order_date_window(filters, start_date, end_date)
    orders = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=["name", "attempt_count"],
        order_by="modified asc",
        limit=limit,
    )
    checked = posted = requeued = dead = 0
    for row in orders:
        checked += 1
        try:
            existing = sap.find_invoice_by_uc_order_id(row.name)
            if existing:
                frappe.db.set_value(
                    "Unicommerce Orders",
                    row.name,
                    {
                        "pipeline_status": "posted",
                        "sap_ar_invoice_docentry": str(existing.get("DocEntry") or ""),
                        "sap_ar_invoice_docnum": str(existing.get("DocNum") or ""),
                        "ar_invoice_tax_actual": float(existing.get("DocTaxAmount") or 0),
                        "batch_hold_since": None,
                    },
                )
                invoice = {}
                if existing.get("DocEntry"):
                    try:
                        invoice = sap.get_invoice_by_doc_entry(existing.get("DocEntry"))
                    except Exception:
                        invoice = {}
                _update_reconciliation_diffs(row.name, invoice=invoice)
                _update_line_items_after_post(row.name, doc_num=existing.get("DocNum"), invoice_detail=invoice)
                posted += 1
            else:
                transitioned_to = _requeue_or_dead_from_verify(
                    row=row,
                    max_retries=max_retries,
                    error_msg="Invoice not found during verify",
                )
                if transitioned_to == "dead":
                    dead += 1
                else:
                    requeued += 1
        except Exception as e:
            transitioned_to = _requeue_or_dead_from_verify(
                row=row,
                max_retries=max_retries,
                error_msg=f"Verify error: {str(e)[:950]}",
            )
            if transitioned_to == "dead":
                dead += 1
            else:
                requeued += 1
        finally:
            frappe.db.commit()

    return {
        "checked": checked,
        "posted": posted,
        "requeued": requeued,
        "dead": dead,
    }


def _resolve_batch_managed(
    sap: SAPClient,
    item_code: str,
    cache: "BatchManagedCache | None" = None,
) -> "bool | None":
    """Return SAP's ``ManageBatchNumbers`` flag for an item.

    Tri-state: ``True`` / ``False`` / ``None`` (lookup failed). The ``cache``
    argument is shared between ``_check_batches`` and ``ar_invoice_payload``
    so both layers make the same decision for the same item in the same
    posting cycle.
    """
    code = str(item_code or "").strip()
    if not code:
        return False
    if cache is not None and code in cache:
        return cache[code]
    try:
        safe_code = code.replace("'", "''")
        payload = sap.get(f"Items('{safe_code}')", params={"$select": "ManageBatchNumbers"})
        value = str(payload.get("ManageBatchNumbers") or "").strip().upper()
        managed = value in ("TYES", "Y", "YES", "TRUE", "1")
        if cache is not None:
            cache[code] = managed
        return managed
    except Exception as exc:
        frappe.logger().warning(
            "_resolve_batch_managed: SAP Service Layer lookup failed for item=%s: %s; "
            "marking as UNKNOWN so validation and payload both skip batch allocation",
            code,
            exc,
        )
        if cache is not None:
            cache[code] = None
        return None


def _try_fefo_rescue_ec_fg(
    sap: SAPClient,
    requirement: dict,
    qty_needed: float,
    reservation_context,
    fefo_cache,
    hana_fefo_cache: dict,
    fefo_overrides: dict,
    fefo_rescue_additions: dict,
    keys_to_remove: list,
    fast_mode: bool,
) -> bool:
    """For EC-FG channels: when the UC-specified batch is unavailable in EC-FG,
    attempt FEFO allocation from EC-FG across all available batches.
    Returns True if rescue succeeded; modifies fefo_overrides / fefo_rescue_additions
    / keys_to_remove in-place so the caller can skip adding a shortage.
    """
    try:
        settings = frappe.get_cached_doc("Unicommerce Settings")
        if not getattr(settings, "ec_fg_fefo_fallback", False):
            return False
    except Exception:
        return False

    batch_number = requirement.get("batch_number")
    if not batch_number or requirement["warehouse_code"] != DEFAULT_WAREHOUSE:
        return False

    item_code = requirement["item_code"]
    cache_key = (item_code, DEFAULT_WAREHOUSE)

    # Always work from hana_fefo_cache so allocations are deducted in-place
    # between successive rescues for the same item (different UC batches).
    # fefo_cache is the shared pre-warmed cache — never mutate it.
    if cache_key not in hana_fefo_cache:
        seed_rows = None
        if fefo_cache is not None:
            seed_rows = fefo_cache.get(cache_key)
        if seed_rows is None:
            try:
                raw = sap.bulk_batch_inventory_by_warehouse(DEFAULT_WAREHOUSE, [item_code])
                seed_rows = [
                    {"distnumber": r["batch_number"], "quantity": r["quantity"], "expdate": r.get("expiry")}
                    for r in raw
                ]
            except Exception as exc:
                frappe.logger().warning(
                    "FEFO rescue: HANA query failed for %s@%s: %s", item_code, DEFAULT_WAREHOUSE, exc,
                )
                hana_fefo_cache[cache_key] = None
                return False
        # Store a mutable copy so deductions don't affect fefo_cache or the original list.
        hana_fefo_cache[cache_key] = [dict(r) for r in seed_rows] if seed_rows else None

    hana_rows = hana_fefo_cache[cache_key]
    if not hana_rows:
        return False

    fefo_allocs = _fefo_allocate_from_rows(hana_rows, qty_needed)
    if not fefo_allocs:
        return False

    # Deduct allocated quantities from the mutable cache so the next rescue
    # for this item sees reduced stock rather than the full snapshot.
    alloc_by_batch = {a["BatchNumber"]: float(a.get("Quantity", 0)) for a in fefo_allocs}
    for row in hana_rows:
        deduct = alloc_by_batch.get(row["distnumber"], 0.0)
        if deduct:
            row["quantity"] = max(0.0, float(row["quantity"]) - deduct)

    fefo_overrides[(item_code, batch_number)] = fefo_allocs
    orig_key = (item_code, batch_number, DEFAULT_WAREHOUSE)
    keys_to_remove.append(orig_key)

    for alloc in fefo_allocs:
        alloc_batch = alloc.get("BatchNumber")
        if not alloc_batch:
            continue
        rescue_key = (item_code, alloc_batch, DEFAULT_WAREHOUSE)
        if rescue_key in fefo_rescue_additions:
            fefo_rescue_additions[rescue_key]["qty_needed"] += float(alloc.get("Quantity") or 0)
        else:
            fefo_rescue_additions[rescue_key] = {
                "record_name": requirement["record_name"],
                "uc_order_id": requirement["uc_order_id"],
                "channel": requirement["channel"],
                "item_code": item_code,
                "batch_number": alloc_batch,
                "warehouse_code": DEFAULT_WAREHOUSE,
                "qty_needed": float(alloc.get("Quantity") or 0),
            }

    frappe.logger().info(
        "FEFO rescue: order %s item %s UC-batch %s → FEFO %s",
        requirement.get("uc_order_id"),
        item_code,
        batch_number,
        [(a["BatchNumber"], a["Quantity"]) for a in fefo_allocs],
    )
    return True


def _check_batches(
    sap: SAPClient,
    staging,
    batch_managed_cache: "BatchManagedCache | None" = None,
    quantity_cache: "dict[tuple[str, str, str], float] | None" = None,
    pre_parsed_items: "list[dict] | None" = None,
    pre_resolved_settings=None,
    fefo_cache: "dict[tuple[str, str], list[dict]] | None" = None,
    wh_resolve_cache: "dict[tuple[str, str], str] | None" = None,
    quantity_cache_authoritative: bool = False,
    reservation_context: ReservationContext | None = None,
    fast_mode: bool = False,
) -> dict:
    """Validate all batch-tracked lines have sufficient quantity in SAP.

    Returns ``{"ok": bool, "missing": [shortage_dict, ...]}``.

    ``batch_managed_cache`` is a tri-state dict (True/False/None — see
    ``BatchManagedCache``). Pass the same dict through to ``ar_invoice_payload``
    so payload construction and validation agree on "unknown" items.

    Behaviour of the tri-state:

    * ``True``  — item is batch-managed → allocate via FEFO and enforce qty.
    * ``False`` — item is NOT batch-managed → skip batch allocation; do not
      enforce a shortage for this line.
    * ``None``  — SAP Service Layer lookup failed for this item. We cannot
      safely allocate a batch. Per the chosen ``skip_payload_too`` policy, BOTH
      ``_check_batches`` and ``ar_invoice_payload`` skip batch allocation for
      the line. SAP may reject at post time (which leads to ``failed`` →
      standard retry path), but this is deliberate: we never silently post an
      unvalidated batch.

    ``quantity_cache`` is an optional dict keyed by ``(item_code, batch_number,
    warehouse_code)`` → available quantity. Callers that pre-warm this cache
    via ``SAPClient.bulk_batch_quantities_by_warehouse`` (e.g. the Ops Center
    pre-validate dry-run) turn a per-line SAP round-trip into an in-memory
    dict lookup. On a cache miss we fall through to the real per-line
    ``check_batch_quantity`` call, so this is always safe to leave unset.

    ``pre_parsed_items`` / ``pre_resolved_settings`` are hot-path hooks used
    by the Ops Center pre-validate flow to skip the redundant
    ``json.loads(staging.order_json)`` + ``_parse_line_items`` and the
    per-call ``frappe.get_single("Unicommerce Settings")`` DB hit. When
    supplied, ``staging`` is only read for ``.name`` and ``.channel_name``,
    so callers can pass any duck-typed object (including a
    ``frappe._dict``) instead of a freshly-loaded Document. Leaving both
    unset preserves the exact original behaviour for the live posting flow.

    ``fefo_cache`` / ``wh_resolve_cache`` are two more Ops Center hot-path
    hooks. ``fefo_cache`` is ``{(item_code, sap_wh_code): [rows]}`` of HANA
    batch rows already sorted FEFO — when a hit is present we allocate
    in-memory via ``_fefo_allocate_from_rows`` and skip a live HANA round-trip.
    ``wh_resolve_cache`` is ``{(channel, uc_wh): sap_wh}`` so the settings JSON
    is parsed once per unique pair instead of once per line. Both default to
    ``None`` and fall back to a live HANA lookup on a miss.
    """
    settings = pre_resolved_settings if pre_resolved_settings is not None else frappe.get_single("Unicommerce Settings")
    if pre_parsed_items is not None:
        items = pre_parsed_items
    else:
        uc_data = json.loads(staging.order_json or "{}")
        items = _parse_line_items(uc_data)
    aggregated: dict[tuple[str, str, str], dict] = {}
    shortages: list[dict] = []
    if batch_managed_cache is None:
        batch_managed_cache = {}
    # Per-call HANA lookup cache: (item_code, wh) → rows (None = HANA query failed).
    _hana_fefo_cache: dict[tuple[str, str], list[dict] | None] = {}

    for item in items:
        batch_num = item.get("batchNumber")
        item_code = item.get("itemSku")
        qty_needed = float(item.get("quantity", 0) or 0)
        if not item_code or qty_needed <= 0:
            continue
        uc_wh = item.get("warehouseCode", "")
        channel_name = getattr(staging, "channel_name", "") or ""
        if wh_resolve_cache is not None:
            wh_key = (channel_name, uc_wh or "")
            sap_wh = wh_resolve_cache.get(wh_key)
            if sap_wh is None:
                sap_wh = _resolve_sap_warehouse(settings, channel_name, uc_wh)
                wh_resolve_cache[wh_key] = sap_wh
        else:
            sap_wh = _resolve_sap_warehouse(settings, channel_name, uc_wh)

        if not batch_num:
            managed = _resolve_batch_managed(sap, item_code, cache=batch_managed_cache)
            if managed is None:
                # SL error → skip batch allocation. Payload builder (passed the
                # same cache) will do the same, keeping the two layers consistent.
                continue
            if not managed:
                continue

            # Resolve FEFO rows from HANA. Priority:
            # 1. fefo_cache pre-warmed by the caller (bulk HANA query, fastest).
            # 2. Per-item HANA query (single item+wh, cached within this call).
            hana_rows: list[dict] | None = None
            cache_key = (item_code, sap_wh)
            if fefo_cache is not None:
                hana_rows = fefo_cache.get(cache_key)
            if hana_rows is None:
                if cache_key not in _hana_fefo_cache:
                    try:
                        raw = sap.bulk_batch_inventory_by_warehouse(sap_wh, [item_code])
                        _hana_fefo_cache[cache_key] = [
                            {"distnumber": r["batch_number"], "quantity": r["quantity"], "expdate": r.get("expiry")}
                            for r in raw
                        ]
                    except Exception as _exc:
                        frappe.logger().warning(
                            "_check_batches: HANA batch lookup %s@%s failed: %s", item_code, sap_wh, _exc,
                        )
                        _hana_fefo_cache[cache_key] = None
                hana_rows = _hana_fefo_cache.get(cache_key)

            fefo_rows = hana_rows or []
            allocations = _fefo_allocate_from_rows(fefo_rows, qty_needed)

            if allocations:
                for alloc in allocations:
                    alloc_batch = alloc.get("BatchNumber")
                    alloc_qty = float(alloc.get("Quantity") or 0)
                    if not alloc_batch or alloc_qty <= 0:
                        continue
                    key = (item_code, alloc_batch, sap_wh)
                    if key not in aggregated:
                        aggregated[key] = {
                            "record_name": staging.name,
                            "uc_order_id": staging.name,
                            "channel": staging.channel_name,
                            "item_code": item_code,
                            "batch_number": alloc_batch,
                            "warehouse_code": sap_wh,
                            "qty_needed": 0.0,
                        }
                    aggregated[key]["qty_needed"] += alloc_qty
                continue

            # No allocation possible — genuine HANA shortage.
            sap_avail = round(sum(float(r.get("quantity") or 0) for r in fefo_rows), 3)
            shortages.append(
                {
                    "record_name": staging.name,
                    "uc_order_id": staging.name,
                    "channel": staging.channel_name,
                    "item_code": item_code,
                    "batch_number": "",
                    "warehouse_code": sap_wh,
                    "qty_needed": round(float(qty_needed or 0), 3),
                    "qty_available": sap_avail,
                    "shortage": round(max(0.0, float(qty_needed or 0) - sap_avail), 3),
                    "reason": "insufficient_sap_batch_qty" if fefo_rows else "no_sap_batch_available",
                }
            )
            continue

        key = (item_code, batch_num, sap_wh)
        if key not in aggregated:
            aggregated[key] = {
                "record_name": staging.name,
                "uc_order_id": staging.name,
                "channel": staging.channel_name,
                "item_code": item_code,
                "batch_number": batch_num,
                "warehouse_code": sap_wh,
                "qty_needed": 0.0,
            }
        aggregated[key]["qty_needed"] += qty_needed

    fefo_overrides: dict[tuple, list[dict]] = {}
    fefo_rescue_additions: dict[tuple, dict] = {}
    keys_to_remove: list[tuple] = []

    for requirement in aggregated.values():
        cache_key = (
            requirement["item_code"],
            requirement["batch_number"],
            requirement["warehouse_code"],
        )
        cache_hit = quantity_cache is not None and cache_key in quantity_cache
        # When the caller promises the cache is authoritative (Ops Center
        # pre-validate after a successful HANA pre-warm), a miss means the
        # batch has literal 0 stock in that warehouse — falling back to
        # ``sap.check_batch_quantity`` only burns ~16 s of retry backoff on
        # an SL endpoint that rejects bulk-less filters with HTTP 400 and
        # then returns the same 0 anyway.
        reserved_qty = _reservation_reserved_qty(reservation_context, cache_key)
        if cache_hit or (quantity_cache is not None and quantity_cache_authoritative):
            available = float(quantity_cache.get(cache_key) or 0) if cache_hit else 0.0
            effective_available = max(0.0, available - reserved_qty)
            try:
                qty_needed = float(requirement["qty_needed"] or 0)
            except (TypeError, ValueError):
                qty_needed = 0.0
            if effective_available < (qty_needed - BATCH_QTY_TOLERANCE):
                if _try_fefo_rescue_ec_fg(
                    sap, requirement, qty_needed, reservation_context,
                    fefo_cache, _hana_fefo_cache, fefo_overrides,
                    fefo_rescue_additions, keys_to_remove, fast_mode,
                ):
                    continue
                shortage_reason = "reservation_conflict" if reserved_qty > 0 else "insufficient_batch_qty"
                shortages.append(
                    {
                        "record_name": requirement["record_name"],
                        "uc_order_id": requirement["uc_order_id"],
                        "channel": requirement["channel"],
                        "item_code": requirement["item_code"],
                        "batch_number": requirement["batch_number"],
                        "warehouse_code": requirement["warehouse_code"],
                        "qty_needed": round(qty_needed, 3),
                        "qty_available": round(effective_available, 3),
                        "shortage": round(max(0.0, qty_needed - effective_available), 3),
                        "reserved_qty": round(reserved_qty, 3),
                        "reason": shortage_reason,
                    }
                )
            continue

        try:
            available = float(
                sap.check_batch_quantity(
                    requirement["item_code"],
                    requirement["batch_number"],
                    requirement["warehouse_code"],
                    fast_mode=fast_mode,
                )
                or 0
            )
        except Exception as exc:
            # check_batch_quantity already has internal retry and normally
            # returns 0.0 on full failure (fail-safe). We still guard here so
            # a pathological HANA exception doesn't abort the entire order's
            # batch check — instead we report the line as a shortage, which
            # moves the order to batch_hold on the next cycle.
            frappe.logger().error(
                "_check_batches: check_batch_quantity raised for %s/%s/%s; "
                "treating as 0 available: %s",
                requirement["item_code"],
                requirement["batch_number"],
                requirement["warehouse_code"],
                exc,
            )
            available = 0.0

        qty_needed = float(requirement["qty_needed"] or 0)
        # Apply tolerance to avoid false holds from SAP decimal-precision rounding
        # (e.g. SAP returns 4.999 when 5.0 units are truly available).
        effective_available = max(0.0, available - reserved_qty)
        if effective_available < (qty_needed - BATCH_QTY_TOLERANCE):
            if _try_fefo_rescue_ec_fg(
                sap, requirement, qty_needed, reservation_context,
                fefo_cache, _hana_fefo_cache, fefo_overrides,
                fefo_rescue_additions, keys_to_remove, fast_mode,
            ):
                continue
            shortage_reason = "reservation_conflict" if reserved_qty > 0 else "insufficient_batch_qty"
            shortages.append(
                {
                    "record_name": requirement["record_name"],
                    "uc_order_id": requirement["uc_order_id"],
                    "channel": requirement["channel"],
                    "item_code": requirement["item_code"],
                    "batch_number": requirement["batch_number"],
                    "warehouse_code": requirement["warehouse_code"],
                    "qty_needed": round(qty_needed, 3),
                    "qty_available": round(effective_available, 3),
                    "shortage": round(max(0.0, qty_needed - effective_available), 3),
                    "reserved_qty": round(reserved_qty, 3),
                    "reason": shortage_reason,
                }
            )
    # Merge FEFO-rescued requirements into aggregated for correct reservation.
    # Accumulate into existing entries rather than overwriting, so a FEFO-rescued
    # batch that already has a direct requirement gets the combined qty reserved.
    for k in keys_to_remove:
        aggregated.pop(k, None)
    for k, v in fefo_rescue_additions.items():
        if k in aggregated:
            aggregated[k]["qty_needed"] += v["qty_needed"]
        else:
            aggregated[k] = v

    # Build fefo_rows_cache for the payload builder: merge fefo_cache (pre-warmed)
    # with any per-item HANA queries done during this call.
    fefo_rows_for_payload: dict[tuple[str, str], list[dict]] = {}
    if fefo_cache:
        fefo_rows_for_payload.update({k: v for k, v in fefo_cache.items() if v is not None})
    fefo_rows_for_payload.update({k: v for k, v in _hana_fefo_cache.items() if v is not None})

    if shortages:
        return {"ok": False, "missing": shortages, "fefo_rows_cache": fefo_rows_for_payload, "fefo_overrides": {}}

    if reservation_context:
        reservation_rows = []
        for requirement in aggregated.values():
            reservation_rows.append(
                {
                    "item_code": requirement["item_code"],
                    "batch_number": requirement["batch_number"],
                    "warehouse_code": requirement["warehouse_code"],
                    "qty": float(requirement["qty_needed"] or 0),
                }
            )
        _reservation_hold_for_order(reservation_context, staging.name, reservation_rows)
    return {"ok": True, "missing": shortages, "fefo_rows_cache": fefo_rows_for_payload, "fefo_overrides": fefo_overrides}


def _batch_shortage_message(shortages: list[dict]) -> str:
    if not shortages:
        return "Batch quantity not available in SAP"
    reason_map = {
        "no_batch_available_fefo": "no FEFO batch",
        "insufficient_batch_qty": "insufficient qty",
        "reservation_conflict": "reserved by earlier order",
    }
    lines = []
    for s in shortages[:5]:
        reason_msg = reason_map.get(str(s.get("reason") or ""), "batch check failed")
        shortage_val = s.get("shortage") or max(0.0, float(s.get("qty_needed") or 0) - float(s.get("qty_available") or 0))
        reserved_note = ""
        try:
            reserved_qty = float(s.get("reserved_qty") or 0)
            if reserved_qty > 0:
                reserved_note = f", reserved {round(reserved_qty, 3)}"
        except Exception:
            reserved_note = ""
        # Use :: separator so item codes or batch numbers containing / parse correctly.
        lines.append(
            f"{s['item_code']}::{s['batch_number']} [{s['warehouse_code']}]: "
            f"need {s['qty_needed']} have {s['qty_available']}{reserved_note} short {round(shortage_val, 3)} ({reason_msg})"
        )
    suffix = f" (+{len(shortages) - 5} more)" if len(shortages) > 5 else ""
    return " | ".join(lines) + suffix



def _requeue_or_dead_from_verify(row, max_retries: int, error_msg: str) -> str:
    """
    Move verify row back to ready (retry) or dead (retry exhausted).
    Returns the resulting status.
    """
    attempt = int(row.attempt_count or 0) + 1
    if attempt >= max_retries:
        frappe.db.set_value(
            "Unicommerce Orders",
            row.name,
            {
                "pipeline_status": "dead",
                "attempt_count": attempt,
                "last_error": error_msg[:1000],
            },
        )
        return "dead"

    frappe.db.set_value(
        "Unicommerce Orders",
        row.name,
        {
            "pipeline_status": "ready",
            "attempt_count": attempt,
            "last_error": error_msg[:1000],
        },
    )
    return "ready"
