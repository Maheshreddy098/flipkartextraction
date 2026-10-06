"""
Query templates for HANA DB Reporting System
"""

from .configuration import (
    COMPANY_MAPPING, 
    REVENUE_RECOGNITION_CUSTOMERS, 
    WHITE_LABELLING_CUSTOMERS,
    INTER_TRANSFER_CUSTOMERS,
    CHANNEL_MAPPING,
    BRAND_MAPPING
)

# Comprehensive Sales Analysis Query Template
COMPREHENSIVE_SALES_QUERY = """
/* Comprehensive Sales Analysis Query */
DECLARE DateF DATE;
DECLARE DateT DATE;
DateF := '{start_date}';
DateT := '{end_date}';

SELECT 
    (CASE 
        WHEN a."Customer Code" = 'C03579' THEN 'KFPL-HR'
        WHEN a."Customer Code" = 'C03564' THEN 'KFPL-MH'
        WHEN a."Customer Code" = 'C03596' THEN 'KFPL-TN'
        ELSE 'KFPL-KA'
    END) AS "Company",
    'Yes' AS "RR-KFPL-SFS",
    'No' AS "RR-KIPL-SFS", 
    'Yes' AS "RR-KFPL-CFS",
    (CASE 
        WHEN a."Customer Code" IN ('C03603','C03604','C03327','C01186','C01072','C03497','C03326','C03324','C03447','C03589','C03529','C03595','C03597') 
        THEN 'No'
        ELSE 'Yes' 
    END) AS "Revenue Recognition",
    TO_VARCHAR(a."Document Date",'DD-Mon-YYYY') AS "Document Date",
    TO_VARCHAR(a."Document Date", 'Mon-YY') AS "Month",
    a."Document",
    a."DocNum",
    a."SeriesN",
    a."Document No",
    a."AcctCode" AS "G/L Code",
    a."AcctName" AS "G/L Name",
    a."Document Status",
    a."Customer Code",
    a."Customer Name",
    a."Common Name",
    a."Channel",
    a." GSTN",
    a." State",
    a."State GSTCode",
    a."City",
    a."Address",
    a."Currency",
    a."LineNum",
    a."Currency Rate",
    a."Description",
    a."Actual Description",
    a."SKU Code",
    (CASE 
        WHEN IFNULL(a."Prdct Ctgry",'') = '' THEN a."Actual Prdct"
        ELSE a."Prdct Ctgry"
    END) AS "Product Category",
    (CASE 
        WHEN a."Customer Code" IN ('C03558','C01177','C03516','C03239','C03562','C01765','C03587','C03560','C03491','C02175','C02253') 
        THEN 'White Labelling'
        ELSE 'Own Brand' 
    END) AS "Brand Category",
    (CASE 
        WHEN a."SKU Code" LIKE '%DC%' OR a."SKU Code" LIKE 'FGDV%' THEN 'DOGSEE'
        ELSE 'HN' 
    END) AS "Brand Name",
    a."Geography",
    a."Country",
    a."HSN/SAC",
    a."Quantity",
    a."unitMsr",
    a."MIS Weight",
    a."UOM",
    a."MRP",
    a."Unit Price",
    a."Discount",
    a."Difference",
    a."Diff %",
    a."INR Price",
    a."Taxable Value",
    a."Total_Disc",
    (a."Taxable Value" - a."Total_Disc" + 
     (CASE WHEN IFNULL(a."Invoice FRT Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT Total" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."Invoice FRT2 Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT2 Total" AS DECIMAL(10,2)) END)
    ) AS "Net Taxable Value",
    a."TaxCode",
    a."GST_Rate",
    (CASE WHEN IFNULL(a."CGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."CGST Tax Amount" AS DECIMAL(10,2)) END) AS "CGST Tax Amount",
    (CASE WHEN IFNULL(a."SGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."SGST Tax Amount" AS DECIMAL(10,2)) END) AS "SGST Tax Amount",
    (CASE WHEN IFNULL(a."IGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."IGST Tax Amount" AS DECIMAL(10,2)) END) AS "IGST Tax Amount",
    (CASE WHEN IFNULL(a."Invoice FRT Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT Total" AS DECIMAL(10,2)) END) AS "Freight Charges",
    (CASE WHEN IFNULL(a."Invoice FRT2 Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT2 Total" AS DECIMAL(10,2)) END) AS "Insurance",
    (a."Taxable Value" - a."Total_Disc" + 
     (CASE WHEN IFNULL(a."Invoice FRT Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT Total" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."Invoice FRT2 Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT2 Total" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."CGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."CGST Tax Amount" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."SGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."SGST Tax Amount" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."IGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."IGST Tax Amount" AS DECIMAL(10,2)) END)
    ) AS "Total Value",
    a."COGS per unit",
    a."COGS",
    a."Gross Margin",
    a."Gross Margin %",
    a."Location Name",
    a."Loc_State",
    a."Loc_GSTN",
    a."Comments",
    a."Order Date",
    a."ORD ID",
    a."Buyer Name"
FROM (
    -- Main sales data subquery with UNION ALL for invoices and credit memos
    {sales_data_subquery}
) a
WHERE a."Document Date" BETWEEN DateF AND DateT
ORDER BY a."Document", a."DocNum", a."LineNum"
"""

# Sales Data Subquery (Invoices and Credit Memos)
SALES_DATA_SUBQUERY = """
SELECT  
    SALES."Document Date",
    SALES."AcctCode",
    SALES."AcctName",
    (CASE WHEN SALES."ObjType" = 13 THEN 'SALES INVOICE' ELSE 'CREDIT MEMO' END) AS "Document",
    SALES."SeriesN",
    SALES."DocNum",
    SALES."SeriesN" || '/' || SALES."Document No" AS "Document No",
    SALES."Document Status",
    SALES."Customer Code", 
    SALES."Customer Name", 
    SALES."Common Name",
    SALES." Group",
    CASE 
        WHEN SALES." Group" LIKE '%E-com%' THEN 'E-com'
        WHEN SALES." Group" LIKE '%Domestic HN%' THEN 'Offline HN'
        WHEN SALES." Group" LIKE '%Domestic Dogsee%' THEN 'Offline Dogsee'
        WHEN SALES." Group" LIKE '%Others%' THEN 'Others'
        WHEN SALES." Group" LIKE '%Export%' THEN 'Export'
        WHEN SALES."Customer Code" IN ('C01186','C03326','C03324') THEN 'Inter Transfer'
        ELSE 'Offline Dogsee' 
    END AS "Channel",
    SALES." GSTN",
    SALES." State",
    SALES."State GSTCode",
    SALES."City",
    SALES."Country",
    SALES."MRP",
    SALES."Unit Price",
    SALES."Discount",
    SALES."Difference",
    SALES."Diff %",
    Sales."Actual Prdct",
    Sales."Prdct Ctgry",
    CASE 
        WHEN Sales."Prdct Ctgry" = '' THEN Sales."Actual Prdct"
        ELSE Sales."Actual Prdct" 
    END AS "Product Category",
    (CASE WHEN SALES."Country" = 'India' THEN 'Domestic'
          WHEN SALES."Country" IS NULL THEN ''
          ELSE 'International' 
     END) AS "Geography", 
    SALES."Address",
    SALES."Currency", 
    SALES."LineNum",
    SALES."Currency Rate", 
    SALES."Dscription" AS "Description",
    (CASE WHEN SALES."U_ActualItem" IS NOT NULL THEN SALES."ItemName" ELSE SALES."Dscription" END) AS "Actual Description",
    (CASE WHEN SALES."DocType" = 'S' THEN SALES."Dscription"
          ELSE (CASE WHEN SALES."U_ActualItem" IS NULL THEN SALES."ItemCode" ELSE SALES."U_ActualItem" END)
     END) AS "SKU Code",
    SALES."OcrCode2" AS "Brand",
    SALES."HSN/SAC",
    SALES."Quantity", 
    SALES."unitMsr", 
    (CASE WHEN SALES."U_ActualItem" IS NULL THEN SALES."U_MIS_weight" 
          ELSE (SELECT "U_MIS_weight" FROM OITM WHERE "ItemCode" = SALES."U_ActualItem") 
     END) AS "MIS Weight",
    (CASE WHEN SALES."U_ActualItem" IS NULL THEN SALES."U_UoM_MIS" 
          ELSE (SELECT "U_UoM_MIS" FROM OITM WHERE "ItemCode" = SALES."U_ActualItem") 
     END) AS "UOM",
    SALES."Price", 
    ABS(SALES."Price" * SALES."Currency Rate") AS "INR Price",
    SALES."Taxable Value",
    SALES."Total_Disc",
    SALES."TaxCode",
    SALES."VatPrcnt" AS "GST_Rate",
    SALES."CGST Tax Amount",
    SALES."SGST Tax Amount", 
    SALES."IGST Tax Amount",
    (CASE WHEN SALES."ObjType" = 13 THEN SALES."GTotal" ELSE SALES."GTotal" * -1 END) AS "GTotal",
    SALES."Invoice Total",
    (CASE WHEN SALES."ObjType" = 13 THEN SALES."Invoice FRT Total" ELSE (SALES."Invoice FRT Total" * -1) END) AS "Invoice FRT Total",
    (CASE WHEN SALES."ObjType" = 13 THEN SALES."Invoice FRT2 Total" ELSE (SALES."Invoice FRT2 Total" * -1) END) AS "Invoice FRT2 Total",
    SALES."ItemCost" AS "COGS per unit",
    (SALES."ItemCost" * SALES."Quantity") AS "COGS", 
    (SALES."Taxable Value") - (SALES."ItemCost" * SALES."Quantity") AS "Gross Margin",
    TO_DECIMAL((((SALES."Taxable Value") - ((SALES."ItemCost" * SALES."Quantity")))/NULLIF((SALES."Taxable Value"),0)),10,2) * 100 || '%' AS "Gross Margin %",
    SALES."Location" AS "Location Name", 
    SALES."State" AS "Loc_State", 
    SALES."GSTRegnNo" AS "Loc_GSTN", 
    SALES."Comments",
    SALES."Order Date",
    '''' || SALES."Order ID" AS "ORD ID",
    SALES."Buyer Name",
    SALES."ItemCost"
FROM (
    {invoice_credit_union_query}
) SALES
"""

