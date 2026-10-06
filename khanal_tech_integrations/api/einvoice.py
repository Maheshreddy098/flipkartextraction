"""E-invoice (Indian GST IRN) generation from SAP B1 AR Invoices.

Two input paths:
  1. HANA-based: pull AR Invoices from SAP B1 HANA DB, map to NIC/IRP schema.
  2. PDF-based: parse a Khanal Foods SAP tax-invoice PDF using pdfplumber.

Both paths return a List<Invoice> array in NIC schema v1.1, ready for the
GST e-invoice portal's bulk upload tool (manual IRN generation — no GSP/API).

Why HANA (not Service Layer) for path 1: the HSN code (OCHP.ChapterID) and
buyer GSTIN / place-of-supply (INV12.BpGSTN / BPStatGSTN) are not exposed by
the Service Layer.  HANA credentials are stored in site_config only (never in
source): einvoice_hana_user / einvoice_hana_password.

PDF parsing uses pdfplumber to extract header fields and line-item tables from
the printed tax-invoice layout.
"""
import json
import os
import re
import tempfile
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt

EINVOICE_SCHEMA_VERSION = "1.1"


def _hana_schema():
    schema = (frappe.db.get_single_value("SAP Settings", "hana_schema") or "").strip()
    if not schema:
        frappe.throw(_("HANA schema not configured. Set 'hana_schema' in SAP Settings."))
    return schema

# GST two-digit numeric state codes — abbreviation lookup (HANA path)
STATE_ABBR_TO_CODE = {
    "JK": "01", "HP": "02", "PB": "03", "CH": "04", "UT": "05", "UK": "05",
    "HR": "06", "DL": "07", "RJ": "08", "UP": "09", "BR": "10", "SK": "11",
    "AR": "12", "NL": "13", "MN": "14", "MZ": "15", "TR": "16", "ML": "17",
    "AS": "18", "WB": "19", "JH": "20", "OR": "21", "OD": "21", "CG": "22",
    "MP": "23", "GJ": "24", "DD": "25", "DN": "26", "MH": "27", "AP": "28",
    "KA": "29", "GA": "30", "LD": "31", "KL": "32", "TN": "33", "PY": "34",
    "AN": "35", "TG": "36", "TS": "36", "LA": "38",
}

# Full state name lookup (PDF path)
STATE_NAME_TO_CODE = {
    "jammu and kashmir": "01", "himachal pradesh": "02", "punjab": "03",
    "chandigarh": "04", "uttarakhand": "05", "haryana": "06",
    "delhi": "07", "rajasthan": "08", "uttar pradesh": "09",
    "bihar": "10", "sikkim": "11", "arunachal pradesh": "12",
    "nagaland": "13", "manipur": "14", "mizoram": "15",
    "tripura": "16", "meghalaya": "17", "assam": "18",
    "west bengal": "19", "jharkhand": "20", "odisha": "21",
    "chhattisgarh": "22", "chattisgarh": "22", "madhya pradesh": "23",
    "gujarat": "24", "daman and diu": "25",
    "dadra and nagar haveli": "26", "maharashtra": "27",
    "andhra pradesh": "28", "karnataka": "29", "goa": "30",
    "lakshadweep": "31", "kerala": "32", "tamil nadu": "33",
    "pondicherry": "34", "puducherry": "34",
    "andaman and nicobar": "35", "telangana": "36",
}

# ---------------------------------------------------------------------------
# Seller (our company) — single filing GSTIN.
# Per-key overrides via site_config: einvoice_seller_<key_lowercase>.
# ---------------------------------------------------------------------------
SELLER_DETAILS = {
    "Gstin": "29AAFCK9270L1ZU",
    "LglNm": "Khanal Foods Pvt Ltd",
    "TrdNm": "Khanal Foods Pvt Ltd",
    "Addr1": "Plot # 179 & 192, Road No 4, Phase 3, KIADB Industrial Area",
    "Addr2": "Malur, Dist Kolar",
    "Loc": "Malur",
    "Pin": 563130,
    "Stcd": "29",
    "Ph": None,
    "Em": None,
    "Fssai": "11219333000096",
    "BankAcc": "069663700002621",
    "BankIfsc": "YESB0000696",
}


def _seller():
    out = dict(SELLER_DETAILS)
    for k in out:
        v = frappe.conf.get(f"einvoice_seller_{k.lower()}")
        if v:
            out[k] = v
    if not out.get("Stcd") and out.get("Gstin"):
        out["Stcd"] = out["Gstin"][:2]
    return out


# ---------------------------------------------------------------------------
# HANA helpers
# ---------------------------------------------------------------------------
def _hana_engine():
    from khanal_tech_integrations.unicommerce.reporting.hana.hana_query_engine import (
        HANAReadOnlyQueryEngine,
    )

    settings = frappe.get_doc("SAP Settings")
    host   = (settings.hana_host or "").strip()
    port   = int(settings.hana_port or 30015)
    user   = (settings.hana_user or "").strip()
    pwd    = settings.get_password("hana_password") or ""
    schema = (settings.hana_schema or "").strip()

    if not host:
        frappe.throw(_("HANA host not configured in SAP Settings."))
    if not user or not pwd:
        frappe.throw(_("HANA credentials (user/password) not configured in SAP Settings."))
    if not schema:
        frappe.throw(_("HANA schema not configured in SAP Settings."))

    cfg = {
        "host": host,
        "port": port,
        "user": user,
        "password": pwd,
        "schema": schema,
        "connection_timeout": 30,
        "query_timeout": 300,
        "max_retries": 3,
    }
    eng = HANAReadOnlyQueryEngine(config=cfg)
    if not eng.connect():
        frappe.throw(_("Could not connect to SAP HANA. Check HANA credentials in SAP Settings."))
    return eng


def _run(sql):
    eng = _hana_engine()
    try:
        df = eng.execute_query(sql)
        return df.to_dict("records")
    finally:
        eng.disconnect()


def _sanitize_date(d):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(d or "")):
        frappe.throw(_("Date must be YYYY-MM-DD: {0}").format(d))
    return str(d)


def _sanitize_card_code(c):
    c = (c or "").strip()
    if c and not re.match(r"^[A-Za-z0-9_-]+$", c):
        frappe.throw(_("Invalid customer code: {0}").format(c))
    return c


