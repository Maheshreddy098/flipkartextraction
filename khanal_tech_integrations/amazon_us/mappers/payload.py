"""Build SAP B1 AR Invoice payload for a single staged Amazon US Order."""
import frappe

_TAX_ITEM_CODE = "EXP000003"
_TAX_GL_ACCOUNT = "_SYS00000000059"       # 22200000-01-001-01 Sales Tax Accrual
_SHIPPING_ITEM_CODE = "EXP000004"
_SHIPPING_GL_ACCOUNT = "_SYS00000000084"  # 41400000-01-001-01 Sales Revenues - Freight
_FALLBACK_TAX_CODE = "etax0"              # 0% e-commerce code verified in INC SalesTaxCodes (exact lowercase)


def build_line_udfs(order_doc):
    """
    Line-level UDFs for AR Invoice / Credit Note lines.

    Field names verified against INC-entity UserFieldsMD for INV1 and RIN1
    (both tables carry the same set): U_Order (Alpha 50, "Order ID"),
    U_OrderedOn (Date), U_BuyerName (Alpha 120), U_City/U_State/U_Country
    (Alpha 20), U_PINCode (Alpha 10). U_Channel and U_OrderID do NOT exist
    in the INC DB — Service Layer silently dropped them from every line.
    Values are truncated to each UDF's EditSize or SAP rejects the document.
    """
    fields = [
        ("U_Order", order_doc.amazon_order_id, 50),
        ("U_BuyerName", getattr(order_doc, "buyer_name", None), 120),
        ("U_City", getattr(order_doc, "ship_city", None), 20),
        ("U_State", getattr(order_doc, "ship_state_or_region", None), 20),
        ("U_PINCode", getattr(order_doc, "ship_postal_code", None), 10),
        ("U_Country", getattr(order_doc, "ship_country", None), 20),
    ]
    udfs = {name: str(value).strip()[:size] for name, value, size in fields if value}
    if getattr(order_doc, "purchase_date", None):
        udfs["U_OrderedOn"] = str(order_doc.purchase_date)[:10]
    return udfs


_SKU_MAP_CACHE_KEY = "amz_us_sap_sku_map"
_SKU_MAP_REFRESH_SECONDS = 3600          # re-pull from SAP after 1 h
_SKU_MAP_STALE_TTL = 7 * 24 * 3600      # keep last good copy up to 7 d if SAP is down


def _get_sap_sku_map():
    """
    Cached {seller_sku: [item_code, ...]} from the SAP item master.
    Refreshes hourly; on SAP failure serves the last good copy (up to 7 days)
    so order staging keeps working through SAP outages.
    """
    import time

    from khanal_tech_integrations.amazon_us.client.sap import fetch_amazon_sku_map

    cached = frappe.cache().get_value(_SKU_MAP_CACHE_KEY)
    if cached and time.time() - cached.get("fetched_at", 0) < _SKU_MAP_REFRESH_SECONDS:
        return cached["map"]

    try:
        sku_map = fetch_amazon_sku_map()
        frappe.cache().set_value(
            _SKU_MAP_CACHE_KEY,
            {"fetched_at": time.time(), "map": sku_map},
            expires_in_sec=_SKU_MAP_STALE_TTL,
        )
        return sku_map
    except Exception as e:
        if cached:
            frappe.logger().warning(f"Amazon US SKU map refresh failed, serving stale copy: {e}")
            return cached["map"]
        frappe.log_error(f"Amazon US SKU map fetch failed with no cached copy: {e}", "Amazon US SAP")
        return {}


def get_item_mapping():
    """
    Return {seller_sku: {"sap_item_code": str}}.

    Hybrid source of truth:
    1. SAP item master U_Amz_SKU — SKUs pointing at exactly ONE item are taken
       as-is, so new listings mapped in SAP flow in without Frappe upkeep.
    2. SKUs on several SAP items (legacy dupes) are only usable when the
       Amazon US Item Mapping doctype picks the winner — never guessed.
    3. Doctype rows always override SAP, so a manual fix wins immediately.
    """
    mapping = {
        sku: {"sap_item_code": codes[0]}
        for sku, codes in _get_sap_sku_map().items()
        if len(codes) == 1
    }
    rows = frappe.get_all(
        "Amazon US Item Mapping",
        fields=["seller_sku", "sap_item_code"],
    )
    for r in rows:
        mapping[r.seller_sku] = {"sap_item_code": r.sap_item_code}
    return mapping


