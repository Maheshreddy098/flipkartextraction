"""
Post staged Amazon US Orders to SAP B1 as AR Invoices (one invoice per order).

Flow for each "ready" order:
  1. Claim it (set stage=posting atomically)
  2. Duplicate check: if NumAtCard already in SAP, mark posted and skip
  3. Build SAP payload via mappers.payload.build_invoice_payload
  4. POST to SAP B1 via client.sap.post_invoice
  5. On success: stage=posted, save DocEntry/DocNum/posted_at
  6. On HanaUnavailableError: unclaim (reset posting→ready), abort batch
  7. On other failure: stage=failed, save last_error
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import frappe
from frappe.utils import now_datetime

from khanal_tech_integrations.amazon_us import ORDER_DOCTYPE, enforce_posting_cutoff, posting_cutoff_violation
from khanal_tech_integrations.amazon_us.client.hana import HanaUnavailableError, _close, open_connection
from khanal_tech_integrations.amazon_us.client.sap import find_invoice_by_order_id, post_invoice
from khanal_tech_integrations.amazon_us.mappers.payload import build_invoice_payload

# SAP license has no concurrent-session ceiling (confirmed: B1i shows 99995
# available). 8 is a server-capacity choice, not a license one -- bump once
# HANA/Service Layer are observed holding up fine under it.
_POOL_SIZE = 8


# ─── Cache helpers ───────────────────────────────────────────────────────────
# _progress_lock guards the Redis read-modify-write below: with _POOL_SIZE
# workers emitting concurrently, two unlocked writes racing would silently
# drop whichever log line lost the race.
_progress_lock = threading.Lock()


def _cache_key(job_id):
    return f"amz_us_post_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[amz_invoice] {msg}")
        return
    with _progress_lock:
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
    with _progress_lock:
        raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        data.update(updates)
        frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


# ─── Main workers ─────────────────────────────────────────────────────────────

def post_ready_orders(from_date, to_date, limit=100, progress_id=None):
    """
    Post all "ready" orders whose actual_ship_date falls in [from_date, to_date].

    Ship date — not purchase date — is what decides which MTR month an order
    lands in: validated against the June 2026 MTR, all 13,019 of its orders
    shipped in June (12,910 same-day transaction, 109 next-day), while orders
    purchased in June but shipped/settled later spilled into July's MTR. Using
    a ship-date window makes "post month X" reproduce MTR month X, and orders
    without a ship date yet (not settled, so in no MTR month) simply wait in
    ready until the FBA shipments sync fills theirs.

    Called via frappe.enqueue or directly. Returns summary dict.
    Posts across a pool of _POOL_SIZE worker threads, each with its own SAP
    session and its own HANA connection (neither is safe to share across
    threads) -- claims are still race-safe via _claim's atomic UPDATE, so
    workers can never double-post the same order.
    Aborts on HanaUnavailableError: the failing worker's slice stops and
    unclaims its current order; other workers notice and stop claiming new
    orders too, but may finish whatever order they're already mid-flight on.
    Any order not claimed by the time this returns is left in ready state.
    Raises if from_date is before Amazon US Settings.posting_cutoff_date -- see
    enforce_posting_cutoff.
    """
    enforce_posting_cutoff(from_date)
    _set(progress_id, {"status": "running"})

    names = frappe.get_all(
        ORDER_DOCTYPE,
        filters={
            "stage": "ready",
            "actual_ship_date": ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]],
        },
        fields=["name", "attempt_count"],
        limit=limit,
        order_by="actual_ship_date asc",
    )

    total = len(names)
    _emit(progress_id, f"Found {total} ready orders. Starting SAP post ({_POOL_SIZE} workers)...")

    if not total:
        result = {"status": "done", "total": 0, "posted": 0, "failed": 0}
        _set(progress_id, result)
        return result

    site = frappe.local.site
    hana_down = threading.Event()
    counts_lock = threading.Lock()
    counts = {"posted": 0, "failed": 0}

    def _process_slice(slice_names):
        frappe.init(site=site)
        frappe.connect()
        try:
            hana_conn, hana_cursor = open_connection()
        except HanaUnavailableError as e:
            hana_down.set()
            msg = f"HANA unavailable: {e}."
            _emit(progress_id, msg, "error")
            frappe.log_error(msg, "Amazon US Invoice")
            return
        try:
            for row in slice_names:
                if hana_down.is_set():
                    break
                name = row["name"]
                if not _claim(name):
                    continue

                doc = frappe.get_doc(ORDER_DOCTYPE, name)
                _emit(progress_id, f"Posting {doc.amazon_order_id}...")

                try:
                    # Always check SAP first, not just on retry: attempt_count
                    # resets to 0 after any reset-for-repost, so a "first
                    # attempt" by that counter can still already be live in
                    # SAP if a concurrent process (another repost pass, a
                    # manual post) claimed the same just-reset order first.
                    # Skipping this on the (attempt_count==0) fast path caused
                    # real duplicate invoices in production testing.
                    existing = find_invoice_by_order_id(doc.amazon_order_id)
                    if existing:
                        _mark_posted(name, existing)
                        with counts_lock:
                            counts["posted"] += 1
                        _emit(progress_id, f"  RECOVERED {doc.amazon_order_id} → already in SAP DocEntry={existing['doc_entry']}")
                        continue

                    payload, skipped = build_invoice_payload(doc, hana_cursor)
                    if payload is None:
                        _mark_failed(name, f"No postable lines. Skipped: {skipped}")
                        with counts_lock:
                            counts["failed"] += 1
                        _emit(progress_id, f"  SKIP {doc.amazon_order_id}: no lines", "warn")
                        continue

                    sap_result = post_invoice(payload)
                    _mark_posted(name, sap_result, payload=payload)
                    with counts_lock:
                        counts["posted"] += 1
                    _emit(progress_id, f"  OK {doc.amazon_order_id} → DocEntry={sap_result['doc_entry']} DocNum={sap_result['doc_num']}")

                except HanaUnavailableError as e:
                    _unclaim(name)
                    hana_down.set()
                    msg = f"HANA unavailable: {e}. Order left in ready state. Aborting batch."
                    _emit(progress_id, msg, "error")
                    frappe.log_error(msg, "Amazon US Invoice")
                    break

                except Exception as e:
                    err = str(e)[:500]
                    _mark_failed(name, err)
                    with counts_lock:
                        counts["failed"] += 1
                    _emit(progress_id, f"  FAIL {doc.amazon_order_id}: {err}", "error")
        finally:
            _close(hana_conn, hana_cursor)
            frappe.destroy()

    slices = [names[i::_POOL_SIZE] for i in range(_POOL_SIZE)]
    with ThreadPoolExecutor(max_workers=_POOL_SIZE) as pool:
        futures = [pool.submit(_process_slice, s) for s in slices if s]
        for f in as_completed(futures):
            f.result()  # re-raise anything a worker didn't catch itself

    posted, failed = counts["posted"], counts["failed"]
    result = {
        "status": "hana_down" if hana_down.is_set() else "done",
        "total": total, "posted": posted, "failed": failed,
    }
    _emit(progress_id, f"Done. Posted={posted} Failed={failed}")
    _set(progress_id, result)
    return result


def post_single_order(amazon_order_id):
    """
    Post one order by ID (synchronous). Used from the ops center per-row action.
    Returns {"status": "success"|"error"|"hana_down", ...}.
    """
    if not frappe.db.exists(ORDER_DOCTYPE, amazon_order_id):
        return {"status": "error", "message": f"Order not found: {amazon_order_id}"}

    doc = frappe.get_doc(ORDER_DOCTYPE, amazon_order_id)

    if doc.stage not in ("ready", "failed"):
        return {"status": "error", "message": f"Order stage is '{doc.stage}', expected ready or failed"}

    cutoff_msg = posting_cutoff_violation(doc.actual_ship_date or doc.purchase_date)
    if cutoff_msg:
        return {"status": "error", "message": cutoff_msg}

    frappe.db.sql(
        """UPDATE `tabAmazon US Order`
           SET stage = 'posting', posting_started_at = %s
           WHERE name = %s AND stage IN ('ready', 'failed')""",
        (str(now_datetime()), doc.name),
    )
    won = int(frappe.db.sql("SELECT ROW_COUNT()")[0][0]) == 1
    frappe.db.commit()
    if not won:
        return {"status": "error", "message": "Order already being processed by another worker"}

    try:
        # Always check SAP first, not just on retry: attempt_count resets to
        # 0 after any reset-for-repost, so a "first attempt" by that counter
        # can still already be live in SAP if a concurrent process (another
        # repost pass, a manual post) claimed the same just-reset order
        # first. Skipping this on the (attempt_count==0) fast path caused
        # real duplicate invoices in production testing.
        existing = find_invoice_by_order_id(doc.amazon_order_id)
        if existing:
            _mark_posted(doc.name, existing)
            return {
                "status": "success",
                "doc_entry": existing["doc_entry"],
                "doc_num": existing["doc_num"],
                "recovered": True,
            }

        hana_conn, hana_cursor = open_connection()
        try:
            payload, skipped = build_invoice_payload(doc, hana_cursor)
        finally:
            _close(hana_conn, hana_cursor)
        if payload is None:
            err = f"No postable lines. Skipped: {skipped}"
            _mark_failed(doc.name, err)
            return {"status": "error", "message": err}

        sap_result = post_invoice(payload)
        _mark_posted(doc.name, sap_result, payload=payload)
        return {"status": "success", "doc_entry": sap_result["doc_entry"], "doc_num": sap_result["doc_num"]}

    except HanaUnavailableError as e:
        _unclaim(doc.name)
        return {"status": "hana_down", "message": f"HANA unavailable: {e}. Order left in ready state."}

    except Exception as e:
        err = str(e)[:500]
        _mark_failed(doc.name, err)
        return {"status": "error", "message": err}


def bulk_retry_failed_orders(from_date, to_date, progress_id=None):
    """
    Reset all failed orders shipped in [from_date, to_date] to ready and
    re-post them. Ship-date window for the same reason as post_ready_orders.
    Loops until no more ready orders remain in the date range.
    """
    enforce_posting_cutoff(from_date)
    _set(progress_id, {"status": "running"})

    frappe.db.sql(
        """UPDATE `tabAmazon US Order`
           SET stage = 'ready'
           WHERE stage = 'failed'
           AND actual_ship_date BETWEEN %s AND %s""",
        (f"{from_date} 00:00:00", f"{to_date} 23:59:59"),
    )
    reset_count = int(frappe.db.sql("SELECT ROW_COUNT()")[0][0])
    frappe.db.commit()
    _emit(progress_id, f"Reset {reset_count} failed → ready. Starting SAP post...")

    if not reset_count:
        result = {"status": "done", "reset": 0, "total": 0, "posted": 0, "failed": 0}
        _set(progress_id, result)
        return result

    total_posted = total_failed = 0
    while True:
        batch = post_ready_orders(from_date, to_date, limit=200, progress_id=None)
        total_posted += batch.get("posted", 0)
        total_failed += batch.get("failed", 0)
        # HANA down mid-batch: stop looping, surface the status
        if batch.get("status") == "hana_down":
            result = {
                "status": "hana_down",
                "reset": reset_count,
                "posted": total_posted,
                "failed": total_failed,
                "message": "HANA went down mid-retry. Remaining orders are in ready state.",
            }
            _emit(progress_id, result["message"], "error")
            _set(progress_id, result)
            return result
        # Fetched fewer than limit → no more ready orders remain
        if batch.get("total", 0) < 200:
            break

    result = {
        "status": "done",
        "reset": reset_count,
        "total": reset_count,
        "posted": total_posted,
        "failed": total_failed,
    }
    _emit(progress_id, f"Bulk retry done. Reset={reset_count} Posted={total_posted} Failed={total_failed}")
    _set(progress_id, result)
    return result


def reset_for_repost(from_date, to_date, dry_run=True, progress_id=None):
    """
    Reset every order shipped in [from_date, to_date] that is currently
    'posted' back to 'ready', clearing every pointer into SAP (invoice
    DocEntry/DocNum/payload, credit note DocEntry/DocNum/refunded_at,
    last_error, attempt_count).

    Exists for repointing this pipeline at a different SAP B1 company DB --
    a freshly replicated test DB, or the eventual live cutover. Frappe's own
    "posted" bookkeeping otherwise still refers to documents that only exist
    in whichever DB they were posted to; post_ready_orders only ever touches
    stage='ready', so without this reset every previously-posted order would
    silently stay un-posted in the newly-targeted DB forever. The credit-note
    worker doesn't need a parallel reset of its own dedup state -- it always
    checks SAP directly (find_credit_note_by_ref), never the local
    cn_doc_entry field -- so clearing cn_doc_entry here is purely to stop the
    dashboard showing a refunded_at/cn_doc_num that points at a DB no longer
    connected, not a functional requirement for re-posting.

    dry_run=True (default) only counts what WOULD be reset -- no writes.
    Safe to call any number of times; only ever moves 'posted' -> 'ready'
    within the given ship-date window, never touches 'ready'/'failed'/'dead'
    orders that were never posted in the first place.
    """
    enforce_posting_cutoff(from_date)
    _set(progress_id, {"status": "running"})

    counts = frappe.db.sql(
        """
        SELECT COUNT(*) AS total,
               SUM(cn_doc_entry IS NOT NULL AND cn_doc_entry != '') AS with_cn
        FROM `tabAmazon US Order`
        WHERE stage = 'posted' AND actual_ship_date BETWEEN %s AND %s
        """,
        (from_date, to_date), as_dict=True,
    )[0]
    total, with_cn = int(counts.total or 0), int(counts.with_cn or 0)

    if dry_run:
        result = {"status": "dry_run", "would_reset": total, "would_reset_credit_notes": with_cn}
        _emit(progress_id, f"DRY RUN: would reset {total} posted orders ({with_cn} with credit notes) back to ready.")
        _set(progress_id, result)
        return result

    if not total:
        result = {"status": "done", "reset": 0, "reset_credit_notes": 0}
        _set(progress_id, result)
        return result

    _emit(progress_id, f"Resetting {total} posted orders ({with_cn} with credit notes) back to ready...")
    frappe.db.sql(
        """
        UPDATE `tabAmazon US Order`
        SET stage = 'ready',
            sap_doc_entry = NULL, sap_doc_num = NULL, posted_at = NULL, payload_json = NULL,
            cn_doc_entry = NULL, cn_doc_num = NULL, refunded_at = NULL,
            last_error = '', attempt_count = 0
        WHERE stage = 'posted' AND actual_ship_date BETWEEN %s AND %s
        """,
        (from_date, to_date),
    )
    frappe.db.commit()

    result = {"status": "done", "reset": total, "reset_credit_notes": with_cn}
    _emit(progress_id, f"Done. Reset {total} orders to ready ({with_cn} had credit notes).")
    _set(progress_id, result)
    return result


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _claim(name):
    """Atomically claim a ready order using conditional UPDATE + ROW_COUNT. Race-safe."""
    frappe.db.sql(
        """UPDATE `tabAmazon US Order`
           SET stage = 'posting',
               posting_started_at = %s,
               attempt_count = COALESCE(attempt_count, 0) + 1
           WHERE name = %s AND stage = 'ready'""",
        (str(now_datetime()), name),
    )
    won = int(frappe.db.sql("SELECT ROW_COUNT()")[0][0]) == 1
    frappe.db.commit()
    return won


def _unclaim(name):
    """Reset a posting order back to ready (e.g. HANA down). Does not decrement attempt_count."""
    frappe.db.sql(
        """UPDATE `tabAmazon US Order`
           SET stage = 'ready', posting_started_at = NULL
           WHERE name = %s AND stage = 'posting'""",
        (name,),
    )
    frappe.db.commit()


def _mark_posted(name, sap_result, payload=None):
    import json as _json
    updates = {
        "stage": "posted",
        "sap_doc_entry": sap_result["doc_entry"],
        "sap_doc_num": sap_result["doc_num"],
        "posted_at": str(now_datetime()),
        "last_error": "",
    }
    if payload is not None:
        updates["payload_json"] = _json.dumps(payload, default=str)
    frappe.db.set_value(ORDER_DOCTYPE, name, updates, update_modified=False)
    frappe.db.commit()


def _mark_failed(name, err):
    frappe.db.set_value(
        ORDER_DOCTYPE,
        name,
        {"stage": "failed", "last_error": err[:1000]},
        update_modified=False,
    )
    frappe.db.commit()