# Invoice and Credit Memo Union Query
INVOICE_CREDIT_UNION_QUERY = """
-- Invoice Query
SELECT DISTINCT 
    T0."DocType",
    T0."DocNum", 
    T0."ObjType",
    T1."LineNum",
    T0."BPLName" AS "Branch",
    T0."Comments",
    T0."Series",
    T10."SeriesName" AS "SeriesN",
    T10."BeginStr" AS "Prefix",
    T0."DocNum" AS "Document No",
    T1."AcctCode",
    T12."AcctName",
    (CASE
        WHEN (T0.CANCELED = 'Y' AND T0."DocStatus" = 'C') THEN 'Canceled'
        WHEN (T0.CANCELED = 'C' AND T0."DocStatus" = 'C') THEN 'Cancellation'
        WHEN T0."DocStatus" = 'C' THEN 'Close'
        WHEN T0."DocStatus" = 'O' THEN 'Open'
    END) AS "Document Status",
    T0."DocDate" AS "Document Date",
    '' AS "ORG Invoice No",
    '' AS "ORG Invoice Date",
    T0."CardCode" AS "Customer Code",
    T0."CardName" AS "Customer Name",
    T2."CardFName" AS "Common Name",
    T3."GroupName" AS " Group",
    T4."StateS" AS " State",
    T4."BpGSTN" AS " GSTN",
    T4."BPStatGSTN" AS "State GSTCode",
    T4."CityB" AS "City",
    T11."Name" AS "Country",
    T0."Address",
    T0."DocCur" AS "Currency",
    T0."DocRate" AS "Currency Rate",
    xx."U_MRP" AS "MRP",
    T1."Price" AS "Unit Price",
    T1."DiscPrcnt" AS "Discount",
    (xx."U_MRP" - T1."Price") AS "Difference",
    (CASE 
        WHEN xx."U_MRP" IS NULL OR xx."U_MRP" = 0 THEN NULL
        ELSE ROUND(((xx."U_MRP" - T1."Price") / xx."U_MRP") * 100, 2)
    END) AS "Diff %",
    T9."U_MIS_weight",
    T9."U_UoM_MIS",
    T9."U_product_name" AS "Actual Prdct",
    (CASE WHEN T0."DocType" = 'S' THEN 'Others'
          WHEN T1."Dscription" LIKE 'EX%' THEN 'Others'
          ELSE (SELECT zz."U_product_name" FROM OITM zz WHERE zz."ItemCode" = T1."ItemCode")
     END) AS "Prdct Ctgry",
    T1."Dscription",
    T9."ItemName",
    T1."ItemCode",
    T1."U_ActualItem",
    T1."OcrCode2",
    (CASE 
        WHEN (T0."DocType" = 'I' AND T9."ItemClass" = 1) THEN T6."ServCode"
        WHEN T0."DocType" = 'S' THEN T6."ServCode" 
        ELSE T5."ChapterID" 
    END) AS "HSN/SAC",
    (CASE WHEN T0.CANCELED = 'Y' THEN T1."Quantity" * -1 ELSE T1."Quantity" END) AS "Quantity",
    T1."unitMsr", 
    (CASE WHEN T0.CANCELED = 'Y' THEN T1."Price" * -1 ELSE T1."Price" END) AS "Price",
    ((CASE WHEN T0."DocType" = 'I' THEN 
        (CASE WHEN T0.CANCELED = 'Y' THEN (T1."TotalSumSy") * -1 ELSE (T1."TotalSumSy") END) 
        ELSE T1."TotalSumSy" 
    END)) AS "Taxable Value",
    T1."TaxCode",
    T1."VatPrcnt", 
    (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END  
     FROM INV4 t44 WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "CGST Tax Amount",
    (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END  
     FROM INV4 t44 WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "SGST Tax Amount",
    (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END  
     FROM INV4 t44 WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -120 AND T44."LineNum" = T1."LineNum") AS "IGST Tax Amount",
    (CASE WHEN T1."LineNum" = (SELECT MIN("LineNum") FROM INV1 WHERE "DocEntry" = T0."DocEntry") THEN 
        (CASE WHEN T0.CANCELED = 'Y' THEN (T0."DocTotal" * -1) ELSE T0."DocTotal" END)
        ELSE NULL 
    END) AS "Invoice Total",
    T1."GTotal",
    (T0."DiscSum" * ((CASE WHEN T0."DocType" = 'I' THEN 
        (CASE WHEN T0.CANCELED = 'Y' THEN (T1."Quantity" * (T1."Price" * T0."DocRate")) * -1
              ELSE (T1."Quantity" * (T1."Price" * T0."DocRate")) END)
        ELSE T1."Price" END)) / 
    (CASE WHEN (SELECT SUM(B."LineTotal") FROM OINV A INNER JOIN INV1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") = 0
          THEN NULL 
          ELSE (SELECT SUM(B."LineTotal") FROM OINV A INNER JOIN INV1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") 
     END)) AS "Total_Disc",
    (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
     FROM INV1 B INNER JOIN INV3 A ON A."DocEntry" = B."DocEntry" 
     WHERE A."ExpnsCode" = 1 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT Total",
    (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
     FROM INV1 B INNER JOIN INV3 A ON A."DocEntry" = B."DocEntry" 
     WHERE A."ExpnsCode" = 2 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT2 Total",
    T1."Project",
    T7."Location", 
    T7."State", 
    T7."GSTRegnNo", 
    T1."StockPrice" AS "ItemCost",
    (T1."U_Order") AS "Order ID",
    T1."U_OrderedOn" AS "Order Date",
    T1."U_BuyerName" AS "Buyer Name"
FROM OINV T0  
INNER JOIN INV1 T1 ON T0."DocEntry" = T1."DocEntry" 
INNER JOIN OACT T12 ON T12."AcctCode" = T1."AcctCode"
LEFT OUTER JOIN OITM xx ON T1."ItemCode" = xx."ItemCode" 
LEFT OUTER JOIN OITM T9 ON T1."U_ActualItem" = T9."ItemCode" 
INNER JOIN OLCT T7 ON T7."Code" = T1."LocCode"
INNER JOIN OCRD T2 ON T0."CardCode" = T2."CardCode" 
INNER JOIN OCRG T3 ON T2."GroupCode" = T3."GroupCode" 
INNER JOIN INV12 T4 ON T0."DocEntry" = T4."DocEntry" 
LEFT JOIN OCHP T5 ON T1."HsnEntry" = T5."AbsEntry"
LEFT JOIN OSAC T6 ON T1."SacEntry" = T6."AbsEntry"
INNER JOIN OSTC T8 ON T1."TaxCode" = T8."Code"
LEFT JOIN NNM1 T10 ON T0."Series" = T10."Series"
LEFT JOIN OCRY T11 ON T4."CountryB" = T11."Code"
WHERE T0.CANCELED NOT IN ('Y', 'C')

UNION ALL

-- Credit Memo Query
SELECT DISTINCT 
    T0."DocType",
    T0."DocNum", 
    T0."ObjType",
    T1."LineNum",
    T0."BPLName" AS "Branch",
    T0."Comments",
    T0."Series",
    T10."SeriesName" AS "SeriesN",
    T10."BeginStr" AS "Prefix",
    T0."DocNum" AS "Document No",
    T1."AcctCode",
    T12."AcctName",
    (CASE
        WHEN (T0.CANCELED = 'Y' AND T0."DocStatus" = 'C') THEN 'Canceled'
        WHEN (T0.CANCELED = 'C' AND T0."DocStatus" = 'C') THEN 'Cancellation'
        WHEN T0."DocStatus" = 'C' THEN 'Close'
        WHEN T0."DocStatus" = 'O' THEN 'Open'
    END) AS "Document Status",
    T0."DocDate" AS "Document Date",
    T0."RevRefNo" AS "ORG Invoice No",
    T0."RevRefDate" AS "ORG Invoice Date",
    T0."CardCode" AS "Customer Code",
    T0."CardName" AS "Customer Name",
    T2."CardFName" AS "Common Name",
    T3."GroupName" AS " Group",
    T4."StateS" AS " State",
    T4."BpGSTN" AS " GSTN",
    T4."BPStatGSTN" AS "State GSTCode",
    T4."CityB" AS "CITY",
    T11."Name" AS "COUNTRY",
    T0."Address",
    T0."DocCur" AS "Currency",
    T0."DocRate" AS "Currency Rate",
    xx."U_MRP" AS "MRP",
    T1."Price" AS "Unit Price",
    T1."DiscPrcnt" AS "Discount",
    (xx."U_MRP" - T1."Price") AS "Difference",
    (CASE 
        WHEN xx."U_MRP" IS NULL OR xx."U_MRP" = 0 THEN NULL
        ELSE ROUND(((xx."U_MRP" - T1."Price") / xx."U_MRP") * 100, 2)
    END) AS "Diff %",
    T9."U_MIS_weight",
    T9."U_UoM_MIS",
    T9."U_product_name" AS "Actual Prdct",
    (SELECT zz."U_product_name" FROM OITM zz WHERE zz."ItemCode" = T1."ItemCode") AS "Prdct Ctgry",
    T1."Dscription",
    T9."ItemName",
    T1."ItemCode",
    T1."U_ActualItem",
    T1."OcrCode2",
    (CASE 
        WHEN (T0."DocType" = 'I' AND T9."ItemClass" = 1) THEN T6."ServCode"
        WHEN T0."DocType" = 'S' THEN T6."ServCode" 
        ELSE T5."ChapterID" 
    END) AS "HSN/SAC",
    (CASE WHEN T0.CANCELED = 'Y' THEN T1."Quantity" ELSE T1."Quantity" * -1 END) AS "Quantity",
    T1."unitMsr", 
    (CASE WHEN T0.CANCELED = 'Y' THEN T1."Price" ELSE T1."Price" * -1 END) AS "Price", 
    (CASE WHEN T0."DocType" = 'I' THEN 
        (CASE WHEN T0.CANCELED = 'Y' THEN (T1."TotalSumSy") ELSE (T1."TotalSumSy" * -1) END)
        ELSE T1."TotalSumSy" 
    END) AS "Taxable Value",
    T1."TaxCode",
    T1."VatPrcnt",
    (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END  
     FROM RIN4 t44 WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "CGST Tax Amount",
    (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END  
     FROM RIN4 t44 WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "SGST Tax Amount",
    (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END  
     FROM RIN4 t44 WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -120 AND T44."LineNum" = T1."LineNum") AS "IGST Tax Amount",
    (CASE WHEN T1."LineNum" = (SELECT MIN("LineNum") FROM RIN1 WHERE "DocEntry" = T0."DocEntry") THEN 
        (CASE WHEN T0.CANCELED = 'Y' THEN (T0."DocTotal") ELSE T0."DocTotal" * -1 END)
        ELSE NULL 
    END) AS "Invoice Total",
    T1."GTotal",
    (T0."DiscSum" * ((CASE WHEN T0."DocType" = 'I' THEN 
        (CASE WHEN T0.CANCELED = 'Y' THEN (T1."Quantity" * (T1."Price" * T0."DocRate")) * -1
              ELSE (T1."Quantity" * (T1."Price" * T0."DocRate")) END)
        ELSE T1."Price" END)) / 
    (CASE WHEN (SELECT SUM(B."LineTotal") FROM ORIN A INNER JOIN RIN1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") = 0
          THEN NULL 
          ELSE (SELECT SUM(B."LineTotal") FROM ORIN A INNER JOIN RIN1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") 
     END)) AS "Total_Disc",
    (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
     FROM RIN1 B INNER JOIN RIN3 A ON A."DocEntry" = B."DocEntry" 
     WHERE A."ExpnsCode" = 1 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT Total",
    (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
     FROM RIN1 B INNER JOIN RIN3 A ON A."DocEntry" = B."DocEntry" 
     WHERE A."ExpnsCode" = 2 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT2 Total",
    T1."Project",
    T7."Location", 
    T7."State", 
    T7."GSTRegnNo",
    T1."StockPrice" AS "ItemCost",
    (T1."U_Order") AS "Order ID",
    T1."U_OrderedOn" AS "Order Date",
    T1."U_BuyerName" AS "Buyer Name"
FROM ORIN T0  
INNER JOIN RIN1 T1 ON T0."DocEntry" = T1."DocEntry" 
INNER JOIN OACT T12 ON T12."AcctCode" = T1."AcctCode"
LEFT OUTER JOIN OITM xx ON T1."ItemCode" = xx."ItemCode" 
LEFT OUTER JOIN OITM T9 ON T1."U_ActualItem" = T9."ItemCode" 
INNER JOIN OLCT T7 ON T7."Code" = T1."LocCode"
INNER JOIN OCRD T2 ON T0."CardCode" = T2."CardCode" 
INNER JOIN OCRG T3 ON T2."GroupCode" = T3."GroupCode" 
INNER JOIN RIN12 T4 ON T0."DocEntry" = T4."DocEntry" 
LEFT JOIN OCHP T5 ON T1."HsnEntry" = T5."AbsEntry"
LEFT JOIN OSAC T6 ON T1."SacEntry" = T6."AbsEntry"
INNER JOIN OSTC T8 ON T1."TaxCode" = T8."Code"
LEFT JOIN NNM1 T10 ON T0."Series" = T10."Series"
LEFT JOIN OCRY T11 ON T11."Code" = T4."CountryB"
WHERE T0.CANCELED NOT IN ('Y', 'C')
"""

