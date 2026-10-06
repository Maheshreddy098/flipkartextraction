import json
from datetime import datetime

import frappe
from frappe.exceptions import UniqueValidationError
from frappe.utils import add_days, add_to_date, get_datetime, now_datetime, today

from ..client import UCClient
from ..returns import load_parent_order, prepare_credit_note_items


ORDER_CURSOR_OVERLAP_MINUTES = 20
RETURN_CURSOR_OVERLAP_MINUTES = 45

# Max characters for Data fields in UC doctype
_DATA_MAX = 140


def _parse_source_datetime(raw_value) -> datetime | None:
    if not raw_value:
        return None
    if isinstance(raw_value, datetime):
        return raw_value
    if isinstance(raw_value, (int, float)) or (isinstance(raw_value, str) and str(raw_value).isdigit()):
        try:
            epoch = int(raw_value)
            if epoch > 10_000_000_000:
                epoch = int(epoch / 1000)
            return datetime.utcfromtimestamp(epoch)
        except Exception:
            return None
    try:
        return get_datetime(str(raw_value).replace("Z", "+00:00"))
    except Exception:
        return None


def _format_cursor(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _next_cursor(
    since: str,
    cycle_ended_at: datetime,
    seen_timestamps: list[datetime],
    deferred_timestamps: list[datetime],
    overlap_minutes: int,
) -> str:
    try:
        base_since = get_datetime(since)
    except Exception:
        base_since = get_datetime(add_days(today(), -60) + " 00:00:00")

    if deferred_timestamps:
        anchor = min(deferred_timestamps)
    elif seen_timestamps:
        anchor = max(seen_timestamps)
    else:
        anchor = cycle_ended_at

    candidate = add_to_date(anchor, minutes=-abs(int(overlap_minutes or 0)), as_datetime=True)
    if candidate < base_since:
        candidate = base_since
    return _format_cursor(candidate)


def _persist_cursor(cursor_key: str, cursor_value: str):
    row = frappe.db.sql(
        """
        SELECT value
        FROM `tabSingles`
        WHERE doctype = %s AND field = %s
        FOR UPDATE
        """,
        ("Unicommerce Settings", "last_fetched_at_json"),
        as_dict=True,
    )
    current = {}
    if row and row[0].get("value"):
        try:
            current = json.loads(row[0]["value"])
        except Exception:
            current = {}
    current[cursor_key] = cursor_value
    frappe.db.set_single_value("Unicommerce Settings", "last_fetched_at_json", json.dumps(current))


def _order_event_timestamp(order: dict) -> datetime | None:
    return (
        _parse_source_datetime(order.get("updated"))
        or _parse_source_datetime(order.get("channelProcessingTime"))
        or _parse_source_datetime(order.get("created"))
        or _parse_source_datetime(order.get("displayOrderDateTime"))
    )


def _return_event_timestamp(ret: dict) -> datetime | None:
    # Actual UC return/get response: returnSaleOrderValue holds metadata
    rsov = ret.get("returnSaleOrderValue") or {}
    return (
        _parse_source_datetime(rsov.get("returnCompletedDate"))
        or _parse_source_datetime(rsov.get("inventoryReceivedDate"))
        or _parse_source_datetime(rsov.get("returnCreatedDate"))
        or _parse_source_datetime(ret.get("updated"))
        or _parse_source_datetime(ret.get("created"))
    )


def _extract_uc_order_id(order: dict) -> str | None:
    return (
        order.get("saleOrderCode")
        or order.get("code")
        or order.get("displayOrderCode")
        or None
    )


def _extract_channel(order: dict) -> str:
    return (
        order.get("channel")
        or order.get("channelName")
        or order.get("saleOrderDTO", {}).get("channel")
        or ""
    )


def _extract_order_date(order: dict) -> str:
    # Priority matches sap_payload._resolve_uc_order_date so that Frappe order_date
    # equals the SAP DocDate we send. displayOrderDateTime is the channel's order date
    # (e.g. the Amazon placement date); created is UC's internal intake timestamp.
    # They can differ by days — using the same priority on both sides avoids a mismatch
    # where Frappe stores a different month than SAP records.
    raw = (
        order.get("displayOrderDateTime")
        or order.get("created")
        or order.get("orderDate")
        or ""
    )
    if not raw:
        return today()
    # Unicommerce can return epoch timestamps in some payloads.
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and str(raw).isdigit()):
        try:
            from datetime import timezone, timedelta
            epoch = int(raw)
            if epoch > 10_000_000_000:
                epoch = int(epoch / 1000)
            IST = timezone(timedelta(hours=5, minutes=30))
            return datetime.fromtimestamp(epoch, tz=IST).date().isoformat()
        except Exception:
            return today()
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return str(raw)[:10]


def _eligible_line_items(order: dict) -> list[dict]:
    active_items = []
    for item in order.get("saleOrderItems") or []:
        cancellation_reason = str(item.get("cancellationReason") or "").strip()
        status_code = str(item.get("statusCode") or "").strip().upper()
        on_hold = bool(item.get("onHold"))
        try:
            quantity = float(
                item.get("quantity")
                or item.get("totalQuantity")
                or item.get("completedQuantity")
                or item.get("allocatedQuantity")
                or item.get("inProcessQuantity")
                or item.get("unallocatedQuantity")
                or 1
            )
        except Exception:
            quantity = 1.0

        if cancellation_reason or on_hold or quantity <= 0:
            continue
        if status_code in {"CANCELLED", "INVALID", "UNFULFILLABLE"}:
            continue
        active_items.append(item)
    return active_items


def _order_ready_for_invoice(order: dict) -> tuple[bool, str]:
    order_status = str(order.get("status") or "").strip().upper()
    if order_status not in {"COMPLETE", "COMPLETED"}:
        return False, f"Order status is {order_status or 'unknown'} (requires COMPLETE)"

    active_items = _eligible_line_items(order)
    if not active_items:
        return False, "Order has no invoice-eligible line items"

    return True, ""


def _safe_int(value) -> int:
    try:
        return int(str(value or "").strip() or "0")
    except Exception:
        return 0


def _safe_str(value, max_len: int = _DATA_MAX) -> str:
    # Do NOT use `value or ""` — that converts 0 / 0.0 to "" (wrong for numeric fields).
    if value is None:
        return ""
    return str(value).strip()[:max_len]


