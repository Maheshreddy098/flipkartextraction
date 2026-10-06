"""
Bulk-fetch Amazon US orders via SP-API Reports API instead of the slow
Orders API + one-OrderItems-call-per-order loop (see fetch.py).

Why: fetch.py's fetch_and_stage() calls fetch_order_items() once PER ORDER.
For a full month (~13k orders) that's ~13k separate rate-limited API calls,
taking hours. This module requests ONE flat-file report per <=30-day chunk
that already has item-level rows inline -- no per-order calls at all.

Source report: GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
  Columns confirmed via Amazon SP-API docs (report-type-values-order):
  amazon-order-id, merchant-order-id, purchase-date, last-updated-date,
  order-status, order-item-id, fulfillment-channel, sales-channel,
  order-channel, ship-service-level, product-name, sku, asin, item-status,
  quantity, currency, item-price, item-tax, shipping-price, shipping-tax,
  gift-wrap-price, gift-wrap-tax, item-promotion-discount,
  ship-promotion-discount, ship-city, ship-state, ship-postal-code,
  ship-country, promotion-ids, cpf, is-business-order,
  purchase-order-number, price-designation.
  Max 30 days per request, any start date, no stated frequency limit.

Known gaps vs the live Orders+OrderItems API path (acceptable -- none of
these are used by the SAP posting logic in mappers/payload.py):
  - No buyer name/email (PII; needs a Restricted Data Token we don't request).
  - No IsPrime / IsReplacementOrder flags -- left 0 on report-sourced orders.
  - Single "quantity" column, not QuantityOrdered/QuantityShipped split --
    both are set equal to it. Whole-order shipped/ready gating still comes
    from order-status, same as fetch.py.
  - order_total_amount is a computed sum (item-price + tax + shipping across
    the order's lines), not a value Amazon returns directly in this report.

Same UPSERT / stage rules as fetch.py's _stage_order_list (kept as a
separate implementation here, not shared, so this new bulk path can't
affect the live per-order fetch path):
  Shipped + all SKUs mapped + has items -> "ready"
  anything else                         -> "fetched"
  posting / posted                      -> metadata-only update, never downgrade
"""
import csv
import io
import json
from datetime import datetime, timedelta

import frappe
from frappe.utils import now_datetime

from khanal_tech_integrations.amazon_us import ORDER_DOCTYPE, ORDER_ITEM_DOCTYPE
from khanal_tech_integrations.amazon_us.client.reports import (
    create_report,
    download_report,
    poll_report,
)
from khanal_tech_integrations.amazon_us.client.sp_api import _pacific_day_to_utc
from khanal_tech_integrations.amazon_us.mappers.payload import get_item_mapping
from khanal_tech_integrations.amazon_us.workers.fetch import _parse_utc, _utc_to_pacific

_REPORT_TYPE = "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL"
_SETTINGS_DOCTYPE = "Amazon US Settings"
_MAX_CHUNK_DAYS = 30
_SHIPPED = "Shipped"


# ─── Cache helpers (for ops-center polling) ───────────────────────────────────

def _cache_key(job_id):
    return f"amz_us_report_fetch_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[amz_report_fetch] {msg}")
        return
    raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    log = data.get("log", [])
    log.append({"msg": msg, "level": level, "at": str(now_datetime())})
    data["log"] = log[-200:]
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


# ─── Date chunking (30-day report limit) ──────────────────────────────────────

