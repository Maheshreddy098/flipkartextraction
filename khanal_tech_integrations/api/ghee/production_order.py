"""
Ghee Reverse Production Order API

Converts finished ghee jars (e.g. FGHN0034) back into raw ghee (RMHN0094) via SAP B1.

Flow per order:
    Step 1 — User selects source FG item(s) + batches to issue (Goods Issue)
    Step 2 — System fetches BOM of output item (RMHN0094); user can edit qty/price
    Step 4 — Creates SAP Production Order; header PlannedQty = is_fg qty from Step 2
    Step 5 — Posts GI (source batches), GR (RMHN0094 + by-products), closes PO

Cost split logic:
    JAR component    → actual price traced from original PO via IBT1 → IGE1
    Packaging/scrap  → 0.01 each, routed to HN-SCRAP warehouse
    RMHN0094 output  → total_gi_cost - jar_cost - scrap_costs  (remainder)
    Total GR cost == Total GI cost by construction

SAP connections:
    Fully isolated from "SAP Settings" (used by every other module in this app).
    Both HANA and Service Layer read/write only the "SAP Test Layer" singleton,
    so pointing this file at a test SAP box never disturbs live services.

    HANA          ← local get_hana_connection() below (reads SAP Test Layer doctype)
    Service Layer ← local AuthenticateSAPB1()/renew_sap_session() below (reads SAP Test Layer doctype)
"""

import json
import traceback
from collections import defaultdict

import requests as _requests
import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, add_to_date, get_datetime

HEADERS = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json",
}

_TEST_DOCTYPE = "SAP Test Layer"

# Warehouse constants
_SCRAP_WHS     = "HN-SCRAP"
_SCRAP_BIN_ABS = 1168       # AbsEntry of HN-SCRAP-SYSTEM-BIN-LOCATION (bin-activated warehouse)
_REAL_WHS      = "HN-WIP"  # Jar and RMHN0094 (raw ghee) always received here


# ---------------------------------------------------------------------------
# Internal helpers — HANA + SAP B1 (SAP Test Layer only — never touches SAP Settings)
# ---------------------------------------------------------------------------

def _b1_url():
    return frappe.db.get_single_value(_TEST_DOCTYPE, "sap_b1_url") or ""


def _hana_schema():
    return frappe.db.get_single_value(_TEST_DOCTYPE, "hana_schema") or ""


def get_hana_connection():
    """HANA connection for read-only ops, built from SAP Test Layer creds."""
    try:
        import hdbcli.dbapi as hana_db

        settings = frappe.get_single(_TEST_DOCTYPE)

        connection = hana_db.connect(
            address=settings.hana_host,
            port=int(settings.hana_port),
            user=settings.hana_user,
            password=settings.get_password("hana_password"),
            autocommit=False,
        )
        cursor = connection.cursor()
        return connection, cursor, settings.hana_schema
    except ImportError:
        frappe.throw(_("SAP HANA driver not found. Please install hdbcli"))
    except Exception as e:
        frappe.log_error(f"Test HANA connection failed: {str(e)}", "Ghee SAP Connection Error")
        frappe.throw(_("Failed to connect to test SAP HANA database"))


def close_hana_connection(connection, cursor):
    try:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    except Exception as e:
        frappe.log_error(f"Error closing test HANA connection: {str(e)}", "Ghee SAP Connection Error")


def _hana_query(sql, params=()):
    conn, cursor, schema = get_hana_connection()
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        close_hana_connection(conn, cursor)


def _hana_exec_many(statements):
    """Execute multiple DML statements in one connection, single commit."""
    conn, cursor, schema = get_hana_connection()
    try:
        for sql in statements:
            cursor.execute(sql)
        conn.commit()
    finally:
        close_hana_connection(conn, cursor)


def renew_sap_session():
    """Log into the test SAP B1 Service Layer, persisting session on SAP Test Layer."""
    b1_session = _requests.Session()
    doc = frappe.get_doc(_TEST_DOCTYPE)
    credentials_json = {
        "CompanyDB": doc.companydb,
        "Password": doc.get_password("password"),
        "UserName": doc.username,
    }
    b1_url = doc.sap_b1_url
    reqUrl = b1_url + "Login"
    response = b1_session.request(
        "POST", reqUrl, data=json.dumps(credentials_json), headers=HEADERS, verify=False
    )
    cookies = b1_session.cookies.get_dict()
    try:
        body = response.json()
    except Exception:
        body = {}
    if not response.ok:
        err_msg = "Unknown"
        if isinstance(body.get("error"), dict):
            m = body["error"].get("message")
            err_msg = m.get("value", err_msg) if isinstance(m, dict) else (m or err_msg)
        else:
            err_msg = response.text[:500] if response.text else err_msg
        raise ValueError(f"Test SAP Login failed ({response.status_code}): {err_msg}")
    b1session = cookies.get("B1SESSION") or body.get("SessionId")
    routeid = cookies.get("ROUTEID")
    if not b1session:
        raise ValueError("Test SAP Login did not return B1SESSION cookie or SessionId.")
    if not routeid:
        raise ValueError("Test SAP Login did not return ROUTEID cookie.")
    doc.b1session = b1session
    doc.routeid = routeid
    session_timeout = body.get("SessionTimeout", 30)
    try:
        doc.expires_on = add_to_date(now_datetime(), minutes=int(session_timeout))
    except (TypeError, ValueError):
        doc.expires_on = add_to_date(now_datetime(), minutes=30)
    doc.save(ignore_permissions=True)
    return b1_session


def AuthenticateSAPB1():
    """Authenticate against test SAP B1, reusing a live SAP Test Layer session if not expired."""
    b1_session = _requests.Session()
    doc = frappe.get_doc(_TEST_DOCTYPE)

    expires_on = frappe.db.get_single_value(_TEST_DOCTYPE, "expires_on")
    b1session_val = frappe.db.get_single_value(_TEST_DOCTYPE, "b1session")
    routeid_val = frappe.db.get_single_value(_TEST_DOCTYPE, "routeid")

    if not expires_on or not b1session_val or not routeid_val:
        return renew_sap_session()
    if now_datetime() >= get_datetime(doc.expires_on):
        return renew_sap_session()

    b1_session.cookies.set("B1SESSION", b1session_val)
    b1_session.cookies.set("ROUTEID", routeid_val)
    return b1_session


class _NoPoolAdapter(_requests.adapters.HTTPAdapter):
    """
    Clears the urllib3 connection pool after every request.

    SAP B1 closes idle TCP sockets server-side; reusing a stale socket raises
    BrokenPipeError. Clearing the pool forces a fresh TCP handshake each call.
    """
    def send(self, request, *args, **kwargs):
        try:
            return super().send(request, *args, **kwargs)
        finally:
            self.poolmanager.clear()


def _no_pool_session(base_session):
    """Return a Session that opens a fresh TCP connection for every request."""
    s = _requests.Session()
    s.cookies.update(base_session.cookies)
    s.headers.update(base_session.headers)
    adapter = _NoPoolAdapter()
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def _b1_post_with_retry(url, payload, session=None, method="POST"):
    """POST/PATCH to SAP B1. On BrokenPipeError, retries once with a fresh no-pool session."""
    for attempt in range(2):
        try:
            if attempt == 0:
                s = session if session else renew_sap_session()
            else:
                s = _no_pool_session(renew_sap_session())
            s.headers["Connection"] = "close"
            resp = s.request(method, url, data=json.dumps(payload), headers=HEADERS, verify=False)
            return resp, s
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            if attempt == 0:
                frappe.log_error(
                    f"SAP B1 connection dropped ({exc}), retrying with no-pool session",
                    "Ghee SAP retry",
                )
                continue
            raise


def _extract_sap_error(resp):
    try:
        err = resp.json().get("error") or {}
        msg = err.get("message") or {}
        return msg.get("value") if isinstance(msg, dict) else str(msg)
    except Exception:
        return resp.text or f"HTTP {resp.status_code}"


# ---------------------------------------------------------------------------
# Internal helpers — cost split
# ---------------------------------------------------------------------------

def _parse_source_batches(param):
    """Parse source_batches param (JSON string or list) → list of dicts."""
    if not param:
        return []
    if isinstance(param, str):
        return json.loads(param)
    return list(param)


def _group_batches_by_item(raw_batches, fallback_item_code=''):
    """Group source_batches list by item_code. Returns OrderedDict {item_code: [batch_dicts]}."""
    from collections import OrderedDict
    groups = OrderedDict()
    for b in raw_batches:
        ic = (b.get('item_code') or fallback_item_code or '').strip()
        groups.setdefault(ic, []).append(b)
    return groups


