"""
AR invoice search and detail from SAP HANA (OINV / INV1 / NNM1).
HANA connection uses ``SAPConnector`` (same as GRN and other modules).
"""

from decimal import Decimal
from typing import Optional

import frappe
from frappe import _
from frappe.utils import cint, getdate

from khanal_tech_integrations.api.common.sap_connector import SAPConnector
from khanal_tech_integrations.utils.logistics_delivery_portal import DELIVERY_LOGISTICS_ROLE

_MAX_STR = 200


def _hana_sql_error_message(exc: Exception, schema_used: Optional[str] = None) -> str:
    """Turn common HANA driver errors into actionable text for portal users."""
    msg = str(exc)
    low = msg.lower()
    if "invalid schema name" in low or " 362," in msg or msg.startswith("(362,"):
        sch = schema_used or _("(unknown)")
        return _(
            "SAP HANA reports an invalid schema (error 362). The value in "
            "Desk / SAP Settings / HANA Schema is currently '{0}'. "
            "That schema does not exist (or is not visible) on this HANA server for the "
            "configured host/port/user. Ask your SAP admin for the correct schema where "
            "B1 tables such as OINV live, update SAP Settings, then try again. Raw error: {1}"
        ).format(sch, msg)
    return msg


def _ar_invoice_header_sql(schema: str, include_u_lrtrackno: bool) -> str:
    """OINV header + series only (no INV1) — fast for portal refresh after Check LR."""
    # No trailing comma before FROM when U_LRtrackno is omitted (HANA rejects `DocTotal , FROM`).
    last_cols = (
        '    T0."DocTotal",\n    T0."U_LRtrackno"\n'
        if include_u_lrtrackno
        else '    T0."DocTotal"\n'
    )
    return """
SELECT
    T0."DocEntry",
    T0."DocNum",
    T2."SeriesName",
    T0."DocDate",
    T0."CardCode",
    T0."CardName",
{last_cols}FROM {schema}."OINV" T0
LEFT JOIN {schema}."NNM1" T2 ON T0."Series" = T2."Series"
WHERE T0."DocEntry" = ?
""".format(
        schema=schema,
        last_cols=last_cols,
    )


def _ar_invoice_detail_sql(schema: str, include_u_lrtrackno: bool) -> str:
    """OINV + INV1 + optional NNM1 for series; U_LRtrackno optional (not all companies define that UDF)."""
    udf_line = '    T0."U_LRtrackno",\n' if include_u_lrtrackno else ""
    return """
SELECT
    T0."DocEntry",
    T0."DocNum",
    T2."SeriesName",
    T0."DocDate",
    T0."CardCode",
    T0."CardName",
    T0."DocTotal",
{udf_line}    T1."LineNum",
    T1."ItemCode",
    T1."Dscription",
    T1."Quantity",
    T1."Price",
    T1."LineTotal"
FROM {schema}."OINV" T0
INNER JOIN {schema}."INV1" T1 ON T0."DocEntry" = T1."DocEntry"
LEFT JOIN {schema}."NNM1" T2 ON T0."Series" = T2."Series"
WHERE T0."DocEntry" = ?
ORDER BY T1."LineNum"
""".format(
        schema=schema,
        udf_line=udf_line,
    )


def _require_logistics_portal():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)
    if DELIVERY_LOGISTICS_ROLE not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Not permitted."), frappe.PermissionError)


def _serialize_value(val):
    if val is None:
        return None
    if hasattr(val, "isoformat") and callable(val.isoformat):
        try:
            return val.isoformat()
        except Exception:
            return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (bytes, bytearray, memoryview)):
        try:
            return bytes(val).decode("utf-8", errors="replace")
        except Exception:
            return None
    return val


def _parse_doc_num_optional(raw) -> Optional[int]:
    """Return None if empty; otherwise same rules as required DocNum."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        n = int(str(raw).strip())
    except ValueError:
        frappe.throw(_("DocNum must be a whole number."), frappe.ValidationError)
    if n < 0 or n > 999999999:
        frappe.throw(_("DocNum is out of range."), frappe.ValidationError)
    return n


def _parse_doc_entry_filter(raw) -> int:
    """Return 0 if empty; otherwise positive DocEntry for WHERE clause."""
    if raw is None or str(raw).strip() == "":
        return 0
    try:
        de = int(str(raw).strip())
    except ValueError:
        frappe.throw(_("DocEntry must be a whole number."), frappe.ValidationError)
    if de <= 0 or de > 999999999:
        frappe.throw(_("DocEntry is out of range."), frappe.ValidationError)
    return de


def _clip_str(val, label: str) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if len(s) > _MAX_STR:
        frappe.throw(_("{0} is too long (max {1} characters).").format(label, _MAX_STR), frappe.ValidationError)
    return s


@frappe.whitelist()
def search_ar_invoices(
    doc_num=None,
    series_name=None,
    doc_date=None,
    card_code=None,
    card_name=None,
    doc_entry=None,
):
    """
    Search AR invoices (OINV + optional NNM1 for series name).

    Provide **DocNum** and/or **DocEntry** (at least one). Other filters narrow results.
    Uses LEFT JOIN to NNM1 so invoices without a numbering-series row (e.g. some opening-balance docs) are still returned.
    Returns up to 50 rows, newest DocDate first.
    """
    _require_logistics_portal()
    num = _parse_doc_num_optional(doc_num)
    doc_entry_f = _parse_doc_entry_filter(doc_entry)
    if num is None and not doc_entry_f:
        frappe.throw(_("Enter DocNum and/or DocEntry to search."), frappe.ValidationError)

    series_f = _clip_str(series_name, _("Series name"))
    card_c = _clip_str(card_code, _("Card code"))
    card_n = _clip_str(card_name, _("Card name"))
    date_val = None
    if doc_date not in (None, ""):
        try:
            date_val = getdate(doc_date)
        except Exception:
            frappe.throw(_("Invalid invoice date."), frappe.ValidationError)

    conn = cursor = None
    schema = None
    rows = []
    connector = SAPConnector()
    try:
        conn, cursor, schema = connector.get_hana_connection()
        sql = """
