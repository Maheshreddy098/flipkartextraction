"""
Build SAP B1 Service Layer payloads from staging documents.
"""

import json
from datetime import datetime
from typing import Any

import frappe
from frappe.utils import getdate, today

from ..geo import (
    classify_tax_bucket,
    extract_shipping_state,
    normalize_state_code,
    resolve_mapped_value,
    resolve_origin_state_code,
    safe_json_field,
)
from ..returns import load_parent_order, normalize_text, resolve_actual_uc_order_id
from .tax import compute_tax_from_line, get_tax_code

ORIGIN_STATE = "KA"
SHIPPING_ITEM_CODE = "EXCM0027"
RETURN_WAREHOUSE_CODE = "EC-QA"

# ---------------------------------------------------------------------------
# Warehouse routing — single source of truth
# ---------------------------------------------------------------------------
# Amazon FBA fulfilment-centre channels have their own dedicated warehouses.
# Every other channel (Amazon IN API, Flipkart, Meesho, etc.) ships out of EC-FG.
# The map is keyed by UPPER-CASED channel name so case differences can't cause
# a mis-route.  Adding a new FBA centre = add one line here.
CHANNEL_WAREHOUSE_MAP: dict[str, str] = {
    "AMAZON_FBA_IN_BOM5": "AMZ-BOM5",
    "AMAZON_FBA_IN_BOM7": "AMZ-BOM7",
    "AMAZON_FBA_IN_BLR7": "AMZ-BLR7",
    "AMAZON_FBA_IN_CJB1": "AMZ-CJB1",
    "AMAZON_FBA_IN_MAA4": "AMZ-MAA4",
    "AMAZON_FBA_IN_DEL4": "AMZ-DEL4",
    "AMAZON_FBA_IN_DEL5": "AMZ-DEL5",
    "AMAZON_FBA_IN_BLR5": "AMZ-BLR5",
    "AMAZON_FBA_IN_BLR8": "AMZ-BLR8",
}
DEFAULT_WAREHOUSE = "EC-FG"


def _resolve_ar_invoice_series(settings, channel: str) -> int:
    series_map = json.loads(getattr(settings, "ar_invoice_series_map", "") or "{}")
    channel_key = (channel or "").strip()
    series = series_map.get(channel_key)
    if series is None and channel_key:
        # Case-insensitive fallback for channel keys
        channel_upper = channel_key.upper()
        for key, value in series_map.items():
            if str(key).upper() == channel_upper:
                series = value
                break
    if series is None:
        series = settings.ar_invoice_series
    if not series:
        frappe.throw(
            f"AR invoice series not configured for channel: {channel}. "
            "Set Unicommerce Settings.ar_invoice_series_map or fallback ar_invoice_series."
        )
    return int(series)


def _safe_get(doc: Any, fieldname: str) -> Any:
    return getattr(doc, fieldname, None)


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except Exception:
        return float(default)


def _resolve_order_address(uc_data: dict) -> dict:
    return (
        uc_data.get("billingAddress")
        or uc_data.get("shippingAddress")
        or ((uc_data.get("addresses") or [{}])[0] or {})
        or {}
    )


def _compose_sap_address(uc_data: dict) -> str:
    addr = _resolve_order_address(uc_data)
    parts = [
        str(addr.get("addressLine1") or "").strip(),
        str(addr.get("addressLine2") or "").strip(),
        str(addr.get("city") or "").strip(),
        str(addr.get("state") or "").strip(),
        str(addr.get("pincode") or "").strip(),
        str(addr.get("country") or "").strip(),
    ]
    return ", ".join([p for p in parts if p])[:254]


def _resolve_transportation_code(uc_data: dict) -> int | None:
    """
    SAP TransportationCode mapping.
    Platform-fulfilled orders are mapped to code 5.
    """
    third_party = uc_data.get("thirdPartyShipping")
    provider = str(uc_data.get("shippingProvider") or "").strip().lower()
    if third_party is True:
        return 5
    if provider and provider not in ("self", "self pickup"):
        return 5
    return None


def _resolve_gst_transaction_type(uc_data: dict, total_tax_expected: float) -> str:
    """Force regular GST Tax Invoice to avoid ambiguous SAP defaults.

    Some SAP localizations infer export flow when the header transaction type is
    omitted and return '(987) Please Select Type of Shipment for Export Invoices'.
    Keep this explicit and stable for UC B2C invoice postings.
    """
    return "gsttrantyp_GSTTaxInvoice"


def _raw_order_json_for_sap(staging_doc, uc_data: dict) -> str:
    """
    Build compact raw order JSON for SAP UDF.
    Uses a safe max-length to avoid document rejection on oversized payloads.
    """
    raw = ""
    if staging_doc is not None:
        raw = str(getattr(staging_doc, "order_json", "") or "").strip()
    if not raw:
        try:
            raw = json.dumps(uc_data or {}, separators=(",", ":"), default=str)
        except Exception:
            raw = "{}"
    max_len = 64000
    if len(raw) > max_len:
        raw = raw[: max_len - 3] + "..."
    return raw


def _epoch_millis_to_date(value: Any) -> str | None:
    """Convert UC epoch-millis values to YYYY-MM-DD date string (IST).
    UC timestamps are business dates in IST. Using fromtimestamp() without tz
    makes the result depend on the server timezone (UTC on AWS) — late-night IST
    orders would roll over to the next day. Pinning to IST fixes this.
    """
    try:
        millis = int(float(value or 0))
    except Exception:
        return None
    if millis <= 0:
        return None
    try:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        return datetime.fromtimestamp(millis / 1000.0, tz=IST).date().isoformat()
    except Exception:
        return None