def _resolve_batches(raw_batches, source_item_code, fallback_warehouse, schema):
    """
    Fetch OBTQ/OBTN data for each batch and validate requested qty <= available.

    Returns:
        batches_info   — [{batch_no, source_qty, warehouse, calc_price, avail_qty}]
        total_qty      — sum of source_qty across all batches
        total_cost     — sum of (source_qty × calc_price)
        first_warehouse
    """
    src = source_item_code.replace("'", "''")
    batches_info = []
    first_whs    = fallback_warehouse

    for b in raw_batches:
        bn_raw  = (b.get("batch_no") or "").strip()
        whs_raw = (b.get("warehouse") or fallback_warehouse or "").strip() or None
        if not bn_raw:
            raise ValueError("Empty batch_no in source_batches")

        bn         = bn_raw.replace("'", "''")
        whs_clause = f' AND T0."WhsCode" = \'{whs_raw}\'' if whs_raw else ""

        rows = _hana_query(f"""
            SELECT T0."WhsCode", T0."Quantity" AS "WhsQty",
                   COALESCE(T1."CostTotal", 0) AS "CostTotal",
                   COALESCE(T1."Quantity", 0)  AS "BatchTotalQty"
            FROM {schema}.OBTQ T0
            LEFT JOIN {schema}.OBTN T1
                ON T1."ItemCode" = T0."ItemCode" AND T0."SysNumber" = T1."SysNumber"
            WHERE T0."ItemCode" = '{src}'
              AND T1."DistNumber" = '{bn}'
              AND T0."Quantity" > 0
            {whs_clause}
            ORDER BY T0."Quantity" DESC
        """)[:1]

        if not rows:
            raise ValueError(f"Batch '{bn_raw}' not found for '{source_item_code}'")

        br       = rows[0]
        avail    = float(br["WhsQty"] or 0)
        cost_t   = float(br["CostTotal"] or 0)
        bt_qty   = float(br["BatchTotalQty"] or 1)
        calc_p   = round(cost_t / bt_qty, 3) if bt_qty > 0 else 0
        whs_code = br["WhsCode"]
        first_whs = first_whs or whs_code

        try:
            req = float(b["source_qty"]) if b.get("source_qty") not in (None, "", 0) else 0
        except (TypeError, ValueError):
            req = 0
        if req <= 0:
            req = avail
        if req > avail:
            raise ValueError(f"Batch '{bn_raw}': requested {req} > available {avail} in {whs_code}")

        batches_info.append({
            "batch_no":   bn_raw,
            "source_qty": req,
            "warehouse":  whs_code,
            "calc_price": calc_p,
            "avail_qty":  avail,
        })

    total_qty  = sum(b["source_qty"] for b in batches_info)
    total_cost = round(sum(b["source_qty"] * b["calc_price"] for b in batches_info), 3)
    return batches_info, total_qty, total_cost, first_whs


def _fetch_bom(item_code, schema):
    """
    Return (bom_rows, bom_base) for item_code from ITT1/OITT.

    bom_rows  — [{Code, ItemName, Quantity, Warehouse, UnitPrice}]
    bom_base  — planned qty of the BOM header (OITT.Qauntity)
    """
    nic      = item_code.replace("'", "''")
    bom_rows = _hana_query(f"""
        SELECT I."Code", I."ItemName", I."Quantity", I."Warehouse",
               COALESCE(NULLIF(M."AvgPrice", 0), NULLIF(M."LastPurPrc", 0), 0) AS "UnitPrice"
        FROM {schema}.ITT1 I
        LEFT JOIN {schema}.OITM M ON M."ItemCode" = I."Code"
        WHERE I."Father" = '{nic}'
        ORDER BY I."VisOrder"
    """)
    bom_hdr  = _hana_query(f'SELECT "Qauntity" FROM {schema}.OITT WHERE "Code" = \'{nic}\'')
    bom_base = float(bom_hdr[0]["Qauntity"] or 1) if bom_hdr else 1.0
    return bom_rows, bom_base


def _get_jar_prices_from_batch_po(batches_info, source_item_code, schema):
    """
    Trace the original production PO for source batches (via IBT1) and return
    component StockPrices from IGE1 of that PO.

    Used to price the jar at its actual cost rather than moving average.
    Returns {item_code: price}.
    """
    src           = source_item_code.replace("'", "''")
    orig_po_entry = None

    for b in batches_info:
        bn_esc = b["batch_no"].replace("'", "''")
        ibt = _hana_query(f"""
            SELECT "BsDocEntry" FROM {schema}.IBT1
            WHERE "ItemCode" = '{src}' AND "BatchNum" = '{bn_esc}'
              AND "BsDocType" = 202 AND "Direction" = 0
            ORDER BY "DocDate" DESC
        """)
        if ibt:
            orig_po_entry = ibt[0]["BsDocEntry"]
            break

    if not orig_po_entry:
        return {}

    po_prices = {}
    for r in _hana_query(f"""
        SELECT "ItemCode", "StockPrice" FROM {schema}.IGE1
        WHERE "BaseType" = 202 AND "BaseEntry" = {orig_po_entry}
          AND "StockPrice" > 0
    """):
        po_prices[r["ItemCode"]] = float(r["StockPrice"])
    return po_prices


def _classify_bom_items(bom_rows, bom_base, req_qty, po_prices, source_item_code=""):
    """
    Classify BOM by-product items (negative qty rows) for reverse PO receipt.

    JAR  (item_name contains "jar") → HN-WIP, price from original PO IGE1 or OITM avg
    REST (sticker, wad, waste, etc) → HN-SCRAP, 0.01 each

    Returns:
        real_items  — jar(s) going to HN-WIP
        scrap_items — everything else going to HN-SCRAP
    """
    real_items  = []
    scrap_items = []

    for row in bom_rows:
        code    = row["Code"]
        qty_bom = float(row["Quantity"] or 0)

        # Only process by-products (negative BOM qty); skip positive (input) lines
        if qty_bom >= 0:
            continue
        qty_bom = abs(qty_bom)

        # Skip the source FG item itself if it appears in the BOM
        if source_item_code and code == source_item_code:
            continue

        per_unit   = qty_bom / bom_base
        total_qty  = round(per_unit * req_qty, 3)
        in_po      = code in po_prices
        item_name  = row.get("ItemName") or ""
        unit_price = float(row["UnitPrice"] or 0)

        is_jar = "jar" in item_name.lower()

        if is_jar:
            # Jar gets its actual price from the original production PO; fallback to OITM avg
            actual_price = po_prices.get(code, unit_price)
            real_items.append({
                "item_code":   code,
                "item_name":   item_name,
                "quantity":    total_qty,
                "warehouse":   _REAL_WHS,
                "unit_price":  round(actual_price, 3),
                "line_cost":   round(actual_price * total_qty, 3),
                "cost_source": "po_ige1" if in_po else "oitm_avg",
            })
        else:
            # All other packaging/waste → scrap at 0.01
            scrap_items.append({
                "item_code":   code,
                "item_name":   item_name,
                "quantity":    total_qty,
                "warehouse":   _SCRAP_WHS,
                "unit_price":  0.01,
                "line_cost":   round(0.01 * total_qty, 3),
                "cost_source": "minimum_0.01",
            })

    return real_items, scrap_items


def _fix_gr_rmhn_price(schema, gr_entry, fg_unit_price, fg_residual, new_item_batch_no):
    """
    Direct HANA patch: correct the RMHN0094 price in the GR document after posting.

    SAP assigns its own moving average to RMHN0094 on receipt. We overwrite with
    fg_residual (= total_gi_cost - jar_cost - scrap_costs) so GR total == GI total.

    JDT1 structure for the GR (when RMHN0094 posted at non-zero):
        Line 0: WIP account Cr  ← fg_residual
        Line 1: RMHN0094 inv Dr ← fg_residual
    """
    oign = _hana_query(
        f'SELECT "TransId","DocTotal" FROM {schema}.OIGN WHERE "DocEntry" = {int(gr_entry)}'
    )
    if not oign:
        frappe.log_error(f"_fix_gr_rmhn_price: OIGN not found for DocEntry {gr_entry}", "Ghee GR fix")
        return False

    trans_id  = oign[0]["TransId"]
    old_total = float(oign[0]["DocTotal"] or 0)

    ign1_rmhn = _hana_query(
        f'SELECT "LineTotal" FROM {schema}.IGN1'
        f' WHERE "DocEntry" = {int(gr_entry)} AND "LineNum" = 0'
    )
    if not ign1_rmhn:
        frappe.log_error(f"_fix_gr_rmhn_price: IGN1 line 0 not found for DocEntry {gr_entry}", "Ghee GR fix")
        return False

    old_rmhn_val = float(ign1_rmhn[0]["LineTotal"] or 0)
    if abs(old_rmhn_val - fg_residual) < 0.01:
        return True  # Already correct, nothing to patch

    new_total = round(old_total - old_rmhn_val + fg_residual, 3)

    stmts = [
        f'UPDATE {schema}.IGN1 SET "Price" = {fg_unit_price}, "StockPrice" = {fg_unit_price},'
        f' "LineTotal" = {fg_residual}'
        f' WHERE "DocEntry" = {int(gr_entry)} AND "LineNum" = 0',

        f'UPDATE {schema}.OIGN SET "DocTotal" = {new_total}'
        f' WHERE "DocEntry" = {int(gr_entry)}',
    ]

    # Update JDT1 only if both journal lines exist (RMHN0094 was posted at non-zero price)
    jdt1_check = _hana_query(
        f'SELECT "Line_ID" FROM {schema}.JDT1'
        f' WHERE "TransId" = {int(trans_id)} AND "Line_ID" IN (0, 1)'
    )
    if len(jdt1_check) >= 2:
        stmts += [
            f'UPDATE {schema}.JDT1 SET "Credit" = {fg_residual}, "SYSCred" = {fg_residual},'
            f' "Debit" = 0, "SYSDeb" = 0'
            f' WHERE "TransId" = {int(trans_id)} AND "Line_ID" = 0',

            f'UPDATE {schema}.JDT1 SET "Debit" = {fg_residual}, "SYSDeb" = {fg_residual},'
            f' "Credit" = 0, "SYSCred" = 0'
            f' WHERE "TransId" = {int(trans_id)} AND "Line_ID" = 1',
        ]

    # Correct the batch ledger in OBTN (CostTotal = total value of this batch receipt)
    bn_esc = ""
    if new_item_batch_no:
        bn_esc = new_item_batch_no.replace("'", "''")
        obn = _hana_query(
            f'SELECT "CostTotal" FROM {schema}.OBTN'
            f' WHERE "ItemCode" = \'RMHN0094\' AND "DistNumber" = \'{bn_esc}\''
        )
        if obn:
            stmts.append(
                f'UPDATE {schema}.OBTN SET "CostTotal" = {fg_residual}'
                f' WHERE "ItemCode" = \'RMHN0094\' AND "DistNumber" = \'{bn_esc}\''
            )

    try:
        _hana_exec_many(stmts)
        return True
    except Exception as e:
        frappe.log_error(f"_fix_gr_rmhn_price failed: {e}\nStatements: {stmts}", "Ghee GR fix")
        return False