def _extract_billing_address(order: dict) -> dict:
    """Return customer/address scalar fields from the UC saleOrderDTO.
    Legacy code uses billingAddress; fall back to shippingAddress if absent.
    """
    addr: dict = (
        order.get("billingAddress")
        or order.get("shippingAddress")
        or {}
    )
    if not addr:
        addr = ((order.get("addresses") or [{}])[0]) or {}

    return {
        "customer_name": _safe_str(addr.get("name") or addr.get("customerName")),
        "city": _safe_str(addr.get("city")),
        "state": _safe_str(addr.get("state")),
        "district": _safe_str(addr.get("district")),
        "pin_code": _safe_int(addr.get("pincode") or addr.get("pinCode") or addr.get("zip")),
    }


def _extract_shipping_package_fields(order: dict) -> dict:
    """Extract shipment_status, shipment_date, shippingpackages from shippingPackages[0]."""
    packages = order.get("shippingPackages") or []
    if not packages:
        return {}
    pkg = packages[0] or {}
    dispatched = pkg.get("dispatched")
    shipment_date = None
    if dispatched:
        dt = _parse_source_datetime(dispatched)
        shipment_date = _format_cursor(dt) if dt else None
    return {
        "shippingpackages": json.dumps(pkg),
        "shipment_status": _safe_str(pkg.get("status")),
        "shipment_date": shipment_date,
    }


def _extract_return_fields(order: dict) -> dict:
    """Extract embedded return detail from order_detail['returns'][0] (if present)."""
    returns = order.get("returns") or []
    if not returns:
        return {}
    ret = returns[0] or {}
    return {
        "return_code": _safe_str(ret.get("code")),
        "statuscode": _safe_str(ret.get("statusCode")),
        "shippingprovider": _safe_str(ret.get("shippingProvider")),
        "trackingnumber": _safe_str(ret.get("trackingNumber")),
        "trackingstatus": _safe_str(ret.get("trackingStatus")),
        "providerstatus": _safe_str(ret.get("providerStatus")),
        "putawaycode": _safe_str(ret.get("putawayCode")),
        "returninvoicecode": _safe_str(ret.get("returnInvoiceCode")),
        "returninvoicedisplaycode": _safe_str(ret.get("returnInvoiceDisplayCode")),
        "actioncode": _safe_str(ret.get("actionCode")),
        "type": _safe_str(ret.get("type")),
        "returncompleteddate": _safe_str(ret.get("returnCompletedDate")),
        "inventoryreceiveddate": _safe_str(ret.get("inventoryReceivedDate")),
        "returnfacilitycode": _safe_str(ret.get("returnFacilityCode")),
        "returnitems": json.dumps(ret) if ret else None,
    }


def _compute_uc_financials(order: dict) -> dict:
    """Compute raw UC financial totals from saleOrderItems at fetch time.

    Stores uc_taxable_value, uc_cgst, uc_sgst, uc_igst, uc_shipping, uc_total
    so reconciliation has a 3-way triangle: UC source → expected → SAP actual.
    """
    taxable = cgst = sgst = igst = shipping = 0.0
    for item in (order.get("saleOrderItems") or []):
        try:
            qty = float(item.get("quantity") or item.get("totalQuantity") or 1)
        except Exception:
            qty = 1.0
        try:
            selling_wo_tax = float(item.get("sellingPriceWithoutTaxesAndDiscount") or 0)
        except Exception:
            selling_wo_tax = 0.0
        try:
            discount = float(item.get("discount") or 0)
        except Exception:
            discount = 0.0
        per_unit_disc = (discount / qty) if qty > 0 else 0.0
        unit_price = max(0.0, selling_wo_tax - per_unit_disc)
        line_taxable = unit_price * qty
        taxable += line_taxable

        try:
            igst_pct = float(item.get("integratedGstPercentage") or 0)
        except Exception:
            igst_pct = 0.0
        try:
            cgst_pct = float(
                item["centralGstPercentage"] if "centralGstPercentage" in item
                else item.get("centralGstTaxPercentage") or 0
            )
        except Exception:
            cgst_pct = 0.0
        try:
            sgst_pct = float(
                item["stateGstPercentage"] if "stateGstPercentage" in item
                else item.get("stateGstTaxPercentage") or 0
            )
        except Exception:
            sgst_pct = 0.0

        if igst_pct > 0:
            igst += line_taxable * igst_pct / 100.0
        else:
            cgst += line_taxable * cgst_pct / 100.0
            sgst += line_taxable * sgst_pct / 100.0

        try:
            item_shipping = (
                float(item.get("shippingCharges") or 0)
                + float(item.get("shippingMethodCharges") or 0)
                + float(item.get("cashOnDeliveryCharges") or 0)
            )
        except Exception:
            item_shipping = 0.0
        shipping += item_shipping

    total = taxable + cgst + sgst + igst + shipping
    return {
        "uc_taxable_value": round(taxable, 2),
        "uc_cgst": round(cgst, 2),
        "uc_sgst": round(sgst, 2),
        "uc_igst": round(igst, 2),
        "uc_shipping": round(shipping, 2),
        "uc_total": round(total, 2),
    }


def _extract_order_scalar_fields(order: dict) -> dict:
    """Map all flat UC saleOrderDTO fields to Unicommerce Orders doctype fields."""
    created_dt = _parse_source_datetime(order.get("created"))
    updated_dt = _parse_source_datetime(order.get("updated"))
    display_dt = _parse_source_datetime(order.get("displayOrderDateTime"))

    # Legacy code stores raw bool/value from API directly into Data field
    cod_raw = order.get("cod")
    cod_value = str(cod_raw) if cod_raw is not None else ""

    # Legacy code uses displayOrderCode as channel_id
    channel_id = _safe_str(order.get("displayOrderCode") or order.get("channelOrderId") or "")

    fields = {
        "channel_id": channel_id,
        "status": _safe_str(order.get("status")),
        "created": _format_cursor(created_dt) if created_dt else None,
        "updated": _format_cursor(updated_dt) if updated_dt else None,
        "displayorderdatetime": _format_cursor(display_dt) if display_dt else None,
        "cod": cod_value,
        **_extract_billing_address(order),
        **_extract_shipping_package_fields(order),
        **_extract_return_fields(order),
        **_compute_uc_financials(order),
    }
    return fields


