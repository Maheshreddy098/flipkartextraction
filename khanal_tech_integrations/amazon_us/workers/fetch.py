"""
Fetch Amazon US orders from SP-API and stage them in the Amazon US Order doctype.

Timezone:
  SP-API returns all timestamps in UTC (ISO 8601 with 'Z').
  Amazon MTR (Custom Unified Transaction) report uses Pacific Time (PDT/PST).
  We store purchase_date in US/Pacific time so date-range filters align with MTR.
  purchase_date_utc stores the original UTC value for audit.

Two sync modes:
  Manual  (fetch_and_stage)  — ops center date-range picker, uses CreatedAfter/CreatedBefore.
                               7-day lookback on from_date to catch boundary orders.
  Incremental (sync_incremental) — scheduler background job, uses LastUpdatedAfter watermark.
                               Captures status changes (Pending→Shipped), cancellations, refunds.
                               Watermark stored in Amazon US Settings.sync_watermark.

Flow:
  1. Fetch orders from SP-API
  2. For each order: fetch order items, UPSERT Amazon US Order doc
  3. Stage:
       Shipped + all SKUs mapped → "ready"
       anything else            → "fetched"
       posting / posted         → metadata-only update (never downgrade stage)
"""
import json
from datetime import datetime, timedelta, timezone

import frappe
from frappe.utils import now_datetime

from khanal_tech_integrations.amazon_us import (
    INCREMENTAL_LOOKBACK_DAYS,
    ORDER_DOCTYPE,
    ORDER_ITEM_DOCTYPE,
)
from khanal_tech_integrations.amazon_us.client.sp_api import (
    fetch_order_items,
    fetch_orders,
    fetch_orders_by_update,
)
from khanal_tech_integrations.amazon_us.mappers.payload import get_item_mapping

_SHIPPED = "Shipped"
_SETTINGS_DOCTYPE = "Amazon US Settings"


# ─── Timezone helpers ─────────────────────────────────────────────────────────

def _utc_to_pacific(raw_utc):
    """
    Convert SP-API UTC timestamp string (e.g. '2026-05-01T07:01:28Z')
    to US/Pacific local time string (e.g. '2026-05-01 00:01:28').
    Handles DST automatically — PDT (UTC-7) in summer, PST (UTC-8) in winter.
    Returns None if input is empty.
    """
    if not raw_utc:
        return None
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        pacific = ZoneInfo("America/Los_Angeles")
    except Exception:
        try:
            import pytz
            pacific = pytz.timezone("America/Los_Angeles")
        except Exception:
            pacific = None

    s = str(raw_utc).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if "." in s:
        dot_idx = s.index(".")
        tz_part = ""
        for marker in ("+", "-"):
            idx = s.rfind(marker, dot_idx)
            if idx != -1:
                tz_part = s[idx:]
                break
        s = s[:dot_idx] + tz_part

    try:
        utc_dt = datetime.fromisoformat(s)
    except Exception:
        return None

    if pacific is not None:
        pacific_dt = utc_dt.astimezone(pacific)
    else:
        pacific_dt = utc_dt.astimezone(timezone(timedelta(hours=-8)))  # PST static fallback

    return pacific_dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_utc(raw_utc):
    """Strip Z/T from SP-API UTC string to Frappe-compatible UTC datetime string."""
    if not raw_utc:
        return None
    return str(raw_utc).replace("T", " ").replace("Z", "").split("+")[0].strip()[:19]


# ─── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_key(job_id):
    return f"amz_us_fetch_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[amz_fetch] {msg}")
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


# ─── Shared staging logic ─────────────────────────────────────────────────────