def _sanitize_doc_nums(doc_nums):
    if isinstance(doc_nums, str):
        doc_nums = json.loads(doc_nums) if doc_nums.strip().startswith("[") else doc_nums.split(",")
    out = []
    for d in doc_nums:
        s = str(d).strip()
        if not s:
            continue
        if not s.isdigit():
            frappe.throw(_("Invoice number must be numeric: {0}").format(s))
        out.append(s)
    if not out:
        frappe.throw(_("Provide at least one invoice number"))
    return out


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _hs(v, default=""):
    """Safe string for HANA column values: handles None and float NaN (truthy!)."""
    if v is None or (isinstance(v, float) and v != v):
        return default
    return str(v).strip()


def _fmt_date(sap_date):
    if not sap_date:
        return ""
    s = str(sap_date)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return s


def _pos_code(row):
    """Numeric POS code: prefer INV12.BPStatGSTN, then buyer GSTIN prefix, then state abbr."""
    pos = str(row.get("BPStatGSTN") or "").strip()
    if pos.isdigit():
        return pos.zfill(2)
    gstin = str(row.get("BpGSTN") or "").strip()
    if len(gstin) >= 2 and gstin[:2].isdigit():
        return gstin[:2]
    return STATE_ABBR_TO_CODE.get(str(row.get("StateS") or "").strip().upper(), "")


# ---------------------------------------------------------------------------
# HANA: list invoices
# ---------------------------------------------------------------------------
@frappe.whitelist()
def list_ar_invoices(from_date, to_date, card_code=None, b2b_only=1):
    """List AR Invoice headers for the date-range picker."""
    from_date = _sanitize_date(from_date)
    to_date = _sanitize_date(to_date)
    card_code = _sanitize_card_code(card_code)

    where = [f'T0."CANCELED" = \'N\'', f'T0."DocDate" BETWEEN \'{from_date}\' AND \'{to_date}\'']
    if card_code:
        where.append(f'T0."CardCode" = \'{card_code}\'')
    if int(b2b_only or 0):
        where.append('T4."BpGSTN" <> \'\'')

    schema = _hana_schema()
    sql = f'''
        SELECT T0."DocEntry", T0."DocNum", T0."DocDate", T0."CardCode", T0."CardName",
               T0."DocTotal", T0."VatSum", T4."BpGSTN"
        FROM "{schema}"."OINV" T0
        LEFT JOIN "{schema}"."INV12" T4 ON T0."DocEntry" = T4."DocEntry"
        WHERE {" AND ".join(where)}
        ORDER BY T0."DocEntry" DESC
    '''
    rows = []
    for r in _run(sql):
        rows.append({
            "doc_entry": r.get("DocEntry"),
            "doc_num": r.get("DocNum"),
            "card_code": r.get("CardCode"),
            "card_name": r.get("CardName"),
            "doc_date": str(r.get("DocDate") or "")[:10],
            "doc_total": r.get("DocTotal"),
            "vat_sum": r.get("VatSum"),
            "buyer_gstin": (r.get("BpGSTN") or "").strip(),
        })
    return {"data": rows, "total": len(rows)}


# ---------------------------------------------------------------------------
# HANA: list AR credit notes
# ---------------------------------------------------------------------------
@frappe.whitelist()
def list_ar_credit_notes(from_date, to_date, card_code=None, b2b_only=1):
    """List AR Credit Note headers for the date-range picker."""
    from_date = _sanitize_date(from_date)
    to_date = _sanitize_date(to_date)
    card_code = _sanitize_card_code(card_code)

    where = [f'T0."CANCELED" = \'N\'', f'T0."DocDate" BETWEEN \'{from_date}\' AND \'{to_date}\'']
    if card_code:
        where.append(f'T0."CardCode" = \'{card_code}\'')
    if int(b2b_only or 0):
        where.append('T4."BpGSTN" <> \'\'')

    schema = _hana_schema()
    sql = f'''
        SELECT T0."DocEntry", T0."DocNum", T0."DocDate", T0."CardCode", T0."CardName",
               T0."DocTotal", T0."VatSum", T4."BpGSTN"
        FROM "{schema}"."ORIN" T0
        LEFT JOIN "{schema}"."RIN12" T4 ON T0."DocEntry" = T4."DocEntry"
        WHERE {" AND ".join(where)}
        ORDER BY T0."DocEntry" DESC
    '''
    rows = []
    for r in _run(sql):
        rows.append({
            "doc_entry": r.get("DocEntry"),
            "doc_num": r.get("DocNum"),
            "card_code": r.get("CardCode"),
            "card_name": r.get("CardName"),
            "doc_date": str(r.get("DocDate") or "")[:10],
            "doc_total": r.get("DocTotal"),
            "vat_sum": r.get("VatSum"),
            "buyer_gstin": (r.get("BpGSTN") or "").strip(),
        })
    return {"data": rows, "total": len(rows)}