def _resolve_uc_order_date(staging_doc, uc_data: dict) -> str:
    """
    Prefer UC dates for SAP date fields:
    1) displayOrderDateTime
    2) created
    Fallback: existing staging date behavior.
    """
    uc_display_date = _epoch_millis_to_date(uc_data.get("displayOrderDateTime"))
    if uc_display_date:
        return uc_display_date
    uc_created_date = _epoch_millis_to_date(uc_data.get("created"))
    if uc_created_date:
        return uc_created_date
    return str(staging_doc.order_date or getdate(staging_doc.created or today()))


def _resolve_shipping_tax_percent(item: dict, default_tax_percent: float, channel: str, item_code: str) -> float:
    """
    Shipping GST % should come from UC shippingChargeTaxPercentage.
    Guardrail: if shipping charge exists but tax % is missing/zero, fall back to item tax %
    so freight line can still post with a deterministic tax code.
    """
    freight_gross = _resolve_freight_gross(item)
    if freight_gross <= 0:
        return 0.0

    raw = item.get("shippingChargeTaxPercentage")
    if raw in (None, ""):
        raw = item.get("shippingchargetaxpercentage")
    percent = _to_float(raw)
    if percent > 0:
        return percent

    fallback = max(_to_float(default_tax_percent), 0.0)
    if fallback > 0:
        frappe.logger().warning(
            "Shipping tax percent missing in UC; fallback to item tax percent channel=%s item=%s fallback=%s",
            channel,
            item_code,
            fallback,
        )
    return fallback


def _resolve_freight_gross(item: dict) -> float:
    """
    Shipping/freight can arrive in different UC fields by channel.
    Include all charge components when present.
    """
    shipping = _to_float(item.get("shippingCharges") or item.get("shippingcharges"))
    shipping_method = _to_float(item.get("shippingMethodCharges") or item.get("shippingmethodcharges"))
    cod = _to_float(item.get("cashOnDeliveryCharges") or item.get("cashondeliverycharges"))
    return round(max(0.0, shipping + shipping_method + cod), 4)


def _resolve_sap_warehouse(settings, channel: str, uc_wh_code: str) -> str:
    # 1. Hardcoded channel→warehouse map — always authoritative, immune to mis-config.
    #    FBA channels get their own fulfilment-centre warehouse; everything else → EC-FG.
    channel_upper = (channel or "").strip().upper()
    if channel_upper in CHANNEL_WAREHOUSE_MAP:
        return CHANNEL_WAREHOUSE_MAP[channel_upper]

    # 2. Settings-level overrides (optional, for edge-cases not in the map above).
    wh_map = json.loads(settings.warehouse_map or "{}")
    channel_wh_map = safe_json_field(settings, "channel_warehouse_map")
    resolved = resolve_mapped_value(wh_map, uc_wh_code)
    if resolved:
        return str(resolved).strip()
    resolved = resolve_mapped_value(channel_wh_map, channel)
    if resolved:
        return str(resolved).strip()

    # 3. Absolute default — EC-FG for every non-FBA channel.
    return DEFAULT_WAREHOUSE


def _resolve_bill_ship_codes(settings, channel: str, tax_bucket: str) -> tuple[str, str]:
    bill_map = safe_json_field(settings, "bill_to_code_map")
    ship_map = safe_json_field(settings, "ship_to_code_map")

    bucket_key = "igst" if tax_bucket == "igst" else "cgst_sgst"
    default_bill = "B2C IGST ADD" if bucket_key == "igst" else "B2C SGST ADD"

    lookup_keys = [
        f"{channel}:{bucket_key}",
        channel,
        bucket_key,
        "default",
    ]

    bill_to_code = default_bill
    ship_to_code = default_bill
    for key in lookup_keys:
        if key and resolve_mapped_value(bill_map, key) is not None:
            bill_to_code = str(resolve_mapped_value(bill_map, key)).strip()
            break
    for key in lookup_keys:
        if key and resolve_mapped_value(ship_map, key) is not None:
            ship_to_code = str(resolve_mapped_value(ship_map, key)).strip()
            break

    return bill_to_code, ship_to_code or bill_to_code


def _with_batch_item_code(batch_numbers: list[dict], item_code: str) -> list[dict]:
    normalized_item_code = normalize_text(item_code)
    rows: list[dict] = []
    for row in batch_numbers or []:
        if not isinstance(row, dict):
            continue
        updated = dict(row)
        if normalized_item_code:
            updated["ItemCode"] = normalized_item_code
        rows.append(updated)
    return rows


def _gl_mode_from_tax_bucket(tax_bucket: str) -> str | None:
    if tax_bucket == "cgst_sgst":
        return "intra"
    if tax_bucket == "igst":
        return "inter"
    return None


def _resolve_gl_channel_section(gl_map: dict, channel: str) -> dict | None:
    if not isinstance(gl_map, dict) or not gl_map:
        return None
    ch = (channel or "").strip()
    section = resolve_mapped_value(gl_map, ch)
    if section is None and ch:
        ch_upper = ch.upper()
        for key, value in gl_map.items():
            if str(key).strip().upper() == ch_upper:
                section = value
                break
    if section is None:
        section = resolve_mapped_value(gl_map, "default")
    return section if isinstance(section, dict) else None