def _extract_return_item_map(order: dict) -> dict[str, dict]:
    """
    Map saleOrderItemCode -> return item payload from order returns[0].returnItems.
    Used to stamp line-level return status/details for reconciliation.
    """
    returns = order.get("returns") or []
    if not returns:
        return {}
    ret = returns[0] or {}
    mapped: dict[str, dict] = {}
    for item in ret.get("returnItems") or []:
        sale_order_item_code = _safe_str(item.get("saleOrderItemCode"))
        if sale_order_item_code:
            mapped[sale_order_item_code] = item
    return mapped


def _build_line_items(order: dict) -> list[dict]:
    """Map UC saleOrderItems to Order Line Items child table rows.
    Field names verified against legacy unicommerce.py push_new_orders().
    """
    rows = []
    return_item_map = _extract_return_item_map(order)
    return_status = _safe_str(((order.get("returns") or [{}])[0] or {}).get("statusCode"))
    for item in (order.get("saleOrderItems") or []):
        # batchDTO is a nested object: {batchCode, batchFieldsDTO: {vendorBatchNumber, ...}}
        batch_dto = item.get("batchDTO") or {}
        batch_fields_dto = batch_dto.get("batchFieldsDTO") or {}
        batch_code = _safe_str(batch_dto.get("batchCode") or item.get("batchCode"))
        vendor_batch = _safe_str(
            batch_fields_dto.get("vendorBatchNumber")
            or item.get("vendorBatchNumber")
        )

        # Timestamps on items are epoch ms — convert same as order-level timestamps
        created_dt = _parse_source_datetime(item.get("created"))
        updated_dt = _parse_source_datetime(item.get("updated"))

        rows.append({
            "doctype": "Order Line Items",
            "id": _safe_str(item.get("id")),
            "itemsku": _safe_str(item.get("itemSku")),
            "sellerskucode": _safe_str(item.get("sellerSkuCode")),
            "channelproductid": _safe_str(item.get("channelProductId")),
            # UC encodes each item row as 1 unit; quantity fields are all null.
            "quantity": _safe_str(item.get("quantity") or item.get("totalQuantity") or "1"),
            "total_price": _safe_str(item.get("totalPrice")),
            "selling_price": _safe_str(item.get("sellingPrice")),
            "created": _format_cursor(created_dt) if created_dt else _safe_str(item.get("created")),
            "updated": _format_cursor(updated_dt) if updated_dt else _safe_str(item.get("updated")),
            "totalintegratedgst": _safe_str(item.get("totalIntegratedGst")),
            "integratedgstpercentage": _safe_str(item.get("integratedGstPercentage")),
            "sellingpricewithouttaxesanddiscount": _safe_str(item.get("sellingPriceWithoutTaxesAndDiscount")),
            "shippingcharges": _safe_str(item.get("shippingCharges")),
            "shippingmethodcharges": _safe_str(item.get("shippingMethodCharges")),
            "cashondeliverycharges": _safe_str(item.get("cashOnDeliveryCharges")),
            "cancellationreason": _safe_str(item.get("cancellationReason")),
            # Legacy: stateGstPercentage / centralGstPercentage (NOT stateGstTaxPercentage).
            # Must NOT use `or` — 0.0 is falsy and would skip the primary key.
            "state_gst_tax_percentage": _safe_str(
                item["stateGstPercentage"] if "stateGstPercentage" in item else item.get("stateGstTaxPercentage")
            ),
            "central_gst_tax_percentage": _safe_str(
                item["centralGstPercentage"] if "centralGstPercentage" in item else item.get("centralGstTaxPercentage")
            ),
            "statuscode": _safe_str(item.get("statusCode")),
            "discount": _safe_str(item.get("discount")),
            "shippingchargetaxpercentage": _safe_str(item.get("shippingChargeTaxPercentage")),
            "bundleskucode": _safe_str(item.get("bundleSkuCode")),
            "code": _safe_str(item.get("code")),
            "batchcode": batch_code,
            "vendorbatchnumber": vendor_batch,
            "uniware_return_status": return_status if _safe_str(item.get("code")) in return_item_map else "",
            "uniware_return_items": return_item_map.get(_safe_str(item.get("code")), {}),
        })
    return rows


def _apply_order_to_doc(doc, order: dict, current_status: str):
    """Apply all fetched UC order fields to an existing Unicommerce Orders doc (ORM)."""
    doc.order_json = json.dumps(order)
    doc.channel_name = _extract_channel(order)
    doc.order_date = _extract_order_date(order)

    for field, value in _extract_order_scalar_fields(order).items():
        if value is not None:
            setattr(doc, field, value)

    if str(current_status or "").strip() in {"", "fetched", "ready"}:
        doc.pipeline_status = "fetched"

    # Rebuild line items from the fresh UC data
    doc.set("line_items", [])
    for item_data in _build_line_items(order):
        doc.append("line_items", item_data)


def _build_new_order_doc(uc_order_id: str, order: dict) -> "frappe.model.document.Document":
    """Create a new Unicommerce Orders doc (not yet inserted)."""
    scalar_fields = _extract_order_scalar_fields(order)
    doc = frappe.get_doc({
        "doctype": "Unicommerce Orders",
        "uniware_id": uc_order_id,
        "channel_name": _extract_channel(order),
        "order_date": _extract_order_date(order),
        "pipeline_status": "fetched",
        "order_json": json.dumps(order),
        "attempt_count": 0,
        **{k: v for k, v in scalar_fields.items() if v is not None},
    })
    for item_data in _build_line_items(order):
        doc.append("line_items", item_data)
    return doc


UC_SEARCH_ENDPOINT = "services/rest/v1/oms/saleOrder/search"
UC_ORDER_DETAIL_ENDPOINT = "services/rest/v1/oms/saleorder/get"
UC_RETURN_SEARCH_ENDPOINT = "services/rest/v1/oms/return/search"
UC_RETURN_DETAIL_ENDPOINT = "services/rest/v1/oms/return/get"


def _emit(worker: str, msg: str, level: str = "info") -> None:
    try:
        # In background jobs frappe.session.user is Administrator; callers
        # may store the real triggering user in frappe.local.uc_notify_user.
        user = getattr(frappe.local, "uc_notify_user", None) or frappe.session.user
        frappe.publish_realtime(
            "uc_ops_progress",
            {"worker": worker, "msg": msg, "level": level},
            user=user,
        )
    except Exception:
        pass