# ---------------------------------------------------------------------------
# Whitelisted API endpoints — read/debug
# ---------------------------------------------------------------------------

@frappe.whitelist()
def list_batches(item_code, whs_code="EC-FG"):
    schema = _hana_schema()
    ic  = (item_code or "").replace("'", "''")
    whs = (whs_code  or "").replace("'", "''")
    return _hana_query(
        f'SELECT n."DistNumber" AS "batch_no", q."Quantity" AS "qty"'
        f' FROM {schema}.OBTN n'
        f' JOIN {schema}.OBTQ q ON q."ItemCode"=n."ItemCode" AND q."SysNumber"=n."SysNumber"'
        f' WHERE n."ItemCode"=\'{ic}\' AND q."WhsCode"=\'{whs}\' AND q."Quantity" > 0'
        f' ORDER BY q."Quantity" DESC'
    )


@frappe.whitelist()
def debug_item_avg(item_code):
    schema = _hana_schema()
    ic = (item_code or "").replace("'", "''")
    oitm = _hana_query(f'SELECT "ItemCode","AvgPrice","LastPurPrc","StdPrice" FROM {schema}.OITM WHERE "ItemCode" = \'{ic}\'')
    obtn = _hana_query(f'SELECT "DistNumber","Quantity","CostTotal","CalcPrice" FROM {schema}.OBTN WHERE "ItemCode" = \'{ic}\' ORDER BY "InDate" DESC')
    return {"oitm": oitm, "obtn": obtn[:10]}


@frappe.whitelist()
def debug_gr_journal(gr_doc_entry):
    """Show IGN1 + JDT1 + OBTN for a given GR DocEntry — used to verify cost patch."""
    schema = _hana_schema()
    ign1 = _hana_query(
        f'SELECT "LineNum","ItemCode","Quantity","Price","StockPrice","LineTotal"'
        f' FROM {schema}.IGN1 WHERE "DocEntry" = {int(gr_doc_entry)}'
    )
    oign = _hana_query(
        f'SELECT "DocEntry","DocNum","TransId","GrossTotal","DocTotal"'
        f' FROM {schema}.OIGN WHERE "DocEntry" = {int(gr_doc_entry)}'
    )
    trans_id = oign[0]["TransId"] if oign else None
    jdt1 = []
    ojdt = []
    if trans_id:
        jdt1 = _hana_query(
            f'SELECT "Line_ID","Account","Debit","Credit","SYSCred","SYSDeb","TransType","BaseRef"'
            f' FROM {schema}.JDT1 WHERE "TransId" = {int(trans_id)}'
        )
        ojdt = _hana_query(
            f'SELECT "TransId","Debit","Credit","LocTotal","TransType"'
            f' FROM {schema}.OJDT WHERE "TransId" = {int(trans_id)}'
        )
    return {"ign1": ign1, "oign": oign, "jdt1": jdt1, "ojdt": ojdt, "trans_id": trans_id}


@frappe.whitelist()
def get_po_status(po_doc_num):
    """Return PO header + WOR1 lines + linked GI/GR doc details for a given DocNum."""
    schema = _hana_schema()
    po = _hana_query(
        f'SELECT "DocNum","ItemCode","DocEntry","Status","U_GINo","U_GIEnt","U_GRNo","U_GREnt"'
        f' FROM {schema}.OWOR WHERE "DocNum" = {int(po_doc_num)}'
    )
    if not po:
        return {"success": False, "message": f"PO {po_doc_num} not found"}
    p    = po[0]
    wor1 = _hana_query(
        f'SELECT "LineNum","ItemCode","PlannedQty","IssuedQty" FROM {schema}.WOR1'
        f' WHERE "DocEntry" = {p["DocEntry"]} ORDER BY "LineNum"'
    )
    gi_lines, gr_lines, jdt1_gr = [], [], []
    if p.get("U_GIEnt"):
        gi_lines = _hana_query(
            f'SELECT "LineNum","ItemCode","Quantity","Price","StockPrice","LineTotal"'
            f' FROM {schema}.IGE1 WHERE "DocEntry" = {int(p["U_GIEnt"])}'
        )
    if p.get("U_GREnt"):
        gr_lines = _hana_query(
            f'SELECT "LineNum","ItemCode","Quantity","Price","StockPrice","LineTotal"'
            f' FROM {schema}.IGN1 WHERE "DocEntry" = {int(p["U_GREnt"])}'
        )
        gr_ent = int(p["U_GREnt"])
        try:
            oign = _hana_query(
                f'SELECT "DocEntry","DocNum","TransId","DocTotal"'
                f' FROM {schema}.OIGN WHERE "DocEntry" = {gr_ent}'
            )
        except Exception as ex:
            oign = [{"_error": str(ex)}]
        jdt1_gr = [{"_oign": oign}]
        if oign and not oign[0].get("_error") and oign[0].get("TransId"):
            jdt1_gr += _hana_query(
                f'SELECT "Line_ID","Account","Debit","Credit","SYSCred","SYSDeb"'
                f' FROM {schema}.JDT1 WHERE "TransId" = {int(oign[0]["TransId"])} ORDER BY "Line_ID"'
            )
    return {"success": True, "po": p, "wor1": wor1, "gi_lines": gi_lines, "gr_lines": gr_lines, "jdt1_gr": jdt1_gr}


@frappe.whitelist()
def get_item_batches(item_code):
    """
    Return available batches for item_code with qty and unit cost (CalcPrice) from HANA.
    Only batches in HN-WIP with qty > 0 are returned.
    """
    item_code = (item_code or "").strip().replace("'", "''")
    if not item_code:
        return {"success": False, "message": "item_code required", "data": []}

    schema = _hana_schema()
    sql = f"""
        SELECT
            T1."DistNumber"       AS "BatchNumber",
            T0."WhsCode"          AS "Warehouse",
            T0."Quantity"         AS "WhsQty",
            T1."MnfDate"          AS "ManufacturingDate",
            T1."ExpDate"          AS "ExpiryDate",
            COALESCE(T1."CostTotal", 0) AS "CostTotal",
            COALESCE(T1."Quantity", 0)  AS "BatchTotalQty"
        FROM {schema}.OBTQ T0
        LEFT JOIN {schema}.OBTN T1
            ON T1."ItemCode" = T0."ItemCode" AND T0."SysNumber" = T1."SysNumber"
        WHERE T0."ItemCode" = '{item_code}'
          AND T0."WhsCode" = 'HN-WIP'
          AND T0."Quantity" > 0
          AND T1."DistNumber" NOT LIKE 'NOT_%'
        ORDER BY T1."InDate" DESC
    """
    try:
        rows = _hana_query(sql)
        data = []
        for r in rows:
            whs_qty    = float(r.get("WhsQty") or 0)
            total_qty  = float(r.get("BatchTotalQty") or 0)
            cost_total = float(r.get("CostTotal") or 0)
            calc_price = round(cost_total / total_qty, 3) if total_qty > 0 else 0
            data.append({
                "batch_number":       r.get("BatchNumber"),
                "warehouse":          r.get("Warehouse"),
                "quantity":           whs_qty,
                "calc_price":         calc_price,
                "batch_cost":         round(whs_qty * calc_price, 3),
                "manufacturing_date": str(r.get("ManufacturingDate") or ""),
                "expiry_date":        str(r.get("ExpiryDate") or ""),
            })
        return {"success": True, "data": data}
    except Exception as e:
        frappe.log_error(str(e), "Ghee get_item_batches Error")
        return {"success": False, "message": str(e), "data": []}


