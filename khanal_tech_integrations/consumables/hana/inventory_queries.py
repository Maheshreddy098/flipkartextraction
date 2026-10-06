import frappe


def get_warehouse_stock_summary(client, warehouse_code: str) -> dict:
    """Total items, batches, qty and expiring-soon count for a warehouse."""
    sql = f"""
SELECT
    COUNT(DISTINCT T0."ItemCode")                                          AS item_count,
    COUNT(*)                                                               AS batch_count,
    COALESCE(SUM(T0."Quantity"), 0)                                        AS total_qty,
    COALESCE(SUM(CASE WHEN T0."ExpDate" <= ADD_DAYS(CURRENT_DATE, 30)
              AND T0."Quantity" > 0 THEN 1 ELSE 0 END), 0)               AS expiring_soon
FROM {client.schema}."OIBT" T0
JOIN {client.schema}."OITM" T4
  ON T0."ItemCode" = T4."ItemCode"
WHERE T0."WhsCode" = ?
  AND T0."Quantity" > 0
  AND T4."validFor" = 'Y'
"""
    rows = client.execute(sql, [warehouse_code])
    if rows:
        return rows[0]
    return {"item_count": 0, "batch_count": 0, "total_qty": 0.0, "expiring_soon": 0}


def get_warehouse_inventory(client, warehouse_code: str, item_group=None, search=None) -> list:
    """Batch-level stock list (OBTN/OBTQ) with FIFO-oriented ordering and optional filters."""
    params = [warehouse_code]
    filters = ['T1."WhsCode" = ?', 'T1."Quantity" > 0']

    # Restrict to item-group codes configured in Consumables Settings.
    settings = frappe.get_single("Consumables Settings")
    configured_codes = []
    for row in (settings.consumable_item_groups or []):
        if getattr(row, "is_active", 1) and getattr(row, "item_group_code", None):
            configured_codes.append(str(row.item_group_code).strip())

    if configured_codes:
        placeholders = ", ".join(["?"] * len(configured_codes))
        filters.append(f'T5."ItmsGrpCod" IN ({placeholders})')
        params.extend(configured_codes)

    if item_group:
        # Use case-insensitive partial match to handle minor naming variations
        # between UI labels and SAP item-group names.
        filters.append('UPPER(T5."ItmsGrpNam") LIKE ?')
        params.append(f'%{str(item_group).strip().upper()}%')

    if search:
        filters.append(
            '(UPPER(T0."ItemCode") LIKE ? OR UPPER(T4."ItemName") LIKE ? OR UPPER(T0."DistNumber") LIKE ?)'
        )
        like_val = f"%{str(search).upper()}%"
        params.extend([like_val, like_val, like_val])

    sql = f"""
SELECT
    T0."ItemCode"       AS item_code,
    T4."ItemName"       AS item_name,
    T5."ItmsGrpNam"     AS item_group,
    T5."ItmsGrpCod"     AS item_group_code,
    T1."WhsCode"        AS warehouse_code,
    T2."WhsName"        AS warehouse_name,
    T2."Location"       AS warehouse_location,
    T0."DistNumber"     AS batch_number,
    T1."Quantity"       AS quantity,
    T4."InvntryUom"     AS uom,
    T0."InDate"         AS production_date,
    T0."ExpDate"        AS expiry_date,
    DAYS_BETWEEN(T0."InDate", CURRENT_DATE) AS days_from_production,
    DAYS_BETWEEN(CURRENT_DATE, T0."ExpDate") AS days_to_expiry,
    CASE
        WHEN T0."ExpDate" < CURRENT_DATE                    THEN 'expired'
        WHEN T0."ExpDate" <= ADD_DAYS(CURRENT_DATE, 30)    THEN 'expiring_soon'
        ELSE 'ok'
    END AS expiry_status
FROM {client.schema}."OBTN" T0
JOIN {client.schema}."OBTQ" T1
  ON T0."ItemCode" = T1."ItemCode"
 AND T0."SysNumber" = T1."SysNumber"
JOIN {client.schema}."OWHS" T2
  ON T1."WhsCode" = T2."WhsCode"
JOIN {client.schema}."OITM" T4
  ON T0."ItemCode" = T4."ItemCode"
JOIN {client.schema}."OITB" T5
  ON T4."ItmsGrpCod" = T5."ItmsGrpCod"
WHERE {" AND ".join(filters)}
  AND T4."validFor" = 'Y'
ORDER BY T1."WhsCode", T4."ItemName", T0."InDate" ASC, T0."SysNumber" ASC, T0."DistNumber" ASC
"""
    return client.execute(sql, params)