def _stage_order_list(orders, item_mapping, job_id=None):
    """
    UPSERT a list of raw SP-API order dicts into Amazon US Order doctype.
    Returns (created, updated, ready_count).

    Rules:
    - stage=posting/posted: update metadata only (LastUpdateDate, OrderStatus), never downgrade
    - stage=fetched/failed/ready: full re-evaluate (re-check Shipped + mapped → ready)
    """
    created = updated = ready_count = 0
    total = len(orders)

    for i, order in enumerate(orders):
        if i > 0 and i % 20 == 0:
            _emit(job_id, f"Progress: {i}/{total} orders processed...")

        amazon_order_id = order.get("AmazonOrderId", "")
        if not amazon_order_id:
            continue

        items_raw = fetch_order_items(amazon_order_id)
        item_rows, all_mapped = _build_item_rows(items_raw, item_mapping)

        order_status = order.get("OrderStatus", "")
        is_shipped = order_status == _SHIPPED
        unmapped_skus = [r["seller_sku"] for r in item_rows if not r["is_mapped"]]
        last_error = ("Unmapped SKUs: " + ", ".join(unmapped_skus)) if unmapped_skus else ""
        order_fields = _extract_order_fields(order)
        order_json_blob = json.dumps({"order": order, "items": items_raw}, default=str)

        existing = frappe.db.exists(ORDER_DOCTYPE, amazon_order_id)
        if existing:
            doc = frappe.get_doc(ORDER_DOCTYPE, amazon_order_id)

            if doc.stage in ("posting", "posted"):
                # Metadata-only update — never revert a completed/in-flight stage
                frappe.db.set_value(
                    ORDER_DOCTYPE,
                    amazon_order_id,
                    {
                        "order_status": order_status,
                        "last_update_date": order_fields.get("last_update_date"),
                        "number_of_items_shipped": order_fields.get("number_of_items_shipped"),
                        "number_of_items_unshipped": order_fields.get("number_of_items_unshipped"),
                    },
                    update_modified=False,
                )
                frappe.db.commit()
                updated += 1
                continue

            new_stage = "ready" if (is_shipped and all_mapped and item_rows) else "fetched"
            if new_stage == "ready":
                ready_count += 1

            for k, v in order_fields.items():
                setattr(doc, k, v)
            doc.stage = new_stage
            doc.last_error = last_error
            doc.order_json = order_json_blob
            doc.items = []
            for row in item_rows:
                doc.append("items", row)
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            updated += 1
        else:
            stage = "ready" if (is_shipped and all_mapped and item_rows) else "fetched"
            if stage == "ready":
                ready_count += 1
            frappe.get_doc({
                "doctype": ORDER_DOCTYPE,
                **order_fields,
                "stage": stage,
                "last_error": last_error,
                "order_json": order_json_blob,
                "items": item_rows,
            }).insert(ignore_permissions=True)
            frappe.db.commit()
            created += 1

    return created, updated, ready_count


def promote_fetched_orders(dry_run=True):
    """
    Re-evaluate stage=fetched Shipped orders against the current item mapping
    (hybrid SAP + doctype) using their already-staged child rows — no SP-API
    refetch. Orders whose SKUs are now all mapped move to ready.
    Returns {"promoted": n, "still_unmapped": {sku: order_count}}.
    """
    from collections import Counter

    from khanal_tech_integrations.amazon_us.mappers.payload import get_item_mapping

    mapping = get_item_mapping()
    promoted = 0
    still_unmapped = Counter()

    names = frappe.get_all(
        ORDER_DOCTYPE,
        filters={"stage": "fetched", "order_status": _SHIPPED},
        pluck="name",
        limit=0,
    )
    for name in names:
        doc = frappe.get_doc(ORDER_DOCTYPE, name)
        unmapped = [r.seller_sku for r in doc.items if r.seller_sku not in mapping]
        if unmapped or not doc.items:
            for sku in set(unmapped):
                still_unmapped[sku] += 1
            continue
        if dry_run:
            promoted += 1
            continue
        for row in doc.items:
            row.sap_item_code = mapping[row.seller_sku]["sap_item_code"]
            row.is_mapped = 1
        doc.stage = "ready"
        doc.last_error = ""
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        promoted += 1

    return {"dry_run": dry_run, "promoted": promoted, "still_unmapped": dict(still_unmapped)}


# ─── Manual fetch (ops center date-range) ─────────────────────────────────────