@frappe.whitelist()
def get_bom_lines(new_item_code):
    """Return ITT1 BOM components for new_item_code (the output item, e.g. RMHN0094)."""
    new_item_code = (new_item_code or "").strip().replace("'", "''")
    if not new_item_code:
        return {"success": False, "message": "new_item_code required", "data": []}

    schema = _hana_schema()
    sql = f"""
        SELECT
            I."Code"        AS "Code",
            I."ItemName"    AS "ItemName",
            I."Quantity"    AS "Quantity",
            I."Warehouse"   AS "Warehouse",
            I."IssueMthd"   AS "IssueMethod",
            COALESCE(
                NULLIF(M."AvgPrice", 0),
                NULLIF(M."LastPurPrc", 0),
                NULLIF(I."Price", 0),
                0
            )               AS "AvgPrice"
        FROM {schema}.ITT1 I
        LEFT JOIN {schema}.OITM M ON M."ItemCode" = I."Code"
        WHERE I."Father" = '{new_item_code}'
        ORDER BY I."VisOrder"
    """
    try:
        rows = _hana_query(sql)
        if not rows:
            return {
                "success": True,
                "data":    [],
                "message": f"No BOM found for '{new_item_code}' in SAP. Create the BOM in SAP B1 first.",
            }
        data = []
        for r in rows:
            data.append({
                "item_code":    r.get("Code") or "",
                "item_name":    r.get("ItemName") or "",
                "quantity":     float(r.get("Quantity") or 0),
                "warehouse":    r.get("Warehouse") or "",
                "issue_method": r.get("IssueMethod") or "",
                "avg_price":    float(r.get("AvgPrice") or 0),
            })
        return {"success": True, "data": data}
    except Exception as e:
        frappe.log_error(str(e), "Ghee get_bom_lines Error")
        return {"success": False, "message": str(e), "data": []}