def fetch_orders(
    max_orders: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    channel_name: str | None = None,
):
    """
    Fetch new/updated orders from Unicommerce and stage them in Unicommerce Orders.

    from_date / to_date: explicit date range (YYYY-MM-DD or datetime string).
    When provided the cursor is NOT advanced — this is a manual backfill run.
    When omitted, the stored cursor drives the window and is advanced after the run.

    Uses order created date range via fromDate/toDate params in UC saleOrder/search API.
    """
    _emit("fetch_orders", "Connecting to Unicommerce API…")
    uc = UCClient()
    uc.login()

    explicit_range = bool(from_date)

    settings = frappe.get_single("Unicommerce Settings")
    cursors = json.loads(settings.last_fetched_at_json or "{}")
    default_since = add_days(today(), -60) + " 00:00:00"
    cycle_ended_at = now_datetime()

    if explicit_range:
        since = str(from_date).strip()
        # Normalise bare dates → datetime strings
        if len(since) == 10:
            since = since + " 00:00:00"
        end = str(to_date).strip() if to_date else str(cycle_ended_at)
        if len(end) == 10:
            end = end + " 23:59:59"
    else:
        since = cursors.get("orders", default_since)
        end = str(cycle_ended_at)

    _emit("fetch_orders", f"Endpoint: POST /{UC_SEARCH_ENDPOINT}", level="endpoint")
    _emit("fetch_orders", f"Date range (order created): {since[:10]} → {end[:10]}", level="info")

    orders = uc.get_orders_between(from_date=since, to_date=end, channel=(channel_name or None))
    if max_orders:
        orders = orders[: int(max_orders)]

    total = len(orders)
    _emit("fetch_orders", f"Found {total} orders from Unicommerce search", level="success" if total else "warning")

    new_count = 0
    updated_count = 0
    skipped_posted = 0
    detail_failed = 0
    seen_timestamps: list[datetime] = []
    deferred_timestamps: list[datetime] = []

    _COMMIT_EVERY = 10  # flush to DB every N orders to limit data loss on crash
    _processed_since_commit = 0

    for idx, summary in enumerate(orders, 1):
        uc_order_id = _extract_uc_order_id(summary)
        if not uc_order_id:
            continue
        summary_ts = _order_event_timestamp(summary)
        if summary_ts:
            seen_timestamps.append(summary_ts)

        _emit("fetch_orders", f"Endpoint: POST /{UC_ORDER_DETAIL_ENDPOINT}  [{idx}/{total}] {uc_order_id}", level="endpoint")

        try:
            # Stage full order detail, not just the search summary.
            order = uc.get_order_detail(uc_order_id)
            if not order:
                detail_failed += 1
                if summary_ts:
                    deferred_timestamps.append(summary_ts)
                _emit("fetch_orders", f"Detail fetch returned empty for {uc_order_id}", level="warning")
                continue
        except Exception as exc:
            detail_failed += 1
            if summary_ts:
                deferred_timestamps.append(summary_ts)
            _emit("fetch_orders", f"Detail fetch failed for {uc_order_id}: {str(exc)[:80]}", level="error")
            continue

        existing_name = frappe.db.exists("Unicommerce Orders", uc_order_id)
        if existing_name:
            current_status = frappe.db.get_value("Unicommerce Orders", existing_name, "pipeline_status")
            if current_status == "posted":
                skipped_posted += 1
                _emit("fetch_orders", f"Skipped {uc_order_id} (already posted)", level="info")
                continue
            existing_doc = frappe.get_doc("Unicommerce Orders", existing_name)
            _apply_order_to_doc(existing_doc, order, current_status)
            existing_doc.save(ignore_permissions=True)
            updated_count += 1
            _emit("fetch_orders", f"Updated {uc_order_id} [{idx}/{total}]", level="info")
        else:
            doc = _build_new_order_doc(uc_order_id, order)
            try:
                doc.insert(ignore_permissions=True)
                new_count += 1
                _emit("fetch_orders", f"Staged new {uc_order_id} [{idx}/{total}]", level="success")
            except UniqueValidationError:
                # Search responses can contain duplicate order codes in a run.
                existing_name = frappe.db.exists("Unicommerce Orders", uc_order_id)
                if existing_name:
                    existing_doc = frappe.get_doc("Unicommerce Orders", existing_name)
                    _apply_order_to_doc(
                        existing_doc,
                        order,
                        frappe.db.get_value("Unicommerce Orders", existing_name, "pipeline_status"),
                    )
                    existing_doc.save(ignore_permissions=True)
                    updated_count += 1

        _processed_since_commit += 1
        if _processed_since_commit >= _COMMIT_EVERY:
            frappe.db.commit()
            _processed_since_commit = 0

    # Only advance the cursor on regular (cursor-based) polls, not manual backfills.
    if explicit_range:
        next_cursor = since  # unchanged
    else:
        next_cursor = _next_cursor(
            since=since,
            cycle_ended_at=cycle_ended_at,
            seen_timestamps=seen_timestamps,
            deferred_timestamps=deferred_timestamps,
            overlap_minutes=ORDER_CURSOR_OVERLAP_MINUTES,
        )
        _persist_cursor("orders", next_cursor)

    frappe.db.commit()

    _emit(
        "fetch_orders",
        f"Done — searched {total}, new {new_count}, updated {updated_count}, skipped {skipped_posted}, failed {detail_failed}",
        level="success",
    )

    frappe.logger().info(
        "Orders poller completed: fetched=%s new=%s updated=%s skipped_posted=%s detail_failed=%s since=%s to=%s explicit_range=%s",
        len(orders),
        new_count,
        updated_count,
        skipped_posted,
        detail_failed,
        since,
        end,
        explicit_range,
    )
    return {
        "fetched": len(orders),
        "new": new_count,
        "updated": updated_count,
        "skipped_posted": skipped_posted,
        "detail_failed": detail_failed,
        "since": since,
        "to": end,
        "explicit_range": explicit_range,
        "next_cursor": next_cursor,
        "endpoints_used": [UC_SEARCH_ENDPOINT, UC_ORDER_DETAIL_ENDPOINT],
    }


