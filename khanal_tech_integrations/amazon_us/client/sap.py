"""SAP B1 session management and AR Invoice posting for Amazon US (INC entity)."""
import json

import frappe
import requests
from frappe.utils import add_to_date, get_datetime, now_datetime

from khanal_tech_integrations.amazon_us import (
    SAP_VERIFY_SSL,
    _SAP_SESSION_CACHE_KEY,
    _SAP_SESSION_CACHE_TTL,
)


def _login():
    """Authenticate against INC SAP Settings. Cache session in Redis."""
    doc = frappe.get_doc("INC SAP Settings")
    b1_url = (doc.sap_b1_url or "").rstrip("/") + "/"
    session = requests.Session()
    resp = session.post(
        b1_url + "Login",
        json={
            "CompanyDB": doc.companydb,
            "Password": doc.get_password("password"),
            "UserName": doc.username,
        },
        headers={"Content-Type": "application/json"},
        verify=SAP_VERIFY_SSL,
        timeout=15,
    )
    resp.raise_for_status()
    cookies = session.cookies.get_dict()
    timeout_min = int(resp.json().get("SessionTimeout", 30))
    expires_on = add_to_date(now_datetime(), minutes=timeout_min)
    frappe.cache().set_value(
        _SAP_SESSION_CACHE_KEY,
        {
            "b1session": cookies["B1SESSION"],
            "routeid": cookies.get("ROUTEID", ""),
            "expires_on": str(expires_on),
            "b1_url": b1_url,
        },
        expires_in_sec=_SAP_SESSION_CACHE_TTL,
    )
    return session, b1_url


def _get_session():
    """Return (session, b1_url). Uses cached session if still valid."""
    cached = frappe.cache().get_value(_SAP_SESSION_CACHE_KEY)
    if cached and cached.get("b1session") and cached.get("expires_on"):
        try:
            expiry = add_to_date(get_datetime(cached["expires_on"]), minutes=-5)
            if now_datetime() < expiry:
                session = requests.Session()
                session.cookies.set("B1SESSION", cached["b1session"])
                session.cookies.set("ROUTEID", cached.get("routeid", ""))
                return session, cached["b1_url"]
        except Exception:
            pass
    return _login()


def post_invoice(payload):
    """
    POST AR Invoice to SAP B1 INC entity.
    Returns {"doc_entry": str, "doc_num": str}.
    Raises frappe.ValidationError on failure.
    """
    session, b1_url = _get_session()
    url = b1_url + "Invoices"

    resp = session.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        verify=SAP_VERIFY_SSL,
        timeout=60,
    )

    if resp.status_code == 401:
        frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
        session, b1_url = _login()
        resp = session.post(
            b1_url + "Invoices",
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=SAP_VERIFY_SSL,
            timeout=60,
        )

    if resp.status_code not in (200, 201):
        err = resp.text
        try:
            err = resp.json().get("error", {}).get("message", {}).get("value", err)
        except Exception:
            pass
        frappe.log_error(
            f"Amazon US AR Invoice POST failed: {resp.status_code} {err}\n\nPayload:\n{json.dumps(payload, indent=2, default=str)[:5000]}",
            "Amazon US SAP",
        )
        raise frappe.ValidationError(f"SAP AR Invoice failed: {err}")

    result = resp.json()
    doc_entry = result.get("DocEntry")
    if not doc_entry:
        raise frappe.ValidationError("SAP did not return DocEntry")

    return {"doc_entry": str(doc_entry), "doc_num": str(result.get("DocNum") or "")}


def post_credit_note(payload):
    """
    POST AR Credit Note to SAP B1 INC entity.
    Returns {"doc_entry": str, "doc_num": str}.
    Raises frappe.ValidationError on failure.
    """
    session, b1_url = _get_session()
    url = b1_url + "CreditNotes"

    resp = session.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        verify=SAP_VERIFY_SSL,
        timeout=60,
    )

    if resp.status_code == 401:
        frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
        session, b1_url = _login()
        resp = session.post(
            b1_url + "CreditNotes",
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=SAP_VERIFY_SSL,
            timeout=60,
        )

    if resp.status_code not in (200, 201):
        err = resp.text
        try:
            err = resp.json().get("error", {}).get("message", {}).get("value", err)
        except Exception:
            pass
        frappe.log_error(
            f"Amazon US AR Credit Note POST failed: {resp.status_code} {err}\n\nPayload:\n{json.dumps(payload, indent=2, default=str)[:5000]}",
            "Amazon US SAP",
        )
        raise frappe.ValidationError(f"SAP AR Credit Note failed: {err}")

    result = resp.json()
    doc_entry = result.get("DocEntry")
    if not doc_entry:
        raise frappe.ValidationError("SAP did not return DocEntry")

    return {"doc_entry": str(doc_entry), "doc_num": str(result.get("DocNum") or "")}