def _resolve_gl_state_section(channel_section: dict, ship_state: str) -> dict | None:
    if not isinstance(channel_section, dict):
        return None
    st = normalize_state_code(ship_state) if ship_state else ""
    section = resolve_mapped_value(channel_section, st) if st else None
    if section is None:
        section = resolve_mapped_value(channel_section, "default")
    return section if isinstance(section, dict) else None


def _resolve_gl_account_code(
    settings,
    channel: str,
    ship_state: str,
    tax_bucket: str,
    line_kind: str,
) -> str | None:
    """
    line_kind: "product" | "shipping"
    """
    gl_map = safe_json_field(settings, "gl_account_map")
    if not gl_map:
        return None
    mode = _gl_mode_from_tax_bucket(tax_bucket)
    if not mode:
        return None
    ch_sec = _resolve_gl_channel_section(gl_map, channel)
    if not ch_sec:
        return None
    st_sec = _resolve_gl_state_section(ch_sec, ship_state)
    if not st_sec:
        return None
    mode_sec = st_sec.get(mode)
    if isinstance(mode_sec, str):
        acct = mode_sec.strip()
        return acct or None
    if not isinstance(mode_sec, dict):
        return None
    acct = mode_sec.get(line_kind)
    if acct in (None, "") and line_kind == "product":
        acct = mode_sec.get("default")
    if acct in (None, ""):
        return None
    return str(acct).strip() or None


def _fefo_allocate_from_rows(rows: list[dict], qty_needed: float) -> list[dict]:
    """Allocate ``qty_needed`` across already-fetched FEFO rows.

    Rows must already be sorted earliest-expiry-first (the DB query does
    this, and the bulk pre-warm in ``ops._prewarm_prevalidate_context``
    preserves the order). Returns SAP ``BatchNumbers`` payload rows, or an
    empty list when the available quantity is below ``qty_needed`` (minus
    the ``BATCH_QTY_TOLERANCE`` fudge). Keeping the allocator pure (no DB
    / no SAP) lets the Ops Center pre-validate reuse a pre-built cache and
    skip per-line DB round-trips entirely.
    """
    needed = round(float(qty_needed or 0), 3)
    if needed <= 0:
        return []

    by_batch: dict[str, float] = {}
    for row in rows or []:
        batch = normalize_text(row.get("distnumber"))
        if not batch:
            continue
        try:
            qty = float(row.get("quantity") or 0)
        except Exception:
            qty = 0.0
        if qty <= 0:
            continue
        by_batch[batch] = round(float(by_batch.get(batch, 0) + qty), 3)

    allocations: list[dict] = []
    remaining = needed
    for batch, qty in by_batch.items():
        if remaining <= 0:
            break
        take = min(qty, remaining)
        if take <= 0:
            continue
        allocations.append({"BatchNumber": batch, "Quantity": round(float(take), 3)})
        remaining = round(remaining - take, 3)

    # Tolerance must match BATCH_QTY_TOLERANCE in workers/invoice.py (0.01).
    if remaining > 0.01:
        return []
    return allocations