@frappe.whitelist()
def promote_fetched_to_ready(limit: int | None = None, start_date: str | None = None, end_date: str | None = None):
    """
    Promote freshly staged orders into the ready queue.

    The fetch worker intentionally stores full order detail as `fetched` first.
    Posting workers rely on `ready`, so this helper makes the pipeline
    scheduler-safe and also provides a manual recovery action.

    start_date / end_date (YYYY-MM-DD, inclusive) restrict promotion to orders
    whose ``order_date`` falls inside the window. Used by the Ops Center
    "Post Invoices" action so a manual run only promotes orders the operator
    actually selected.
    """
    filters: dict = {"pipeline_status": "fetched"}
    start = (start_date or "").strip()
    end = (end_date or "").strip()
    if start and end:
        filters["order_date"] = ["between", [start, end]]
    elif start:
        filters["order_date"] = [">=", start]
    elif end:
        filters["order_date"] = ["<=", end]

    kwargs = {
        "doctype": "Unicommerce Orders",
        "filters": filters,
        "fields": ["name", "order_json"],
        "order_by": "order_date asc, creation asc",
    }
    if limit is not None:
        kwargs["limit"] = max(int(limit or 0), 0)

    rows = frappe.get_all(**kwargs)
    moved = 0
    deferred = 0
    for row in rows:
        order = {}
        try:
            order = json.loads(row.order_json or "{}")
        except Exception:
            order = {}
        is_ready, reason = _order_ready_for_invoice(order)
        if not is_ready:
            frappe.db.set_value(
                "Unicommerce Orders",
                row.name,
                {
                    "last_error": reason[:1000],
                },
            )
            deferred += 1
            continue
        frappe.db.set_value(
            "Unicommerce Orders",
            row.name,
            {
                "pipeline_status": "ready",
                "last_error": "",
            },
        )
        moved += 1

    frappe.db.commit()
    return {"moved_to_ready": moved, "deferred": deferred, "limit": limit}


@frappe.whitelist()
def retry_batch_holds(limit: int = 500):
    """Emergency manual release of ``batch_hold`` orders back to ``ready``.

    This is a deliberate bypass of the 30-min cooldown enforced by
    ``_recover_batch_hold_orders`` — use only when an operator has confirmed
    fresh stock is available and wants the next posting cycle to retry
    immediately.

    Semantics (matches auto-recovery except for the cooldown):

    * ``attempt_count`` is incremented so the hold-cap escalation to ``dead``
      still works (``BATCH_HOLD_MAX_ATTEMPTS``).
    * ``last_error`` is preserved for diagnostic continuity — the next cycle
      overwrites it with a fresh shortage message or clears it on successful
      posting.
    * ``batch_hold_since`` is preserved on the ``batch_hold`` → ``ready``
      transition so the wall-clock cap (``BATCH_HOLD_MAX_HOURS``) still trips
      if the shortage persists. It is cleared only when the order actually
      leaves the hold cycle (``posted`` / ``failed`` / ``dead``) via the
      invoice worker.
    * The caller (Ops Center "Release batch holds" button) is audit-logged at
      INFO level so a Frappe admin can always see who bypassed the cooldown
      and when.

    The dedicated scheduler cron that used to call this function on a
    fixed interval has been removed; auto-recovery lives in
    ``workers.invoice._recover_batch_hold_orders`` inside the ``post_invoices``
    cycle.
    """
    try:
        limit = max(int(limit or 0), 0)
    except Exception:
        limit = 500
    limit = limit or 500

    rows = frappe.get_all(
        "Unicommerce Orders",
        filters={"pipeline_status": "batch_hold"},
        fields=["name", "attempt_count"],
        order_by="modified asc",
        limit=limit,
    )
    moved = 0
    actor = frappe.session.user or "Administrator"
    for row in rows:
        frappe.db.set_value(
            "Unicommerce Orders",
            row.name,
            {
                "pipeline_status": "ready",
                "attempt_count": int(row.attempt_count or 0) + 1,
            },
        )
        moved += 1
    frappe.db.commit()
    if moved:
        frappe.logger().info(
            "retry_batch_holds: manually released %s batch_hold order(s) to ready by %s",
            moved,
            actor,
        )
    return {"moved_to_ready": moved, "limit": limit, "actor": actor}


def _extract_return_date(ret: dict) -> str:
    # Prefer the most final event: completedDate > receivedDate > deliveryDate > createdDate.
    # This matches the SAP CN DocDate we want: the date goods were confirmed back in warehouse.
    rsov = ret.get("returnSaleOrderValue") or {}
    raw = (
        rsov.get("returnCompletedDate")
        or rsov.get("inventoryReceivedDate")
        or rsov.get("returnDeliveryDate")
        or rsov.get("returnCreatedDate")
        or ret.get("created")
        or ""
    )
    if not raw:
        return today()
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and str(raw).isdigit()):
        try:
            epoch = int(raw)
            if epoch > 10_000_000_000:
                epoch = int(epoch / 1000)
            return datetime.utcfromtimestamp(epoch).date().isoformat()
        except Exception:
            return today()
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return str(raw)[:10]


def _extract_return_ids(ret: dict) -> tuple[str | None, str | None]:
    # UC return/get response may differ by tenant/API version. Prefer explicit ids first.
    rsov = ret.get("returnSaleOrderValue") or {}

    def _pick_text(*values):
        for value in values:
            txt = str(value or "").strip()
            if txt:
                return txt
        return None

    uc_return_id = _pick_text(
        rsov.get("reversePickupCode"),
        rsov.get("shipmentCode"),
        rsov.get("code"),
        rsov.get("returnCode"),
        ret.get("reversePickupCode"),
        ret.get("shipmentCode"),
        ret.get("code"),
        ret.get("returnCode"),
    )

    uc_order_id = _pick_text(
        rsov.get("saleOrderCode"),
        rsov.get("saleordercode"),
        rsov.get("orderCode"),
        rsov.get("ucOrderCode"),
        ret.get("saleOrderCode"),
        ret.get("saleordercode"),
        ret.get("orderCode"),
        ret.get("ucOrderCode"),
    )
    if uc_order_id:
        return uc_return_id, uc_order_id

    # Fallback: derive order from return item codes by mapping to Order Line Items.code.
    item_codes: list[str] = []
    for row in ret.get("returnSaleOrderItems") or []:
        item_code = _pick_text(
            (row or {}).get("saleOrderItemCode"),
            (row or {}).get("code"),
            (row or {}).get("channelSaleOrderItemCode"),
        )
        if item_code:
            item_codes.append(item_code)

    if not item_codes:
        return uc_return_id, None

    unique_codes = sorted(set(item_codes))
    try:
        line_rows = frappe.get_all(
            "Order Line Items",
            filters={"code": ["in", unique_codes]},
            fields=["parent"],
            limit=max(len(unique_codes), 1) * 3,
        )
        parent_order_ids = sorted({str(row.get("parent") or "").strip() for row in line_rows if row.get("parent")})
    except Exception:
        parent_order_ids = []

    if not parent_order_ids:
        return uc_return_id, None
    if len(parent_order_ids) == 1:
        return uc_return_id, parent_order_ids[0]

    # Prefer a posted parent when multiple matches are found.
    posted_parent = frappe.db.get_value(
        "Unicommerce Orders",
        {"name": ["in", parent_order_ids], "pipeline_status": "posted"},
        "name",
    )
    if posted_parent:
        return uc_return_id, str(posted_parent)
    return uc_return_id, parent_order_ids[0]