# ---------------------------------------------------------------------------
# HANA: generate JSON (DocNum-based)
# ---------------------------------------------------------------------------
def _fetch_invoice_rows(doc_nums):
    schema = _hana_schema()
    in_list = ", ".join(doc_nums)
    sql = f'''
        SELECT T0."DocEntry", T0."DocNum", T0."DocDate", T0."DocDueDate",
               T0."CardCode", T0."CardName", T0."DocTotal", T0."VatSum",
               T0."NumAtCard", T0."Comments", T6."SeriesName",
               T4."BpGSTN", T4."StateS", T4."BPStatGSTN",
               T4."LocGSTN", T4."LocStatCod",
               T2."Street" AS "BuyerStreet", T2."Block" AS "BuyerBlock",
               T2."City" AS "BuyerCity", T2."ZipCode" AS "BuyerZip",
               T_SHP."Street" AS "ShipStreet", T_SHP."City" AS "ShipCity",
               T_SHP."ZipCode" AS "ShipZip",
               T_BP."LicTradNum" AS "BP_FedTaxId",
               T_WHS."Street" AS "WHS_Street", T_WHS."Block" AS "WHS_Block",
               T_WHS."City" AS "WHS_City", T_WHS."ZipCode" AS "WHS_Zip",
               T_WHS."State" AS "WHS_State", T_WHS."Country" AS "WHS_Country",
               T1."LineNum", T1."ItemCode", T1."Dscription", T1."Quantity",
               T1."Price", T1."LineTotal", T1."VatPrcnt", T1."unitMsr",
               T5."ChapterID"
        FROM "{schema}"."OINV" T0
        INNER JOIN "{schema}"."INV1" T1 ON T0."DocEntry" = T1."DocEntry"
        LEFT JOIN "{schema}"."INV12" T4 ON T0."DocEntry" = T4."DocEntry"
        LEFT JOIN "{schema}"."CRD1" T2 ON T2."CardCode" = T0."CardCode"
             AND T2."Address" = T0."PayToCode" AND T2."AdresType" = 'B'
        LEFT JOIN "{schema}"."CRD1" T_SHP ON T_SHP."CardCode" = T0."CardCode"
             AND T_SHP."Address" = T0."ShipToCode" AND T_SHP."AdresType" = 'S'
        LEFT JOIN "{schema}"."OCRD" T_BP ON T_BP."CardCode" = T0."CardCode"
        LEFT JOIN "{schema}"."OWHS" T_WHS ON T_WHS."WhsCode" = T1."WhsCode"
        LEFT JOIN "{schema}"."OCHP" T5 ON T1."HsnEntry" = T5."AbsEntry"
        LEFT JOIN "{schema}"."NNM1" T6 ON T0."Series" = T6."Series"
        WHERE T0."DocNum" IN ({in_list})
        ORDER BY T0."DocEntry", T1."LineNum"
    '''
    return _run(sql)


def _fetch_credit_note_rows(doc_nums):
    schema = _hana_schema()
    in_list = ", ".join(doc_nums)
    sql = f'''
        SELECT T0."DocEntry", T0."DocNum", T0."DocDate", T0."DocDueDate",
               T0."CardCode", T0."CardName", T0."DocTotal", T0."VatSum",
               T0."NumAtCard", T0."Comments", T6."SeriesName",
               T4."BpGSTN", T4."StateS", T4."BPStatGSTN",
               T4."LocGSTN", T4."LocStatCod",
               T2."Street" AS "BuyerStreet", T2."Block" AS "BuyerBlock",
               T2."City" AS "BuyerCity", T2."ZipCode" AS "BuyerZip",
               T_SHP."Street" AS "ShipStreet", T_SHP."City" AS "ShipCity",
               T_SHP."ZipCode" AS "ShipZip",
               T_BP."LicTradNum" AS "BP_FedTaxId",
               T_WHS."Street" AS "WHS_Street", T_WHS."Block" AS "WHS_Block",
               T_WHS."City" AS "WHS_City", T_WHS."ZipCode" AS "WHS_Zip",
               T_WHS."State" AS "WHS_State", T_WHS."Country" AS "WHS_Country",
               T1."LineNum", T1."ItemCode", T1."Dscription", T1."Quantity",
               T1."Price", T1."LineTotal", T1."VatPrcnt", T1."unitMsr",
               T5."ChapterID",
               T7."DocNum" AS "BaseDocNum", T7."DocDate" AS "BaseDocDate",
               T8."SeriesName" AS "BaseSeriesName"
        FROM "{schema}"."ORIN" T0
        INNER JOIN "{schema}"."RIN1" T1 ON T0."DocEntry" = T1."DocEntry"
        LEFT JOIN "{schema}"."RIN12" T4 ON T0."DocEntry" = T4."DocEntry"
        LEFT JOIN "{schema}"."CRD1" T2 ON T2."CardCode" = T0."CardCode"
             AND T2."Address" = T0."PayToCode" AND T2."AdresType" = 'B'
        LEFT JOIN "{schema}"."CRD1" T_SHP ON T_SHP."CardCode" = T0."CardCode"
             AND T_SHP."Address" = T0."ShipToCode" AND T_SHP."AdresType" = 'S'
        LEFT JOIN "{schema}"."OCRD" T_BP ON T_BP."CardCode" = T0."CardCode"
        LEFT JOIN "{schema}"."OWHS" T_WHS ON T_WHS."WhsCode" = T1."WhsCode"
        LEFT JOIN "{schema}"."OCHP" T5 ON T1."HsnEntry" = T5."AbsEntry"
        LEFT JOIN "{schema}"."NNM1" T6 ON T0."Series" = T6."Series"
        LEFT JOIN "{schema}"."OINV" T7 ON T1."BaseEntry" = T7."DocEntry"
             AND T1."BaseType" = 13
        LEFT JOIN "{schema}"."NNM1" T8 ON T7."Series" = T8."Series"
        WHERE T0."DocNum" IN ({in_list})
        ORDER BY T0."DocEntry", T1."LineNum"
    '''
    return _run(sql)


def _map_line(row, sl_no, is_inter):
    qty = flt(row.get("Quantity") or 0)
    rate = flt(row.get("Price") or 0)
    taxable = round(flt(row.get("LineTotal") if row.get("LineTotal") is not None else qty * rate), 2)
    gst_rate = flt(row.get("VatPrcnt") or 0)
    if is_inter:
        igst = round(taxable * gst_rate / 100, 2)
        cgst = sgst = 0.0
    else:
        igst = 0.0
        cgst = sgst = round(taxable * gst_rate / 200, 2)
    return {
        "SlNo": str(sl_no),
        "PrdDesc": row.get("Dscription") or row.get("ItemCode") or "",
        "IsServc": "N",
        "HsnCd": re.sub(r"\D", "", str(row.get("ChapterID") or "")),
        "Barcde": (row.get("ItemCode") or "").strip(),
        "Qty": qty,
        "FreeQty": 0.0,
        "Unit": (row.get("unitMsr") or "PCS"),
        "UnitPrice": rate,
        "TotAmt": round(qty * rate, 2),
        "Discount": 0.0,
        "PreTaxVal": taxable,
        "AssAmt": taxable,
        "GstRt": gst_rate,
        "IgstAmt": igst,
        "CgstAmt": cgst,
        "SgstAmt": sgst,
        "CesRt": 0.0,
        "CesAmt": 0.0,
        "OthChrg": 0.0,
        "TotItemVal": round(taxable + igst + cgst + sgst, 2),
        "OrgCntry": "IN",
        "PrdSlNo": (row.get("ItemCode") or "").strip(),
    }