# Additional Query Templates
QUERY_TEMPLATES = {
    "comprehensive_sales": COMPREHENSIVE_SALES_QUERY,
    "sales_summary": """
        SELECT 
            T0.DocDate,
            T0.CardCode,
            T0.CardName,
            SUM(T1.LineTotal) as TotalSales,
            COUNT(T0.DocEntry) as OrderCount
        FROM OINV T0
        INNER JOIN INV1 T1 ON T0.DocEntry = T1.DocEntry
        WHERE T0.DocDate BETWEEN '{start_date}' AND '{end_date}'
        AND T0.CANCELED NOT IN ('Y', 'C')
        GROUP BY T0.DocDate, T0.CardCode, T0.CardName
        ORDER BY T0.DocDate DESC
    """,
    
    "inventory_analysis": """
        SELECT 
            T0.ItemCode,
            T0.ItemName,
            T0.OnHand,
            T0.IsCommited,
            T0.OnOrder,
            T0.WhsCode
        FROM OITW T0
        INNER JOIN OITM T1 ON T0.ItemCode = T1.ItemCode
        WHERE T0.WhsCode IN ('AMZ-BOM5', 'AMZ-BLR5', 'AMZ-DEL4')
        ORDER BY T0.OnHand DESC
    """,
    
    "batch_analysis": """
        SELECT 
            T0.ItemCode,
            T0.DistNumber,
            T0.Quantity,
            T0.Location,
            T0.MfrDate,
            T0.ExpDate
        FROM OBTN T0
        WHERE T0.Location IN ('AMZ-BOM5', 'AMZ-BLR5', 'AMZ-DEL4')
        AND T0.Quantity > 0
        ORDER BY T0.ItemCode, T0.ExpDate
    """,
    
    "customer_analysis": """
        SELECT 
            T0.CardCode,
            T0.CardName,
            T1.GroupName,
            COUNT(T2.DocEntry) as TotalOrders,
            SUM(T2.DocTotal) as TotalSales
        FROM OCRD T0
        LEFT JOIN OCRG T1 ON T0.GroupCode = T1.GroupCode
        LEFT JOIN OINV T2 ON T0.CardCode = T2.CardCode
        WHERE T2.DocDate BETWEEN '{start_date}' AND '{end_date}'
        AND T2.CANCELED NOT IN ('Y', 'C')
        GROUP BY T0.CardCode, T0.CardName, T1.GroupName
        ORDER BY TotalSales DESC
    """
}