def _extract_return_items(ret: dict) -> list:
    # UC return/get response: returnSaleOrderItems is the items list.
    return ret.get("returnSaleOrderItems") or []


def _extract_return_type(ret: dict) -> str:
    rsov = ret.get("returnSaleOrderValue") or {}
    # Items carry a shipmentCode; presence of rtoReason signals RTO
    raw = rsov.get("rtoReason") or ""
    if raw:
        return "courier"
    # Fallback: check items for any marker
    return "customer"


def fetch_returns(
    max_returns: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
):
    """
    Fetch returns and create UC Credit Note Staging rows.

    from_date / to_date: explicit date range (YYYY-MM-DD or datetime string).
    When provided the cursor is NOT advanced — safe for manual/backfill runs.
    When omitted, the stored cursor drives the window and is advanced after the run.

    "Parent order not in staging" means the return references a sale order that has
    not been fetched yet. Fetch orders first, then re-run fetch returns.
    """
    _emit("fetch_returns", "Connecting to Unicommerce API…")
    uc = UCClient()
    uc.login()

    explicit_range = bool(from_date)

    settings = frappe.get_single("Unicommerce Settings")
    cursors = json.loads(settings.last_fetched_at_json or "{}")
    default_since = add_days(today(), -90) + " 00:00:00"
    cycle_ended_at = now_datetime()

    if explicit_range:
        since = str(from_date).strip()
        if len(since) == 10:
            since = since + " 00:00:00"
        end = str(to_date).strip() if to_date else str(cycle_ended_at)
        if len(end) == 10:
            end = end + " 23:59:59"
    else:
        since = cursors.get("returns", default_since)
        end = str(cycle_ended_at)

    _emit("fetch_returns", f"Endpoint: POST /{UC_RETURN_SEARCH_ENDPOINT} (CIR + RTO)", level="endpoint")
    _emit("fetch_returns", f"Date range (return created): {since[:10]} → {end[:10]}")

    # Cursor mode: use updatedFrom/updatedTo to catch status changes on old returns.
    # Explicit date range: use createdFrom/createdTo to get returns created in that window.
    returns = uc.get_returns_between(from_date=str(since), to_date=str(end), use_updated=not explicit_range)
    if max_returns:
        returns = returns[: int(max_returns)]

    total = len(returns)
    _emit("fetch_returns", f"Found {total} returns from Unicommerce", level="success" if total else "warning")

    created = 0
    updated = 0
    skipped_existing = 0
    skipped_parent = 0
    skipped_no_ids = 0
    deferred_timestamps: list[datetime] = []
    seen_timestamps: list[datetime] = []

    for idx, ret in enumerate(returns, 1):
        uc_return_id, uc_order_id = _extract_return_ids(ret)
        if not uc_return_id or not uc_order_id:
            skipped_no_ids += 1
            continue
        return_ts = _return_event_timestamp(ret)
        if return_ts:
            seen_timestamps.append(return_ts)

        _emit("fetch_returns", f"Endpoint: POST /{UC_RETURN_DETAIL_ENDPOINT}  [{idx}/{total}] {uc_return_id}", level="endpoint")

        existing_name = frappe.db.exists("UC Credit Note Staging", {"uc_return_id": uc_return_id})
        if existing_name and frappe.db.get_value("UC Credit Note Staging", existing_name, "status") == "posted":
            skipped_existing += 1
            continue

        parent = load_parent_order(uc_order_id)
        if not parent:
            skipped_parent += 1
            if return_ts:
                deferred_timestamps.append(return_ts)
            _emit(
                "fetch_returns",
                f"Skipped {uc_return_id}: parent order {uc_order_id} not in staging. "
                "Fetch orders for this date range first, then re-run fetch returns.",
                level="warning",
            )
            continue

        items = _extract_return_items(ret)
        rsov = ret.get("returnSaleOrderValue") or {}
        fallback_warehouse = (
            rsov.get("forwardItemFacility")
            or ret.get("returnFacilityCode")
            or ""
        )
        prepared_items = prepare_credit_note_items(
            parent,
            items,
            fallback_warehouse=fallback_warehouse,
        )
        return_type = _extract_return_type(ret)
        parent_ready = parent.pipeline_status == "posted" and bool(parent.sap_ar_invoice_docentry)
        if not parent_ready or prepared_items["unresolved_count"]:
            if return_ts:
                deferred_timestamps.append(return_ts)
        last_error = ""
        if not parent_ready:
            last_error = "Parent order is not posted to SAP yet"
        elif prepared_items["unresolved_count"]:
            last_error = f"Awaiting SAP base-line mapping for {prepared_items['unresolved_count']} return item(s)"

        payload = {
            "uc_order_id": parent.name,
            "parent_sap_doc_entry": parent.sap_ar_invoice_docentry if parent_ready else "",
            "return_date": _extract_return_date(ret),
            "return_type": return_type,
            "items_json": json.dumps(prepared_items["items"]),
            "status": "pending",
            "last_error": last_error[:1000],
        }

        if existing_name:
            current_status = frappe.db.get_value("UC Credit Note Staging", existing_name, "status")
            if current_status == "dead":
                payload["status"] = "dead"
            frappe.db.set_value("UC Credit Note Staging", existing_name, payload)
            updated += 1
            continue

        doc = frappe.get_doc({"doctype": "UC Credit Note Staging", "uc_return_id": uc_return_id, "attempt_count": 0, **payload})
        doc.insert(ignore_permissions=True)
        created += 1
        _emit("fetch_returns", f"Staged credit note {uc_return_id} [{idx}/{total}]", level="success")

    if explicit_range:
        next_cursor = since  # unchanged — backfill run, don't move the cursor
    else:
        next_cursor = _next_cursor(
            since=since,
            cycle_ended_at=cycle_ended_at,
            seen_timestamps=seen_timestamps,
            deferred_timestamps=deferred_timestamps,
            overlap_minutes=RETURN_CURSOR_OVERLAP_MINUTES,
        )
        _persist_cursor("returns", next_cursor)

    frappe.db.commit()

    _emit(
        "fetch_returns",
        f"Done — searched {total}, staged {created}, updated {updated}, "
        f"skipped_posted {skipped_existing}, parent_missing {skipped_parent}, no_ids {skipped_no_ids}",
        level="success",
    )

    return {
        "fetched": len(returns),
        "created": created,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "skipped_parent_not_found": skipped_parent,
        "skipped_no_ids": skipped_no_ids,
        "since": since,
        "to": end,
        "explicit_range": explicit_range,
        "next_cursor": next_cursor,
        "endpoints_used": [UC_RETURN_SEARCH_ENDPOINT, UC_RETURN_DETAIL_ENDPOINT],
    }


