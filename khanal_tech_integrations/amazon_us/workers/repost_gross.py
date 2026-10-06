"""
One-off repair: restructure posted invoices from NET (promo deducted) to GROSS.

Finance policy (2026-07-14): promotional rebates — item promo and ship promo —
are expenditure and must never reduce the AR invoice. Every invoice posted
before commit 43e025ef netted them, so any posted order that carries a promo
discount has a wrong (understated) invoice in SAP.

Per affected order this worker:
  1. cancels the linked credit note in SAP, if any (must go first — SAP will
     not cancel an invoice that has an open CN drawn against it),
  2. cancels the AR invoice,
  3. resets the local doc to stage=ready with all SAP pointers cleared,
  4. reposts the invoice through post_single_order (gross payload).

Credit notes are NOT reposted here: run
workers.credit_note.post_refunds_from_finances_api for the month afterwards —
its NumAtCard dedup filters CancelStatus eq 'csNo', so the cancelled CNs are
invisible to it and it reposts them (gross) alongside the ones never posted.

Idempotent: orders whose stored payload_json is already gross (every item
line's UnitPrice*qty matches the staged gross item_price_amount) are skipped,
so a re-run after a completed or interrupted pass only touches what is still
net-structured. Cancel steps treat already-cancelled/absent docs as success.

Usage:
    bench --site dev.localhost execute \
        khanal_tech_integrations.amazon_us.workers.repost_gross.run \
        --kwargs '{"dry_run": True}'
"""
import json
import zlib
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import frappe

from khanal_tech_integrations.amazon_us import ORDER_DOCTYPE, SAP_VERIFY_SSL
from khanal_tech_integrations.amazon_us.client.sap import _get_session
from khanal_tech_integrations.amazon_us.workers.invoice import post_single_order

_POOL_SIZE = 6


def _promo_order_rows():
    return frappe.db.sql(
        """SELECT o.name, o.sap_doc_entry, o.cn_doc_entry, o.payload_json
           FROM `tabAmazon US Order` o
           WHERE o.stage = 'posted' AND o.sap_doc_entry IS NOT NULL
             AND EXISTS (SELECT 1 FROM `tabAmazon US Order Item` i
                         WHERE i.parent = o.name
                           AND (i.promotion_discount_amount > 0
                                OR i.shipping_discount_amount > 0))
           ORDER BY o.name""",
        as_dict=True,
    )


def _is_already_gross(row):
    """True when the stored invoice payload already carries gross prices.

    Compares TOTAL dollar amounts, not per-ItemCode: SAP's item mapping
    (U_Amz_SKU) can drift after a payload was originally posted (item master
    cleanup moves a seller_sku to a different FGDC code), so a line-by-line
    match by current sap_item_code silently misses invoices posted under a
    now-stale item code -- caught live 2026-07-14 (Denties_S_B_L invoiced
    under FGDC00005 while current staging points at FGDC00009; the mismatch
    made a per-code check skip validation entirely and leave a net invoice
    marked 'already gross'). Summing bypasses the identity question
    altogether: net invoices are short by the promo amount regardless of
    which item code carried the line."""
    if not row["payload_json"]:
        return False
    lines = json.loads(row["payload_json"]).get("DocumentLines", [])
    posted_inventory = 0.0
    posted_freight = 0.0
    for line in lines:
        code = line.get("ItemCode")
        amount = float(line.get("UnitPrice") or 0) * float(line.get("Quantity") or 0)
        if code == "EXP000004":
            posted_freight += amount
        elif not line.get("AccountCode"):  # skip EXP000003 tax service line
            posted_inventory += amount
    totals = frappe.db.sql(
        """SELECT SUM(item_price_amount) gross, SUM(shipping_price_amount) ship_gross
           FROM `tabAmazon US Order Item` WHERE parent = %(p)s""",
        {"p": row["name"]}, as_dict=True,
    )[0]
    gross = float(totals["gross"] or 0)
    ship_gross = float(totals["ship_gross"] or 0)
    if posted_freight < ship_gross - 0.011:
        return False
    if posted_inventory < gross - 0.011:
        return False
    return True


def _cancel(session, b1_url, endpoint, doc_entry, expected_order_id):
    """Cancel a document — but only after confirming the DocEntry actually
    belongs to this order. Local pointers can be stale after a SAP company-DB
    repoint, and a stale DocEntry may coincidentally exist in the current DB
    as someone else's document; NumAtCard is the canonical identity (invoices
    carry the Amazon order id, CNs a refund id prefixed with it), so a
    mismatch means the pointer is dead and there is nothing of ours to cancel.

    Returns (ok, detail). Already-cancelled, not-found, and stale-pointer all
    count as ok — the goal state is 'no live doc of ours'."""
    lookup = session.get(
        f"{b1_url}{endpoint}({int(doc_entry)})?$select=NumAtCard,CancelStatus",
        verify=SAP_VERIFY_SSL,
        timeout=60,
    )
    if lookup.status_code == 404:
        return True, "not found (already gone)"
    if lookup.status_code != 200:
        return False, f"lookup HTTP {lookup.status_code}: {lookup.text[:200]}"
    doc = lookup.json()
    if not (doc.get("NumAtCard") or "").startswith(expected_order_id):
        return True, f"stale pointer: {endpoint}({doc_entry}) is NumAtCard '{doc.get('NumAtCard')}', not ours — left untouched"
    if doc.get("CancelStatus") != "csNo":
        return True, f"already cancelled ({doc.get('CancelStatus')})"

    resp = session.post(
        f"{b1_url}{endpoint}({int(doc_entry)})/Cancel",
        verify=SAP_VERIFY_SSL,
        timeout=60,
    )
    if resp.status_code in (200, 204):
        return True, "cancelled"
    body = resp.text[:300]
    if "already been cancelled" in body or "-8034" in body:
        return True, "already cancelled"
    return False, f"HTTP {resp.status_code}: {body}"