@frappe.whitelist()
def preview_cost_split(source_item_code='', batch_no=None, new_item_code='',
                       source_warehouse=None, source_qty=None, source_batches=None):
    """
    Returns cost split preview for the Step 2 BOM table.

    Accepts either:
        Single batch  — source_item_code + batch_no + source_qty
        Multi batch   — source_batches = JSON [{item_code, batch_no, source_qty, warehouse}, ...]

    Returns bom_lines where:
        is_fg=True  → RMHN0094 (output raw ghee), quantity = total source qty, cost = remainder
        is_fg=False → by-products (jar, packaging, waste)
    """
    source_item_code = (source_item_code or "").strip()
    new_item_code    = (new_item_code or "").strip()
    source_warehouse = (source_warehouse or "").strip() or None

    if not new_item_code:
        return {"success": False, "message": "new_item_code required"}

    raw_batches = _parse_source_batches(source_batches)
    if not raw_batches:
        bn = (batch_no or "").strip()
        if not bn:
            return {"success": False, "message": "batch_no or source_batches required"}
        raw_batches = [{"item_code": source_item_code, "batch_no": bn,
                        "source_qty": source_qty, "warehouse": source_warehouse}]

    schema          = _hana_schema()
    batches_by_item = _group_batches_by_item(raw_batches, source_item_code)

    try:
        total_batch_cost = 0.0
        total_req_qty    = 0.0
        all_batches_info = []
        merged_po_prices = {}
        actual_whs       = source_warehouse or ""

        for ic, ic_batches in batches_by_item.items():
            if not ic:
                continue
            bi, rq, bc, whs = _resolve_batches(ic_batches, ic, source_warehouse, schema)
            for b in bi:
                b["item_code"] = ic
            all_batches_info.extend(bi)
            total_req_qty    += rq
            total_batch_cost += bc
            actual_whs        = actual_whs or whs
            merged_po_prices.update(_get_jar_prices_from_batch_po(bi, ic, schema))

        total_batch_cost = round(total_batch_cost, 3)

        bom_rows, bom_base = _fetch_bom(new_item_code, schema)
        if not bom_rows:
            return {"success": False, "message": f"No BOM found for '{new_item_code}' in SAP — add BOM in SAP B1 first"}

        real_items, scrap_items = _classify_bom_items(
            bom_rows, bom_base, total_req_qty, merged_po_prices, source_item_code,
        )

        total_real  = sum(i["line_cost"] for i in real_items)
        total_scrap = sum(i["line_cost"] for i in scrap_items)
        fg_residual = round(total_batch_cost - total_real - total_scrap, 3)

        fg_name_rows = _hana_query(
            f'SELECT "ItemName" FROM {schema}.OITM WHERE "ItemCode" = \'{new_item_code.replace(chr(39), chr(39)*2)}\''
        )
        fg_name = fg_name_rows[0]["ItemName"] if fg_name_rows else new_item_code

        # is_fg=True line is the output item (RMHN0094); user can edit its quantity in Step 2
        fg_items = [{
            "item_code":   new_item_code,
            "item_name":   fg_name,
            "quantity":    total_req_qty,
            "warehouse":   _REAL_WHS,
            "unit_price":  round(fg_residual / total_req_qty, 3) if total_req_qty > 0 else 0,
            "line_cost":   fg_residual,
            "cost_source": "remainder",
            "is_fg":       True,
        }]

        return {
            "success":          True,
            "batch_cost":       total_batch_cost,
            "batch_qty":        total_req_qty,
            "calc_price":       round(total_batch_cost / total_req_qty, 3) if total_req_qty > 0 else 0,
            "source_warehouse": actual_whs,
            "bom_lines":        real_items + fg_items + scrap_items,
            "batches_info":     all_batches_info,
        }

    except Exception as e:
        frappe.log_error(str(e), "Ghee preview_cost_split Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_production_order(
    source_item_code='',
    new_item_code='',
    source_batch_no=None,
    source_qty=None,
    source_warehouse=None,
    new_item_warehouse='HN-WIP',
    doc_date=None,
    remarks=None,
    source_batches=None,
    gpo_name=None,
    bom_lines=None,
):
    """
    Create a SAP B1 Production Order for the reverse ghee flow.

    PO structure:
        Header  — new_item_code (RMHN0094), PlannedQuantity = is_fg qty from Step 2 BOM
        Lines   — one positive-qty input line per source FG item (e.g. FGHN0034)
                  one negative-qty output line per BOM by-product (jar, packaging, waste)

    bom_lines (JSON from Step 2) must include an is_fg=True line whose quantity
    becomes the PO header PlannedQuantity. If not provided, falls back to total source qty.
    """
    source_item_code   = (source_item_code or "").strip()
    new_item_code      = (new_item_code or "").strip()
    new_item_warehouse = (new_item_warehouse or "HN-WIP").strip()
    doc_date           = doc_date or nowdate()

    if not new_item_code:
        return {"success": False, "message": "new_item_code required"}

    raw_batches = _parse_source_batches(source_batches)
    schema      = _hana_schema()

    # --- Resolve source batches: get qty, warehouse, and cost per item group ---
    item_totals      = {}   # {item_code: {qty, warehouse}}
    all_batches_info = []
    merged_po_prices = {}
    total_source_qty = 0.0  # Total FG quantity being issued (drives GI)

    if raw_batches:
        batches_by_grp = _group_batches_by_item(raw_batches, source_item_code)
        for ic, ic_batches in batches_by_grp.items():
            if not ic:
                continue
            try:
                bi, rq, _bc, whs = _resolve_batches(
                    ic_batches, ic, (source_warehouse or "").strip() or None, schema
                )
            except Exception as e:
                return {"success": False, "message": str(e)}
            item_totals[ic] = {"qty": rq, "warehouse": whs}
            total_source_qty += rq
            for b in bi:
                b["item_code"] = ic
            all_batches_info.extend(bi)
        source_batch_no = ", ".join(b["batch_no"] for b in all_batches_info)
    else:
        source_batch_no  = (source_batch_no or "").strip()
        source_warehouse = (source_warehouse or "").strip()
        if not source_item_code or not source_batch_no:
            return {"success": False, "message": "source_item_code + source_batch_no or source_batches required"}
        try:
            total_source_qty = float(source_qty or 1)
        except (TypeError, ValueError):
            return {"success": False, "message": "source_qty must be a number"}
        item_totals = {source_item_code: {"qty": total_source_qty, "warehouse": source_warehouse}}
        all_batches_info = [{"item_code": source_item_code, "batch_no": source_batch_no,
                              "source_qty": total_source_qty, "warehouse": source_warehouse}]

    if total_source_qty <= 0:
        return {"success": False, "message": "source_qty must be > 0"}

    # PO header warehouse = actual source batch warehouse (avoids LocationCode mismatch)
    first_src_whs = next(
        (info["warehouse"] for info in item_totals.values() if info.get("warehouse")), None
    )
    header_whs = first_src_whs or new_item_warehouse or source_warehouse or ""

    # --- Parse BOM lines from Step 2 (includes any user edits) ---
    bom_lines_parsed = None
    if bom_lines:
        bom_lines_parsed = json.loads(bom_lines) if isinstance(bom_lines, str) else (bom_lines or [])

    if bom_lines_parsed is None:
        # Fallback: fetch BOM from SAP and classify (no user edits available)
        bom_rows, bom_base = _fetch_bom(new_item_code, schema)
        if not bom_rows:
            return {"success": False, "message": f"No BOM found for '{new_item_code}' in SAP — add BOM in SAP B1 first"}
        _batches_by_ic = _group_batches_by_item(all_batches_info)
        for _ic, _bi in _batches_by_ic.items():
            merged_po_prices.update(_get_jar_prices_from_batch_po(_bi, _ic, schema))
        real_items, scrap_items = _classify_bom_items(
            bom_rows, bom_base, total_source_qty, merged_po_prices, source_item_code,
        )
        by_product_lines = real_items + scrap_items
    else:
        # Use user-edited BOM lines from Step 2; exclude is_fg (header item handled separately)
        by_product_lines = [l for l in bom_lines_parsed if not l.get("is_fg")]

    # --- Read RMHN0094 planned qty from the is_fg line (user may have edited it in Step 2) ---
    # This qty becomes the PO header PlannedQuantity and the GR receipt quantity.
    # GI (source FG) always uses total_source_qty — it is never changed by Step 2 edits.
    fg_planned_qty = total_source_qty  # Default: same as source qty if no is_fg line found
    if bom_lines_parsed:
        fg_line = next((l for l in bom_lines_parsed if l.get("is_fg")), None)
        if fg_line and float(fg_line.get("quantity") or 0) > 0:
            fg_planned_qty = float(fg_line["quantity"])

    # --- Build WOR1 lines ---
    po_lines = []

    # Input lines: one per source FG item code (positive qty = consume from stock)
    for ic, info in item_totals.items():
        po_lines.append({
            "ItemNo":                   ic,
            "PlannedQuantity":          info["qty"],
            "Warehouse":                info["warehouse"] or header_whs,
            "ProductionOrderIssueType": "im_Manual",
        })

    # By-product output lines (negative qty = received back into stock)
    for line in by_product_lines:
        po_lines.append({
            "ItemNo":                   line["item_code"],
            "PlannedQuantity":          -float(line["quantity"]),
            "Warehouse":                line.get("warehouse") or header_whs,
            "ProductionOrderIssueType": "im_Manual",
        })

    src_codes_str = ", ".join(item_totals.keys())
    payload = {
        "ItemNo":               new_item_code,
        "PlannedQuantity":      fg_planned_qty,   # RMHN0094 qty from Step 2 (user-editable)
        "ProductionOrderType":  "bopotStandard",
        "PostingDate":          str(doc_date),
        "DueDate":              str(doc_date),
        "Warehouse":            header_whs,
        "Remarks":              (remarks or f"Ghee Reverse PO: {src_codes_str} batch {source_batch_no}")[:254],
        "ProductionOrderLines": po_lines,
    }

    try:
        session = AuthenticateSAPB1()
        b1_url  = _b1_url()
        resp, session = _b1_post_with_retry(b1_url + "ProductionOrders", payload, session)

        if resp.status_code not in (200, 201):
            msg = _extract_sap_error(resp)
            frappe.log_error(
                f"SAP PO create failed: {msg}\nPayload: {payload}",
                "Ghee create_production_order",
            )
            _update_gpo(gpo_name, status="Failed", error_message=f"SAP error: {msg}")
            return {"success": False, "message": f"SAP error: {msg}"}

        data       = resp.json()
        po_entry   = data.get("AbsoluteEntry") or data.get("DocEntry")
        po_doc_num = data.get("DocumentNumber", "")

        # Release PO immediately so GI/GR can be posted against it
        patch_resp = session.request(
            "PATCH", b1_url + f"ProductionOrders({po_entry})",
            data=json.dumps({"ProductionOrderStatus": "R"}),
            headers=HEADERS, verify=False,
        )
        if patch_resp.status_code not in (200, 201, 204):
            frappe.log_error(
                f"SAP PO release failed: {patch_resp.text}",
                "Ghee create_production_order",
            )

        _update_gpo(gpo_name, status="PO Created", po_created_at=str(now_datetime()),
                    po_entry=str(po_entry), po_doc_num=str(po_doc_num))
        return {"success": True, "po_entry": po_entry, "po_doc_num": po_doc_num}

    except Exception as e:
        frappe.log_error(str(e), "Ghee create_production_order Error")
        _update_gpo(gpo_name, status="Failed", error_message=str(e))
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def complete_production_order(
    po_entry,
    po_doc_num,
    source_item_code,
    source_batch_no=None,
    source_qty=None,
    source_warehouse=None,
    doc_date=None,
    source_batches=None,
    new_item_batch_no=None,
    new_item_warehouse=None,
    output_batches=None,
    gpo_name=None,
    bom_lines=None,
):
    """
    Complete the reverse production — posts GI, GR, and closes the PO.

    Steps:
        1. Fetch PO from SAP (get new_item_code, WOR1 line numbers, idempotency UDFs)
        2. Resolve source batch costs (from live OBTQ if GI pending, or OBTN if GI done)
        3. Compute cost split using Step 2 BOM lines (user-edited values respected)
        4. POST InventoryGenExits  — issue source FG batch(es), linked to PO
        5. POST InventoryGenEntries — receive RMHN0094 + all by-products, linked to PO
        6. PATCH ProductionOrders  — stamp UDF links, close PO
        7. HANA jugad              — correct RMHN0094 price post-posting

    Quantity rules:
        GI quantity   = total_source_qty (sum of user-selected batch qtys, never changed)
        GR quantity   = fg_planned_qty (is_fg line qty from Step 2, user may have edited)
        fg_unit_price = fg_residual / fg_planned_qty
    """
    doc_date = doc_date or nowdate()

    # Parse output_batches: JSON string or dict → {item_code: batch_no}
    if isinstance(output_batches, str):
        output_batches = json.loads(output_batches) if output_batches else {}
    output_batches = output_batches or {}

    # Auto-generate RMHN0094 batch number if not provided
    _date_sfx = nowdate().replace("-", "")[2:]  # YYMMDD
    if not new_item_batch_no:
        new_item_batch_no = f"RMH-{po_doc_num}-{_date_sfx}"
    output_batches.setdefault("__fg__", new_item_batch_no)

    try:
        po_entry = int(po_entry)
    except (TypeError, ValueError) as e:
        return {"success": False, "message": f"Invalid po_entry: {e}"}

    raw_batches = _parse_source_batches(source_batches)
    schema      = _hana_schema()

    try:
        # Commit before long SAP calls to avoid MariaDB lock wait timeout (1205)
        frappe.db.commit()

        session = _no_pool_session(renew_sap_session())
        session.headers['Connection'] = 'close'
        b1_url  = _b1_url()

        # --- Step 1: Fetch PO to get new_item_code, WOR1 line numbers, idempotency UDFs ---
        frappe.log_error(f"GPO step: fetching PO {po_entry}", "Ghee CPO step")
        po_resp = session.request(
            "GET", b1_url + f"ProductionOrders({po_entry})",
            headers=HEADERS, verify=False,
        )
        if po_resp.status_code not in (200, 201):
            return {"success": False, "step": "fetch_po",
                    "message": f"Could not fetch PO: {_extract_sap_error(po_resp)}"}
        po_data = po_resp.json()

        new_item_code = po_data.get("ItemNo") or ""
        if not new_item_code:
            return {"success": False, "message": "Could not determine new_item_code from PO"}

        # Fetch RMHN0094 item name for GPO record
        fg_item_name = ""
        try:
            _fn_rows = _hana_query(
                f'SELECT "ItemName" FROM {schema}.OITM WHERE "ItemCode" = \'{new_item_code.replace(chr(39), chr(39)+chr(39))}\''
            )
            fg_item_name = str(_fn_rows[0]["ItemName"]) if _fn_rows else ""
        except Exception:
            pass

        # Read idempotency UDFs — if GI/GR already posted we skip re-posting
        existing_gi_entry = po_data.get("U_GIEnt")
        existing_gi_doc   = po_data.get("U_GINo")
        existing_gr_entry = po_data.get("U_GREnt")
        existing_gr_doc   = po_data.get("U_GRNo")

        # WOR1 lines: map item_code → line number for GI/GR BaseLine linking
        wor1_lines = po_data.get("ProductionOrderLines", [])
        item_to_base_line = {
            ln["ItemNo"]: ln["LineNumber"]
            for ln in wor1_lines
            if float(ln.get("PlannedQuantity", 0)) < 0  # By-product lines (negative)
        }
        item_to_src_wor1_line = {
            ln["ItemNo"]: ln["LineNumber"]
            for ln in wor1_lines
            if float(ln.get("PlannedQuantity", 0)) > 0  # Input FG lines (positive)
        }

        # --- Step 2: Resolve source batch costs ---
        gi_already_done = bool(existing_gi_entry and str(existing_gi_entry).strip() not in ("", "0"))

        if gi_already_done:
            # GI already posted — source batches consumed; read cost from OBTN (batch ledger)
            gi_entry = int(existing_gi_entry)
            gi_doc   = int(existing_gi_doc) if existing_gi_doc else gi_entry

            all_batches_info = []
            if raw_batches:
                for b in raw_batches:
                    ic = (b.get("item_code") or source_item_code or "").strip()
                    all_batches_info.append({
                        "item_code":  ic,
                        "batch_no":   (b.get("batch_no") or "").strip(),
                        "source_qty": float(b.get("source_qty") or 0),
                        "warehouse":  (b.get("warehouse") or source_warehouse or "").strip(),
                    })
            else:
                source_batch_no = (source_batch_no or "").strip()
                try:
                    _sq = float(source_qty or 0)
                except (TypeError, ValueError):
                    _sq = 0
                all_batches_info = [{
                    "item_code":  source_item_code,
                    "batch_no":   source_batch_no,
                    "source_qty": _sq,
                    "warehouse":  (source_warehouse or "").strip(),
                }]

            total_source_qty = sum(b["source_qty"] for b in all_batches_info)
            first_whs = all_batches_info[0]["warehouse"] if all_batches_info else (source_warehouse or "")

            # Compute cost from OBTN (OBTQ qty = 0 post-GI but OBTN retains cost history)
            running_cost = 0.0
            for b in all_batches_info:
                ic_esc = b["item_code"].replace("'", "''")
                bn_esc = b["batch_no"].replace("'", "''")
                obn = _hana_query(f"""
                    SELECT COALESCE("CostTotal", 0) AS "CT",
                           COALESCE("Quantity", 0)  AS "BQ"
                    FROM {schema}.OBTN
                    WHERE "ItemCode" = '{ic_esc}' AND "DistNumber" = '{bn_esc}'
                """)
                if obn:
                    ct = float(obn[0]["CT"] or 0)
                    bq = float(obn[0]["BQ"] or 1)
                    cp = round(ct / bq, 3) if bq > 0 else 0
                else:
                    cp = 0
                b["calc_price"] = cp
                running_cost += b["source_qty"] * cp
            total_batch_cost = round(running_cost, 3)

        else:
            # GI not yet posted — resolve from live OBTQ stock
            all_batches_info = []
            total_source_qty = 0.0
            total_batch_cost = 0.0
            first_whs        = (source_warehouse or "").strip()

            if raw_batches:
                for ic, ic_batches in _group_batches_by_item(raw_batches, source_item_code).items():
                    if not ic:
                        continue
                    try:
                        bi, rq, bc, whs = _resolve_batches(
                            ic_batches, ic, (source_warehouse or "").strip() or None, schema
                        )
                    except Exception as e:
                        return {"success": False, "message": str(e)}
                    for b in bi:
                        b["item_code"] = ic
                    all_batches_info.extend(bi)
                    total_source_qty += rq
                    total_batch_cost += bc
                    first_whs = first_whs or whs
                total_batch_cost = round(total_batch_cost, 3)
            else:
                source_batch_no  = (source_batch_no or "").strip()
                source_warehouse = (source_warehouse or "").strip()
                if not source_batch_no:
                    return {"success": False, "message": "source_batch_no or source_batches required"}
                try:
                    total_source_qty = float(source_qty or 0)
                except (TypeError, ValueError):
                    return {"success": False, "message": "source_qty must be a number"}
                src    = source_item_code.replace("'", "''")
                bn_esc = source_batch_no.replace("'", "''")
                rows   = _hana_query(f"""
                    SELECT T0."WhsCode",
                           COALESCE(T1."CostTotal", 0) AS "CostTotal",
                           COALESCE(T1."Quantity", 0)  AS "BatchTotalQty"
                    FROM {schema}.OBTQ T0
                    LEFT JOIN {schema}.OBTN T1
                        ON T1."ItemCode" = T0."ItemCode" AND T0."SysNumber" = T1."SysNumber"
                    WHERE T0."ItemCode" = '{src}' AND T1."DistNumber" = '{bn_esc}'
                      AND T0."Quantity" > 0
                """)[:1]
                if rows:
                    ct  = float(rows[0]["CostTotal"] or 0)
                    btq = float(rows[0]["BatchTotalQty"] or 1)
                    cp  = round(ct / btq, 3) if btq > 0 else 0
                    first_whs = rows[0]["WhsCode"] or source_warehouse
                else:
                    cp, first_whs = 0, source_warehouse
                all_batches_info = [{
                    "item_code":  source_item_code,
                    "batch_no":   source_batch_no,
                    "source_qty": total_source_qty,
                    "warehouse":  first_whs,
                    "calc_price": cp,
                }]
                total_batch_cost = round(total_source_qty * cp, 3)

        if total_source_qty <= 0:
            return {"success": False, "message": "source_qty must be > 0"}

        # --- Step 3: Cost split — use Step 2 BOM lines if provided (includes user edits) ---
        _bom_parsed = None
        if bom_lines:
            _bom_parsed = json.loads(bom_lines) if isinstance(bom_lines, str) else (bom_lines or [])

        if _bom_parsed is not None:
            # Step 2 BOM lines provided: separate by-products from the is_fg output line
            real_items  = [l for l in _bom_parsed if not l.get("is_fg") and _SCRAP_WHS not in (l.get("warehouse") or "")]
            scrap_items = [l for l in _bom_parsed if not l.get("is_fg") and _SCRAP_WHS in (l.get("warehouse") or "")]
        else:
            # Fallback: re-fetch BOM from SAP and classify
            bom_rows, bom_base = _fetch_bom(new_item_code, schema)
            if not bom_rows:
                return {"success": False, "message": f"No BOM found for '{new_item_code}' in SAP — add BOM in SAP B1 first"}
            merged_po_prices = {}
            _batches_by_ic2  = _group_batches_by_item(all_batches_info)
            for _ic, _bi in _batches_by_ic2.items():
                merged_po_prices.update(_get_jar_prices_from_batch_po(_bi, _ic, schema))
            real_items, scrap_items = _classify_bom_items(
                bom_rows, bom_base, total_source_qty, merged_po_prices, source_item_code,
            )

        # --- Read RMHN0094 planned qty from is_fg line (user may have edited it in Step 2) ---
        # GI uses total_source_qty (FG issued); GR uses fg_planned_qty (raw ghee received).
        # These differ only if the user explicitly changed the is_fg qty in Step 2.
        fg_planned_qty = total_source_qty  # Default if no is_fg line in bom_lines
        if _bom_parsed:
            fg_line = next((l for l in _bom_parsed if l.get("is_fg")), None)
            if fg_line and float(fg_line.get("quantity") or 0) > 0:
                fg_planned_qty = float(fg_line["quantity"])

        # Auto-fill output batch numbers for any by-product not given one
        for _item in real_items + scrap_items:
            ic = _item["item_code"]
            if not output_batches.get(ic):
                output_batches[ic] = f"{ic[:6]}-{po_doc_num}-{_date_sfx}"

        # Recalculate line_cost from unit_price × quantity — frontend line_cost may be stale
        # (e.g. user edited qty in Step 2 without clicking Save, leaving old line_cost from
        # a preview that used a different source qty or BOM base)
        for _item in real_items + scrap_items:
            _item["line_cost"] = round(
                float(_item.get("quantity") or 0) * float(_item.get("unit_price") or 0), 3
            )

        # Cost split: jar gets actual price, scrap gets 0.01, RMHN0094 gets remainder
        total_real    = sum(i["line_cost"] for i in real_items)
        total_scrap   = sum(i["line_cost"] for i in scrap_items)
        fg_residual   = round(total_batch_cost - total_real - total_scrap, 3)

        # Unit price uses fg_planned_qty (not total_source_qty) so per-unit is accurate
        fg_unit_price = max(round(fg_residual / fg_planned_qty, 3) if fg_planned_qty > 0 else 0, 0)

        recv_whs = _REAL_WHS  # RMHN0094 always goes to HN-WIP

        # --- Step 4: Goods Issue — issue source FG batch(es), linked to PO ---
        if gi_already_done:
            pass  # gi_entry, gi_doc already set from PO UDFs above
        else:
            # One GI line per (item_code × warehouse) group
            all_gi_lines = []
            for ic, ic_batches in _group_batches_by_item(all_batches_info).items():
                wor1_line_for_ic = item_to_src_wor1_line.get(ic, 0)
                ic_whs_groups    = defaultdict(list)
                for b in ic_batches:
                    ic_whs_groups[b["warehouse"]].append(b)
                for whs, whs_batches in ic_whs_groups.items():
                    all_gi_lines.append({
                        "Quantity":      sum(b["source_qty"] for b in whs_batches),
                        "WarehouseCode": whs,
                        "BaseType":      202,
                        "BaseEntry":     po_entry,
                        "BaseLine":      wor1_line_for_ic,
                        "BatchNumbers":  [
                            {"BatchNumber": b["batch_no"], "Quantity": b["source_qty"]}
                            for b in whs_batches
                        ],
                    })

            gi_entry = gi_doc = None
            frappe.log_error(
                f"GPO step: posting GI for PO {po_entry} ({len(all_gi_lines)} lines)", "Ghee CPO step"
            )
            _gi_resp, session = _b1_post_with_retry(
                b1_url + "InventoryGenExits",
                {
                    "DocDate":       str(doc_date),
                    "JournalMemo":   f"Reverse PO {po_doc_num} - Goods Issue",
                    "DocObjectCode": "oInventoryGenExit",
                    "DocumentLines": all_gi_lines,
                },
                session,
            )
            if _gi_resp.status_code not in (200, 201):
                return {"success": False, "step": "goods_issue",
                        "message": f"GI failed: {_extract_sap_error(_gi_resp)}"}
            _gid     = _gi_resp.json()
            gi_entry = _gid.get("DocEntry")
            gi_doc   = _gid.get("DocNum") or gi_entry

            # Stamp GI entry on PO so retries skip re-posting
            session.request(
                "PATCH", b1_url + f"ProductionOrders({po_entry})",
                data=json.dumps({"U_GINo": int(gi_doc), "U_GIEnt": int(gi_entry)}),
                headers=HEADERS, verify=False,
            )
            _update_gpo(gpo_name, status="GI Done", gi_done_at=str(now_datetime()),
                        goods_issue_doc=str(gi_doc))

            # Stamp issued batch number on each input WOR1 line (U_IssBatch UDF)
            for _ic, _src_ln in item_to_src_wor1_line.items():
                _ic_batches = [b["batch_no"] for b in all_batches_info if b.get("item_code") == _ic and b.get("batch_no")]
                _batch_str  = ",".join(_ic_batches)[:50]
                session.request(
                    "PATCH", b1_url + f"ProductionOrders({po_entry})",
                    data=json.dumps({"ProductionOrderLines": [{"LineNumber": _src_ln, "U_IssBatch": _batch_str}]}),
                    headers=HEADERS, verify=False,
                )

        # --- Step 5: Goods Receipt — one combined GR for RMHN0094 + all by-products ---
        # All lines linked to the PO via BaseType=202.
        # RMHN0094 (header item) has no BaseLine; by-products use their WOR1 BaseLine.
        # SAP closes the PO when all receipts are in one document.
        gr1_entry = gr1_doc = None
        if existing_gr_entry and str(existing_gr_entry).strip() not in ("", "0"):
            gr1_entry = int(existing_gr_entry)
            gr1_doc   = int(existing_gr_doc) if existing_gr_doc else gr1_entry

        if gr1_entry is None:
            # Line 0: RMHN0094 (output raw ghee) — quantity from Step 2 is_fg line
            gr_lines = [{
                "Quantity":      fg_planned_qty,   # User-edited RMHN0094 qty from Step 2
                "WarehouseCode": recv_whs,
                "BaseType":      202,
                "BaseEntry":     po_entry,
            }]
            if new_item_batch_no:
                gr_lines[0]["BatchNumbers"] = [{"BatchNumber": new_item_batch_no, "Quantity": fg_planned_qty}]

            # By-product lines — each linked to its WOR1 line via BaseLine
            for item in real_items + scrap_items:
                base_line = item_to_base_line.get(item["item_code"])
                if base_line is None:
                    frappe.log_error(
                        f"GR: no WOR1 BaseLine for {item['item_code']} in PO {po_entry} — skipping",
                        "Ghee complete_production_order",
                    )
                    continue
                gr_line = {
                    "Quantity":      item["quantity"],
                    "UnitPrice":     item["unit_price"],
                    "WarehouseCode": item["warehouse"],
                    "BaseType":      202,
                    "BaseEntry":     po_entry,
                    "BaseLine":      base_line,
                }
                item_batch = output_batches.get(item["item_code"], "")
                if item_batch:
                    gr_line["BatchNumbers"] = [{"BatchNumber": item_batch, "Quantity": item["quantity"]}]
                    if item["warehouse"] == _SCRAP_WHS:
                        # Scrap warehouse is bin-activated — must specify bin location
                        gr_line["BinAllocations"] = [{
                            "BinAbsEntry":           _SCRAP_BIN_ABS,
                            "Quantity":              item["quantity"],
                            "BaseLineNumber":        0,
                            "AllowNegativeQuantity": "tNO",
                        }]
                gr_lines.append(gr_line)

            frappe.log_error(f"GPO step: posting GR for PO {po_entry}", "Ghee CPO step")
            gr_resp, session = _b1_post_with_retry(
                b1_url + "InventoryGenEntries",
                {
                    "DocDate":       str(doc_date),
                    "JournalMemo":   f"Reverse PO {po_doc_num} - Goods Receipt",
                    "DocObjectCode": "oInventoryGenEntry",
                    "DocumentLines": gr_lines,
                },
                session,
            )
            if gr_resp.status_code not in (200, 201):
                return {"success": False, "step": "goods_receipt_1",
                        "message": f"GR failed: {_extract_sap_error(gr_resp)}"}
            gr_data   = gr_resp.json()
            gr1_entry = gr_data.get("DocEntry")
            gr1_doc   = gr_data.get("DocNum") or gr1_entry

            # Stamp GR entry on PO so retries skip re-posting
            session.request(
                "PATCH", b1_url + f"ProductionOrders({po_entry})",
                data=json.dumps({
                    "U_GRNo":  int(gr1_doc)   if gr1_doc   else 0,
                    "U_GREnt": int(gr1_entry) if gr1_entry else 0,
                }),
                headers=HEADERS, verify=False,
            )
            _update_gpo(gpo_name, status="GR Done", gr_done_at=str(now_datetime()),
                        goods_receipt_doc=str(gr1_doc))

            # Stamp output batch + GR price on each by-product WOR1 line (U_IssBatch, U_GRPrice UDFs)
            _wor1_gr_updates = []
            for _item in real_items + scrap_items:
                _ln = item_to_base_line.get(_item["item_code"])
                if _ln is not None:
                    _batch = output_batches.get(_item["item_code"], "")
                    _wor1_gr_updates.append({
                        "LineNumber": _ln,
                        "U_IssBatch": (_batch or "")[:50],
                        "U_GRPrice":  round(float(_item["unit_price"]), 3),
                    })
            if _wor1_gr_updates:
                session.request(
                    "PATCH", b1_url + f"ProductionOrders({po_entry})",
                    data=json.dumps({"ProductionOrderLines": _wor1_gr_updates}),
                    headers=HEADERS, verify=False,
                )

        # --- Step 6: Close PO — must happen BEFORE HANA price jugad ---
        # _fix_gr_rmhn_price patches JDT1 directly; SAP validates on close and sees
        # inconsistency if the jugad runs first while the PO is still open.
        all_src_batches = ", ".join(b["batch_no"] for b in all_batches_info)
        udf_resp = session.request(
            "PATCH", b1_url + f"ProductionOrders({po_entry})",
            data=json.dumps({
                "U_GINo":     int(gi_doc)    if gi_doc    else 0,
                "U_GIEnt":    int(gi_entry)  if gi_entry  else 0,
                "U_GRNo":     int(gr1_doc)   if gr1_doc   else 0,
                "U_GREnt":    int(gr1_entry) if gr1_entry else 0,
                "U_RecBatch": all_src_batches[:50],
            }),
            headers=HEADERS, verify=False,
        )
        if udf_resp.status_code not in (200, 201, 204):
            frappe.log_error(f"PO UDF stamp failed: {udf_resp.text}", "Ghee complete_production_order")

        close_resp = session.request(
            "PATCH", b1_url + f"ProductionOrders({po_entry})",
            data=json.dumps({"ProductionOrderStatus": "boposClosed"}),
            headers=HEADERS, verify=False,
        )
        if close_resp.status_code not in (200, 201, 204):
            frappe.log_error(f"PO close failed: {close_resp.text}", "Ghee complete_production_order")

        # --- Step 7: HANA jugad — correct RMHN0094 price in GR after posting ---
        # SAP uses moving average for RMHN0094 on receipt; we overwrite with fg_residual
        # so that GR total == GI total (cost conservation).
        _fix_gr_rmhn_price(schema, gr1_entry, fg_unit_price, fg_residual, new_item_batch_no)

        total_gr_cost = round(total_real + total_scrap + fg_residual, 3)
        po_closed     = close_resp.status_code in (200, 201, 204)

        # --- Build GPO cost breakdown for the child table (items) ---
        _gpo_items = []
        for it in real_items + scrap_items:
            _gpo_items.append({
                "item_code":   it["item_code"],
                "item_name":   it.get("item_name", ""),
                "quantity":    it["quantity"],
                "unit_price":  it["unit_price"],
                "line_cost":   it["line_cost"],
                "warehouse":   it["warehouse"],
                "batch_no":    output_batches.get(it["item_code"], ""),
                "cost_source": it.get("cost_source", ""),
            })
        # RMHN0094 as the residual cost line
        _gpo_items.append({
            "item_code":   new_item_code,
            "item_name":   fg_item_name,
            "quantity":    fg_planned_qty,      # User-edited qty from Step 2
            "unit_price":  fg_unit_price,
            "line_cost":   fg_residual,
            "warehouse":   recv_whs,
            "batch_no":    new_item_batch_no or "",
            "cost_source": "remainder",
        })

        # Build definitive cost_split_json from actual GR data (not stale frontend preview)
        _actual_bom_lines = []
        for it in real_items + scrap_items:
            _actual_bom_lines.append({
                "item_code":   it["item_code"],
                "item_name":   it.get("item_name", ""),
                "quantity":    it["quantity"],
                "unit_price":  it["unit_price"],
                "line_cost":   round(it["unit_price"] * it["quantity"], 3),
                "warehouse":   it["warehouse"],
                "is_fg":       False,
                "cost_source": it.get("cost_source", ""),
            })
        _actual_bom_lines.append({
            "item_code":   new_item_code,
            "item_name":   fg_item_name,
            "quantity":    fg_planned_qty,      # User-edited qty from Step 2
            "unit_price":  fg_unit_price,
            "line_cost":   fg_residual,
            "warehouse":   recv_whs,
            "is_fg":       True,
            "cost_source": "remainder",
        })
        _actual_cost_split = json.dumps({
            "batch_cost": total_batch_cost,
            "batch_qty":  total_source_qty,
            "bom_lines":  _actual_bom_lines,
        })

        _update_gpo(
            gpo_name,
            status="Completed",
            completed_at=str(now_datetime()),
            po_closed=1 if po_closed else 0,
            total_gi_cost=total_batch_cost,
            total_gr_cost=total_gr_cost,
            jar_cost=total_real,
            scrap_cost=total_scrap,
            fg_residual=fg_residual,
            cost_split_json=_actual_cost_split,
            error_message="",
            items=_gpo_items,
        )

        return {
            "success":             True,
            "goods_issue_doc":     gi_doc,
            "goods_receipt_doc":   gr1_doc,
            "goods_receipt_2_doc": gr1_doc,
            "po_closed":           po_closed,
            "cost_summary": {
                "total_gi_cost": total_batch_cost,
                "jar_cost":      total_real,
                "scrap_cost":    total_scrap,
                "fg_residual":   fg_residual,
                "total_gr_cost": total_gr_cost,
                "balanced":      abs(total_gr_cost - total_batch_cost) < 0.01,
            },
        }

    except Exception as e:
        tb = traceback.format_exc()
        frappe.log_error(tb, "Ghee complete_production_order Error")
        _update_gpo(gpo_name, status="Failed", error_message=str(e))
        return {"success": False, "message": str(e)}