def ar_invoice_payload(
    staging_doc,
    batch_managed_cache: "dict[str, bool | None] | None" = None,
    fefo_rows_cache: "dict[tuple[str, str], list[dict]] | None" = None,
    fefo_overrides: "dict[tuple, list[dict]] | None" = None,
) -> dict:
    """Build the SAP AR Invoice payload from a staged UC order.

    ``batch_managed_cache`` is a tri-state dict (``True``/``False``/``None``)
    shared with the pre-post validator (``_check_batches``). When the SAP
    Service Layer lookup for ``ManageBatchNumbers`` failed for an item, the
    cache holds ``None`` for that item and the payload builder skips batch
    allocation so both layers make the same decision. See
    ``workers/invoice.BatchManagedCache`` for the contract.
    """
    settings = frappe.get_single("Unicommerce Settings")
    channel_map = json.loads(settings.channel_customer_map or "{}")
    tax_inclusive_map = json.loads(settings.tax_inclusive_map or "{}")

    uc_data = json.loads(staging_doc.order_json or "{}")
    channel = staging_doc.channel_name or ""
    customer_code = resolve_mapped_value(channel_map, channel) or resolve_mapped_value(channel_map, "default")
    if not customer_code:
        frappe.throw(f"No SAP customer mapped for channel: {channel}")

    items = _parse_line_items(uc_data)
    if not items:
        frappe.throw(f"No items found in order_json for order {staging_doc.name}")

    tax_inclusive = bool(resolve_mapped_value(tax_inclusive_map, channel, False))
    ship_state = extract_shipping_state(uc_data) or ORIGIN_STATE
    origin_state_code = resolve_origin_state_code(channel=channel, settings=settings)
    tax_bucket = classify_tax_bucket(ship_state, None, origin_state_code)
    bill_to_code, ship_to_code = _resolve_bill_ship_codes(settings, channel, tax_bucket)
    order_address = _resolve_order_address(uc_data)
    order_id = normalize_text(staging_doc.uniware_id or uc_data.get("code") or staging_doc.name)
    uc_order_date = _resolve_uc_order_date(staging_doc, uc_data)
    ordered_on = uc_order_date
    raw_order_json = _raw_order_json_for_sap(staging_doc, uc_data)
    line_udfs = {
        "U_Order": order_id,
        "U_OrderedOn": ordered_on,
        "U_BuyerName": str(staging_doc.customer_name or order_address.get("name") or "").strip(),
        "U_City": str(order_address.get("city") or "").strip(),
        "U_State": str(order_address.get("state") or "").strip(),
        "U_PINCode": str(order_address.get("pincode") or "").strip(),
        "U_Country": str(order_address.get("country") or "India").strip(),
        "U_Order_JSON": raw_order_json,
    }
    doc_lines = []
    total_tax_expected = 0.0
    processed_bundle_codes: set[str] = set()
    freight_buckets: dict[tuple[str, str, float], dict] = {}

    for item in items:
        bundle_code = normalize_text(item.get("bundleSkuCode"))
        if bundle_code:
            if bundle_code in processed_bundle_codes:
                continue
            bundle_items = [
                row for row in items if normalize_text(row.get("bundleSkuCode")) == bundle_code
            ]
            if not bundle_items:
                continue
            processed_bundle_codes.add(bundle_code)
            # Use min() — minimum component quantity equals bundle-unit count when
            # all component per-bundle ratios are ≥ 1. max() over-counts when ratios differ.
            bundle_qty = min(float(row.get("quantity", 0) or 0) for row in bundle_items)
            if not bundle_qty:
                frappe.logger().warning(f"Bundle {bundle_code} has zero quantity — skipping SAP line")
                continue
            parent_tax_percent = float(bundle_items[0].get("taxPercent", 0) or 0)
            parent_uc_wh = bundle_items[0].get("warehouseCode", "")
            parent_sap_wh = _resolve_sap_warehouse(settings, channel, parent_uc_wh)
            parent_tax_code = get_tax_code(parent_tax_percent, ship_state, origin_state_code)
            doc_lines.append(
                {
                    "LineNum": len(doc_lines),
                    "ItemCode": bundle_code,
                    "Quantity": bundle_qty,
                    "UnitPrice": 0.0,
                    "WarehouseCode": parent_sap_wh,
                    "TaxCode": parent_tax_code,
                    "TaxType": "tt_Yes",
                    "TaxLiable": "tYES",
                    "TaxTotal": 0.0,
                    "BatchNumbers": [],
                    "TreeType": "iSalesTree",
                }
            )
            for bundle_item in bundle_items:
                total_tax_expected += _append_sales_line(
                    doc_lines=doc_lines,
                    item=bundle_item,
                    ship_state=ship_state,
                    origin_state_code=origin_state_code,
                    tax_inclusive=tax_inclusive,
                    settings=settings,
                    channel=channel,
                    tax_bucket=tax_bucket,
                    tree_type="iIngredient",
                    freight_buckets=freight_buckets,
                    line_udfs=line_udfs,
                    batch_managed_cache=batch_managed_cache,
                    fefo_rows_cache=fefo_rows_cache,
                    fefo_overrides=fefo_overrides,
                )
            continue

        total_tax_expected += _append_sales_line(
            doc_lines=doc_lines,
            item=item,
            ship_state=ship_state,
            origin_state_code=origin_state_code,
            tax_inclusive=tax_inclusive,
            settings=settings,
            channel=channel,
            tax_bucket=tax_bucket,
            freight_buckets=freight_buckets,
            line_udfs=line_udfs,
            batch_managed_cache=batch_managed_cache,
            fefo_rows_cache=fefo_rows_cache,
            fefo_overrides=fefo_overrides,
        )

    for bucket in sorted(
        freight_buckets.values(),
        key=lambda row: (str(row.get("warehouse_code") or ""), str(row.get("tax_code") or ""), float(row.get("tax_percent") or 0)),
    ):
        freight_gross = _to_float(bucket.get("gross"))
        freight_tax_percent = _to_float(bucket.get("tax_percent"))
        sap_wh_code = str(bucket.get("warehouse_code") or "").strip()
        tax_code = str(bucket.get("tax_code") or "").strip()
        freight_unit_price_ex_tax = (
            freight_gross * (100 / (100 + freight_tax_percent)) if freight_tax_percent > 0 else freight_gross
        )
        freight_line = {
            "LineNum": len(doc_lines),
            "ItemCode": SHIPPING_ITEM_CODE,
            "Quantity": 1,
            "UnitPrice": round(freight_unit_price_ex_tax, 4),
            "WarehouseCode": sap_wh_code,
            "TaxCode": tax_code,
            "TaxType": "tt_Yes",
            "TaxLiable": "tYES",
            "TaxTotal": round(compute_tax_from_line(freight_gross, 1, freight_tax_percent, tax_inclusive=True), 5),
            "BatchNumbers": [],
        }
        if line_udfs:
            freight_line.update(line_udfs)
        ship_gl = _resolve_gl_account_code(settings, channel, ship_state, tax_bucket, "shipping")
        if ship_gl:
            freight_line["AccountCode"] = ship_gl
        doc_lines.append(freight_line)

    series = _resolve_ar_invoice_series(settings, channel)

    payload = {
        "CardCode": customer_code,
        "DocDate": uc_order_date,
        "DocDueDate": uc_order_date,
        "Series": series,
        "GSTTransactionType": _resolve_gst_transaction_type(uc_data, total_tax_expected),
        "U_UCOrderID": staging_doc.name,
        "U_FrappeGRNKey": "3",
        "PayToCode": bill_to_code,
        "ShipToCode": ship_to_code,
        "Address": _compose_sap_address(uc_data),
        "DocumentLines": doc_lines,
        "Comments": f"Unicommerce Order: {staging_doc.name} | Channel: {channel}",
    }
    transport_code = _resolve_transportation_code(uc_data)
    if transport_code is not None:
        payload["TransportationCode"] = int(transport_code)

    staging_doc.ar_invoice_tax_expected = round(total_tax_expected, 2)
    return payload