SELECT TOP 50
    T0."DocEntry",
    T0."DocNum",
    T2."SeriesName",
    T0."DocDate",
    T0."CardCode",
    T0."CardName",
    T0."DocTotal"
FROM {schema}."OINV" T0
LEFT JOIN {schema}."NNM1" T2 ON T0."Series" = T2."Series"
WHERE 1=1
""".format(
            schema=schema
        )

        params: list = []
        if num is not None and doc_entry_f:
            sql += ' AND T0."DocNum" = ? AND T0."DocEntry" = ?'
            params.extend([num, doc_entry_f])
        elif num is not None:
            sql += ' AND T0."DocNum" = ?'
            params.append(num)
        else:
            sql += ' AND T0."DocEntry" = ?'
            params.append(doc_entry_f)
        if date_val is not None:
            sql += ' AND T0."DocDate" = ?'
            params.append(date_val)
        if series_f is not None:
            sql += ' AND T2."SeriesName" = ?'
            params.append(series_f)
        if card_c is not None:
            sql += ' AND T0."CardCode" = ?'
            params.append(card_c)
        if card_n is not None:
            sql += ' AND T0."CardName" = ?'
            params.append(card_n)

        sql += ' ORDER BY T0."DocDate" DESC'

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Logistics delivery HANA search")
        frappe.throw(_hana_sql_error_message(e, schema), frappe.ValidationError)
    finally:
        connector.close_hana_connection(conn, cursor)

    keys = (
        "doc_entry",
        "doc_num",
        "series_name",
        "doc_date",
        "card_code",
        "card_name",
        "doc_total",
    )
    out = []
    for row in rows:
        out.append({k: _serialize_value(v) for k, v in zip(keys, row)})
    return {"invoices": out}


@frappe.whitelist()
def get_ar_invoice_detail(doc_entry=None, include_lines=None):
    """Header + line items for one OINV by DocEntry.

    Pass ``include_lines=0`` (or ``false``) to load **header only** (no INV1 join) — faster after
    Check LR & Preview when line items are not needed.
    """
    _require_logistics_portal()
    de = cint(doc_entry)
    if not de:
        frappe.throw(_("DocEntry is required."), frappe.ValidationError)

    want_lines = True
    if include_lines is not None and str(include_lines).strip() != "":
        s = str(include_lines).strip().lower()
        want_lines = s not in ("0", "false", "no", "off")

    conn = cursor = None
    schema = None
    rows = []
    include_u_lr = True
    connector = SAPConnector()
    try:
        conn, cursor, schema = connector.get_hana_connection()
        sql_fn = _ar_invoice_detail_sql if want_lines else _ar_invoice_header_sql
        sql = sql_fn(schema, include_u_lrtrackno=True)
        try:
            cursor.execute(sql, (de,))
            rows = cursor.fetchall()
        except Exception as ex:
            msg_l = str(ex).lower()
            if (
                "u_lrtrackno" in msg_l
                and ("invalid column" in msg_l or " 260," in str(ex) or str(ex).startswith("(260,"))
            ):
                include_u_lr = False
                sql = sql_fn(schema, include_u_lrtrackno=False)
                cursor.execute(sql, (de,))
                rows = cursor.fetchall()
            else:
                raise
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Logistics delivery HANA detail")
        frappe.throw(_hana_sql_error_message(e, schema), frappe.ValidationError)
    finally:
        connector.close_hana_connection(conn, cursor)

    if not rows:
        frappe.throw(_("No invoice found for this DocEntry."), frappe.DoesNotExistError)

    header_keys = (
        "doc_entry",
        "doc_num",
        "series_name",
        "doc_date",
        "card_code",
        "card_name",
        "doc_total",
        "u_lrtrackno",
    )
    line_keys = ("line_num", "item_code", "dscription", "quantity", "price", "line_total")

    first = rows[0]
    if include_u_lr:
        header = {k: _serialize_value(v) for k, v in zip(header_keys, first[:8])}
        line_lo, line_hi = 8, 14
    else:
        header_short_keys = header_keys[:-1]
        header = {k: _serialize_value(v) for k, v in zip(header_short_keys, first[:7])}
        header["u_lrtrackno"] = None
        line_lo, line_hi = 7, 13

    lines = []
    if want_lines:
        for r in rows:
            lines.append({k: _serialize_value(v) for k, v in zip(line_keys, r[line_lo:line_hi])})

    return {"header": header, "lines": lines}