def _map_invoice(header, lines):
    seller = _seller()
    doc_num = header.get("DocNum") or header.get("DocEntry") or "?"

    # INV12.LocGSTN = dispatching warehouse/branch GSTIN (actual seller for this invoice).
    # Falls back to hardcoded SELLER_DETAILS when not set.
    loc_gstin = (header.get("LocGSTN") or "").strip()
    loc_state = (header.get("LocStatCod") or "").strip()
    if loc_gstin:
        seller = dict(seller)
        seller["Gstin"] = loc_gstin
        seller["Stcd"] = STATE_ABBR_TO_CODE.get(loc_state.upper(), loc_gstin[:2])
        # Override address from the dispatching warehouse (OWHS)
        whs_addr1 = " ".join(
            p for p in [_hs(header.get("WHS_Street")), _hs(header.get("WHS_Block"))] if p
        )[:100]
        whs_city = _hs(header.get("WHS_City"))
        whs_zip_raw = re.sub(r"\D", "", _hs(header.get("WHS_Zip")) or "")
        if whs_addr1:
            seller["Addr1"] = whs_addr1
            seller["Addr2"] = None
        if whs_city:
            seller["Loc"] = whs_city
        if whs_zip_raw:
            seller["Pin"] = int(whs_zip_raw)

    seller_gstin = seller.get("Gstin", "")
    seller_state = seller.get("Stcd") or seller_gstin[:2]

    # Buyer GSTIN: INV12.BpGSTN, reject only if it matches the EFFECTIVE seller GSTIN
    def _valid_gstin(v):
        v = (v or "").strip()
        return v if (v and v != seller_gstin) else None

    buyer_gstin = (
        _valid_gstin(header.get("BpGSTN"))
        or _valid_gstin(header.get("BP_FedTaxId"))
        or ""
    )

    if not buyer_gstin:
        frappe.throw(_(
            "Invoice {0}: Buyer GSTIN missing in SAP. "
            "Set customer GSTIN in INV12 / CRD1 bill-to address / OCRD BP master before generating e-invoice."
        ).format(doc_num))
    if buyer_gstin == seller_gstin:
        frappe.throw(_(
            "Invoice {0}: Buyer GSTIN ({1}) matches Seller GSTIN. "
            "Fix customer GSTIN in SAP BP master."
        ).format(doc_num, buyer_gstin))

    buyer_state = buyer_gstin[:2] if len(buyer_gstin) >= 2 else ""
    pos = _pos_code(header)
    is_inter = bool(seller_state) and bool(pos) and seller_state != pos

    buyer_addr1 = " ".join(p for p in [_hs(header.get("BuyerStreet")), _hs(header.get("BuyerBlock"))] if p)[:100]
    buyer_loc = _hs(header.get("BuyerCity"))
    buyer_zip = re.sub(r"\D", "", _hs(header.get("BuyerZip")))
    if not buyer_addr1:
        buyer_addr1 = (buyer_loc or _hs(header.get("CardName")) or "NA")[:100]

    items = [_map_line(r, i + 1, is_inter) for i, r in enumerate(lines)]
    ass_val = round(sum(flt(it["AssAmt"]) for it in items), 2)
    cgst_val = round(sum(flt(it["CgstAmt"]) for it in items), 2)
    sgst_val = round(sum(flt(it["SgstAmt"]) for it in items), 2)
    igst_val = round(sum(flt(it["IgstAmt"]) for it in items), 2)
    tot_inv_val = flt(header.get("DocTotal") or (ass_val + cgst_val + sgst_val + igst_val))

    num_at_card = _hs(header.get("NumAtCard"))
    comments = _hs(header.get("Comments"))
    ref_parts = []
    if num_at_card:
        ref_parts.append(f"P.O.#: {num_at_card}")
    if comments:
        ref_parts.append(comments)

    series = _hs(header.get("SeriesName"))
    doc_no = f"{series}/{header.get('DocNum')}" if series else str(header.get("DocNum") or "")

    addl_info = []
    if seller.get("Fssai"):
        addl_info.append(f"FSSAI: {seller['Fssai']}")

    inv_rm_raw = "; ".join(ref_parts)[:100] if ref_parts else None
    inv_rm = inv_rm_raw if inv_rm_raw and len(inv_rm_raw) >= 3 else None

    return {
        "Version": EINVOICE_SCHEMA_VERSION,
        "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N", "EcmGstin": None, "IgstOnIntra": "N"},
        "DocDtls": {"Typ": "INV", "No": doc_no, "Dt": _fmt_date(header.get("DocDate"))},
        "SellerDtls": {
            "Gstin": seller.get("Gstin"), "LglNm": seller.get("LglNm"), "TrdNm": seller.get("TrdNm"),
            "Addr1": seller.get("Addr1"), "Addr2": seller.get("Addr2"), "Loc": seller.get("Loc"),
            "Pin": seller.get("Pin"), "Stcd": seller_state, "Ph": seller.get("Ph"), "Em": seller.get("Em"),
        },
        "BuyerDtls": {
            "Gstin": buyer_gstin, "LglNm": header.get("CardName") or "", "TrdNm": header.get("CardName") or "",
            "Pos": pos, "Addr1": buyer_addr1, "Addr2": None, "Loc": buyer_loc,
            "Pin": int(buyer_zip) if buyer_zip else 0, "Stcd": buyer_state, "Ph": None, "Em": None,
        },
        "DispDtls": None,
        "ShipDtls": None,
        "ItemList": items,
        "ValDtls": {
            "AssVal": ass_val, "CgstVal": cgst_val, "SgstVal": sgst_val, "IgstVal": igst_val,
            "CesVal": 0.0, "Discount": 0.0, "OthChrg": 0.0, "RndOffAmt": 0.0,
            "TotInvVal": round(tot_inv_val, 2),
        },
        "PayDtls": {
            "Nm": seller.get("LglNm"), "Accdet": seller.get("BankAcc"), "Mode": "Bank Transfer",
            "Fininsbr": seller.get("BankIfsc"), "Paymtdue": round(tot_inv_val, 2),
        },
        "RefDtls": {
            "InvRm": inv_rm,
            "DocPerdDtls": {"InvStDt": _fmt_date(header.get("DocDate")), "InvEndDt": _fmt_date(header.get("DocDueDate"))},
        },
        "AddlDocDtls": [{"Url": None, "Docs": None, "Info": "; ".join(addl_info)}] if addl_info else None,
        "ExpDtls": None,
        "EwbDtls": None,
    }