def credit_note_payload(cn_staging_doc) -> dict:
    settings = frappe.get_single("Unicommerce Settings")
    if not cn_staging_doc.parent_sap_doc_entry:
        frappe.throw(f"Missing parent_sap_doc_entry for return {cn_staging_doc.uc_return_id}")
    if not settings.credit_note_series:
        frappe.throw("Unicommerce Settings.credit_note_series is not configured")

    items = json.loads(cn_staging_doc.items_json or "[]")
    if not items:
        frappe.throw(f"No return items found for return {cn_staging_doc.uc_return_id}")

    parent_order = load_parent_order(cn_staging_doc.uc_order_id)
    parent_channel = getattr(parent_order, "channel_name", "") if parent_order else ""
    parent_ship_state = normalize_state_code(getattr(parent_order, "state", "") if parent_order else "")
    parent_origin_state = resolve_origin_state_code(channel=parent_channel, settings=settings)
    parent_tax_bucket = classify_tax_bucket(parent_ship_state, None, parent_origin_state)

    def _allocate_return_batches(source_batches: list[dict], return_qty: float) -> list[dict]:
        qty_needed = round(float(return_qty or 0), 3)
        if qty_needed <= 0:
            return []
        normalized = []
        for row in source_batches or []:
            batch_no = normalize_text((row or {}).get("BatchNumber"))
            if not batch_no:
                continue
            try:
                batch_qty = float((row or {}).get("Quantity") or 0)
            except Exception:
                batch_qty = 0.0
            if batch_qty <= 0:
                continue
            normalized.append({"BatchNumber": batch_no, "Quantity": round(batch_qty, 3)})
        if not normalized:
            return []

        allocations = []
        remaining = qty_needed
        for row in normalized:
            if remaining <= 0:
                break
            take = min(float(row.get("Quantity") or 0), remaining)
            if take <= 0:
                continue
            allocations.append(
                {
                    "BatchNumber": row["BatchNumber"],
                    "Quantity": round(float(take), 3),
                }
            )
            remaining = round(remaining - float(take), 3)

        if remaining > 0 and allocations:
            allocations[-1]["Quantity"] = round(float(allocations[-1]["Quantity"]) + remaining, 3)
        return allocations

    lines = []
    for item in items:
        item_code = normalize_text(item.get("itemSku") or item.get("sapItemCode"))
        qty = float(item.get("quantity", 0) or 0)
        source_batches = item.get("sapBatchNumbers") or []
        source_account_code = normalize_text(item.get("sapAccountCode"))
        if item.get("sapBaseLine") in (None, ""):
            frappe.throw(
                f"Missing SAP base line for return item {item_code or 'unknown'} in {cn_staging_doc.uc_return_id}"
            )
        if not item_code:
            frappe.throw(f"Missing itemSku in return {cn_staging_doc.uc_return_id}")
        if qty <= 0:
            frappe.throw(f"Invalid quantity for return item {item_code} in {cn_staging_doc.uc_return_id}")
        if not source_batches:
            frappe.throw(
                f"Missing parent invoice batch mapping for return item {item_code} in {cn_staging_doc.uc_return_id}"
            )
        # Warehouse for return: FBA channels use their originating AMZ-* warehouse;
        # all other channels use the QA quarantine warehouse (EC-QA).
        item_uc_wh = normalize_text(item.get("warehouseCode"))
        channel_upper = (parent_channel or "").strip().upper()
        if channel_upper in CHANNEL_WAREHOUSE_MAP:
            return_wh = CHANNEL_WAREHOUSE_MAP[channel_upper]
        else:
            return_wh = _resolve_sap_warehouse(settings, parent_channel, item_uc_wh) or RETURN_WAREHOUSE_CODE

        line = {
            "ItemCode": item_code,
            "Quantity": qty,
            "WarehouseCode": return_wh,
            "BaseType": 13,  # AR Invoice
            "BaseEntry": int(cn_staging_doc.parent_sap_doc_entry),
            "BaseLine": int(item.get("sapBaseLine", 0) or 0),
            "BatchNumbers": _allocate_return_batches(source_batches, qty),
        }
        if not line.get("BatchNumbers"):
            frappe.throw(
                f"Could not allocate return qty from parent invoice batches for {item_code} in {cn_staging_doc.uc_return_id}"
            )

        account_code = source_account_code
        if not account_code and parent_channel:
            account_code = _resolve_gl_account_code(
                settings=settings,
                channel=parent_channel,
                ship_state=parent_ship_state,
                tax_bucket=parent_tax_bucket,
                line_kind="product",
            ) or ""
        if account_code:
            line["AccountCode"] = account_code

        lines.append(line)

    actual_uc_order_id = resolve_actual_uc_order_id(cn_staging_doc.uc_order_id)
    # Use the return date from the staging doc (returnCreatedDate/returnDeliveryDate from UC)
    # so the SAP CN falls in the correct GST period. Falls back to today only if the
    # staging doc has no return_date (old records or fetch edge-cases).
    cn_doc_date = str(cn_staging_doc.return_date or today())
    return {
        "CardCode": _get_customer_for_order(cn_staging_doc.uc_order_id),
        "DocDate": cn_doc_date,
        "Series": int(settings.credit_note_series),
        "U_UCReturnID": cn_staging_doc.uc_return_id,
        "DocumentLines": lines,
        "Comments": f"Return for UC Order: {actual_uc_order_id}",
    }


