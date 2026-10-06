"""SP-API client: LWA token management + order/item fetch."""
import time

import frappe
import requests

from khanal_tech_integrations.amazon_us import (
    SP_API_TOKEN_URL,
    SP_API_BASE,
    SP_API_ORDERS_PATH,
    _LWA_CACHE_KEY,
)

_PAGE_SIZE = 100
_LWA_BUFFER_SEC = 60


def get_lwa_token(force_refresh=False):
    """Return a valid LWA access token. Cached in Redis until near expiry."""
    if not force_refresh:
        cached = frappe.cache().get_value(_LWA_CACHE_KEY)
        if cached and cached.get("access_token"):
            return cached["access_token"]

    doc = frappe.get_doc("Amazon US Settings")
    resp = requests.post(
        SP_API_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": doc.get_password("lwa_refresh_token"),
            "client_id": doc.lwa_client_id,
            "client_secret": doc.get_password("lwa_client_secret"),
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    token = body["access_token"]
    ttl = max(60, int(body.get("expires_in", 3600)) - _LWA_BUFFER_SEC)
    frappe.cache().set_value(_LWA_CACHE_KEY, {"access_token": token}, expires_in_sec=ttl)
    return token


def _headers():
    return {
        "x-amz-access-token": get_lwa_token(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _is_expired_token_error(resp):
    """
    SP-API mostly returns 401 for a bad/expired access token, but some endpoints
    (e.g. Reports API) return 403 with an "Unauthorized" error whose message says
    the token has expired. Treat that as equivalent to 401 so it gets refreshed.
    """
    if resp.status_code == 401:
        return True
    if resp.status_code != 403:
        return False
    try:
        errors = resp.json().get("errors", [])
    except ValueError:
        return False
    for err in errors:
        text = f"{err.get('message', '')} {err.get('details', '')}".lower()
        if "expired" in text:
            return True
    return False


def _get(path, params=None):
    """
    GET from SP-API with 429 backoff retry, 401/expired-403 token refresh, and ConnectionError retry.
    20 attempts (not 7): restricted-tier Orders API allows ~1 req/60s sustained after
    burst is exhausted, so a large paginated pull needs enough patience to ride out the
    throttle window instead of giving up mid-pagination.
    """
    url = SP_API_BASE + path
    last_exc = None
    for attempt in range(20):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            wait = min(2 ** attempt, 64)
            frappe.logger().warning(f"SP-API ConnectionError on {path}, retrying in {wait}s (attempt {attempt + 1}): {exc}")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            wait = min(2 ** attempt, 64)
            frappe.logger().warning(f"SP-API 429 on {path}, retrying in {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            continue
        if _is_expired_token_error(resp):
            get_lwa_token(force_refresh=True)
            resp = requests.get(url, headers=_headers(), params=params, timeout=30)
            if _is_expired_token_error(resp):
                raise Exception(f"SP-API {resp.status_code} on {path} after token refresh — credentials invalid")
        return resp
    if last_exc:
        raise last_exc
    return resp


def _post(path, body=None):
    """POST to SP-API with 429 backoff retry, 401/expired-403 token refresh, and ConnectionError retry."""
    url = SP_API_BASE + path
    last_exc = None
    for attempt in range(20):
        try:
            resp = requests.post(url, headers=_headers(), json=body or {}, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            wait = min(2 ** attempt, 64)
            frappe.logger().warning(f"SP-API ConnectionError POST {path}, retrying in {wait}s (attempt {attempt + 1}): {exc}")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            wait = min(2 ** attempt, 64)
            frappe.logger().warning(f"SP-API 429 POST {path}, retrying in {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            continue
        if _is_expired_token_error(resp):
            get_lwa_token(force_refresh=True)
            resp = requests.post(url, headers=_headers(), json=body or {}, timeout=30)
            if _is_expired_token_error(resp):
                raise Exception(f"SP-API {resp.status_code} POST {path} after token refresh — credentials invalid")
        return resp
    if last_exc:
        raise last_exc
    return resp


def _pacific_day_to_utc(date_str, end_of_day=False):
    """
    Convert a Pacific calendar date (YYYY-MM-DD) to a UTC ISO 8601 string.
    Handles DST automatically via America/Los_Angeles.
    end_of_day=False → midnight Pacific (start of day)
    end_of_day=True  → 23:59:59 Pacific (end of day)
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        pacific = ZoneInfo("America/Los_Angeles")
    except Exception:
        import pytz
        pacific = pytz.timezone("America/Los_Angeles")

    h, m, s = (23, 59, 59) if end_of_day else (0, 0, 0)
    naive = datetime(int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10]), h, m, s)
    if hasattr(pacific, "localize"):  # pytz
        local_dt = pacific.localize(naive)
    else:
        local_dt = naive.replace(tzinfo=pacific)
    utc_dt = local_dt.astimezone(__import__("datetime").timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_orders(from_date, to_date):
    """
    Fetch ALL orders (all statuses) for the given date range (YYYY-MM-DD Pacific strings).
    Boundaries are converted to UTC so the window covers the full Pacific calendar day,
    matching what Amazon MTR reports as the order date.
    Handles NextToken pagination. Returns list of order dicts.
    """
    doc = frappe.get_doc("Amazon US Settings")
    params_base = {
        "MarketplaceIds": doc.marketplace_id,
        "CreatedAfter": _pacific_day_to_utc(from_date, end_of_day=False),
        "CreatedBefore": _pacific_day_to_utc(to_date, end_of_day=True),
        "MaxResultsPerPage": _PAGE_SIZE,
    }

    orders, next_token = [], None
    while True:
        params = {"NextToken": next_token} if next_token else params_base
        resp = _get(SP_API_ORDERS_PATH, params=params)
        if resp.status_code != 200:
            frappe.log_error(
                f"SP-API orders fetch failed: {resp.status_code} {resp.text[:500]}",
                "Amazon US SP-API",
            )
            raise Exception(f"SP-API orders fetch failed: {resp.status_code}")
        body = resp.json().get("payload", {})
        orders.extend(body.get("Orders", []))
        next_token = body.get("NextToken")
        if not next_token:
            break

    return orders


def fetch_orders_by_update(last_updated_after_utc):
    """
    Fetch all orders updated since last_updated_after_utc (ISO 8601 UTC string, e.g. '2026-06-01T00:00:00Z').
    Uses LastUpdatedAfter — the correct cursor for incremental sync.
    Captures new orders AND status changes (Pending→Shipped, cancellations, refunds).
    NOTE: LastUpdatedAfter and CreatedAfter are mutually exclusive in SP-API.
    """
    doc = frappe.get_doc("Amazon US Settings")
    params_base = {
        "MarketplaceIds": doc.marketplace_id,
        "LastUpdatedAfter": last_updated_after_utc,
        "MaxResultsPerPage": _PAGE_SIZE,
    }

    orders, next_token = [], None
    while True:
        params = {"NextToken": next_token} if next_token else params_base
        resp = _get(SP_API_ORDERS_PATH, params=params)
        if resp.status_code != 200:
            frappe.log_error(
                f"SP-API orders (LastUpdatedAfter) failed: {resp.status_code} {resp.text[:500]}",
                "Amazon US SP-API",
            )
            raise Exception(f"SP-API incremental fetch failed: {resp.status_code}")
        body = resp.json().get("payload", {})
        orders.extend(body.get("Orders", []))
        next_token = body.get("NextToken")
        if not next_token:
            break

    return orders


def fetch_order_items(amazon_order_id):
    """
    Fetch all line items for a single Amazon order.
    Returns list of item dicts. Returns [] on error (logged).
    """
    path = f"/orders/v0/orders/{amazon_order_id}/orderItems"
    items, next_token = [], None
    while True:
        params = {"NextToken": next_token} if next_token else None
        resp = _get(path, params=params)
        if resp.status_code != 200:
            frappe.log_error(
                f"SP-API items failed for {amazon_order_id}: {resp.status_code} {resp.text[:300]}",
                "Amazon US SP-API",
            )
            return []
        body = resp.json().get("payload", {})
        items.extend(body.get("OrderItems", []))
        next_token = body.get("NextToken")
        if not next_token:
            break
    return items