def _reset_local(order_id):
    frappe.db.sql(
        """UPDATE `tabAmazon US Order`
           SET stage = 'ready',
               sap_doc_entry = NULL, sap_doc_num = NULL, posted_at = NULL,
               payload_json = NULL,
               cn_doc_entry = NULL, cn_doc_num = NULL, refunded_at = NULL,
               last_error = '', attempt_count = 0
           WHERE name = %(name)s AND stage = 'posted'""",
        {"name": order_id},
    )
    frappe.db.commit()


def run(dry_run=True, limit=None, order_ids=None, shard=None, shards=None):
    """Cancel + repost gross. Set limit for a pilot slice (e.g. 10), or pass
    order_ids (list) to target explicit orders.

    shard/shards split the workload across independent bench-execute
    processes (e.g. shards=3, shard=0/1/2 in three terminals). Partitioning
    hashes the immutable order id (crc32 % shards), so every process derives
    the same disjoint sets no matter when it starts or how the underlying
    rows change — two processes can never touch the same order, which
    matters because a double-processed order would repost twice (the reset
    zeroes attempt_count, so post_single_order skips its duplicate guard)."""
    rows = _promo_order_rows()
    if order_ids:
        wanted = set(order_ids)
        rows = [r for r in rows if r["name"] in wanted]
    if shards is not None:
        rows = [r for r in rows if zlib.crc32(r["name"].encode()) % int(shards) == int(shard)]
    already_gross = [r for r in rows if _is_already_gross(r)]
    gross_names = {r["name"] for r in already_gross}
    rows = [r for r in rows if r["name"] not in gross_names]
    if limit:
        rows = rows[: int(limit)]

    if dry_run:
        print(json.dumps({
            "would_process": len(rows),
            "skipped_already_gross": len(already_gross),
            "with_cn": sum(1 for r in rows if r["cn_doc_entry"]),
            "sample": [{"name": r["name"], "inv": r["sap_doc_entry"], "cn": r["cn_doc_entry"]} for r in rows[:10]],
        }, indent=1, default=str))
        return

    site = frappe.local.site
    counts = {"cancelled_cn": 0, "cancelled_inv": 0, "reposted": 0,
              "cancel_failed": 0, "repost_failed": 0}
    failures = []
    lock = Lock()

    def _slice(chunk):
        frappe.init(site=site)
        frappe.connect()
        session, b1_url = _get_session()
        for r in chunk:
            oid = r["name"]
            try:
                if r["cn_doc_entry"]:
                    ok, detail = _cancel(session, b1_url, "CreditNotes", r["cn_doc_entry"], oid)
                    if not ok:
                        with lock:
                            counts["cancel_failed"] += 1
                            failures.append({"order": oid, "step": "cancel_cn", "detail": detail})
                        continue
                    with lock:
                        counts["cancelled_cn"] += 1
                ok, detail = _cancel(session, b1_url, "Invoices", r["sap_doc_entry"], oid)
                if not ok:
                    with lock:
                        counts["cancel_failed"] += 1
                        failures.append({"order": oid, "step": "cancel_inv", "detail": detail})
                    continue
                with lock:
                    counts["cancelled_inv"] += 1

                _reset_local(oid)
                result = post_single_order(oid)
                with lock:
                    if result.get("status") == "success":
                        counts["reposted"] += 1
                    else:
                        counts["repost_failed"] += 1
                        failures.append({"order": oid, "step": "repost", "detail": result})
            except Exception as e:
                with lock:
                    counts["repost_failed"] += 1
                    failures.append({"order": oid, "step": "exception", "detail": str(e)[:300]})
        frappe.destroy()

    chunks = [rows[i::_POOL_SIZE] for i in range(_POOL_SIZE)]
    with ThreadPoolExecutor(max_workers=_POOL_SIZE) as pool:
        list(pool.map(_slice, [c for c in chunks if c]))

    summary = {"total": len(rows), **counts, "failures": failures[:100]}
    suffix = f"_shard{shard}" if shards is not None else ""
    out_path = frappe.get_site_path("private", "files", f"repost_gross_summary{suffix}.json")
    with open(out_path, "w") as f:
        json.dump({"total": len(rows), **counts, "failures": failures}, f, indent=1, default=str)
    print(json.dumps(summary, indent=1, default=str))
    print(f"full failure list: {out_path}")