def _apply_sku_aliases(items: list[dict]) -> list[dict]:
    """Rewrite lines for SKUs that are broken catalog duplicates of a bundle.

    Some UC catalog SKUs (e.g. FGHN0056, "Pack of 3") are registered as a
    plain SIMPLE item in Unicommerce instead of BUNDLE, so `bundleSkuCode`
    never appears on their order lines and the bundle-tree branch in
    ``ar_invoice_payload`` never fires — the order would otherwise post as
    1x the pack SKU instead of N x its real, batch-managed component.
    ``Unicommerce Settings.sku_alias_map`` is the manually-maintained fix
    list, same convention as ``channel_customer_map`` etc. Quantity is
    multiplied and unitPrice divided by the same factor, so price stays
    evenly distributed per invoiced child unit and downstream discount/tax
    math (which divides by quantity) falls out correctly unchanged.

    Format: {"FGHN0056": {"item_code": "FGHN0054", "qty_multiplier": 3}}
    """
    settings = frappe.get_single("Unicommerce Settings")
    alias_map = json.loads(getattr(settings, "sku_alias_map", "") or "{}")
    if not alias_map:
        return items

    rewritten = []
    for item in items:
        sku = normalize_text(item.get("itemSku"))
        alias = alias_map.get(sku)
        multiplier = float(alias.get("qty_multiplier") or 0) if alias else 0
        if not alias or multiplier <= 0 or not alias.get("item_code"):
            rewritten.append(item)
            continue
        new_item = dict(item)
        new_item["itemSku"] = normalize_text(alias["item_code"])
        new_item["quantity"] = float(item.get("quantity") or 0) * multiplier
        if item.get("unitPrice") not in (None, ""):
            new_item["unitPrice"] = round(float(item["unitPrice"]) / multiplier, 4)
        rewritten.append(new_item)
    return rewritten


def _parse_line_items(uc_data: dict) -> list[dict]:
    # Preferred normalized shape from prompt flow
    direct_items = uc_data.get("items", [])
    if direct_items:
        return _apply_sku_aliases(direct_items)

    # Tenant detail API shape: saleOrderItems
    so_items = uc_data.get("saleOrderItems", [])
    if not so_items:
        return []

    normalized = []
    for row in so_items:
        qty = (
            row.get("quantity")
            or row.get("totalQuantity")
            or row.get("completedQuantity")
            or row.get("allocatedQuantity")
            or row.get("inProcessQuantity")
            or row.get("unallocatedQuantity")
            or 1
        )
        tax_percent = (
            row.get("taxPercentage")
            or row.get("integratedGstPercentage")
            or ((row.get("stateGstPercentage") or 0) + (row.get("centralGstPercentage") or 0))
            or 0
        )
        unit_price = row.get("sellingPriceWithoutTaxesAndDiscount")
        if unit_price in (None, ""):
            unit_price = row.get("sellingPrice") or row.get("totalPrice") or 0

        batch_num = (
            ((row.get("batchDTO") or {}).get("batchFieldsDTO") or {}).get("vendorBatchNumber")
            or ""
        )
        normalized.append(
            {
                "itemSku": normalize_text(row.get("itemSku")),
                "quantity": qty,
                "unitPrice": unit_price,
                "discount": row.get("discount"),
                "taxPercent": tax_percent,
                "batchNumber": normalize_text(batch_num),
                "warehouseCode": normalize_text(row.get("facilityCode")),
                "saleOrderItemCode": normalize_text(row.get("code")),
                "bundleSkuCode": normalize_text(row.get("bundleSkuCode")),
                # Optional freight fields. These are present in UC `saleOrderItems`
                # for many tenants (see legacy unicommerce_clean).
                "shippingCharges": row.get("shippingCharges"),
                "shippingChargeTaxPercentage": row.get("shippingChargeTaxPercentage"),
                "shippingMethodCharges": row.get("shippingMethodCharges"),
                "cashOnDeliveryCharges": row.get("cashOnDeliveryCharges"),
                # Tenant-dependent casing fallbacks (kept for robustness).
                "shippingcharges": row.get("shippingcharges"),
                "shippingchargetaxpercentage": row.get("shippingchargetaxpercentage"),
                "shippingmethodcharges": row.get("shippingmethodcharges"),
                "cashondeliverycharges": row.get("cashondeliverycharges"),
            }
        )
    return _apply_sku_aliases(normalized)


def _get_customer_for_order(order_ref: str) -> str:
    settings = frappe.get_single("Unicommerce Settings")
    channel_map = json.loads(settings.channel_customer_map or "{}")

    parent_order = load_parent_order(order_ref)
    channel = getattr(parent_order, "channel_name", None) if parent_order else None
    if not channel:
        channel = frappe.db.get_value("Unicommerce Orders", order_ref, "channel_name")
    if not channel:
        frappe.throw(f"Unable to resolve parent order channel for {order_ref}")

    customer_code = resolve_mapped_value(channel_map, channel) or resolve_mapped_value(channel_map, "default")
    if not customer_code:
        frappe.throw(f"No SAP customer mapped for channel: {channel}")
    return customer_code