def get_item_batch_detail(client, warehouse_code: str, item_code: str) -> list:
    """All batches for a specific item in a warehouse, sorted FIFO/FEFO.
    Matches SAP: if SAP shows quantity for a batch, it's shown here too —
    including expired batches, since SAP itself doesn't block on expiry."""
    sql = f"""
SELECT
    T0."DistNumber"     AS batch_number,
    T0."ItemCode"       AS item_code,
    T4."ItemName"       AS item_name,
    T1."Quantity"       AS quantity,
    T4."InvntryUom"     AS uom,
    T0."InDate"         AS production_date,
    T0."ExpDate"        AS expiry_date
FROM {client.schema}."OBTN" T0
JOIN {client.schema}."OBTQ" T1
  ON T0."ItemCode" = T1."ItemCode"
 AND T0."SysNumber" = T1."SysNumber"
JOIN {client.schema}."OITM" T4
  ON T0."ItemCode" = T4."ItemCode"
WHERE T1."WhsCode" = ?
  AND T0."ItemCode" = ?
  AND T1."Quantity" > 0
  AND T4."validFor" = 'Y'
ORDER BY T0."InDate" ASC, T0."SysNumber" ASC, T0."DistNumber" ASC
"""
    return client.execute(sql, [warehouse_code, item_code])


def get_batch_costs(client, item_codes: list) -> dict:
    """Unit cost of every batch of these items, exactly as SAP's own
    Batch Details window shows it: OBTN."CostTotal" / OBTN."Quantity".

    This is the batch's one standing cost — the single number SAP displays
    for that lot — not a GRN-receipt reconstruction of it. Keyed by
    (item_code, batch_number) because batch numbers repeat across items.

    Batches with no quantity or no cost are simply absent from the result;
    callers fall back to the item-level cost (get_item_current_cost) for
    those, the same fallback they already apply to non-batch items.
    """
    if not item_codes:
        return {}
    placeholders = ", ".join(["?"] * len(item_codes))
    sql = f"""
SELECT
    T0."ItemCode"   AS item_code,
    T0."DistNumber" AS batch_number,
    CASE WHEN T0."Quantity" > 0
         THEN T0."CostTotal" / T0."Quantity"
         ELSE 0
    END             AS batch_cost
FROM {client.schema}."OBTN" T0
WHERE T0."ItemCode" IN ({placeholders})
  AND T0."Quantity" > 0
  AND COALESCE(T0."CostTotal", 0) > 0
"""
    rows = client.execute(sql, list(item_codes))
    return {
        (row["item_code"], row["batch_number"]): round(float(row["batch_cost"]), 6)
        for row in rows
        if row.get("batch_number")
    }


def get_item_valuation_info(client, item_codes: list) -> dict:
    """ManBtchNum from OITM — whether each item is batch-managed.
    Returns {item_code: {"is_batch": bool}}.

    There are no FIFO-valuated items in this SAP company to treat specially —
    every consumable item is costed from its own named batch's standing cost
    (get_batch_costs — the Batch Details figure, OBTN.CostTotal/Quantity),
    so only batch-managed-or-not matters here.
    """
    if not item_codes:
        return {}
    placeholders = ", ".join(["?"] * len(item_codes))
    sql = f"""
SELECT
    "ItemCode"   AS item_code,
    "ManBtchNum" AS man_btch_num
FROM {client.schema}."OITM"
WHERE "ItemCode" IN ({placeholders})
"""
    rows = client.execute(sql, list(item_codes))
    return {
        row["item_code"]: {
            "is_batch": (row.get("man_btch_num") or "").upper() == "Y",
        }
        for row in rows
    }



def get_item_current_cost(client, warehouse_code: str, item_codes: list) -> dict:
    """SAP's own live-computed "Item Cost" per item, at this warehouse — exactly
    what SAP's marketing-document Item Cost column reads, regardless of the
    item's valuation method (FIFO, Moving Average, Standard, or anything else).

    Confirmed directly against real documents: OITM.LastPurPrc and OITW/OITM
    AvgPrice do NOT reliably match SAP's displayed Item Cost (e.g. an item with
    LastPurPrc=115 showed Item Cost=93 in SAP). OINM."CalcPrice" on the item's
    most recent inventory transaction is SAP's own rolling valuation cost after
    that transaction, and matches every case checked exactly — PROVIDED "most
    recent" is found correctly.

    Ordering by DocDate + CreatedBy is NOT safe: two OINM rows for the same
    item/warehouse can share both the same DocDate AND the same CreatedBy
    (e.g. two lines processed within the same document/batch), and HANA's tie
    order for that is undefined — this caused real, reproducible wrong prices
    (picked a stale sibling row instead of the actual latest one). TransNum +
    TransSeq is SAP's own genuinely unique, strictly-increasing transaction
    sequence — confirmed no ties across real data, correct chronological order
    every time.

    Falls back to LastPurPrc only for items with zero transaction history at
    this warehouse (nothing in OINM to read a CalcPrice from yet).
    """
    if not item_codes:
        return {}
    placeholders = ", ".join(["?"] * len(item_codes))
    sql = f"""
SELECT
    M."ItemCode" AS item_code,
    COALESCE(NULLIF(N.calc_price, 0), NULLIF(M."LastPurPrc", 0), 0) AS item_cost
FROM {client.schema}."OITM" M
LEFT JOIN (
    SELECT "ItemCode" AS item_code, "CalcPrice" AS calc_price
    FROM (
        SELECT
            "ItemCode",
            "CalcPrice",
            ROW_NUMBER() OVER (PARTITION BY "ItemCode" ORDER BY "TransNum" DESC, "TransSeq" DESC) AS rn
        FROM {client.schema}."OINM"
        WHERE "ItemCode" IN ({placeholders}) AND "Warehouse" = ?
    ) ranked
    WHERE rn = 1
) N ON N.item_code = M."ItemCode"
WHERE M."ItemCode" IN ({placeholders})
"""
    rows = client.execute(sql, list(item_codes) + [warehouse_code] + list(item_codes))
    return {row["item_code"]: float(row.get("item_cost") or 0) for row in rows}