# ---------------------------------------------------------------------------
# Ghee Production Order — persistent state machine (all orders saved here)
# ---------------------------------------------------------------------------

def _update_gpo(gpo_name, items=None, **fields):
    """Update GPO doc fields and optional items child table. Silent if gpo_name is empty."""
    if not gpo_name:
        return
    try:
        doc = frappe.get_doc("Ghee Production Order", gpo_name)
        for field, value in fields.items():
            if value is not None:
                setattr(doc, field, value)
        if items is not None:
            doc.set("items", [])
            for row in items:
                doc.append("items", row)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as exc:
        frappe.log_error(str(exc), f"_update_gpo({gpo_name}) failed")


@frappe.whitelist()
def save_production_order(
    name=None,
    status=None,
    current_step=None,
    source_item_code=None,
    new_item_code=None,
    doc_date=None,
    new_item_warehouse=None,
    remarks=None,
    selected_batches_json=None,
    output_batch_nos_json=None,
    cost_split_json=None,
    po_entry=None,
    po_doc_num=None,
    goods_issue_doc=None,
    goods_receipt_doc=None,
    po_closed=None,
    error_message=None,
):
    """Create or update a Ghee Production Order. Records persist forever (no delete)."""
    if name:
        doc = frappe.get_doc("Ghee Production Order", name)
    else:
        doc = frappe.new_doc("Ghee Production Order")

    scalar_fields = {
        "status":                status,
        "current_step":          current_step,
        "source_item_code":      source_item_code,
        "new_item_code":         new_item_code,
        "doc_date":              doc_date,
        "new_item_warehouse":    new_item_warehouse,
        "remarks":               remarks,
        "selected_batches_json": selected_batches_json,
        "output_batch_nos_json": output_batch_nos_json,
        "cost_split_json":       cost_split_json,
        "po_entry":              str(po_entry) if po_entry is not None else None,
        "po_doc_num":            str(po_doc_num) if po_doc_num is not None else None,
        "goods_issue_doc":       goods_issue_doc,
        "goods_receipt_doc":     goods_receipt_doc,
        "po_closed":             po_closed,
        "error_message":         error_message,
    }
    for field, value in scalar_fields.items():
        if value is not None:
            setattr(doc, field, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def get_production_order(name):
    """Return a single Ghee Production Order with all fields including items child table."""
    rows = frappe.db.sql(
        "SELECT * FROM `tabGhee Production Order` WHERE name = %s LIMIT 1",
        (name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(f"Ghee Production Order {name} not found", frappe.DoesNotExistError)
    doc = rows[0]
    doc["items"] = frappe.db.sql(
        "SELECT * FROM `tabGhee Production Order Item` WHERE parent = %s ORDER BY idx",
        (name,),
        as_dict=True,
    )
    doc["source_batches"] = []
    return doc


@frappe.whitelist()
def get_all_production_orders(from_date=None, to_date=None, status=None):
    """Return Ghee Production Orders for the dashboard, newest first."""
    filters = []
    values  = []
    if status:
        filters.append("status = %s")
        values.append(status)
    if from_date:
        filters.append("doc_date >= %s")
        values.append(from_date)
    if to_date:
        filters.append("doc_date <= %s")
        values.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = frappe.db.sql(
        f"""
        SELECT name, owner, status, current_step,
               source_item_code, new_item_code,
               po_entry, po_doc_num,
               goods_issue_doc, goods_receipt_doc, po_closed,
               total_gi_cost, total_gr_cost, fg_residual,
               po_created_at, gi_done_at, gr_done_at, completed_at,
               error_message, doc_date, modified
        FROM `tabGhee Production Order`
        {where}
        ORDER BY modified DESC
        LIMIT 500
        """,
        tuple(values) if values else (),
        as_dict=True,
    )
    return {"success": True, "orders": rows}


# ---------------------------------------------------------------------------
# Legacy draft endpoints — kept for backward compatibility with older clients
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_active_ghee_draft():
    user = frappe.session.user
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabGhee Production Draft`
        WHERE owner = %s AND status != 'Completed'
        ORDER BY modified DESC LIMIT 1
        """,
        (user,),
        as_dict=True,
    )
    if not rows:
        return None
    doc = frappe.get_doc("Ghee Production Draft", rows[0]["name"])
    return doc.as_dict()


@frappe.whitelist()
def save_ghee_draft(
    name=None, status=None, current_step=None, source_item_code=None,
    new_item_code=None, doc_date=None, new_item_warehouse=None, remarks=None,
    selected_batches_json=None, output_batch_nos_json=None, cost_split_json=None,
    po_entry=None, po_doc_num=None, goods_issue_doc=None, goods_receipt_doc=None,
    goods_receipt_2_doc=None, po_closed=None, cost_summary_json=None, error_message=None,
):
    if name:
        doc = frappe.get_doc("Ghee Production Draft", name)
    else:
        doc = frappe.new_doc("Ghee Production Draft")

    fields = {
        "status": status, "current_step": current_step,
        "source_item_code": source_item_code, "new_item_code": new_item_code,
        "doc_date": doc_date, "new_item_warehouse": new_item_warehouse,
        "remarks": remarks, "selected_batches_json": selected_batches_json,
        "output_batch_nos_json": output_batch_nos_json, "cost_split_json": cost_split_json,
        "po_entry": str(po_entry) if po_entry is not None else None,
        "po_doc_num": str(po_doc_num) if po_doc_num is not None else None,
        "goods_issue_doc": goods_issue_doc, "goods_receipt_doc": goods_receipt_doc,
        "goods_receipt_2_doc": goods_receipt_2_doc, "po_closed": po_closed,
        "cost_summary_json": cost_summary_json, "error_message": error_message,
    }
    for field, value in fields.items():
        if value is not None:
            setattr(doc, field, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def delete_ghee_draft(name):
    frappe.delete_doc("Ghee Production Draft", name, ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def get_all_ghee_drafts():
    rows = frappe.db.sql(
        """
        SELECT name, owner, status, current_step,
               source_item_code, new_item_code,
               po_entry, po_doc_num,
               goods_issue_doc, goods_receipt_doc, po_closed,
               modified, error_message
        FROM `tabGhee Production Draft`
        ORDER BY modified DESC
        LIMIT 200
        """,
        as_dict=True,
    )
    return {"success": True, "drafts": rows}


@frappe.whitelist()
def get_ghee_draft(name):
    doc = frappe.get_doc("Ghee Production Draft", name)
    return doc.as_dict()


@frappe.whitelist()
def migrate_ghee_drafts():
    """One-time migration: copy Ghee Production Draft records to Ghee Production Order."""
    drafts = frappe.db.sql(
        "SELECT * FROM `tabGhee Production Draft` ORDER BY creation ASC",
        as_dict=True,
    )
    migrated = skipped = 0
    for d in drafts:
        try:
            doc = frappe.new_doc("Ghee Production Order")
            for f in ("status", "current_step", "source_item_code", "new_item_code",
                      "doc_date", "new_item_warehouse", "remarks",
                      "selected_batches_json", "output_batch_nos_json", "cost_split_json",
                      "po_entry", "po_doc_num", "goods_issue_doc", "goods_receipt_doc",
                      "po_closed", "error_message"):
                if d.get(f) is not None:
                    setattr(doc, f, d[f])
            if doc.status == "Error":
                doc.status = "Failed"
            doc.save(ignore_permissions=True)
            migrated += 1
        except Exception as exc:
            frappe.log_error(str(exc), f"migrate_ghee_drafts: {d.get('name')}")
            skipped += 1

    frappe.db.commit()
    return {"success": True, "migrated": migrated, "skipped": skipped}