def _append_sales_line(
    doc_lines: list[dict],
    item: dict,
    ship_state: str,
    origin_state_code: str,
    tax_inclusive: bool,
    settings,
    channel: str,
    tax_bucket: str,
    tree_type: str | None = None,
    freight_buckets: dict[tuple[str, str, float], dict] | None = None,
    line_udfs: dict[str, str] | None = None,
    batch_managed_cache: "dict[str, bool | None] | None" = None,
    fefo_rows_cache: "dict[tuple[str, str], list[dict]] | None" = None,
    fefo_overrides: "dict[tuple, list[dict]] | None" = None,
) -> float:
    item_code = normalize_text(item.get("itemSku"))
    qty = float(item.get("quantity", 0) or 0)
    unit_price = float(item.get("unitPrice", 0) or 0)
    discount_total = _to_float(item.get("discount"))
    if discount_total > 0 and qty > 0:
        # UC discount is line-level amount; convert to per-unit before posting to SAP.
        unit_price = max(0.0, unit_price - (discount_total / qty))
    tax_percent = float(item.get("taxPercent", 0) or 0)
    batch_num = normalize_text(item.get("batchNumber"))
    uc_wh_code = normalize_text(item.get("warehouseCode"))
    sap_wh_code = _resolve_sap_warehouse(settings, channel, uc_wh_code)

    if not item_code:
        frappe.throw("Missing itemSku in staged order payload")
    if qty <= 0:
        frappe.throw(f"Invalid quantity for item {item_code}")
    batch_numbers: list[dict] = []
    if batch_num:
        # fefo_overrides: keyed by (item_code, uc_batch_number); the UC-specified batch
        # was unavailable in EC-FG so _check_batches allocated FEFO batches instead.
        # The override holds the total allocation across all aggregated lines for this
        # (item_code, batch_num) pair. Scale proportionally to this line's qty so that
        # BatchNumbers sum == Quantity on every individual SAP line.
        if fefo_overrides and (item_code, batch_num) in fefo_overrides:
            override_allocs = fefo_overrides[(item_code, batch_num)]
            total_override_qty = sum(float(b.get("Quantity", 0)) for b in override_allocs)
            if total_override_qty > 0:
                scale = float(qty) / total_override_qty
                scaled = [
                    {"BatchNumber": b["BatchNumber"], "Quantity": round(float(b["Quantity"]) * scale, 3)}
                    for b in override_allocs
                ]
                # Adjust last entry to absorb rounding drift so sum == line qty exactly.
                drift = round(float(qty) - sum(s["Quantity"] for s in scaled), 3)
                if drift and scaled:
                    scaled[-1]["Quantity"] = round(scaled[-1]["Quantity"] + drift, 3)
                batch_numbers = scaled
            else:
                batch_numbers = list(override_allocs)
        else:
            batch_numbers = [{"BatchNumber": batch_num, "Quantity": round(float(qty), 3)}]
    else:
        # If the pre-validator (``_check_batches``) recorded ``None`` for this
        # item, the SAP ManageBatchNumbers lookup failed and we must NOT
        # auto-allocate batches here (the validator already skipped shortage
        # enforcement for the same item — keeping both layers consistent).
        cache_entry = None
        if batch_managed_cache is not None:
            cache_entry = batch_managed_cache.get(item_code)
        if cache_entry is None and batch_managed_cache is not None and item_code in batch_managed_cache:
            # Explicit None recorded by the validator → skip allocation.
            batch_numbers = []
        else:
            # Use HANA-sourced FEFO rows pre-fetched by _check_batches.
            # If the cache has no entry for this (item, wh), emit empty — SAP
            # will reject a batchless line if the item requires batch management,
            # which surfaces as a normal posting failure on the order.
            rows = (fefo_rows_cache or {}).get((item_code, sap_wh_code), [])
            batch_numbers = _fefo_allocate_from_rows(rows, qty)
    batch_numbers = _with_batch_item_code(batch_numbers, item_code)

    tax_code = get_tax_code(tax_percent, ship_state, origin_state_code)
    line_tax = compute_tax_from_line(unit_price, qty, tax_percent, tax_inclusive)
    line = {
        "LineNum": len(doc_lines),
        "ItemCode": item_code,
        "Quantity": qty,
        "UnitPrice": unit_price if not tax_inclusive else round(unit_price / (1 + tax_percent / 100), 4),
        "WarehouseCode": sap_wh_code,
        "TaxCode": tax_code,
        "TaxType": "tt_Yes",
        "TaxLiable": "tYES",
        "TaxTotal": round(line_tax, 5),
        "BatchNumbers": batch_numbers,
        "U_Sale_order_itemcode": normalize_text(item.get("saleOrderItemCode")),
        "U_ActualItem": item_code,
    }
    if line_udfs:
        line.update(line_udfs)
    gl_acct = _resolve_gl_account_code(settings, channel, ship_state, tax_bucket, "product")
    if gl_acct:
        line["AccountCode"] = gl_acct
    if tree_type:
        line["TreeType"] = tree_type
    doc_lines.append(line)

    freight_gross = _resolve_freight_gross(item)
    freight_tax_percent = _resolve_shipping_tax_percent(item, tax_percent, channel, item_code)
    if freight_gross > 0:
        freight_tax_code = get_tax_code(freight_tax_percent, ship_state, origin_state_code)
        line_tax += compute_tax_from_line(
            freight_gross,
            1,
            freight_tax_percent,
            tax_inclusive=True,
        )
        if freight_buckets is None:
            freight_buckets = {}
        bucket_key = (sap_wh_code, freight_tax_code, round(float(freight_tax_percent or 0), 4))
        if bucket_key not in freight_buckets:
            freight_buckets[bucket_key] = {
                "warehouse_code": sap_wh_code,
                "tax_code": freight_tax_code,
                "tax_percent": round(float(freight_tax_percent or 0), 4),
                "gross": 0.0,
            }
        freight_buckets[bucket_key]["gross"] = round(
            float(freight_buckets[bucket_key].get("gross") or 0) + freight_gross,
            4,
        )

    return line_tax


