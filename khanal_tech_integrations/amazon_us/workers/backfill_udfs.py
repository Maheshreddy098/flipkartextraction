"""
One-off backfill: write line UDFs (U_Order, U_OrderedOn, U_BuyerName, U_City,
U_State, U_PINCode, U_Country) onto already-posted SAP AR Invoices and Credit
Notes. Invoices posted before 2026-07-09 sent U_Channel/U_OrderID, which don't
exist on INV1/RIN1 — Service Layer silently dropped them, so every line UDF is
empty.

PRE-REQUISITE: SAP B1 client -> Administration -> System Initialization ->
Document Settings -> General tab -> "Enable Updating U. Fields when Doc. Rows
Locked" must be ticked, otherwise every PATCH fails with
"[INV1.U_Order] Field cannot be updated (ODBC -1029)".

Run:
    bench --site dev.localhost execute \
        khanal_tech_integrations.amazon_us.workers.backfill_udfs.run \
        --kwargs "{'dry_run': True, 'limit': 5}"

Progress is checkpointed to private/files/amazon_us_udf_backfill.json —
safe to re-run; already-patched DocEntries are skipped.
"""
import json
import os

import frappe

from khanal_tech_integrations.amazon_us import SAP_VERIFY_SSL, _SAP_SESSION_CACHE_KEY
from khanal_tech_integrations.amazon_us.client.sap import _get_session, _login
from khanal_tech_integrations.amazon_us.mappers.payload import build_line_udfs

_CHECKPOINT = "amazon_us_udf_backfill.json"


def _checkpoint_path():
    return frappe.get_site_path("private", "files", _CHECKPOINT)


def _load_checkpoint():
    path = _checkpoint_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"invoices_done": [], "credit_notes_done": [], "failures": {}}


def _save_checkpoint(state):
    with open(_checkpoint_path(), "w") as f:
        json.dump(state, f)


def _patch(session, b1_url, entity, doc_entry, body):
    """PATCH with one 401-relogin retry. Returns (ok, error_text)."""
    url = f"{b1_url}{entity}({doc_entry})"
    resp = session.patch(url, json=body, headers={"Content-Type": "application/json"},
                         verify=SAP_VERIFY_SSL, timeout=60)
    if resp.status_code == 401:
        frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
        session, b1_url = _login()
        resp = session.patch(f"{b1_url}{entity}({doc_entry})", json=body,
                             headers={"Content-Type": "application/json"},
                             verify=SAP_VERIFY_SSL, timeout=60)
    if resp.status_code in (200, 204):
        return True, ""
    err = resp.text[:500]
    try:
        err = resp.json()["error"]["message"]["value"]
    except Exception:
        pass
    return False, err


def run(dry_run=True, limit=0):
    """
    Backfill line UDFs on posted invoices, then credit notes.
    dry_run: build payloads and count, PATCH nothing.
    limit:   stop after N documents per entity (0 = all).
    """
    state = _load_checkpoint()
    inv_done = set(state["invoices_done"])
    cn_done = set(state["credit_notes_done"])
    session, b1_url = _get_session()

    orders = frappe.get_all(
        "Amazon US Order",
        filters={"stage": "posted"},
        fields=["name", "amazon_order_id", "sap_doc_entry", "cn_doc_entry",
                "payload_json", "purchase_date", "buyer_name", "ship_city",
                "ship_state_or_region", "ship_postal_code", "ship_country"],
    )

    inv_ok = inv_err = cn_ok = cn_err = skipped = 0

    for i, o in enumerate(orders):
        if not o.sap_doc_entry or not o.payload_json:
            skipped += 1
            continue
        udfs = build_line_udfs(o)
        if not udfs:
            skipped += 1
            continue

        # ── AR Invoice ──
        if o.sap_doc_entry not in inv_done and (not limit or inv_ok + inv_err < limit):
            nlines = len(json.loads(o.payload_json).get("DocumentLines", []))
            if nlines:
                body = {"DocumentLines": [dict(LineNum=n, **udfs) for n in range(nlines)]}
                if dry_run:
                    inv_ok += 1
                else:
                    ok, err = _patch(session, b1_url, "Invoices", o.sap_doc_entry, body)
                    if ok:
                        inv_ok += 1
                        inv_done.add(o.sap_doc_entry)
                    else:
                        inv_err += 1
                        state["failures"][f"INV {o.sap_doc_entry}"] = err

        # ── AR Credit Note (line count unknown -> GET first) ──
        if o.cn_doc_entry and o.cn_doc_entry not in cn_done and (not limit or cn_ok + cn_err < limit):
            if dry_run:
                cn_ok += 1
            else:
                r = session.get(f"{b1_url}CreditNotes({o.cn_doc_entry})?$select=DocumentLines",
                                verify=SAP_VERIFY_SSL, timeout=30)
                if r.status_code == 200:
                    line_nums = [l["LineNum"] for l in r.json().get("DocumentLines", [])]
                    body = {"DocumentLines": [dict(LineNum=n, **udfs) for n in line_nums]}
                    ok, err = _patch(session, b1_url, "CreditNotes", o.cn_doc_entry, body)
                    if ok:
                        cn_ok += 1
                        cn_done.add(o.cn_doc_entry)
                    else:
                        cn_err += 1
                        state["failures"][f"CN {o.cn_doc_entry}"] = err
                else:
                    cn_err += 1
                    state["failures"][f"CN {o.cn_doc_entry}"] = f"GET {r.status_code}"

        if not dry_run and i and i % 200 == 0:
            state["invoices_done"] = sorted(inv_done)
            state["credit_notes_done"] = sorted(cn_done)
            _save_checkpoint(state)
            print(f"[{i}/{len(orders)}] inv ok={inv_ok} err={inv_err} | cn ok={cn_ok} err={cn_err}")

        if limit and inv_ok + inv_err >= limit and (cn_ok + cn_err >= limit or not o.cn_doc_entry):
            break

    if not dry_run:
        state["invoices_done"] = sorted(inv_done)
        state["credit_notes_done"] = sorted(cn_done)
        _save_checkpoint(state)

    summary = {
        "dry_run": dry_run,
        "orders_scanned": len(orders),
        "invoices_patched": inv_ok,
        "invoice_failures": inv_err,
        "credit_notes_patched": cn_ok,
        "credit_note_failures": cn_err,
        "skipped_no_data": skipped,
        "failure_samples": dict(list(state["failures"].items())[:5]),
    }
    print(json.dumps(summary, indent=1))
    return summary