def _map_credit_note(header, lines):
    """Build NIC IRP payload for an AR Credit Note (Typ=CRN)."""
    obj = _map_invoice(header, lines)
    obj["DocDtls"]["Typ"] = "CRN"

    # Collect distinct base invoices for PrecDocDtls from line-level BaseEntry join
    seen, prec_docs = set(), []
    for line in lines:
        base_num = line.get("BaseDocNum")
        if base_num and base_num == base_num:  # excludes NaN
            base_num_key = str(base_num)
            if base_num_key not in seen:
                seen.add(base_num_key)
                base_series = _hs(line.get("BaseSeriesName"))
                base_inv_no = f"{base_series}/{base_num}" if base_series else str(base_num)
                prec_docs.append({
                    "InvNo": base_inv_no,
                    "InvDt": _fmt_date(line.get("BaseDocDate")),
                    "OthrRefNo": None,
                })

    ref = obj.get("RefDtls") or {}
    if prec_docs:
        ref["PrecDocDtls"] = prec_docs
    # InvRm is required for CRN (3-100 chars)
    if not _hs(ref.get("InvRm")):
        ref["InvRm"] = "Credit Note"
    obj["RefDtls"] = ref

    return obj


@frappe.whitelist()
def debug_bp_gstin_fields(doc_num):
    """
    Diagnostic: show OWHS warehouse GSTIN columns + INV1 warehouse codes for an invoice.
    Call from browser console:
      frappe.call({method:'khanal_tech_integrations.api.einvoice.debug_bp_gstin_fields',
                   args:{doc_num:'30544'}}).then(r=>console.log(JSON.stringify(r.message,null,2)))
    """
    schema = _hana_schema()
    results = {}
    doc_num = str(doc_num).strip()

    # Warehouses used in this invoice's line items
    whs_sql = f'''
        SELECT DISTINCT T1."WhsCode"
        FROM "{schema}"."OINV" T0
        INNER JOIN "{schema}"."INV1" T1 ON T1."DocEntry" = T0."DocEntry"
        WHERE T0."DocNum" = {doc_num}
    '''
    whs_rows = _run(whs_sql)
    whs_codes = [r["WhsCode"] for r in whs_rows]
    results["invoice_warehouses"] = whs_codes

    # GSTIN/tax-related columns that exist in OWHS
    col_sql = f'''
        SELECT COLUMN_NAME
        FROM TABLE_COLUMNS
        WHERE SCHEMA_NAME = '{schema}'
          AND TABLE_NAME = 'OWHS'
          AND (UPPER(COLUMN_NAME) LIKE '%GSTIN%'
            OR UPPER(COLUMN_NAME) LIKE '%GST%'
            OR UPPER(COLUMN_NAME) LIKE '%TAX%'
            OR UPPER(COLUMN_NAME) LIKE '%VATID%'
            OR UPPER(COLUMN_NAME) LIKE '%LOC%'
            OR UPPER(COLUMN_NAME) LIKE '%STATE%'
            OR UPPER(COLUMN_NAME) LIKE '%INDIA%'
            OR UPPER(COLUMN_NAME) LIKE '%NATTY%'
            OR UPPER(COLUMN_NAME) LIKE '%BPNAT%'
            OR UPPER(COLUMN_NAME) LIKE '%REG%')
        ORDER BY COLUMN_NAME
    '''
    col_rows = _run(col_sql)
    results["owhs_relevant_columns"] = [r["COLUMN_NAME"] for r in col_rows]

    # Actual OWHS rows for those warehouses with all relevant columns
    if whs_codes and results["owhs_relevant_columns"]:
        cols = ", ".join(f'"{c}"' for c in results["owhs_relevant_columns"])
        in_list = ", ".join(f"'{w}'" for w in whs_codes)
        owhs_sql = f'SELECT "WhsCode", {cols} FROM "{schema}"."OWHS" WHERE "WhsCode" IN ({in_list})'
        results["owhs_values"] = _run(owhs_sql)

    # Full INV12 row
    inv12_sql = f'''
        SELECT T4.*
        FROM "{schema}"."OINV" T0
        LEFT JOIN "{schema}"."INV12" T4 ON T4."DocEntry" = T0."DocEntry"
        WHERE T0."DocNum" = {doc_num}
    '''
    inv12_rows = _run(inv12_sql)
    results["inv12_row"] = inv12_rows[0] if inv12_rows else {}

    return results


@frappe.whitelist()
def generate_einvoice_json(doc_nums):
    """Build NIC e-invoice JSON array for the given SAP AR Invoice DocNums.

    doc_nums: JSON list or comma-separated string of SAP Invoice DocNum values.
    Returns {"data": [<einvoice obj>, ...], "count": n, "warnings": [...]}.
    """
    doc_nums = _sanitize_doc_nums(doc_nums)
    rows = _fetch_invoice_rows(doc_nums)
    if not rows:
        frappe.throw(_("No invoices found for: {0}").format(", ".join(doc_nums)))

    grouped = {}
    for r in rows:
        grouped.setdefault(r["DocEntry"], []).append(r)

    out, warnings = [], []
    for de, lines in grouped.items():
        header = lines[0]
        obj = _map_invoice(header, lines)
        if not (header.get("BpGSTN") or "").strip():
            warnings.append(f"Invoice {header.get('DocNum')}: no buyer GSTIN (not B2B?)")
        missing_hsn = [str(l.get("ItemCode")) for l in lines if not (l.get("ChapterID") or "").strip()]
        if missing_hsn:
            warnings.append(f"Invoice {header.get('DocNum')}: missing HSN for {', '.join(missing_hsn)}")
        out.append(obj)

    return {"data": out, "count": len(out), "warnings": warnings}