def _apply_schema_to_query(query: str, schema: str = None) -> str:
    """
    Replace hardcoded schema references with runtime schema.
    """
    normalized_schema = (schema or "").strip().strip('"')
    if not normalized_schema:
        return query
    return query.replace("KFL_LIVE.", f"{normalized_schema}.")


def get_comprehensive_sales_query(start_date: str, end_date: str, schema: str = None) -> str:
    """
    Get the comprehensive sales query with date parameters
    """
    # Replace the sales data subquery placeholder
    sales_data_subquery = SALES_DATA_SUBQUERY.format(
        invoice_credit_union_query=INVOICE_CREDIT_UNION_QUERY
    )
    
    query = COMPREHENSIVE_SALES_QUERY.format(
        start_date=start_date,
        end_date=end_date,
        sales_data_subquery=sales_data_subquery
    )
    return _apply_schema_to_query(query, schema)

def get_query_template(template_name: str, **kwargs) -> str:
    """
    Get a query template with parameters replaced
    """
    if template_name not in QUERY_TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found")
    
    query = QUERY_TEMPLATES[template_name].format(**kwargs)
    return _apply_schema_to_query(query, kwargs.get("schema"))

# Updated comprehensive query with detailed calculations and additional White Labelling customers


COMPREHENSIVE_SALES_QUERY_SIMPLIFIED = """
SELECT 
    (CASE 
        WHEN a."Customer Code" = 'C03579' THEN 'KFPL-HR'
        WHEN a."Customer Code" = 'C03564' THEN 'KFPL-MH'
        WHEN a."Customer Code" = 'C03596' THEN 'KFPL-TN'
        ELSE 'KFPL-KA'
    END) AS "Company",
    'Yes' AS "RR-KFPL-SFS",
    'No' AS "RR-KIPL-SFS",
    'Yes' AS "RR-KFPL-CFS",
    (CASE 
        WHEN a."Customer Code" IN ('C03603','C03604','C03327','C01186','C01072','C03497','C03326','C03324','C03447','C03589','C03529','C03595','C03597') 
        THEN 'No'
        ELSE 'Yes' 
    END) AS "Revenue Recognition",
    TO_VARCHAR(a."Document Date",'DD-Mon-YYYY') AS "Document Date",
    TO_VARCHAR(a."Document Date", 'Mon-YY') AS "Month",
    a."Document",
    a."DocNum",
    a."SeriesN",
    a."Document No",
    a."AcctCode" AS "G/L Code",
    a."AcctName" AS "G/L Name",
    a."Document Status",
    a."Customer Code",
    a."Customer Name",
    a."Common Name",
    a."Channel",
    a." GSTN",
    a." State",
    a."State GSTCode",
    a."City",
    a."Address",
    a."Currency",
    a."LineNum",
    a."Currency Rate",
    a."Description",
    a."Actual Description",
    a."SKU Code",
    (CASE 
        WHEN IFNULL(a."Prdct Ctgry", '') = '' THEN a."Actual Prdct"
        ELSE a."Prdct Ctgry"
    END) AS "Product Category",
    (CASE 
        WHEN a."Customer Code" IN ('C00231','C03500','C00394','C00629','C00778','C00878','C01049','C03384','C03507','C03558','C01177','C03516','C03239','C03562','C01765','C03587','C03560','C03491','C02175','C02253','C03554','C02567','C03573','C03458','C02776','C03547','C03034','C03496') 
        THEN 'White Labelling'
        ELSE 'Own Brand' 
    END) AS "Brand Category",
    (CASE 
        WHEN a."SKU Code" LIKE '%DC%' OR a."SKU Code" LIKE 'FGDV%' THEN 'DOGSEE'
        ELSE 'HN' 
    END) AS "Brand Name",
    a."Geography",
    a."Country",
    a."HSN/SAC",
    a."Quantity",
    a."unitMsr",
    a."MIS Weight",
    a."UOM",
    a."MRP",
    a."Unit Price",
    a."Discount",
    a."Difference",
    a."Diff %",
    a."INR Price",
    a."Taxable Value",
    a."Total_Disc",
    (a."Taxable Value" - a."Total_Disc" + 
     (CASE WHEN IFNULL(a."Invoice FRT Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT Total" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."Invoice FRT2 Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT2 Total" AS DECIMAL(10,2)) END)) AS "Net Taxable Value",
    a."TaxCode",
    a."GST_Rate",
    (CASE WHEN IFNULL(a."CGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."CGST Tax Amount" AS DECIMAL(10,2)) END) AS "CGST Tax Amount",
    (CASE WHEN IFNULL(a."SGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."SGST Tax Amount" AS DECIMAL(10,2)) END) AS "SGST Tax Amount",
    (CASE WHEN IFNULL(a."IGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."IGST Tax Amount" AS DECIMAL(10,2)) END) AS "IGST Tax Amount",
    (CASE WHEN IFNULL(a."Invoice FRT Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT Total" AS DECIMAL(10,2)) END) AS "Freight Charges",
    (CASE WHEN IFNULL(a."Invoice FRT2 Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT2 Total" AS DECIMAL(10,2)) END) AS "Insurance",
    (a."Taxable Value" - a."Total_Disc" + 
     (CASE WHEN IFNULL(a."Invoice FRT Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT Total" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."Invoice FRT2 Total", 0) = 0 THEN 0 ELSE CAST(a."Invoice FRT2 Total" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."CGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."CGST Tax Amount" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."SGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."SGST Tax Amount" AS DECIMAL(10,2)) END) +
     (CASE WHEN IFNULL(a."IGST Tax Amount", 0) = 0 THEN 0 ELSE CAST(a."IGST Tax Amount" AS DECIMAL(10,2)) END)) AS "Total Value",
    a."COGS per unit",
    a."COGS",
    a."Gross Margin",
    a."Gross Margin %",
    a."Location Name",
    a."Loc_State",
    a."Loc_GSTN",
    a."Comments",
    a."Order Date",
    a."ORD ID",
    a."Buyer Name"
FROM (
    SELECT  
        SALES."Document Date",
        SALES."AcctCode",
        SALES."AcctName",
        (CASE WHEN SALES."ObjType" = 13 THEN 'SALES INVOICE' ELSE 'CREDIT MEMO' END) AS "Document",
        SALES."SeriesN",
        SALES."DocNum",
        SALES."SeriesN" || '/' || SALES."Document No" AS "Document No",
        SALES."Document Status",
        SALES."Customer Code", 
        SALES."Customer Name", 
        SALES."Common Name",
        SALES." Group",
        CASE 
            WHEN SALES." Group" LIKE '%E-com%' THEN 'E-com'
            WHEN SALES." Group" LIKE '%Domestic HN%' THEN 'Offline HN'
            WHEN SALES." Group" LIKE '%Domestic Dogsee%' THEN 'Offline Dogsee'
            WHEN SALES." Group" LIKE '%Others%' THEN 'Others'
            WHEN SALES." Group" LIKE '%Export%' THEN 'Export'
            WHEN SALES."Customer Code" IN ('C01186','C03326','C03324') THEN 'Inter Transfer'
            ELSE 'Offline Dogsee' 
        END AS "Channel",
        SALES." GSTN",
        SALES." State",
        SALES."State GSTCode",
        SALES."City",
        SALES."Country",
        SALES."MRP",
        SALES."Unit Price",
        SALES."Discount",
        SALES."Difference",
        SALES."Diff %",
        Sales."Actual Prdct",
        Sales."Prdct Ctgry",
        CASE 
            WHEN Sales."Prdct Ctgry" = '' THEN Sales."Actual Prdct"
            ELSE Sales."Actual Prdct" 
        END AS "Product Category",
        (CASE 
            WHEN SALES."Country" = 'India' THEN 'Domestic'
            WHEN SALES."Country" IS NULL THEN ''
            ELSE 'International' 
        END) AS "Geography", 
        SALES."Address",
        SALES."Currency", 
        SALES."LineNum",
        SALES."Currency Rate", 
        SALES."Dscription" AS "Description",
        (CASE WHEN SALES."U_ActualItem" IS NOT NULL THEN SALES."ItemName" ELSE SALES."Dscription" END) AS "Actual Description",
        (CASE 
            WHEN SALES."DocType" = 'S' THEN SALES."Dscription"
            ELSE (CASE WHEN SALES."U_ActualItem" IS NULL THEN SALES."ItemCode" ELSE SALES."U_ActualItem" END)
        END) AS "SKU Code",
        SALES."OcrCode2" AS "Brand",
        SALES."HSN/SAC",
        SALES."Quantity", 
        SALES."unitMsr", 
        (CASE 
            WHEN SALES."U_ActualItem" IS NULL THEN SALES."U_MIS_weight" 
            ELSE (SELECT "U_MIS_weight" FROM KFL_LIVE.OITM WHERE "ItemCode" = SALES."U_ActualItem") 
        END) AS "MIS Weight",
        (CASE 
            WHEN SALES."U_ActualItem" IS NULL THEN SALES."U_UoM_MIS" 
            ELSE (SELECT "U_UoM_MIS" FROM KFL_LIVE.OITM WHERE "ItemCode" = SALES."U_ActualItem") 
        END) AS "UOM",
        SALES."Price", 
        ABS(SALES."Price" * SALES."Currency Rate") AS "INR Price",
        SALES."Taxable Value",
        SALES."Total_Disc",
        SALES."TaxCode",
        SALES."VatPrcnt" AS "GST_Rate",
        SALES."CGST Tax Amount",
        SALES."SGST Tax Amount", 
        SALES."IGST Tax Amount",
        (CASE WHEN SALES."ObjType" = 13 THEN SALES."GTotal" ELSE SALES."GTotal" * -1 END) AS "GTotal",
        SALES."Invoice Total",
        (CASE WHEN SALES."ObjType" = 13 THEN SALES."Invoice FRT Total" ELSE (SALES."Invoice FRT Total" * -1) END) AS "Invoice FRT Total",
        (CASE WHEN SALES."ObjType" = 13 THEN SALES."Invoice FRT2 Total" ELSE (SALES."Invoice FRT2 Total" * -1) END) AS "Invoice FRT2 Total",
        SALES."ItemCost" AS "COGS per unit",
        (SALES."ItemCost" * SALES."Quantity") AS "COGS", 
        (SALES."Taxable Value") - (SALES."ItemCost" * SALES."Quantity") AS "Gross Margin",
        TO_DECIMAL((((SALES."Taxable Value") - ((SALES."ItemCost" * SALES."Quantity"))) / NULLIF((SALES."Taxable Value"), 0)), 10, 2) * 100 || '%' AS "Gross Margin %",
        SALES."Location" AS "Location Name", 
        SALES."State" AS "Loc_State", 
        SALES."GSTRegnNo" AS "Loc_GSTN", 
        SALES."Comments",
        SALES."Order Date",
        '''' || SALES."Order ID" AS "ORD ID",
        SALES."Buyer Name",
        SALES."ItemCost"
    FROM (
        -- First UNION ALL (Sales Invoices)
        SELECT DISTINCT 
            T0."DocType",
            T0."DocNum", 
            T0."ObjType", 
            T1."LineNum",
            T0."BPLName" AS "Branch",
            T0."Comments",
            T0."Series",
            T10."SeriesName" AS "SeriesN",
            T10."BeginStr" AS "Prefix",
            T0."DocNum" AS "Document No",
            T1."AcctCode",
            T12."AcctName",
            (CASE
                WHEN (T0.CANCELED = 'Y' AND T0."DocStatus" = 'C') THEN 'Canceled'
                WHEN (T0.CANCELED = 'C' AND T0."DocStatus" = 'C') THEN 'Cancellation'
                WHEN T0."DocStatus" = 'C' THEN 'Close'
                WHEN T0."DocStatus" = 'O' THEN 'Open'
            END) AS "Document Status",
            T0."DocDate" AS "Document Date",
            '' AS "ORG Invoice No",
            '' AS "ORG Invoice Date",
            T0."CardCode" AS "Customer Code",
            T0."CardName" AS "Customer Name",
            T2."CardFName" AS "Common Name",
            T3."GroupName" AS " Group",
            T4."StateS" AS " State",
            T4."BpGSTN" AS " GSTN",
            T4."BPStatGSTN" AS "State GSTCode",
            T4."CityB" AS "City",
            T11."Name" AS "Country",
            T0."Address",
            T0."DocCur" AS "Currency",
            T0."DocRate" AS "Currency Rate",
            xx."U_MRP" AS "MRP",
            T1."Price" AS "Unit Price",
            T1."DiscPrcnt" AS "Discount",
            (xx."U_MRP" - T1."Price") AS "Difference",
            (CASE 
                WHEN xx."U_MRP" IS NULL OR xx."U_MRP" = 0 THEN NULL
                ELSE ROUND(((xx."U_MRP" - T1."Price") / xx."U_MRP") * 100, 2)
            END) AS "Diff %",
            T9."U_MIS_weight",
            T9."U_UoM_MIS",
            T9."U_product_name" AS "Actual Prdct",
            (CASE 
                WHEN T0."DocType" = 'S' THEN 'Others'
                WHEN T1."Dscription" LIKE 'EX%' THEN 'Others'
                ELSE (SELECT zz."U_product_name" FROM KFL_LIVE.OITM zz WHERE zz."ItemCode" = T1."ItemCode")
            END) AS "Prdct Ctgry",
            (CASE 
                WHEN T1."LineNum" = (SELECT MIN("LineNum") FROM KFL_LIVE.INV1 WHERE "DocEntry" = T0."DocEntry") THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T0."DocTotalFC" * -1) ELSE T0."DocTotalFC" END)
                ELSE NULL 
            END) AS "Invoice Total FC", 
            T1."Dscription",
            T9."ItemName",
            T1."ItemCode",
            T1."U_ActualItem",
            T1."OcrCode2",
            (CASE 
                WHEN (T0."DocType" = 'I' AND T9."ItemClass" = 1) THEN T6."ServCode"
                WHEN T0."DocType" = 'S' THEN T6."ServCode" 
                ELSE T5."ChapterID" 
            END) AS "HSN/SAC",
            (CASE WHEN T0.CANCELED = 'Y' THEN T1."Quantity" * -1 ELSE T1."Quantity" END) AS "Quantity",
            T1."unitMsr", 
            (CASE WHEN T0.CANCELED = 'Y' THEN T1."Price" * -1 ELSE T1."Price" END) AS "Price",
            ((CASE 
                WHEN T0."DocType" = 'I' THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T1."TotalSumSy") * -1 ELSE (T1."TotalSumSy") END) 
                ELSE T1."TotalSumSy" 
            END)) AS "Taxable Value",
            T1."TaxCode",
            T1."VatPrcnt", 
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END  
             FROM KFL_LIVE.INV4 t44 
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "CGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END  
             FROM KFL_LIVE.INV4 t44 
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "SGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END  
             FROM KFL_LIVE.INV4 t44 
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -120 AND T44."LineNum" = T1."LineNum") AS "IGST Tax Amount",
            (CASE 
                WHEN T1."LineNum" = (SELECT MIN("LineNum") FROM KFL_LIVE.INV1 WHERE "DocEntry" = T0."DocEntry") THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T0."DocTotal" * -1) ELSE T0."DocTotal" END)
                ELSE NULL 
            END) AS "Invoice Total",
            T1."GTotal",
            (T0."DiscSum" * ((CASE 
                WHEN T0."DocType" = 'I' THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T1."Quantity" * (T1."Price" * T0."DocRate")) * -1
                          ELSE (T1."Quantity" * (T1."Price" * T0."DocRate")) END)
                ELSE T1."Price" 
            END)) / (CASE 
                WHEN (SELECT SUM(B."LineTotal") FROM KFL_LIVE.OINV A INNER JOIN KFL_LIVE.INV1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") = 0
                THEN NULL 
                ELSE (SELECT SUM(B."LineTotal") FROM KFL_LIVE.OINV A INNER JOIN KFL_LIVE.INV1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") 
            END)) AS "Total_Disc",
            (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
             FROM KFL_LIVE.INV1 B INNER JOIN KFL_LIVE.INV3 A ON A."DocEntry" = B."DocEntry" 
             WHERE A."ExpnsCode" = 1 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT Total",
            (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
             FROM KFL_LIVE.INV1 B INNER JOIN KFL_LIVE.INV3 A ON A."DocEntry" = B."DocEntry" 
             WHERE A."ExpnsCode" = 2 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT2 Total",  
            T1."Project",
            T7."Location", 
            T7."State", 
            T7."GSTRegnNo", 
            T1."StockPrice" AS "ItemCost",
            (T1."U_Order") AS "Order ID",
            T1."U_OrderedOn" AS "Order Date",
            T1."U_BuyerName" AS "Buyer Name"
        FROM KFL_LIVE.OINV T0  
        INNER JOIN KFL_LIVE.INV1 T1 ON T0."DocEntry" = T1."DocEntry" 
        INNER JOIN KFL_LIVE.OACT T12 ON T12."AcctCode" = T1."AcctCode"
        LEFT OUTER JOIN KFL_LIVE.OITM xx ON T1."ItemCode" = xx."ItemCode" 
        LEFT OUTER JOIN KFL_LIVE.OITM T9 ON T1."U_ActualItem" = T9."ItemCode" 
        INNER JOIN KFL_LIVE.OLCT T7 ON T7."Code" = T1."LocCode"
        INNER JOIN KFL_LIVE.OCRD T2 ON T0."CardCode" = T2."CardCode" 
        INNER JOIN KFL_LIVE.OCRG T3 ON T2."GroupCode" = T3."GroupCode" 
        INNER JOIN KFL_LIVE.INV12 T4 ON T0."DocEntry" = T4."DocEntry" 
        LEFT JOIN KFL_LIVE.OCHP T5 ON T1."HsnEntry" = T5."AbsEntry"
        LEFT JOIN KFL_LIVE.OSAC T6 ON T1."SacEntry" = T6."AbsEntry"
        INNER JOIN KFL_LIVE.OSTC T8 ON T1."TaxCode" = T8."Code"
        LEFT JOIN KFL_LIVE.NNM1 T10 ON T0."Series" = T10."Series"
        LEFT JOIN KFL_LIVE.OCRY T11 ON T4."CountryB" = T11."Code"
        WHERE T0.CANCELED NOT IN ('Y', 'C')
        
        UNION ALL 
        
        -- Second UNION ALL (Credit Memos)
        SELECT DISTINCT 
            T0."DocType",
            T0."DocNum", 
            T0."ObjType", 
            T1."LineNum",
            T0."BPLName" AS "Branch",  
            T0."Comments",
            T0."Series",
            T10."SeriesName" AS "SeriesN",
            T10."BeginStr" AS "Prefix",
            T0."DocNum" AS "Document No",
            T1."AcctCode",
            T12."AcctName",
            (CASE
                WHEN (T0.CANCELED = 'Y' AND T0."DocStatus" = 'C') THEN 'Canceled'
                WHEN (T0.CANCELED = 'C' AND T0."DocStatus" = 'C') THEN 'Cancellation'
                WHEN T0."DocStatus" = 'C' THEN 'Close'
                WHEN T0."DocStatus" = 'O' THEN 'Open'
            END) AS "Document Status",
            T0."DocDate" AS "Document Date",
            T0."RevRefNo" AS "ORG Invoice No",
            T0."RevRefDate" AS "ORG Invoice Date",
            T0."CardCode" AS "Customer Code",
            T0."CardName" AS "Customer Name",
            T2."CardFName" AS "Common Name",
            T3."GroupName" AS " Group",
            T4."StateS" AS " State",
            T4."BpGSTN" AS " GSTN",
            T4."BPStatGSTN" AS "State GSTCode",
            T4."CityB" AS "City",
            T11."Name" AS "Country",
            T0."Address",
            T0."DocCur" AS "Currency",
            T0."DocRate" AS "Currency Rate",
            xx."U_MRP" AS "MRP",
            T1."Price" AS "Unit Price",
            T1."DiscPrcnt" AS "Discount",
            (xx."U_MRP" - T1."Price") AS "Difference",
            (CASE 
                WHEN xx."U_MRP" IS NULL OR xx."U_MRP" = 0 THEN NULL
                ELSE ROUND(((xx."U_MRP" - T1."Price") / xx."U_MRP") * 100, 2)
            END) AS "Diff %",
            T9."U_MIS_weight",
            T9."U_UoM_MIS",
            T9."U_product_name" AS "Actual Prdct",
            (SELECT zz."U_product_name" FROM KFL_LIVE.OITM zz WHERE zz."ItemCode" = T1."ItemCode") AS "Prdct Ctgry",
            (CASE 
                WHEN T1."LineNum" = (SELECT MIN("LineNum") FROM KFL_LIVE.RIN1 WHERE "DocEntry" = T0."DocEntry") THEN T0."DocTotalFC" * -1 
                ELSE NULL 
            END) AS "Invoice Total FC", 
            T1."Dscription",
            T9."ItemName",
            T1."ItemCode",
            T1."U_ActualItem",
            T1."OcrCode2",
            (CASE 
                WHEN (T0."DocType" = 'I' AND T9."ItemClass" = 1) THEN T6."ServCode"
                WHEN T0."DocType" = 'S' THEN T6."ServCode" 
                ELSE T5."ChapterID" 
            END) AS "HSN/SAC",
            (CASE WHEN T0.CANCELED = 'Y' THEN T1."Quantity" ELSE T1."Quantity" * -1 END) AS "Quantity",
            T1."unitMsr", 
            (CASE WHEN T0.CANCELED = 'Y' THEN T1."Price" ELSE T1."Price" * -1 END) AS "Price", 
            (CASE 
                WHEN T0."DocType" = 'I' THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T1."TotalSumSy") ELSE (T1."TotalSumSy" * -1) END) 
                ELSE T1."TotalSumSy" 
            END) AS "Taxable Value",
            T1."TaxCode",
            T1."VatPrcnt",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END  
             FROM KFL_LIVE.RIN4 t44 
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND t44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "CGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END  
             FROM KFL_LIVE.RIN4 t44 
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND t44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "SGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END  
             FROM KFL_LIVE.RIN4 t44 
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND t44."staType" = -120 AND T44."LineNum" = T1."LineNum") AS "IGST Tax Amount",
            (CASE 
                WHEN T1."LineNum" = (SELECT MIN("LineNum") FROM KFL_LIVE.RIN1 WHERE "DocEntry" = T0."DocEntry") THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T0."DocTotal") ELSE T0."DocTotal" * -1 END) 
                ELSE NULL 
            END) AS "Invoice Total",
            T1."GTotal",
            (T0."DiscSum" * ((CASE 
                WHEN T0."DocType" = 'I' THEN 
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T1."Quantity" * (T1."Price" * T0."DocRate")) * -1
                          ELSE (T1."Quantity" * (T1."Price" * T0."DocRate")) END)
                ELSE T1."Price" 
            END)) / (CASE 
                WHEN (SELECT SUM(B."LineTotal") FROM KFL_LIVE.ORIN A INNER JOIN KFL_LIVE.RIN1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") = 0
                THEN NULL 
                ELSE (SELECT SUM(B."LineTotal") FROM KFL_LIVE.ORIN A INNER JOIN KFL_LIVE.RIN1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry") 
            END)) AS "Total_Disc",
            (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
             FROM KFL_LIVE.RIN1 B INNER JOIN KFL_LIVE.RIN3 A ON A."DocEntry" = B."DocEntry" 
             WHERE A."ExpnsCode" = 1 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT Total",
            (SELECT (((A."LineTotal")) / (SUM(B."Quantity")) * T1."Quantity") 
             FROM KFL_LIVE.RIN1 B INNER JOIN KFL_LIVE.RIN3 A ON A."DocEntry" = B."DocEntry" 
             WHERE A."ExpnsCode" = 2 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT2 Total",
            T1."Project",
            T7."Location", 
            T7."State", 
            T7."GSTRegnNo",
            T1."StockPrice" AS "ItemCost",
            (T1."U_Order") AS "Order ID",
            T1."U_OrderedOn" AS "Order Date",
            T1."U_BuyerName" AS "Buyer Name"
        FROM KFL_LIVE.ORIN T0  
        INNER JOIN KFL_LIVE.RIN1 T1 ON T0."DocEntry" = T1."DocEntry" 
        INNER JOIN KFL_LIVE.OACT T12 ON T12."AcctCode" = T1."AcctCode"
        LEFT OUTER JOIN KFL_LIVE.OITM xx ON T1."ItemCode" = xx."ItemCode" 
        LEFT OUTER JOIN KFL_LIVE.OITM T9 ON T1."U_ActualItem" = T9."ItemCode" 
        INNER JOIN KFL_LIVE.OLCT T7 ON T7."Code" = T1."LocCode"
        INNER JOIN KFL_LIVE.OCRD T2 ON T0."CardCode" = T2."CardCode" 
        INNER JOIN KFL_LIVE.OCRG T3 ON T2."GroupCode" = T3."GroupCode" 
        INNER JOIN KFL_LIVE.RIN12 T4 ON T0."DocEntry" = T4."DocEntry" 
        LEFT JOIN KFL_LIVE.OCHP T5 ON T1."HsnEntry" = T5."AbsEntry"
        LEFT JOIN KFL_LIVE.OSAC T6 ON T1."SacEntry" = T6."AbsEntry"
        INNER JOIN KFL_LIVE.OSTC T8 ON T1."TaxCode" = T8."Code"
        LEFT JOIN KFL_LIVE.NNM1 T10 ON T0."Series" = T10."Series"
        LEFT JOIN KFL_LIVE.OCRY T11 ON T11."Code" = T4."CountryB"
        WHERE T0.CANCELED NOT IN ('Y', 'C')
    ) SALES
    WHERE SALES."Document Date" BETWEEN '{start_date}' AND '{end_date}'
) a
WHERE a."Channel" LIKE '%E-com%' 
AND a."Customer Code" NOT IN ('C03568','C03566','C03567','C03552','C03569','C00770')
ORDER BY "Document", a."DocNum", a."LineNum"
"""