def fetch_and_stage(from_date, to_date, progress_id=None):
    """
    Fetch all SP-API orders created in date range and stage them.
    Date range is interpreted as Pacific Time to match Amazon MTR report.

    7-day lookback: SP-API query starts 7 days before from_date to catch
    orders purchased near the tail of the prior period that shipped within
    this period (MTR uses shipment date; SP-API filters by purchase date only).
    Returns summary dict.
    """
    fetch_from = (
        datetime.strptime(from_date, "%Y-%m-%d") - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)
    ).strftime("%Y-%m-%d")

    _set(progress_id, {"status": "running"})
    _emit(
        progress_id,
        f"Fetching orders from SP-API: {from_date} → {to_date} (Pacific Time, "
        f"{INCREMENTAL_LOOKBACK_DAYS}-day lookback from {fetch_from})",
    )

    try:
        orders = fetch_orders(fetch_from, to_date)
    except Exception as e:
        err = str(e)
        _emit(progress_id, f"SP-API fetch failed: {err}", "error")
        _set(progress_id, {"status": "error", "message": err})
        frappe.log_error(f"fetch_and_stage SP-API error: {err}", "Amazon US Fetch")
        return {"status": "error", "message": err}

    total = len(orders)
    shipped_count = sum(1 for o in orders if o.get("OrderStatus") == _SHIPPED)
    _emit(progress_id, f"Got {total} orders ({shipped_count} Shipped). Staging...")

    item_mapping = get_item_mapping()
    created, updated, ready_count = _stage_order_list(orders, item_mapping, progress_id)

    result = {
        "status": "done",
        "total_orders": total,
        "shipped": shipped_count,
        "ready": ready_count,
        "created": created,
        "updated": updated,
    }
    _emit(progress_id, f"Done. {total} orders | {shipped_count} Shipped | {ready_count} ready to post.")
    _set(progress_id, result)
    return result


# ─── Incremental background sync ──────────────────────────────────────────────