@frappe.whitelist()
def generate_credit_note_json(doc_nums):
    """Build NIC e-invoice JSON array for SAP AR Credit Note DocNums.

    doc_nums: JSON list or comma-separated string of SAP Credit Note DocNum values.
    Returns {"data": [...], "count": n, "warnings": [...]}.
    """
    doc_nums = _sanitize_doc_nums(doc_nums)
    rows = _fetch_credit_note_rows(doc_nums)
    if not rows:
        frappe.throw(_("No credit notes found for: {0}").format(", ".join(doc_nums)))

    grouped = {}
    for r in rows:
        grouped.setdefault(r["DocEntry"], []).append(r)

    out, warnings = [], []
    for de, lines in grouped.items():
        header = lines[0]
        obj = _map_credit_note(header, lines)
        if not (header.get("BpGSTN") or "").strip():
            warnings.append(f"Credit Note {header.get('DocNum')}: no buyer GSTIN (not B2B?)")
        missing_hsn = [str(l.get("ItemCode")) for l in lines if not (l.get("ChapterID") or "").strip()]
        if missing_hsn:
            warnings.append(f"Credit Note {header.get('DocNum')}: missing HSN for {', '.join(missing_hsn)}")

        # Hard enforcement: NIC schema — Addr1 1-100 chars, InvRm 3-100 chars
        buyer = obj.get("BuyerDtls") or {}
        addr1 = str(buyer.get("Addr1") or "").strip()[:100]
        if not addr1:
            addr1 = (str(buyer.get("LglNm") or "") or str(header.get("CardName") or "") or "NA")[:100]
        buyer["Addr1"] = addr1
        obj["BuyerDtls"] = buyer
        ref = obj.get("RefDtls") or {}
        inv_rm = str(ref.get("InvRm") or "").strip()[:100]
        ref["InvRm"] = inv_rm if len(inv_rm) >= 3 else "Credit Note"
        obj["RefDtls"] = ref

        out.append(obj)

    return {"data": out, "count": len(out), "warnings": warnings}


# ---------------------------------------------------------------------------
# PDF path: extract + parse
# ---------------------------------------------------------------------------
def _pdf_extract_full_text(pdf_path):
    import pdfplumber
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                lines.append(t)
    return "\n".join(lines)


def _pdf_extract_item_rows(pdf_path):
    import pdfplumber
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                header_idx = None
                for i, row in enumerate(table):
                    if row and any(c and re.search(r'Sl\.?\s*No', str(c), re.I) for c in row):
                        header_idx = i
                        break
                if header_idx is None:
                    continue

                header = table[header_idx]
                col = {}
                for j, h in enumerate(header):
                    if h is None:
                        continue
                    h_clean = h.replace("\n", " ").strip().lower()
                    if re.search(r'sl\.?\s*no', h_clean):
                        col.setdefault("sl", j)
                    elif h_clean == "sku":
                        col.setdefault("sku", j)
                    elif re.search(r'item|description', h_clean):
                        col.setdefault("desc", j)
                    elif re.search(r'hsn|sac', h_clean):
                        col.setdefault("hsn", j)
                    elif re.search(r'^qty', h_clean):
                        col.setdefault("qty", j)
                    elif re.search(r'^uom', h_clean):
                        col.setdefault("uom", j)
                    elif h_clean == "mrp":
                        col.setdefault("mrp", j)
                    elif h_clean == "rate":
                        col.setdefault("rate", j)
                    elif re.search(r'taxable', h_clean):
                        col.setdefault("taxable", j)
                    elif re.search(r'tax\s*%', h_clean):
                        col.setdefault("tax_pct", j)

                required = {"sl", "sku", "hsn", "qty", "rate", "taxable"}
                if not required.issubset(col.keys()):
                    continue

                for row in table[header_idx + 1:]:
                    if not row:
                        continue
                    sl_val = str(row[col["sl"]] or "").strip()
                    if not sl_val.isdigit():
                        continue
                    sku_val = str(row[col["sku"]] or "").strip()
                    if not sku_val:
                        continue

                    desc_raw = str(row[col.get("desc", 2)] or "")
                    desc = re.sub(r'\s+India\s*\(\)', '', desc_raw)
                    desc = re.sub(r'\s*\(\)\s*$', '', desc)
                    desc = desc.replace("\n", " ").strip()

                    mrp_val = row[col["mrp"]] if "mrp" in col else None
                    mrp = float(str(mrp_val).replace(",", "").strip() or "0") if mrp_val not in (None, "", "0") else None

                    tax_raw = row[col["tax_pct"]] if "tax_pct" in col else "18"
                    tax_pct = float(str(tax_raw).replace(",", "").strip() or "18") if tax_raw else 18.0

                    def _ca(v):
                        return float(str(v).replace(",", "").strip() or "0") if v else 0.0

                    def _ci(v):
                        try:
                            return int(str(v).replace(",", "").strip())
                        except Exception:
                            return 0

                    rows.append({
                        "sl": int(sl_val),
                        "sku": sku_val,
                        "desc": desc,
                        "hsn": str(row[col["hsn"]] or "").strip(),
                        "qty": _ci(row[col["qty"]]),
                        "uom": str(row[col.get("uom", 5)] or "PCS").strip().upper() or "PCS",
                        "mrp": mrp,
                        "rate": _ca(row[col["rate"]]),
                        "taxable": _ca(row[col["taxable"]]),
                        "tax_pct": tax_pct,
                    })

    seen, unique = set(), []
    for r in rows:
        if r["sl"] not in seen:
            seen.add(r["sl"])
            unique.append(r)
    return sorted(unique, key=lambda x: x["sl"])