@frappe.whitelist()
def audit_staged_order_completeness(
    limit: int = 200,
    pipeline_status: str | None = None,
) -> dict:
    """
    Validate whether critical Unicommerce Orders fields are populated in staging.
    Intended for real-data verification after fetch runs.
    """
    filters = {}
    if pipeline_status:
        filters["pipeline_status"] = str(pipeline_status).strip()

    rows = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=[
            "name",
            "uniware_id",
            "channel_name",
            "pipeline_status",
            "channel_id",
            "status",
            "order_date",
            "created",
            "updated",
            "displayorderdatetime",
            "customer_name",
            "state",
            "pin_code",
        ],
        order_by="modified desc",
        limit=max(int(limit or 0), 1),
    )

    parent_checks = [
        "uniware_id",
        "channel_id",
        "channel_name",
        "status",
        "order_date",
        "created",
        "updated",
        "displayorderdatetime",
    ]
    line_checks = ["id", "itemsku", "quantity", "code", "sellingpricewithouttaxesanddiscount"]

    parent_missing_counts = {f: 0 for f in parent_checks}
    line_missing_counts = {f: 0 for f in line_checks}
    sample_parent_missing = []
    sample_line_missing = []
    zero_line_items = 0
    line_rows_scanned = 0
    parent_missing_orders = 0

    for row in rows:
        missing_parent = [f for f in parent_checks if not _safe_str(row.get(f))]
        if missing_parent:
            parent_missing_orders += 1
            for f in missing_parent:
                parent_missing_counts[f] += 1
            if len(sample_parent_missing) < 20:
                sample_parent_missing.append(
                    {
                        "order": row.get("name"),
                        "pipeline_status": row.get("pipeline_status"),
                        "missing_fields": missing_parent,
                    }
                )

        doc = frappe.get_doc("Unicommerce Orders", row.get("name"))
        if not (doc.line_items or []):
            zero_line_items += 1
            continue

        for li in doc.line_items or []:
            line_rows_scanned += 1
            missing_line = [f for f in line_checks if not _safe_str(getattr(li, f, ""))]
            if not missing_line:
                continue
            for f in missing_line:
                line_missing_counts[f] += 1
            if len(sample_line_missing) < 30:
                sample_line_missing.append(
                    {
                        "order": row.get("name"),
                        "line_item": li.name,
                        "missing_fields": missing_line,
                    }
                )

    scanned = len(rows)
    return {
        "scanned_orders": scanned,
        "pipeline_status_filter": pipeline_status or "ALL",
        "zero_line_items": zero_line_items,
        "parent_missing_counts": parent_missing_counts,
        "line_rows_scanned": line_rows_scanned,
        "line_missing_counts": line_missing_counts,
        "sample_parent_missing": sample_parent_missing,
        "sample_line_missing": sample_line_missing,
        "parent_fully_populated_orders": scanned - parent_missing_orders,
    }