def expected_invoice_pricing_from_uc(uc_data: dict, channel: str) -> dict:
    """Pure pricing snapshot — no SAP / batch / HANA calls.

    Replays the discount → ``UnitPrice`` → line-tax maths from
    ``_append_sales_line`` plus aggregated freight buckets (same rules as
    ``ar_invoice_payload``), so Ops tooling can compare what an AR invoice
    **should** contain vs what Service Layer stored.

    Returns ``{"ok": False, "reason": ...}`` only for empty item lists.
    Bundle orders are evaluated from their component rows; SAP bundle parent
    stubs are already ignored in ``_sap_invoice_lines_for_price_audit``.
    """
    settings = frappe.get_single("Unicommerce Settings")
    tax_inclusive_map = json.loads(settings.tax_inclusive_map or "{}")
    tax_inclusive = bool(resolve_mapped_value(tax_inclusive_map, channel, False))

    items = _parse_line_items(uc_data)
    if not items:
        return {"ok": False, "reason": "no_items", "lines": [], "expected_doc_tax": 0.0}

    ship_state = extract_shipping_state(uc_data) or ORIGIN_STATE
    origin_state_code = resolve_origin_state_code(channel=channel, settings=settings)

    freight_buckets: dict[tuple[str, str, float], dict] = {}
    product_lines: list[dict] = []
    total_tax = 0.0

    for it in items:
        qty = float(it.get("quantity", 0) or 0)
        if qty <= 0:
            continue
        unit_price = float(it.get("unitPrice", 0) or 0)
        discount_total = _to_float(it.get("discount"))
        if discount_total > 0 and qty > 0:
            unit_price = max(0.0, unit_price - (discount_total / qty))
        tax_percent = float(it.get("taxPercent", 0) or 0)
        item_code = normalize_text(it.get("itemSku"))
        sap_wh = _resolve_sap_warehouse(settings, channel, normalize_text(it.get("warehouseCode")))
        line_tax = compute_tax_from_line(unit_price, qty, tax_percent, tax_inclusive)
        total_tax += float(line_tax)
        sap_unit = unit_price if not tax_inclusive else round(unit_price / (1 + tax_percent / 100), 4)
        product_lines.append(
            {
                "kind": "product",
                "ItemCode": item_code,
                "Quantity": round(qty, 4),
                "ExpectedUnitPrice": round(float(sap_unit), 4),
                "ExpectedLineTax": round(float(line_tax), 2),
            }
        )

        freight_gross = _resolve_freight_gross(it)
        freight_tax_percent = _resolve_shipping_tax_percent(it, tax_percent, channel, item_code)
        if freight_gross > 0:
            freight_tax_code = get_tax_code(freight_tax_percent, ship_state, origin_state_code)
            bucket_key = (sap_wh, freight_tax_code, round(float(freight_tax_percent or 0), 4))
            if bucket_key not in freight_buckets:
                freight_buckets[bucket_key] = {
                    "warehouse_code": sap_wh,
                    "tax_code": freight_tax_code,
                    "tax_percent": round(float(freight_tax_percent or 0), 4),
                    "gross": 0.0,
                }
            freight_buckets[bucket_key]["gross"] = round(
                float(freight_buckets[bucket_key].get("gross") or 0) + float(freight_gross),
                4,
            )

    freight_lines: list[dict] = []
    for bucket in sorted(
        freight_buckets.values(),
        key=lambda row: (
            str(row.get("warehouse_code") or ""),
            str(row.get("tax_code") or ""),
            float(row.get("tax_percent") or 0),
        ),
    ):
        freight_gross = _to_float(bucket.get("gross"))
        freight_tax_percent = _to_float(bucket.get("tax_percent"))
        sap_wh_code = str(bucket.get("warehouse_code") or "").strip()
        tax_code = str(bucket.get("tax_code") or "").strip()
        freight_unit_price_ex_tax = (
            freight_gross * (100 / (100 + freight_tax_percent)) if freight_tax_percent > 0 else freight_gross
        )
        freight_tax_amt = compute_tax_from_line(freight_gross, 1, freight_tax_percent, tax_inclusive=True)
        total_tax += float(freight_tax_amt)
        freight_lines.append(
            {
                "kind": "shipping",
                "ItemCode": SHIPPING_ITEM_CODE,
                "Quantity": 1.0,
                "ExpectedUnitPrice": round(float(freight_unit_price_ex_tax), 4),
                "ExpectedLineTax": round(float(freight_tax_amt), 2),
                "WarehouseCode": sap_wh_code,
                "TaxCode": tax_code,
            }
        )

    return {
        "ok": True,
        "tax_inclusive": tax_inclusive,
        "lines": product_lines + freight_lines,
        "expected_doc_tax": round(float(total_tax), 2),
    }
