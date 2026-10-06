"""
SAP B1 Batch Inventory (Raw / Finished) – OBTN, OBTQ, OITM, OITB, OWHS.

Batch stock with MaterialType (Raw Material / Finished Good from item group),
warehouse, batch number, quantity, UoM, production/expiry dates, and days from production.
FIFO order within each item. Excludes WASTE% items; only items in Raw/Finish groups.
"""

# Main rows: batch inventory with material type and days from production
SAP_B1_BATCH_INVENTORY_ROWS_QUERY = """
    SELECT
        T0."ItemCode" AS item_code,
        T4."ItemName" AS item_name,
        CASE
            WHEN T5."ItmsGrpNam" LIKE '%Raw%' THEN 'Raw Material'
            WHEN T5."ItmsGrpNam" LIKE '%Finish%' THEN 'Finished Good'
        END AS material_type,
        T1."WhsCode" AS whscode,
        T2."WhsName" AS whsname,
        T0."DistNumber" AS batch_number,
        T1."Quantity" AS quantity,
        T4."InvntryUom" AS uom,
        T0."MnfDate" AS production_date,
        T0."ExpDate" AS expiry_date,
        DAYS_BETWEEN(T0."MnfDate", CURRENT_DATE) AS days_from_production
    FROM {schema}."OBTN" T0
    JOIN {schema}."OBTQ" T1
        ON T0."ItemCode" = T1."ItemCode"
        AND T0."SysNumber" = T1."SysNumber"
    JOIN {schema}."OWHS" T2
        ON T1."WhsCode" = T2."WhsCode"
    JOIN {schema}."OITM" T4
        ON T0."ItemCode" = T4."ItemCode"
    JOIN {schema}."OITB" T5
        ON T4."ItmsGrpCod" = T5."ItmsGrpCod"
    WHERE
        T1."Quantity" > 0
        AND (
            T5."ItmsGrpNam" LIKE '%Raw%'
            OR T5."ItmsGrpNam" LIKE '%Finish%'
        )
        AND T0."ItemCode" NOT LIKE 'WASTE%'
        AND {where_clause}
    ORDER BY
        T0."ItemCode",
        T1."WhsCode",
        T0."MnfDate"
    LIMIT ?
"""

# Summary: total batches, total qty, and by material type (for dashboard cards/charts)
SAP_B1_BATCH_INVENTORY_SUMMARY_QUERY = """
    SELECT
        CASE
            WHEN T5."ItmsGrpNam" LIKE '%Raw%' THEN 'Raw Material'
            WHEN T5."ItmsGrpNam" LIKE '%Finish%' THEN 'Finished Good'
        END AS material_type,
        COUNT(DISTINCT T0."ItemCode" || '-' || T1."WhsCode" || '-' || T0."DistNumber") AS batch_count,
        SUM(T1."Quantity") AS total_qty
    FROM {schema}."OBTN" T0
    JOIN {schema}."OBTQ" T1
        ON T0."ItemCode" = T1."ItemCode"
        AND T0."SysNumber" = T1."SysNumber"
    JOIN {schema}."OWHS" T2
        ON T1."WhsCode" = T2."WhsCode"
    JOIN {schema}."OITM" T4
        ON T0."ItemCode" = T4."ItemCode"
    JOIN {schema}."OITB" T5
        ON T4."ItmsGrpCod" = T5."ItmsGrpCod"
    WHERE
        T1."Quantity" > 0
        AND (
            T5."ItmsGrpNam" LIKE '%Raw%'
            OR T5."ItmsGrpNam" LIKE '%Finish%'
        )
        AND T0."ItemCode" NOT LIKE 'WASTE%'
        AND {where_clause}
    GROUP BY
        CASE
            WHEN T5."ItmsGrpNam" LIKE '%Raw%' THEN 'Raw Material'
            WHEN T5."ItmsGrpNam" LIKE '%Finish%' THEN 'Finished Good'
        END
    ORDER BY total_qty DESC
"""