def get_comprehensive_sales_query_simplified(
    start_date: str = None, end_date: str = None, schema: str = None
) -> str:
    """
    Get the simplified comprehensive sales query without DECLARE statements
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        str: SQL query string
    """
    query = COMPREHENSIVE_SALES_QUERY_SIMPLIFIED
    if start_date and end_date:
        query = query.format(start_date=start_date, end_date=end_date)
    return _apply_schema_to_query(query, schema)


# ---------------------------------------------------------------------------
# GSTR1 Revenue (trimmed) — used by the GST Reconciliation flow on the Ops
# Center. Only the columns required to build the SAP pivot
# (Customer Name × SeriesN × Taxable Value × CGST × SGST × IGST) plus a few
# joining keys are projected. Filtered to KFL_LIVE.OINV / KFL_LIVE.ORIN
# (sales invoice + credit memo) like the long pasted query, but without the
# unused gross-margin/COGS/HSN expansions.
# ---------------------------------------------------------------------------

GSTR1_REVENUE_QUERY = """
SELECT
    a."Document Date",
    a."Document",
    a."DocNum",
    a."SeriesN",
    a."Document No",
    a."Customer Code",
    a."Customer Name",
    a."Common Name",
    a."Channel",
    a."UC Order ID",
    a."Taxable Value",
    a."Total_Disc",
    (a."Taxable Value" - a."Total_Disc") AS "Net Taxable Value",
    a."CGST Tax Amount",
    a."SGST Tax Amount",
    a."IGST Tax Amount",
    a."Invoice FRT Total" AS "Freight Charges"
FROM (
    SELECT
        SALES."Document Date",
        (CASE WHEN SALES."ObjType" = 13 THEN 'SALES INVOICE' ELSE 'CREDIT MEMO' END) AS "Document",
        SALES."SeriesN",
        SALES."DocNum",
        SALES."SeriesN" || '/' || SALES."Document No" AS "Document No",
        SALES."Customer Code",
        SALES."Customer Name",
        SALES."Common Name",
        CASE
            WHEN SALES." Group" LIKE '%E-com%' THEN 'E-com'
            WHEN SALES." Group" LIKE '%Domestic HN%' THEN 'Offline HN'
            WHEN SALES." Group" LIKE '%Domestic Dogsee%' THEN 'Offline Dogsee'
            WHEN SALES." Group" LIKE '%Others%' THEN 'Others'
            WHEN SALES." Group" LIKE '%Export%' THEN 'Export'
            WHEN SALES."Customer Code" IN ('C01186','C03326','C03324') THEN 'Inter Transfer'
            ELSE 'Offline Dogsee'
        END AS "Channel",
        SALES."UC Order ID",
        SALES."Taxable Value",
        SALES."Total_Disc",
        SALES."CGST Tax Amount",
        SALES."SGST Tax Amount",
        SALES."IGST Tax Amount",
        (CASE WHEN SALES."ObjType" = 13 THEN SALES."Invoice FRT Total" ELSE (SALES."Invoice FRT Total" * -1) END) AS "Invoice FRT Total"
    FROM (
        SELECT DISTINCT
            T0."ObjType",
            T1."LineNum",
            T10."SeriesName" AS "SeriesN",
            T0."DocNum",
            T0."DocNum" AS "Document No",
            T0."DocDate" AS "Document Date",
            T0."CardCode" AS "Customer Code",
            T0."CardName" AS "Customer Name",
            T2."CardFName" AS "Common Name",
            T3."GroupName" AS " Group",
            T1."U_Order" AS "UC Order ID",
            ((CASE
                WHEN T0."DocType" = 'I' THEN
                    (CASE WHEN T0.CANCELED = 'Y' THEN T1."TotalSumSy" * -1 ELSE T1."TotalSumSy" END)
                ELSE T1."TotalSumSy"
            END)) AS "Taxable Value",
            (T0."DiscSum" * ((CASE
                WHEN T0."DocType" = 'I' THEN
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T1."Quantity" * (T1."Price" * T0."DocRate")) * -1
                          ELSE (T1."Quantity" * (T1."Price" * T0."DocRate")) END)
                ELSE T1."Price"
            END)) / NULLIF(
                (SELECT SUM(B."LineTotal") FROM KFL_LIVE.OINV A INNER JOIN KFL_LIVE.INV1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry"),
                0
            )) AS "Total_Disc",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END
             FROM KFL_LIVE.INV4 t44
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "CGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END
             FROM KFL_LIVE.INV4 t44
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "SGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" * -1 ELSE t44."TaxSum" END
             FROM KFL_LIVE.INV4 t44
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND T44."staType" = -120 AND T44."LineNum" = T1."LineNum") AS "IGST Tax Amount",
            (SELECT (((A."LineTotal")) / NULLIF(SUM(B."Quantity"), 0) * T1."Quantity")
             FROM KFL_LIVE.INV1 B INNER JOIN KFL_LIVE.INV3 A ON A."DocEntry" = B."DocEntry"
             WHERE A."ExpnsCode" = 1 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT Total",
            T0."DocType",
            T0.CANCELED,
            T1."Quantity",
            T1."Price"
        FROM KFL_LIVE.OINV T0
        INNER JOIN KFL_LIVE.INV1 T1 ON T0."DocEntry" = T1."DocEntry"
        INNER JOIN KFL_LIVE.OCRD T2 ON T0."CardCode" = T2."CardCode"
        INNER JOIN KFL_LIVE.OCRG T3 ON T2."GroupCode" = T3."GroupCode"
        LEFT JOIN KFL_LIVE.NNM1 T10 ON T0."Series" = T10."Series"
        WHERE T0.CANCELED NOT IN ('Y', 'C')

        UNION ALL

        SELECT DISTINCT
            T0."ObjType",
            T1."LineNum",
            T10."SeriesName" AS "SeriesN",
            T0."DocNum",
            T0."DocNum" AS "Document No",
            T0."DocDate" AS "Document Date",
            T0."CardCode" AS "Customer Code",
            T0."CardName" AS "Customer Name",
            T2."CardFName" AS "Common Name",
            T3."GroupName" AS " Group",
            T1."U_Order" AS "UC Order ID",
            (CASE
                WHEN T0."DocType" = 'I' THEN
                    (CASE WHEN T0.CANCELED = 'Y' THEN T1."TotalSumSy" ELSE T1."TotalSumSy" * -1 END)
                ELSE T1."TotalSumSy"
            END) AS "Taxable Value",
            (T0."DiscSum" * ((CASE
                WHEN T0."DocType" = 'I' THEN
                    (CASE WHEN T0.CANCELED = 'Y' THEN (T1."Quantity" * (T1."Price" * T0."DocRate")) * -1
                          ELSE (T1."Quantity" * (T1."Price" * T0."DocRate")) END)
                ELSE T1."Price"
            END)) / NULLIF(
                (SELECT SUM(B."LineTotal") FROM KFL_LIVE.ORIN A INNER JOIN KFL_LIVE.RIN1 B ON A."DocEntry" = B."DocEntry" WHERE A."DocEntry" = T1."DocEntry"),
                0
            )) AS "Total_Disc",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END
             FROM KFL_LIVE.RIN4 t44
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND t44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "CGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END
             FROM KFL_LIVE.RIN4 t44
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND t44."staType" = -100 AND T44."LineNum" = T1."LineNum") AS "SGST Tax Amount",
            (SELECT CASE WHEN T0.CANCELED = 'Y' THEN t44."TaxSum" ELSE t44."TaxSum" * -1 END
             FROM KFL_LIVE.RIN4 t44
             WHERE T1."DocEntry" = T44."DocEntry" AND t44."RelateType" = 1 AND t44."staType" = -120 AND T44."LineNum" = T1."LineNum") AS "IGST Tax Amount",
            (SELECT (((A."LineTotal")) / NULLIF(SUM(B."Quantity"), 0) * T1."Quantity")
             FROM KFL_LIVE.RIN1 B INNER JOIN KFL_LIVE.RIN3 A ON A."DocEntry" = B."DocEntry"
             WHERE A."ExpnsCode" = 1 AND B."DocEntry" = T1."DocEntry" GROUP BY A."LineTotal") AS "Invoice FRT Total",
            T0."DocType",
            T0.CANCELED,
            T1."Quantity",
            T1."Price"
        FROM KFL_LIVE.ORIN T0
        INNER JOIN KFL_LIVE.RIN1 T1 ON T0."DocEntry" = T1."DocEntry"
        INNER JOIN KFL_LIVE.OCRD T2 ON T0."CardCode" = T2."CardCode"
        INNER JOIN KFL_LIVE.OCRG T3 ON T2."GroupCode" = T3."GroupCode"
        LEFT JOIN KFL_LIVE.NNM1 T10 ON T0."Series" = T10."Series"
        WHERE T0.CANCELED NOT IN ('Y', 'C')
    ) SALES
    WHERE SALES."Document Date" BETWEEN '{start_date}' AND '{end_date}'
) a
ORDER BY a."Document Date", a."DocNum"
"""