def build_invoice_payload(order_doc, hana_cursor):
    """
    Build SAP B1 AR Invoice payload for a staged Amazon US Order.

    hana_cursor: an already-open HANA cursor (client.hana.open_connection),
    reused across every line of every order in the posting run instead of
    reconnecting per line item.

    DocDate = actual_ship_date (shipment date, Pacific). Finance policy
    (confirmed 2026-07-08): revenue is recognized on shipment, matching the
    MTR report's posted-date indexing -- an order bought May 31 but shipped
    Jun 2 belongs to June's books. actual_ship_date comes from the FBA
    shipments report sync (workers/fba_shipments.py) -- an order can reach
    stage=ready (Shipped status + mapped SKUs) before that separate sync has
    covered it, so this is NOT guaranteed to be set. Orders without it are
    refused here (returns None) rather than silently falling back to
    purchase_date: that fallback produced wrong-month invoices in
    production testing (2026-07-14) once, before ship-date sync had run.
    Run the FBA shipments sync and retry rather than posting on a guess.
    NumAtCard = AmazonOrderId (external reference).
    CardCode, Series, Warehouse, TaxCode, PayToCode pulled from Amazon US Settings.
    All inventory items use FEFO batch allocation (US stock is always batch-managed).
    EXP000003 appended with total order tax (item_tax_amount + shipping_tax_amount).
    Line UnitPrice is the GROSS item price (item_price_amount / qty) and the freight
    line is the gross shipping charge. Amazon promotional rebates (item and shipping)
    are deliberately NOT deducted anywhere on the invoice — Finance policy
    (2026-07-14 review of Revenue Report_Amazn USA.xlsx): promotional rebates are
    an expenditure booked outside the AR invoice, so revenue must stay gross.

    Returns (payload_dict, skipped_list).
    payload_dict is None if no postable lines remain.
    Raises HanaUnavailableError if HANA is down — callers must NOT mark orders failed.
    Raises ValueError on insufficient FEFO stock.
    """
    from khanal_tech_integrations.amazon_us.client.hana import allocate_batches_fefo

    ship_date = getattr(order_doc, "actual_ship_date", None)
    if not ship_date:
        return None, [{"reason": "No actual_ship_date -- run the FBA shipments sync before posting"}]
    doc_date = str(ship_date)[:10]

    settings = frappe.get_doc("Amazon US Settings")
    tax_code = settings.sap_tax_code or _FALLBACK_TAX_CODE
    pay_to_code = settings.sap_pay_to_code or "Amazon USA-B2C"
    item_mapping = get_item_mapping()

    line_udfs = build_line_udfs(order_doc)

    doc_lines = []
    skipped = []
    total_tax = 0.0
    total_shipping = 0.0

    for row in order_doc.items:
        sku = (row.seller_sku or "").strip()
        if not sku:
            continue
        qty = float(row.quantity or 0)
        if qty <= 0:
            continue

        total_tax += float(row.item_tax_amount or 0) + float(row.shipping_tax_amount or 0)
        # Gross shipping: ship-promotion-discount is a promotional rebate and per
        # Finance policy (2026-07-14) rebates never reduce the invoice.
        total_shipping += float(row.shipping_price_amount or 0)

        mapping = item_mapping.get(sku)
        if not mapping:
            skipped.append({"seller_sku": sku, "reason": "No SAP mapping"})
            continue

        sap_item_code = mapping["sap_item_code"]
        # Gross unit price: promotion_discount_amount is intentionally ignored
        # (Finance policy 2026-07-14 — promo rebates are expenditure, not a
        # price reduction; revenue posts gross).
        gross_price = float(row.item_price_amount or 0)
        unit_price = round(gross_price / qty, 5) if qty else 0.0

        # HanaUnavailableError bubbles up — caller must NOT mark order failed
        batches = allocate_batches_fefo(hana_cursor, sap_item_code, qty, settings.sap_warehouse_code)

        line = {
            "ItemCode": sap_item_code,
            "Quantity": qty,
            "UnitPrice": unit_price,
            "WarehouseCode": settings.sap_warehouse_code,
            "TaxCode": tax_code,
            **line_udfs,
        }
        if batches:
            line["BatchNumbers"] = batches

        doc_lines.append(line)

    if not doc_lines:
        return None, skipped

    if total_tax > 0:
        doc_lines.append({
            "ItemCode": _TAX_ITEM_CODE,
            "Quantity": 1,
            "UnitPrice": round(total_tax, 2),
            "WarehouseCode": settings.sap_warehouse_code,
            "TaxCode": tax_code,
            "AccountCode": _TAX_GL_ACCOUNT,
            **line_udfs,
        })

    if total_shipping > 0:
        doc_lines.append({
            "ItemCode": _SHIPPING_ITEM_CODE,
            "Quantity": 1,
            "UnitPrice": round(total_shipping, 2),
            "WarehouseCode": settings.sap_warehouse_code,
            "TaxCode": tax_code,
            "AccountCode": _SHIPPING_GL_ACCOUNT,
            **line_udfs,
        })

    payload = {
        "CardCode": settings.sap_card_code,
        "DocDate": doc_date,
        "DocDueDate": doc_date,
        "Series": int(settings.sap_series),
        "NumAtCard": order_doc.amazon_order_id,
        "PayToCode": pay_to_code,
        "DocumentLines": doc_lines,
    }

    return payload, skipped