def _pdf_parse_header(text):
    def find(pattern, default=""):
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else default

    addr_block = text[:text.find("GSTIN")].strip().splitlines()
    seller_name  = addr_block[0].strip() if addr_block else "Khanal Foods Pvt Ltd"
    seller_addr1 = addr_block[1].strip() if len(addr_block) > 1 else ""
    seller_addr2 = addr_block[2].strip() if len(addr_block) > 2 else ""
    seller_city  = addr_block[3].strip().rstrip(",").strip() if len(addr_block) > 3 else "Bengaluru"

    pin_match = re.search(r'Karnataka\s*-\s*(\d{6})', text, re.I)
    seller_pin = int(pin_match.group(1)) if pin_match else 560048

    buyer_name = ""
    buyer_addr1 = ""
    bill_to_m = re.search(r'Bill To:.*?\n(.*?)\nGST No\.', text, re.S | re.I)
    if bill_to_m:
        blines = [l.strip() for l in bill_to_m.group(1).splitlines() if l.strip()]
        name_lines = [l for l in blines if not re.match(r'Customer Code', l, re.I)]
        if name_lines:
            raw = name_lines[0]
            words = raw.split()
            half = len(words) // 2
            if half > 1 and words[:half] == words[half:]:
                raw = " ".join(words[:half])
            buyer_name = raw
        if len(name_lines) > 1:
            buyer_addr1 = name_lines[1][:100]

    buyer_pin_m = re.search(r'India\s*-\s*(\d{6})', text)
    buyer_pin = int(buyer_pin_m.group(1)) if buyer_pin_m else 0

    return {
        "seller_name": seller_name,
        "seller_addr1": seller_addr1,
        "seller_addr2": seller_addr2,
        "seller_city": seller_city,
        "seller_pin": seller_pin,
        "seller_gstin": find(r'GSTIN\s*:\s*([A-Z0-9]{15})'),
        "company_id": find(r'Company ID\s*:\s*([A-Z0-9]+)'),
        "fssai": find(r'FSSAI\s*:\s*([0-9]+)'),
        "existing_irn": find(r'IRN No\.\s*:([a-f0-9]{64})'),
        "inv_no": find(r'Invoice No\.?\s+([\w/]+)'),
        "inv_date": find(r'Invoice Date\s*:\s*([\d/]+)'),
        "due_date": find(r'DueDate\s*:\s*([\d/]+)'),
        "dc_no": find(r'D\s*C\s*No[.:]?\s*[:]?\s*(\d{4,6})'),
        "po_ref": find(r'P\.O\.#\s*:\s*([^\n]+)'),
        "terms": find(r'Terms\s*:\s*([\w-]+)'),
        "buyer_gstin": find(r'GST No\.\s*:\s*([A-Z0-9]{15})'),
        "buyer_name": buyer_name,
        "buyer_addr1": buyer_addr1,
        "buyer_city": find(r'Place of Supply\s*:\s*(\w[\w\s]*)').strip(),
        "buyer_pin": buyer_pin,
        "contact_phone": find(r'(?:Contact|Conatct) Mobile No\.\s*:\s*(\d+)'),
        "bank_acc": find(r'Account No\.\s*:\s*([0-9]+)'),
        "bank_ifsc": find(r'IFSC\s*:\s*([A-Z0-9]+)'),
        "taxable_amt": float(str(find(r'Taxable Amount\s+([\d,]+\.\d{2})')).replace(",", "") or "0"),
        "tax_amt": float(str(find(r'Tax Amount\s+([\d,]+\.\d{2})')).replace(",", "") or "0"),
        "total_amt": float(str(find(r'Total\s+₹\s+([\d,]+\.\d{2})')).replace(",", "") or "0"),
        "remarks": re.sub(
            r'\s*(IGST|CGST|SGST|Tax Amount|Taxable Amount|Sub Total|Total|Freight|^Pcs$).*', '',
            find(r'Remarks\s*:\s*([^\n]+)')
        ).strip() or None,
        # Credit Note specific fields
        "credit_note_no": find(r'Credit Note No\.?\s+([\w/]+)'),
        "orig_inv_no": find(r'Invoice No\s*:\s*([\w/]+)'),
        "is_credit_note": bool(re.search(r'\bCredit Note\b', text, re.I)),
    }