def _date_chunks(from_date, to_date, max_days=_MAX_CHUNK_DAYS):
    """Split [from_date, to_date] (YYYY-MM-DD) into <=max_days chunks."""
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    chunks = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_days - 1), end)
        chunks.append((cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cur = chunk_end + timedelta(days=1)
    return chunks


# ─── Report parsing ────────────────────────────────────────────────────────────

def _parse_report_rows(content, item_mapping):
    """
    Parse the TSV report into {amazon_order_id: {..order fields.., "items": [rows]}}.
    Order-level fields repeat on every row belonging to that order; item rows
    are pre-mapped to sap_item_code here so downstream staging doesn't need
    the raw SP-API item shape.
    """
    orders = {}
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for row in reader:
        order_id = (row.get("amazon-order-id") or "").strip()
        if not order_id:
            continue

        if order_id not in orders:
            orders[order_id] = {
                "order_status": (row.get("order-status") or "").strip(),
                "fulfillment_channel": (row.get("fulfillment-channel") or "").strip(),
                "sales_channel": (row.get("sales-channel") or "").strip(),
                "ship_service_level": (row.get("ship-service-level") or "").strip(),
                "purchase_date_raw": (row.get("purchase-date") or "").strip(),
                "last_updated_raw": (row.get("last-updated-date") or "").strip(),
                "is_business_order": (row.get("is-business-order") or "").strip().lower() == "true",
                "ship_city": (row.get("ship-city") or "")[:140],
                "ship_state_or_region": (row.get("ship-state") or "")[:140],
                "ship_postal_code": (row.get("ship-postal-code") or "")[:20],
                "ship_country": (row.get("ship-country") or "")[:10],
                "currency": (row.get("currency") or "USD").strip(),
                "items": [],
            }

        sku = (row.get("sku") or "").strip()
        if not sku:
            continue

        def _f(key):
            try:
                return float(row.get(key) or 0)
            except ValueError:
                return 0.0

        qty = _f("quantity")
        if qty <= 0:
            continue

        item_price = _f("item-price")
        mapping = item_mapping.get(sku)

        orders[order_id]["items"].append({
            "doctype": ORDER_ITEM_DOCTYPE,
            "seller_sku": sku,
            "sap_item_code": mapping["sap_item_code"] if mapping else "",
            "is_mapped": 1 if mapping else 0,
            "asin": (row.get("asin") or "").strip(),
            "title": (row.get("product-name") or "")[:140],
            "order_item_id": (row.get("order-item-id") or "").strip(),
            "condition_id": "",
            "quantity_ordered": qty,
            "quantity_shipped": qty,  # report has one "quantity" column, not split
            "quantity": qty,
            "unit_price": round(item_price / qty, 5) if qty else 0.0,
            "item_price_amount": item_price,
            "item_tax_amount": _f("item-tax"),
            "shipping_price_amount": _f("shipping-price"),
            "shipping_tax_amount": _f("shipping-tax"),
            "shipping_discount_amount": _f("ship-promotion-discount"),
            "promotion_discount_amount": _f("item-promotion-discount"),
            "cod_fee": 0.0,
        })

    return orders


def _order_fields_from_report(order_id, meta, marketplace_id):
    """Build Amazon US Order scalar fields from parsed report meta (mirrors
    fetch.py's _extract_order_fields shape, filling report-unavailable
    fields with safe defaults not used by SAP posting logic)."""
    items = meta["items"]
    order_total = sum(
        i["item_price_amount"] + i["item_tax_amount"] + i["shipping_price_amount"] + i["shipping_tax_amount"]
        for i in items
    )
    is_shipped = meta["order_status"] == _SHIPPED
    return {
        "amazon_order_id": order_id,
        "marketplace_id": marketplace_id,
        "order_status": meta["order_status"],
        "fulfillment_channel": meta["fulfillment_channel"],
        "sales_channel": meta["sales_channel"],
        "order_type": "",
        "ship_service_level": meta["ship_service_level"],
        "is_prime": 0,
        "is_business_order": 1 if meta["is_business_order"] else 0,
        "is_replacement_order": 0,
        "purchase_date": _utc_to_pacific(meta["purchase_date_raw"]),
        "purchase_date_utc": _parse_utc(meta["purchase_date_raw"]),
        "last_update_date": _utc_to_pacific(meta["last_updated_raw"]),
        "number_of_items_shipped": len(items) if is_shipped else 0,
        "number_of_items_unshipped": 0 if is_shipped else len(items),
        "order_total_amount": round(order_total, 2),
        "order_total_currency": meta["currency"],
        "buyer_name": "",
        "buyer_email": "",
        "ship_city": meta["ship_city"],
        "ship_state_or_region": meta["ship_state_or_region"],
        "ship_postal_code": meta["ship_postal_code"],
        "ship_country": meta["ship_country"],
    }


# ─── Staging (UPSERT) ──────────────────────────────────────────────────────────

def _stage_report_orders(orders, marketplace_id, progress_id=None):
    """
    UPSERT parsed report orders into Amazon US Order doctype.
    Same stage rules as fetch.py's _stage_order_list, kept as an independent
    implementation so this bulk path can't affect the live per-order path.
    Returns (created, updated, ready_count).
    """
    created = updated = ready_count = 0
    total = len(orders)

    for i, (order_id, meta) in enumerate(orders.items()):
        if i > 0 and i % 500 == 0:
            _emit(progress_id, f"Staging: {i}/{total} orders...")

        item_rows = meta["items"]
        is_shipped = meta["order_status"] == _SHIPPED
        all_mapped = all(r["is_mapped"] for r in item_rows) if item_rows else False
        unmapped_skus = [r["seller_sku"] for r in item_rows if not r["is_mapped"]]
        last_error = ("Unmapped SKUs: " + ", ".join(unmapped_skus)) if unmapped_skus else ""

        order_fields = _order_fields_from_report(order_id, meta, marketplace_id)
        order_json_blob = json.dumps({"report_row": meta, "source": "reports_api"}, default=str)

        existing = frappe.db.exists(ORDER_DOCTYPE, order_id)
        if existing:
            doc = frappe.get_doc(ORDER_DOCTYPE, order_id)

            if doc.stage in ("posting", "posted"):
                frappe.db.set_value(
                    ORDER_DOCTYPE,
                    order_id,
                    {
                        "order_status": meta["order_status"],
                        "last_update_date": order_fields.get("last_update_date"),
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


# ─── Entry point ────────────────────────────────────────────────────────────

def fetch_and_stage_via_report(from_date, to_date, lookback_days=30, progress_id=None):
    """
    Bulk-fetch and stage orders for [from_date, to_date] (YYYY-MM-DD Pacific)
    using the Reports API instead of per-order Orders+OrderItems calls.
    Chunks into <=30-day report requests automatically. Returns summary dict.

    lookback_days extends the fetch window backwards from from_date. The MTR
    (Custom Unified Transaction) report is indexed by POSTED date while this
    report filters by ORDER (purchase) date, so a month's MTR contains orders
    purchased well before the month started -- verified: June 2026's MTR held
    512 orders purchased May 16-31 that a no-lookback fetch missed entirely.
    30 days covers the observed ~16-day trailing skew with margin. Staging a
    wider window is safe: posting is a separate step filtered by its own
    purchase-date range, so earlier-dated orders are never invoiced unless
    the posting range explicitly includes them.
    """
    _set(progress_id, {"status": "running"})
    settings = frappe.get_doc(_SETTINGS_DOCTYPE)
    marketplace_id = settings.marketplace_id
    item_mapping = get_item_mapping()

    fetch_from = (
        datetime.strptime(from_date, "%Y-%m-%d") - timedelta(days=int(lookback_days))
    ).strftime("%Y-%m-%d")

    chunks = _date_chunks(fetch_from, to_date)
    _emit(
        progress_id,
        f"Bulk report fetch: {from_date} -> {to_date} "
        f"({lookback_days}-day lookback from {fetch_from}) in {len(chunks)} chunk(s) of <=30 days",
    )

    total_created = total_updated = total_ready = 0

    for idx, (chunk_from, chunk_to) in enumerate(chunks):
        data_start = _pacific_day_to_utc(chunk_from, end_of_day=False)
        data_end = _pacific_day_to_utc(chunk_to, end_of_day=True)
        _emit(progress_id, f"[{idx + 1}/{len(chunks)}] Requesting report: {chunk_from} -> {chunk_to} (UTC {data_start} -> {data_end})")

        try:
            report_id = create_report(_REPORT_TYPE, marketplace_id, data_start, data_end)
        except Exception as e:
            err = str(e)
            _emit(progress_id, f"create_report failed: {err}", "error")
            _set(progress_id, {"status": "error", "message": err})
            frappe.log_error(err, "Amazon US Order Report — create_report")
            return {"status": "error", "message": err}

        _emit(progress_id, f"[{idx + 1}/{len(chunks)}] Report requested: {report_id}. Polling (max 30 min)...")

        try:
            doc_id = poll_report(report_id, poll_interval=30, max_wait=1800)
        except Exception as e:
            err = str(e)
            _emit(progress_id, f"poll_report failed: {err}", "error")
            _set(progress_id, {"status": "error", "message": err})
            frappe.log_error(err, "Amazon US Order Report — poll_report")
            return {"status": "error", "message": err}

        _emit(progress_id, f"[{idx + 1}/{len(chunks)}] Report ready ({doc_id}). Downloading...")

        try:
            content = download_report(doc_id)
        except Exception as e:
            err = str(e)
            _emit(progress_id, f"download_report failed: {err}", "error")
            _set(progress_id, {"status": "error", "message": err})
            frappe.log_error(err, "Amazon US Order Report — download_report")
            return {"status": "error", "message": err}

        orders = _parse_report_rows(content, item_mapping)
        shipped_count = sum(1 for m in orders.values() if m["order_status"] == _SHIPPED)
        _emit(progress_id, f"[{idx + 1}/{len(chunks)}] Parsed {len(orders)} orders ({shipped_count} Shipped). Staging...")

        created, updated, ready_count = _stage_report_orders(orders, marketplace_id, progress_id)
        total_created += created
        total_updated += updated
        total_ready += ready_count

        _emit(progress_id, f"[{idx + 1}/{len(chunks)}] Done chunk: created={created} updated={updated} ready={ready_count}")

    result = {
        "status": "done",
        "chunks": len(chunks),
        "created": total_created,
        "updated": total_updated,
        "ready": total_ready,
    }
    _emit(progress_id, f"Done. created={total_created} updated={total_updated} ready={total_ready}")
    _set(progress_id, result)
    return result