def get_item_distribution_rules(client, item_codes: list) -> dict:
    """Brand Category / Brand Name / Product Type for each item — SAP's Item
    Master Data > Item Details tab shows these (OITM.U_BC, U_BN, U_PC), and a
    client-side mechanism (no server-side Formatted Search targets these
    fields — confirmed via CSHS) copies them onto a document line's
    distribution-rule dimensions the moment the item is picked. Service Layer
    never applies that automatically, so a line built through this
    integration must set it explicitly or SAP rejects the document.

    Confirmed against real posted PDN1/POR1 history across Consumables, Raw
    Material, Packing Material, and Finished Goods items (not just one item
    type): OcrCode/CostingCode = U_BC, OcrCode2/CostingCode2 = U_BN,
    OcrCode3/CostingCode3 = U_PC ("Product Type").

    U_PSC ("Product Category" — a different, separately labeled item field)
    is NOT this source: its values (e.g. "Consumables") never appear in any
    real posted OcrCode/OcrCode2/OcrCode3 history and aren't even registered
    as valid distribution rule codes in OOCR — confirmed and explicitly
    ruled out.

    Returns {item_code: {"brand_category": ..., "brand_name": ..., "product_type": ...}}.
    """
    if not item_codes:
        return {}
    placeholders = ", ".join(["?"] * len(item_codes))
    sql = f"""
SELECT
    "ItemCode" AS item_code,
    "U_BC"     AS brand_category,
    "U_BN"     AS brand_name,
    "U_PC"     AS product_type
FROM {client.schema}."OITM"
WHERE "ItemCode" IN ({placeholders})
"""
    rows = client.execute(sql, list(item_codes))
    return {
        row["item_code"]: {
            "brand_category": (row.get("brand_category") or "").strip(),
            "brand_name": (row.get("brand_name") or "").strip(),
            "product_type": (row.get("product_type") or "").strip(),
        }
        for row in rows
    }


def get_item_uom_entries(client, item_codes: list) -> dict:
    """The UoMEntry SAP itself would default a document line to, per item.

    This is NOT a text match of the item's display unit against OUOM — that
    coincidentally works only when the display text happens to also be a
    registered OUOM code, and silently fails otherwise (e.g. an item whose
    InvntryUom reads "Pack" but "Pack" was never registered as a real OUOM
    row). The actual mechanism SAP uses is the item's own UoM Group
    (OITM.UgpEntry) resolving to that group's base unit (OUGP.BaseUom) — this
    works uniformly whether the item is in a real group or in "Manual"
    (UgpEntry -1, whose own BaseUom is also -1, confirmed against real data).
    Keyed by item_code.
    """
    if not item_codes:
        return {}
    placeholders = ", ".join(["?"] * len(item_codes))
    sql = f"""
SELECT M."ItemCode" AS item_code, G."BaseUom" AS uom_entry
FROM {client.schema}."OITM" M
LEFT JOIN {client.schema}."OUGP" G ON M."UgpEntry" = G."UgpEntry"
WHERE M."ItemCode" IN ({placeholders})
"""
    rows = client.execute(sql, list(item_codes))
    return {
        row["item_code"]: int(row["uom_entry"])
        for row in rows
        if row.get("uom_entry") is not None
    }


def search_consumable_items(client, search: str, configured_codes: list) -> list:
    """Search OITM directly for active consumable items regardless of stock level.
    Used for CMR item picker so zero-stock items are still requestable."""
    params = []
    extra_filters = []

    if configured_codes:
        placeholders = ", ".join(["?"] * len(configured_codes))
        extra_filters.append(f'T5."ItmsGrpCod" IN ({placeholders})')
        params.extend(configured_codes)

    if search:
        extra_filters.append('(UPPER(T4."ItemCode") LIKE ? OR UPPER(T4."ItemName") LIKE ?)')
        like_val = f"%{str(search).upper()}%"
        params.extend([like_val, like_val])

    extra_where = (" AND " + " AND ".join(extra_filters)) if extra_filters else ""

    sql = f"""
SELECT
    T4."ItemCode"       AS item_code,
    T4."ItemName"       AS item_name,
    T4."InvntryUom"     AS uom,
    T5."ItmsGrpNam"     AS item_group,
    T5."ItmsGrpCod"     AS item_group_code
FROM {client.schema}."OITM" T4
JOIN {client.schema}."OITB" T5
  ON T4."ItmsGrpCod" = T5."ItmsGrpCod"
WHERE T4."validFor" = 'Y'
  {extra_where}
ORDER BY T4."ItemName" ASC
LIMIT 100
"""
    return client.execute(sql, params)