def sync_incremental():
    """
    Background scheduler job: LastUpdatedAfter watermark sync.
    Runs every 30 min. Captures new orders and status transitions
    (Pending→Shipped, cancellations, refunds) since the last run.

    Watermark stored in Amazon US Settings.sync_watermark.
    Lookback buffer = settings.lookback_days (default INCREMENTAL_LOOKBACK_DAYS).
    """
    settings = frappe.get_doc(_SETTINGS_DOCTYPE)
    lookback_days = int(getattr(settings, "lookback_days", None) or INCREMENTAL_LOOKBACK_DAYS)

    raw_watermark = getattr(settings, "sync_watermark", None)
    if raw_watermark:
        if isinstance(raw_watermark, str):
            wm_dt = datetime.fromisoformat(raw_watermark.replace(" ", "T"))
        else:
            wm_dt = raw_watermark
        if wm_dt.tzinfo is None:
            wm_dt = wm_dt.replace(tzinfo=timezone.utc)
    else:
        # First run: go back 30 days for initial catch-up
        wm_dt = datetime.now(timezone.utc) - timedelta(days=30)
        frappe.logger().info("[amz_sync] No watermark found — running 30-day catch-up")

    fetch_from_utc = (wm_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    frappe.logger().info(f"[amz_sync] LastUpdatedAfter={fetch_from_utc} (watermark={wm_dt.isoformat()}, lookback={lookback_days}d)")

    try:
        orders = fetch_orders_by_update(fetch_from_utc)
    except Exception as e:
        err = str(e)
        frappe.log_error(f"sync_incremental SP-API error: {err}", "Amazon US Incremental Sync")
        return {"status": "error", "message": err}

    frappe.logger().info(f"[amz_sync] Got {len(orders)} orders to process")
    item_mapping = get_item_mapping()
    created, updated, ready_count = _stage_order_list(orders, item_mapping, job_id=None)

    # Advance watermark to now (UTC)
    new_watermark = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    frappe.db.set_value(
        _SETTINGS_DOCTYPE,
        _SETTINGS_DOCTYPE,
        "sync_watermark",
        new_watermark,
        update_modified=False,
    )
    frappe.db.commit()

    frappe.logger().info(
        f"[amz_sync] Done. total={len(orders)} created={created} updated={updated} "
        f"ready={ready_count} watermark→{new_watermark}"
    )
    return {
        "status": "done",
        "total_orders": len(orders),
        "created": created,
        "updated": updated,
        "ready": ready_count,
        "new_watermark": new_watermark,
    }


# ─── Field extractors ─────────────────────────────────────────────────────────

def _extract_order_fields(order):
    """Extract all scalar fields from a raw SP-API order dict."""
    buyer_info = order.get("BuyerInfo") or {}
    ship_addr = order.get("ShippingAddress") or {}
    order_total = order.get("OrderTotal") or {}

    return {
        "amazon_order_id": order.get("AmazonOrderId", ""),
        "marketplace_id": order.get("MarketplaceId", ""),
        "order_status": order.get("OrderStatus", ""),
        "fulfillment_channel": order.get("FulfillmentChannel", ""),
        "sales_channel": order.get("SalesChannel", ""),
        "order_type": order.get("OrderType", ""),
        "ship_service_level": order.get("ShipServiceLevel", ""),
        "is_prime": 1 if order.get("IsPrime") else 0,
        "is_business_order": 1 if order.get("IsBusinessOrder") else 0,
        "is_replacement_order": 1 if order.get("IsReplacementOrder") else 0,
        # Timestamps — Pacific for MTR alignment, UTC for audit
        "purchase_date": _utc_to_pacific(order.get("PurchaseDate")),
        "purchase_date_utc": _parse_utc(order.get("PurchaseDate")),
        "last_update_date": _utc_to_pacific(order.get("LastUpdateDate")),
        # Counts
        "number_of_items_shipped": int(order.get("NumberOfItemsShipped") or 0),
        "number_of_items_unshipped": int(order.get("NumberOfItemsUnshipped") or 0),
        # Order total
        "order_total_amount": float(order_total.get("Amount") or 0),
        "order_total_currency": order_total.get("CurrencyCode", "USD"),
        # Buyer
        "buyer_name": (buyer_info.get("BuyerName") or ship_addr.get("Name") or "")[:140],
        "buyer_email": (buyer_info.get("BuyerEmail") or "")[:140],
        # Shipping address
        "ship_city": (ship_addr.get("City") or "")[:140],
        "ship_state_or_region": (ship_addr.get("StateOrRegion") or "")[:140],
        "ship_postal_code": (ship_addr.get("PostalCode") or "")[:20],
        "ship_country": (ship_addr.get("CountryCode") or "")[:10],
    }


def _build_item_rows(items_raw, item_mapping):
    """
    Convert raw SP-API order items to Amazon US Order Item child rows.
    Returns (rows, all_mapped_bool).
    """
    rows = []
    all_mapped = True

    for item in items_raw:
        sku = (item.get("SellerSKU") or "").strip()
        if not sku:
            continue

        qty_ordered = float(item.get("QuantityOrdered") or 0)
        qty_shipped = float(item.get("QuantityShipped") or 0)
        qty = qty_shipped if qty_shipped > 0 else qty_ordered
        if qty <= 0:
            continue

        def _amt(key):
            return float((item.get(key) or {}).get("Amount") or 0)

        item_price = _amt("ItemPrice")
        unit_price = round(item_price / qty, 5) if qty else 0.0

        mapping = item_mapping.get(sku)
        is_mapped = bool(mapping)
        if not is_mapped:
            all_mapped = False

        rows.append({
            "doctype": ORDER_ITEM_DOCTYPE,
            "seller_sku": sku,
            "sap_item_code": mapping["sap_item_code"] if mapping else "",
            "is_mapped": 1 if is_mapped else 0,
            "quantity_ordered": qty_ordered,
            "quantity_shipped": qty_shipped,
            "quantity": qty,
            "unit_price": unit_price,
            "asin": item.get("ASIN", ""),
            "order_item_id": item.get("OrderItemId", ""),
            "condition_id": item.get("ConditionId", ""),
            "title": (item.get("Title") or "")[:140],
            "item_price_amount": item_price,
            "item_tax_amount": _amt("ItemTax"),
            "shipping_price_amount": _amt("ShippingPrice"),
            "shipping_tax_amount": _amt("ShippingTax"),
            "shipping_discount_amount": _amt("ShippingDiscount"),
            "promotion_discount_amount": _amt("PromotionDiscount"),
            "cod_fee": _amt("CODFee"),
        })

    return rows, all_mapped