import re as _re
from datetime import datetime as _datetime

_ISO_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _assert_iso_date(value: str, label: str) -> str:
    """Reject anything that isn't a strict YYYY-MM-DD date.

    Defence-in-depth against SQL injection via `.format(start_date=...)`:
    our orchestrator already normalises dates, but any direct caller of
    ``get_gstr1_revenue_query`` / ``generate_gstr1_revenue_report_readonly``
    could otherwise feed arbitrary text into the query template.
    """
    text = (value or "").strip()
    if not _ISO_DATE_RE.match(text):
        raise ValueError(f"{label} must be YYYY-MM-DD, got: {value!r}")
    try:
        _datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid calendar date: {value!r}") from exc
    return text


def get_gstr1_revenue_query(
    start_date: str, end_date: str, schema: str = None
) -> str:
    """Trimmed GSTR1 revenue query for the Ops Center GST Reconciliation flow.

    Returns one row per OINV/ORIN line with: Document Date, Document, DocNum,
    SeriesN, Document No, Customer Code, Customer Name, Common Name, Channel,
    UC Order ID (INV1.U_Order — line-level UDF set by our AR Invoice payload
    builder, matches Unicommerce Orders.uniware_id / .name), Taxable Value,
    Total_Disc, Net Taxable Value, CGST/SGST/IGST Tax Amount, Freight Charges.
    Aggregation (SeriesN filtering + per-order join keyed by "UC Order ID")
    is applied by the Python orchestrator in unicommerce/reporting/gst_recon.py.

    Dates are **strictly validated** as ``YYYY-MM-DD`` before being interpolated
    into the template because this path uses `.format()` rather than HANA
    bound parameters — any invalid format raises ``ValueError`` before the
    query is ever sent to SAP.

    Note: We intentionally do NOT select OINV.U_UCOrderID. That header UDF is
    used in the SAP Service Layer payload (see sap_payload.py) but is not
    projected onto the OINV HANA table in this installation; selecting it
    raises `invalid column name`. The line-level U_Order is sufficient for
    per-order reconciliation because our posting flow is strictly 1 UC order →
    1 SAP AR Invoice.
    """
    start_date = _assert_iso_date(start_date, "start_date")
    end_date = _assert_iso_date(end_date, "end_date")
    query = GSTR1_REVENUE_QUERY.format(start_date=start_date, end_date=end_date)
    return _apply_schema_to_query(query, schema)