@frappe.whitelist()
def audit_staged_business_coverage(
    days: int = 7,
    statuses: str | None = None,
) -> dict:
    """
    Channel-wise business coverage audit for staged orders.
    Focuses on practical posting-readiness signals (shipping, batches, returns).
    """
    day_window = max(int(days or 1), 1)
    status_list = [
        s.strip() for s in str(statuses or "").split(",") if s.strip()
    ]

    where_parts = ["o.modified >= DATE_SUB(NOW(), INTERVAL %(days)s DAY)"]
    params: dict = {"days": day_window}
    if status_list:
        where_parts.append("o.pipeline_status IN %(status_list)s")
        params["status_list"] = tuple(status_list)
    where_clause = " AND ".join(where_parts)

    order_rows = frappe.db.sql(
        f"""
        SELECT
            o.channel_name AS channel,
            COUNT(*) AS order_count,
            SUM(CASE WHEN IFNULL(o.shippingpackages, '') != '' THEN 1 ELSE 0 END) AS with_shipping_packages,
            SUM(CASE WHEN IFNULL(o.shipment_status, '') != '' THEN 1 ELSE 0 END) AS with_shipment_status,
            SUM(CASE WHEN IFNULL(o.shipment_date, '') != '' THEN 1 ELSE 0 END) AS with_shipment_date,
            SUM(CASE WHEN IFNULL(o.return_code, '') != '' THEN 1 ELSE 0 END) AS with_return_code,
            SUM(CASE WHEN IFNULL(o.returnitems, '') != '' THEN 1 ELSE 0 END) AS with_return_items
        FROM `tabUnicommerce Orders` o
        WHERE {where_clause}
        GROUP BY o.channel_name
        ORDER BY order_count DESC
        """,
        params,
        as_dict=True,
    )

    line_rows = frappe.db.sql(
        f"""
        SELECT
            o.channel_name AS channel,
            COUNT(*) AS line_count,
            SUM(CASE WHEN IFNULL(li.vendorbatchnumber, '') != '' THEN 1 ELSE 0 END) AS with_vendor_batch,
            SUM(CASE WHEN IFNULL(li.batchcode, '') != '' THEN 1 ELSE 0 END) AS with_uniware_batch,
            SUM(
                CASE
                    WHEN CAST(IFNULL(NULLIF(TRIM(li.shippingcharges), ''), '0') AS DECIMAL(18,4)) > 0
                    THEN 1 ELSE 0
                END
            ) AS with_shipping_charge,
            SUM(
                CASE
                    WHEN CAST(IFNULL(NULLIF(TRIM(li.shippingchargetaxpercentage), ''), '0') AS DECIMAL(18,4)) > 0
                    THEN 1 ELSE 0
                END
            ) AS with_shipping_tax_percent,
            SUM(CASE WHEN IFNULL(li.uniware_return_status, '') != '' THEN 1 ELSE 0 END) AS with_return_status,
            SUM(CASE WHEN IFNULL(li.uniware_return_items, '') != '' THEN 1 ELSE 0 END) AS with_return_items
        FROM `tabOrder Line Items` li
        INNER JOIN `tabUnicommerce Orders` o ON o.name = li.parent
        WHERE {where_clause}
        GROUP BY o.channel_name
        ORDER BY line_count DESC
        """,
        params,
        as_dict=True,
    )

    line_map = {(_safe_str(r.get("channel")) or "UNKNOWN"): r for r in line_rows}
    report_rows = []
    for row in order_rows:
        channel = _safe_str(row.get("channel")) or "UNKNOWN"
        order_count = int(row.get("order_count") or 0)
        line_row = line_map.get(channel, {})
        line_count = int(line_row.get("line_count") or 0)

        def _pct(part: int, whole: int) -> float:
            if whole <= 0:
                return 0.0
            return round((float(part or 0) * 100.0) / float(whole), 2)

        report_rows.append(
            {
                "channel": channel,
                "orders": order_count,
                "lines": line_count,
                "orders_shipping_packages_pct": _pct(int(row.get("with_shipping_packages") or 0), order_count),
                "orders_shipment_status_pct": _pct(int(row.get("with_shipment_status") or 0), order_count),
                "orders_shipment_date_pct": _pct(int(row.get("with_shipment_date") or 0), order_count),
                "orders_return_code_pct": _pct(int(row.get("with_return_code") or 0), order_count),
                "orders_return_items_pct": _pct(int(row.get("with_return_items") or 0), order_count),
                "lines_vendor_batch_pct": _pct(int(line_row.get("with_vendor_batch") or 0), line_count),
                "lines_uniware_batch_pct": _pct(int(line_row.get("with_uniware_batch") or 0), line_count),
                "lines_shipping_charge_pct": _pct(int(line_row.get("with_shipping_charge") or 0), line_count),
                "lines_shipping_tax_pct": _pct(int(line_row.get("with_shipping_tax_percent") or 0), line_count),
                "lines_return_status_pct": _pct(int(line_row.get("with_return_status") or 0), line_count),
                "lines_return_items_pct": _pct(int(line_row.get("with_return_items") or 0), line_count),
            }
        )

    return {
        "window_days": day_window,
        "status_filter": status_list or "ALL",
        "channels": report_rows,
    }


def backfill_uc_financials(batch_size: int = 500, start_date: str | None = None) -> dict:
    """Backfill uc_taxable_value / uc_cgst / uc_sgst / uc_igst /
    uc_shipping / uc_total for existing Unicommerce Orders rows.

    start_date (YYYY-MM-DD): only process orders on or after this date.
    Leave blank to process all orders; pass '2026-05-01' to skip April and earlier.

    Safe to run on posted orders — only touches the 6 uc_* columns, never
    changes pipeline_status or any SAP reference fields.
    Safe to run multiple times — skips rows where uc_taxable_value != 0 already.

    Usage:
        bench --site dev.localhost execute \\
            khanal_tech_integrations.unicommerce.workers.fetch.backfill_uc_financials \\
            --kwargs '{"batch_size": 500, "start_date": "2026-05-01"}'
    """
    updated = skipped = failed = no_json = 0
    date_clause = ""
    date_params: dict = {"limit": int(batch_size)}
    if start_date and str(start_date).strip():
        date_clause = "AND order_date >= %(start_date)s"
        date_params["start_date"] = str(start_date).strip()

    while True:
        # Always query at OFFSET 0 — updated rows gain uc_taxable_value != 0
        # and fall out of the WHERE clause, so the result set shrinks naturally.
        # Incrementing an offset while updating causes rows to be skipped.
        rows = frappe.db.sql(
            f"""
            SELECT name, order_json
            FROM `tabUnicommerce Orders`
            WHERE IFNULL(uc_taxable_value, 0) = 0
              AND order_json IS NOT NULL
              AND order_json != ''
              AND order_json != 'null'
              {date_clause}
            ORDER BY name
            LIMIT %(limit)s
            """,
            date_params,
            as_dict=True,
        )
        if not rows:
            break

        any_written = False
        for row in rows:
            try:
                order = json.loads(row.order_json or "{}")
                if not order:
                    no_json += 1
                    continue
                financials = _compute_uc_financials(order)
                if any(v != 0.0 for v in financials.values()):
                    frappe.db.set_value(
                        "Unicommerce Orders",
                        row.name,
                        financials,
                        update_modified=False,
                    )
                    updated += 1
                    any_written = True
                else:
                    # Genuine zero-value order — stamp a sentinel so we don't
                    # re-process it on every run (set uc_total to a tiny non-zero
                    # sentinel is wrong; instead mark skipped and break the loop
                    # when no rows in a batch were written).
                    skipped += 1
            except Exception as exc:
                failed += 1
                frappe.logger().warning(
                    f"backfill_uc_financials: failed for {row.name}: {exc}"
                )

        frappe.db.commit()
        frappe.logger().info(
            f"backfill_uc_financials: batch done — updated={updated} "
            f"skipped={skipped} failed={failed}"
        )
        # If no rows in this batch were written (all zero-value orders), stop
        # to avoid an infinite loop on genuine zero-value orders.
        if not any_written:
            break

    result = {"updated": updated, "skipped": skipped, "failed": failed, "no_json": no_json}
    frappe.logger().info(f"backfill_uc_financials done: {result}")
    print(result)
    return result