def fetch_amazon_sku_map():
    """
    Pull the Amazon SKU -> SAP ItemCode map from the INC item master
    (OITM.U_Amz_SKU). A UDF may hold several SKUs separated by commas or
    semicolons, and the same SKU may appear on several items (legacy dupes),
    so the value is a list: {seller_sku: [item_code, ...]}.
    Raises on SAP/network failure — caller decides the fallback.
    """
    session, b1_url = _get_session()
    sku_map = {}
    url = b1_url + "Items?$filter=U_Amz_SKU ne null&$select=ItemCode,U_Amz_SKU"
    while url:
        resp = session.get(
            url, verify=SAP_VERIFY_SSL, timeout=60,
            headers={"Prefer": "odata.maxpagesize=500"},
        )
        if resp.status_code == 401:
            frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
            session, b1_url = _login()
            continue
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("value", []):
            for sku in str(item.get("U_Amz_SKU") or "").replace(";", ",").split(","):
                sku = sku.strip()
                if sku:
                    sku_map.setdefault(sku, []).append(item["ItemCode"])
        url = data.get("odata.nextLink") or ""
        if url and not url.startswith("http"):
            url = b1_url + url
    return sku_map


def find_credit_note_by_ref(refund_id):
    """
    Query SAP B1 for an existing AR Credit Note with NumAtCard == refund_id.
    Returns {"doc_entry": str, "doc_num": str} if found, else None.
    Duplicate guard: safe to re-run the credit-note worker any number of times.
    """
    session, b1_url = _get_session()
    escaped = refund_id.replace("'", "''")
    # Same cancelled-document exclusion as find_invoice_by_order_id.
    url = (
        b1_url
        + f"CreditNotes?$filter=NumAtCard eq '{escaped}' and CancelStatus eq 'csNo'&$select=DocEntry,DocNum&$top=1"
    )
    try:
        resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=30)
        if resp.status_code == 401:
            frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
            session, b1_url = _login()
            resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=30)
        if resp.status_code == 200:
            rows = resp.json().get("value", [])
            if rows:
                return {
                    "doc_entry": str(rows[0]["DocEntry"]),
                    "doc_num": str(rows[0].get("DocNum") or ""),
                }
    except Exception as e:
        frappe.log_error(f"Duplicate check failed for credit note {refund_id}: {e}", "Amazon US SAP")
    return None


def get_credit_note_lines(doc_entry):
    """
    Return the DocumentLines of an existing AR Credit Note (list of dicts).
    Raises on failure — callers treat "can't read" differently from "no lines".
    """
    session, b1_url = _get_session()
    url = b1_url + f"CreditNotes({int(doc_entry)})?$select=DocumentLines"
    resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=30)
    if resp.status_code == 401:
        frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
        session, b1_url = _login()
        resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=30)
    resp.raise_for_status()
    return resp.json().get("DocumentLines", [])


def find_invoice_by_order_id(amazon_order_id):
    """
    Query SAP B1 for an existing AR Invoice with NumAtCard == amazon_order_id.
    Returns {"doc_entry": str, "doc_num": str} if found, else None.
    Used as a duplicate guard before posting: if network dropped after a successful POST,
    the next retry finds the existing invoice and marks the order posted without double-posting.
    """
    session, b1_url = _get_session()
    escaped = amazon_order_id.replace("'", "''")
    # CancelStatus eq 'csNo': a cancelled invoice (csCancelled) and its
    # cancellation document (csCancellation, which shares the NumAtCard but
    # does NOT carry Cancelled='tYES') must not satisfy the duplicate guard --
    # otherwise an order whose invoice was cancelled for correction would be
    # "recovered" against a dead document instead of re-posted. Verified
    # against a real cancellation pair: only CancelStatus separates all three
    # document states.
    url = (
        b1_url
        + f"Invoices?$filter=NumAtCard eq '{escaped}' and CancelStatus eq 'csNo'&$select=DocEntry,DocNum&$top=1"
    )
    try:
        resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=30)
        if resp.status_code == 401:
            frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
            session, b1_url = _login()
            resp = session.get(url, verify=SAP_VERIFY_SSL, timeout=30)
        if resp.status_code == 200:
            rows = resp.json().get("value", [])
            if rows:
                return {
                    "doc_entry": str(rows[0]["DocEntry"]),
                    "doc_num": str(rows[0].get("DocNum") or ""),
                }
    except Exception as e:
        frappe.log_error(f"Duplicate check failed for {amazon_order_id}: {e}", "Amazon US SAP")
    return None