def _build_irp_from_pdf(header, items):
    """Assemble IRP payload from parsed PDF header + line items."""
    seller = _seller()

    seller_gstin = header.get("seller_gstin") or seller["Gstin"]
    seller_state = seller_gstin[:2] if len(seller_gstin) >= 2 else seller["Stcd"]

    buyer_gstin = header.get("buyer_gstin", "")
    buyer_state = buyer_gstin[:2] if len(buyer_gstin) >= 2 else ""

    pos_name = header.get("buyer_city", "")
    pos_code = buyer_state or STATE_NAME_TO_CODE.get(pos_name.strip().lower(), "")

    is_inter = bool(seller_state) and bool(pos_code) and (seller_state != pos_code)

    tax_amt = header.get("tax_amt", 0.0)
    igst_val = round(tax_amt, 2) if is_inter else 0.0
    cgst_val = 0.0 if is_inter else round(tax_amt / 2, 2)
    sgst_val = cgst_val

    item_list = []
    for it in items:
        if is_inter:
            igst_item = round(it["taxable"] * it["tax_pct"] / 100, 2)
            cgst_item = sgst_item = 0.0
        else:
            igst_item = 0.0
            cgst_item = sgst_item = round(it["taxable"] * it["tax_pct"] / 200, 2)

        entry = {
            "SlNo": str(it["sl"]),
            "PrdDesc": it["desc"],
            "IsServc": "N",
            "HsnCd": it["hsn"],
            "Barcde": it["sku"],
            "Qty": float(it["qty"]),
            "FreeQty": 0.0,
            "Unit": it["uom"] or "PCS",
            "UnitPrice": it["rate"],
            "TotAmt": round(it["qty"] * it["rate"], 2),
            "Discount": 0.0,
            "PreTaxVal": round(it["taxable"], 2),
            "AssAmt": round(it["taxable"], 2),
            "GstRt": it["tax_pct"],
            "IgstAmt": igst_item,
            "CgstAmt": cgst_item,
            "SgstAmt": sgst_item,
            "CesRt": 0.0,
            "CesAmt": 0.0,
            "CesNonAdvlAmt": 0.0,
            "StateCesRt": 0.0,
            "StateCesAmt": 0.0,
            "StateCesNonAdvlAmt": 0.0,
            "OthChrg": 0.0,
            "TotItemVal": round(it["taxable"] + igst_item + cgst_item + sgst_item, 2),
            "OrdLineRef": str(it["sl"]),
            "OrgCntry": "IN",
            "PrdSlNo": it["sku"],
            "BchDtls": {"Nm": it["sku"], "ExpDt": None, "WrDt": None},
        }
        if it.get("mrp"):
            entry["AttribDtls"] = [{"Nm": "MRP", "Val": str(int(it["mrp"]))}]
        item_list.append(entry)

    ref_parts = []
    if header.get("dc_no"):
        ref_parts.append(f"DC No.: {header['dc_no']}")
    if header.get("po_ref"):
        ref_parts.append(header["po_ref"].strip())
    if header.get("remarks"):
        ref_parts.append(header["remarks"].strip())

    addl_parts = []
    fssai = header.get("fssai") or seller.get("Fssai")
    if fssai:
        addl_parts.append(f"FSSAI: {fssai}")
    if header.get("company_id"):
        addl_parts.append(f"Company ID: {header['company_id']}")
    if header.get("existing_irn"):
        addl_parts.append(f"IRN: {header['existing_irn']}")

    bank_acc = header.get("bank_acc") or seller.get("BankAcc")
    bank_ifsc = header.get("bank_ifsc") or seller.get("BankIfsc")
    total_amt = header.get("total_amt", 0.0)
    taxable_amt = header.get("taxable_amt", 0.0)

    inv_date = header.get("inv_date", "")
    due_date = header.get("due_date", "") or inv_date

    ref_str = ("; ".join(ref_parts))[:100]
    if len(ref_str) < 3:
        ref_str = None

    is_crn = header.get("is_credit_note", False)
    if is_crn and not ref_str:
        ref_str = "Credit Note"
    doc_type = "CRN" if is_crn else "INV"
    doc_no = (header.get("credit_note_no") if is_crn else None) or header.get("inv_no", "")
    prec_docs = None
    if is_crn:
        orig_inv = (header.get("orig_inv_no") or "").strip()
        if orig_inv and orig_inv.upper() != "NA":
            prec_docs = [{"InvNo": orig_inv, "InvDt": inv_date, "OthrRefNo": None}]

    return {
        "Version": EINVOICE_SCHEMA_VERSION,
        "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N", "EcmGstin": None, "IgstOnIntra": "N"},
        "DocDtls": {"Typ": doc_type, "No": doc_no, "Dt": inv_date},
        "SellerDtls": {
            "Gstin": seller_gstin,
            "LglNm": header.get("seller_name") or seller["LglNm"],
            "TrdNm": header.get("seller_name") or seller["TrdNm"],
            "Addr1": header.get("seller_addr1") or seller["Addr1"],
            "Addr2": header.get("seller_addr2") or seller.get("Addr2"),
            "Loc": header.get("seller_city") or seller["Loc"],
            "Pin": header.get("seller_pin") or seller["Pin"],
            "Stcd": seller_state,
            "Ph": None,
            "Em": None,
        },
        "BuyerDtls": {
            "Gstin": buyer_gstin,
            "LglNm": header.get("buyer_name", ""),
            "TrdNm": header.get("buyer_name", ""),
            "Pos": pos_code,
            "Addr1": header.get("buyer_addr1") or pos_name or "NA",
            "Addr2": None,
            "Loc": pos_name,
            "Pin": header.get("buyer_pin", 0),
            "Stcd": buyer_state,
            "Ph": header.get("contact_phone"),
            "Em": None,
        },
        "DispDtls": None,
        "ShipDtls": {
            "Gstin": buyer_gstin,
            "LglNm": header.get("buyer_name", ""),
            "TrdNm": header.get("buyer_name", ""),
            "Addr1": header.get("buyer_addr1") or pos_name or "NA",
            "Addr2": None,
            "Loc": pos_name,
            "Pin": header.get("buyer_pin", 0),
            "Stcd": buyer_state,
        },
        "ItemList": item_list,
        "ValDtls": {
            "AssVal": taxable_amt, "CgstVal": cgst_val, "SgstVal": sgst_val, "IgstVal": igst_val,
            "CesVal": 0.0, "StCesVal": 0.0, "Discount": 0.0, "OthChrg": 0.0,
            "RndOffAmt": 0.0, "TotInvVal": total_amt, "TotInvValFc": None,
        },
        "PayDtls": {
            "Nm": header.get("seller_name") or seller["LglNm"],
            "Accdet": bank_acc, "Mode": "Bank Transfer", "Fininsbr": bank_ifsc,
            "Payterm": header.get("terms"), "Payloc": None, "Dir": None, "Crtrn": None,
            "Crday": 30, "Paidamt": 0.0, "Paymtdue": total_amt,
        },
        "RefDtls": {
            "InvRm": ref_str,
            "DocPerdDtls": {"InvStDt": inv_date, "InvEndDt": due_date},
            "PrecDocDtls": prec_docs,
            "ContrDtls": None,
        },
        "AddlDocDtls": [{"Url": None, "Docs": None, "Info": "; ".join(addl_parts)}] if addl_parts else None,
        "ExpDtls": None,
        "EwbDtls": None,
    }


@frappe.whitelist(allow_guest=False)
def parse_invoice_pdf():
    """Parse a Khanal Foods SAP tax-invoice PDF and return NIC e-invoice JSON.

    Expects a multipart/form-data POST with field name 'pdf_file'.
    Returns {"data": [<invoice>], "warnings": [...]}.
    """
    file_obj = frappe.request.files.get("pdf_file")
    if not file_obj:
        frappe.throw(_("No PDF file uploaded (expected field: pdf_file)"))

    pdf_bytes = file_obj.stream.read()
    if not pdf_bytes:
        frappe.throw(_("Uploaded PDF is empty"))

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        full_text = _pdf_extract_full_text(tmp_path)
        items = _pdf_extract_item_rows(tmp_path)
        header = _pdf_parse_header(full_text)

        warnings = []
        if not items:
            frappe.throw(_("No line items found in PDF. Check that the PDF layout matches the expected SAP invoice format."))
        if not header.get("buyer_gstin"):
            warnings.append("Buyer GSTIN not found in PDF — may not be a B2B invoice")
        missing_hsn = [str(it["sku"]) for it in items if not (it.get("hsn") or "").strip()]
        if missing_hsn:
            warnings.append(f"Missing HSN for SKUs: {', '.join(missing_hsn)}")

        invoice = _build_irp_from_pdf(header, items)
        return {"data": [invoice], "count": 1, "warnings": warnings}

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
