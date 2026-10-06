"""FEFO batch allocation from INC HANA for Amazon US (AMZ-FBA warehouse)."""
import frappe


class HanaUnavailableError(Exception):
    """HANA unreachable or misconfigured. Callers must NOT mark orders failed — leave ready for retry."""


def _get_schema():
    return (frappe.db.get_single_value("INC SAP Settings", "hana_schema") or "").strip()


def _connect():
    """Return (conn, cursor) for INC HANA. Returns (None, None) on any failure."""
    try:
        import hdbcli.dbapi as hana_db
    except ImportError:
        frappe.log_error("hdbcli not installed; FEFO unavailable.", "Amazon US HANA")
        return None, None

    try:
        doc = frappe.get_doc("INC SAP Settings")
        host = (getattr(doc, "hana_host", None) or "").strip()
        port = int(getattr(doc, "hana_port", None) or 30015)
        user = (getattr(doc, "hana_user", None) or "").strip()
        password = doc.get_password("hana_password") or ""
        schema = _get_schema()

        if not all([host, user, password, schema]):
            frappe.log_error("INC SAP Settings HANA fields incomplete.", "Amazon US HANA")
            return None, None

        conn = hana_db.connect(address=host, port=port, user=user, password=password, autocommit=False)
        return conn, conn.cursor()
    except Exception as e:
        frappe.log_error(f"HANA connection failed: {e}", "Amazon US HANA")
        return None, None


def _close(conn, cursor):
    try:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    except Exception:
        pass


def resolve_acct_code(format_code: str) -> str:
    """Return OACT.AcctCode for a given GL FormatCode (hyphens stripped).

    SAP B1 Service Layer requires the internal AcctCode (e.g. _SYS00000000059),
    not the display FormatCode (e.g. 22200000-01-001-01). Falls back to the
    original value if HANA is unavailable or the code is not found.
    """
    schema = _get_schema()
    if not schema or not format_code:
        return format_code

    stripped = format_code.replace("-", "")
    conn, cursor = _connect()
    if not conn:
        return format_code

    try:
        cursor.execute(
            'SELECT "AcctCode" FROM "' + schema + '"."OACT" WHERE "FormatCode" = ?',
            [stripped],
        )
        row = cursor.fetchone()
        return str(row[0]).strip() if row else format_code
    except Exception as e:
        frappe.log_error(f"resolve_acct_code failed for {format_code}: {e}", "Amazon US HANA")
        return format_code
    finally:
        _close(conn, cursor)


def open_connection():
    """
    Open one HANA connection for a batch of FEFO lookups. Caller owns it and
    must close it with _close() when done (a whole posting run reuses this
    one connection instead of reconnecting per line item).
    Raises HanaUnavailableError if HANA is unreachable.
    """
    schema = _get_schema()
    if not schema:
        raise HanaUnavailableError("HANA schema not configured in INC SAP Settings")

    conn, cursor = _connect()
    if not conn:
        raise HanaUnavailableError("HANA connection failed — check INC SAP Settings and error log")

    return conn, cursor


def allocate_batches_fefo(cursor, item_code, required_qty, warehouse="AMZ-FBA"):
    """
    FEFO batch allocation for item_code from warehouse, over an already-open
    HANA cursor (see open_connection) — a posting run opens one connection
    and reuses it for every line, instead of reconnecting per line item.
    Returns list of {"BatchNumber": str, "Quantity": float} until required_qty filled.
    Returns [] if item has no batch records (not batch-managed); caller omits BatchNumbers key.
    Raises HanaUnavailableError if the query fails (connection dropped mid-batch) —
    callers must NOT mark orders failed.
    Raises ValueError if HANA is reachable but available stock < required_qty.
    """
    schema = _get_schema()
    try:
        query = f"""
            SELECT
                T1."DistNumber"  AS "BatchNumber",
                T0."Quantity"    AS "AvailQty"
            FROM "{schema}"."OBTQ" T0
            JOIN "{schema}"."OBTN" T1
                ON T0."ItemCode"   = T1."ItemCode"
               AND T0."SysNumber"  = T1."SysNumber"
            WHERE
                T0."ItemCode" = ?
                AND T0."WhsCode" = ?
                AND T0."Quantity" > 0
            ORDER BY
                T1."ExpDate" ASC NULLS LAST,
                T1."InDate"  ASC
        """
        cursor.execute(query, [item_code, warehouse])
        rows = cursor.fetchall() or []
    except Exception as e:
        frappe.log_error(f"FEFO query failed for {item_code}: {e}", "Amazon US HANA")
        raise HanaUnavailableError(f"FEFO query failed for {item_code}: {e}")

    if not rows:
        return []

    allocated = []
    remaining = float(required_qty)

    for row in rows:
        if remaining <= 0:
            break
        batch_no = str(row[0]).strip()
        avail = float(row[1] or 0)
        if avail <= 0:
            continue
        take = min(avail, remaining)
        allocated.append({"BatchNumber": batch_no, "Quantity": take})
        remaining -= take

    if round(remaining, 3) > 0:
        total_avail = sum(float(r[1] or 0) for r in rows)
        raise ValueError(
            f"Insufficient stock for {item_code} in {warehouse}: "
            f"need {required_qty}, available {total_avail:.2f}"
        )

    return allocated
