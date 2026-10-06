"""
Inventory Dashboard API
Provides endpoints for the Inventory Reports dashboard in kiosk-frontend (admin panel).

Design goals:
- Read-only SAP HANA access (SELECT-only queries via SAPConnector)
- Parameterized SQL only (use '?' placeholders)
- Server-side admin enforcement (never trust only the frontend)
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from khanal_tech_integrations.api.common.sap_connector import SAPConnector
from khanal_tech_integrations.queries.inventory import QUERY_REGISTRY


# -----------------------------
# Security helpers
# -----------------------------

_ADMIN_ROLES = {"System Administrator", "Administrator", "System Manager"}


def _require_admin():
    """Raise if the current user is not an admin."""
    user = frappe.session.user
    if user == "Administrator":
        return
    roles = set(frappe.get_roles(user) or [])
    if roles.intersection(_ADMIN_ROLES):
        return

    # Kiosk-specific: some users may get admin access via User Plant Access permissions
    # (frontend checks `session.plant.permissions.includes('admin')`).
    try:
        access_rows = frappe.get_all(
            "User Plant Access",
            filters={"user": user, "enabled": 1},
            fields=["permissions"],
            limit_page_length=200,
        )
        for row in access_rows:
            perms_raw = row.get("permissions")
            if not perms_raw:
                continue
            try:
                perms = json.loads(perms_raw) if isinstance(perms_raw, str) else perms_raw
            except Exception:
                perms = []
            if isinstance(perms, list) and "admin" in perms:
                return
    except Exception:
        # If this check fails for any reason, fall back to strict role-based admin.
        pass

    frappe.throw(_("Not permitted"), frappe.PermissionError)


# -----------------------------
# Filter parsing / normalization
# -----------------------------

def _parse_filters(filters) -> dict:
    if not filters:
        return {}
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            return {}
    return filters if isinstance(filters, dict) else {}


def _normalize_filters(filters: dict) -> dict:
    normalized: dict = {}

    whs = filters.get("warehouse_code") or filters.get("whscode") or filters.get("warehouse")
    if isinstance(whs, str) and whs.strip():
        normalized["warehouse_code"] = whs.strip()

    search = filters.get("search")
    if isinstance(search, str) and search.strip():
        normalized["search"] = search.strip()

    low_stock_threshold = filters.get("low_stock_threshold")
    if low_stock_threshold is not None:
        try:
            threshold = float(low_stock_threshold)
            if threshold >= 0:
                normalized["low_stock_threshold"] = threshold
        except Exception:
            pass

    return normalized


def _normalize_date_range(filters: dict) -> dict:
    """Normalize optional date range filters (YYYY-MM-DD). Defaults to last 30 days."""
    normalized: dict = {}
    start_raw = filters.get("start_date") or filters.get("from_date") or filters.get("date_from")
    end_raw = filters.get("end_date") or filters.get("to_date") or filters.get("date_to")

    today = now_datetime().date()
    default_start = today - timedelta(days=30)

    def _parse_date_any(v):
        """Parse dates from common UI formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY."""
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if not v:
            return None
        if isinstance(v, str):
            s = v.strip()
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return date(y, mo, d)
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return date(y, mo, d)
            m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", s)
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return date(y, mo, d)
        try:
            return get_datetime(v).date()
        except Exception:
            return None

    start_date = None
    end_date = None
    if start_raw:
        start_date = _parse_date_any(start_raw)
    if end_raw:
        end_date = _parse_date_any(end_raw)

    if start_date is None and end_date is None:
        start_date = default_start
        end_date = today
    elif start_date is None:
        start_date = end_date - timedelta(days=30)
    elif end_date is None:
        end_date = today

    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    normalized["start_date"] = start_date
    normalized["end_date"] = end_date
    return normalized


def _normalize_procurement_filters(filters: dict) -> dict:
    """Filters for procurement traceability report."""
    normalized = _normalize_filters(filters)
    normalized.update(_normalize_date_range(filters))

    vendor = filters.get("vendor_code") or filters.get("cardcode") or filters.get("vendor")
    if isinstance(vendor, str) and vendor.strip():
        normalized["vendor_code"] = vendor.strip()

    material_type = filters.get("material_type") or filters.get("item_type")
    if isinstance(material_type, str) and material_type.strip():
        mt = material_type.strip().upper()
        if mt in {"RM", "PM", "OTHER"}:
            normalized["material_type"] = mt

    return normalized


def _hana_find_column(cursor, schema: str, table: str, candidates: list[str]) -> str | None:
    """
    Find the first existing column from candidates in a given SAP B1 table.
    Returns the actual column name (preserves case) or None.
    """
    if not schema or not table or not candidates:
        return None
    schema_u = str(schema).upper()
    table_u = str(table).upper()
    for cand in candidates:
        if not cand:
            continue
        cand_u = str(cand).upper()
        try:
            cursor.execute(
                """
                SELECT TOP 1 COLUMN_NAME
                FROM SYS.TABLE_COLUMNS
                WHERE SCHEMA_NAME = ? AND TABLE_NAME = ? AND UPPER(COLUMN_NAME) = ?
                """,
                [schema_u, table_u, cand_u],
            )
            r = cursor.fetchone()
            if r and r[0]:
                return r[0]
        except Exception:
            # If metadata lookup fails, fall back to safe None.
            continue
    return None


_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?)\b", re.IGNORECASE)


def _extract_size_grams(text: str | None) -> tuple[float | None, str | None]:
    """Extract size in grams from item description/name (e.g. 50g, 1 kg)."""
    if not text:
        return None, None
    m = _SIZE_RE.search(text)
    if not m:
        return None, None
    try:
        qty = float(m.group(1))
    except Exception:
        return None, None
    unit = (m.group(2) or "").lower()
    grams = qty * 1000.0 if unit == "kg" else qty
    return grams, m.group(0)


def _infer_flavour_from_text(text: str | None) -> str | None:
    """Best-effort flavour inference from item text when no UDF exists."""
    if not text:
        return None
    s = str(text).strip()
    if not s:
        return None
    # Remove size tokens to reduce noise
    s2 = _SIZE_RE.sub("", s)
    # Prefer content inside parentheses (often flavour/variant)
    m = re.search(r"\(([^)]+)\)", s2)
    if m:
        val = m.group(1).strip()
        return val[:60] if val else None
    # Prefer last segment after a delimiter
    parts = [p.strip() for p in re.split(r"[-/|]", s2) if p and p.strip()]
    cand = parts[-1] if parts else s2
    cand = re.sub(r"[^A-Za-z ]+", " ", cand).strip()
    return cand[:60] if cand else None


def _size_bucket(grams: float | None) -> str:
    if grams is None:
        return "Unknown"
    g = float(grams)
    if g <= 25:
        return "≤25g"
    if g <= 50:
        return "26–50g"
    if g <= 100:
        return "51–100g"
    if g <= 250:
        return "101–250g"
    if g <= 500:
        return "251–500g"
    if g <= 1000:
        return "501–1000g"
    return ">1000g"


def _age_bucket(days: int | None) -> str:
    if days is None:
        return "Unknown"
    d = int(days)
    if d <= 7:
        return "0–7"
    if d <= 14:
        return "8–14"
    if d <= 30:
        return "15–30"
    if d <= 60:
        return "31–60"
    if d <= 90:
        return "61–90"
    return "90+"


def _normalize_product_specs_filters(filters: dict) -> dict:
    normalized = _normalize_filters(filters)
    include_zero = filters.get("include_zero")
    normalized["include_zero"] = bool(int(include_zero)) if include_zero is not None else False
    return normalized


def _build_where_clause(normalized: dict, params: list) -> str:
    """Build a safe WHERE clause for OITW+OITM queries."""
    where = []

    if normalized.get("warehouse_code"):
        where.append('w."WhsCode" = ?')
        params.append(normalized["warehouse_code"])

    if normalized.get("search"):
        pattern = f'%{normalized["search"]}%'
        where.append('(UPPER(i."ItemCode") LIKE UPPER(?) OR UPPER(i."ItemName") LIKE UPPER(?))')
        params.extend([pattern, pattern])

    if not where:
        return "1=1"
    return " AND ".join(where)


def _build_batch_where_clause(normalized: dict, params: list) -> str:
    """Build a safe WHERE clause for OBTQ/OBTN batch queries."""
    where = []

    if normalized.get("warehouse_code"):
        where.append('q."WhsCode" = ?')
        params.append(normalized["warehouse_code"])

    if normalized.get("search"):
        pattern = f'%{normalized["search"]}%'
        where.append('(UPPER(i."ItemCode") LIKE UPPER(?) OR UPPER(i."ItemName") LIKE UPPER(?))')
        params.extend([pattern, pattern])

    if not where:
        return "1=1"
    return " AND ".join(where)


def _build_sap_b1_batch_inventory_where_clause(normalized: dict, params: list) -> str:
    """Build WHERE clause for SAP B1 batch inventory (OBTN/OBTQ/OITM/OITB; aliases T0,T1,T4,T5)."""
    where = []

    if normalized.get("warehouse_code"):
        where.append('T1."WhsCode" = ?')
        params.append(normalized["warehouse_code"])

    if normalized.get("search"):
        pattern = f'%{normalized["search"]}%'
        where.append('(UPPER(T0."ItemCode") LIKE UPPER(?) OR UPPER(T4."ItemName") LIKE UPPER(?))')
        params.extend([pattern, pattern])

    material_type = normalized.get("material_type")
    if material_type == "Raw Material":
        where.append("T5.\"ItmsGrpNam\" LIKE '%Raw%'")
    elif material_type == "Finished Good":
        where.append("T5.\"ItmsGrpNam\" LIKE '%Finish%'")

    if not where:
        return "1=1"
    return " AND ".join(where)


# -----------------------------
# Public API (whitelisted)
# -----------------------------

@frappe.whitelist()
def get_summary(filters=None):
    """
    Summary metrics for inventory (stock-on-hand only).

    Uses:
    - OITW: per warehouse stock + AvgPrice
    - OITM: item master (name, active flag, etc.)
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)
        low_stock_threshold = float(normalized.get("low_stock_threshold") or 10)

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_where_clause(normalized, params)

            query = QUERY_REGISTRY['summary'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, low_stock_threshold])
            row = cursor.fetchone() or (0, 0, 0, 0)

            return {
                "metrics": {
                    "total_skus_with_stock": int(row[0] or 0),
                    "total_onhand_qty": float(row[1] or 0),
                    "total_stock_value": float(row[2] or 0),
                    "low_stock_threshold": low_stock_threshold,
                    "low_stock_skus": int(row[3] or 0),
                },
                "filters": normalized,
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_summary: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_warehouse_breakdown(filters=None):
    """Warehouse-wise stock qty + value."""
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_where_clause(normalized, params)
            query = QUERY_REGISTRY['warehouse_breakdown'].format(schema=schema, where_clause=where)
            cursor.execute(query, params)
            rows = cursor.fetchall() or []
            
            breakdown = []
            for r in rows:
                breakdown.append({
                    "whscode": r[0],
                    "whsname": r[1],
                    "sku_count": int(r[2] or 0),
                    "onhand_qty": float(r[3] or 0),
                    "stock_value": float(r[4] or 0),
                })
            
            totals = {
                "sku_count": sum(int(r["sku_count"]) for r in breakdown),
                "onhand_qty": sum(float(r["onhand_qty"]) for r in breakdown),
                "stock_value": sum(float(r["stock_value"]) for r in breakdown),
            }
            return {"warehouses": breakdown, "totals": totals, "filters": normalized}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_warehouse_breakdown: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_top_items(filters=None, limit=20, sort="value"):
    """Top items by stock value (default) or by on-hand quantity."""
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 20
        safe_limit = max(1, min(safe_limit, 200))

        sort_key = str(sort or "value").lower()
        order_by = "stock_value DESC" if sort_key != "qty" else "onhand_qty DESC"

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_where_clause(normalized, params)

            query_key = 'top_items_value' if order_by == 'stock_value DESC' else 'top_items_qty'
            query = QUERY_REGISTRY[query_key].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, safe_limit])
            rows = cursor.fetchall() or []

            items = []
            for r in rows:
                items.append(
                    {
                        "item_code": r[0],
                        "item_name": r[1],
                        "onhand_qty": float(r[2] or 0),
                        "stock_value": float(r[3] or 0),
                    }
                )
            return {"items": items, "filters": normalized, "sort": sort_key, "limit": safe_limit}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_top_items: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_slow_moving(filters=None, days=90, limit=50):
    """
    Slow-moving items:
    - OnHand > 0 (from OITW)
    - last movement date (from OINM) is NULL or older than 'days'
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_days = int(days)
        except Exception:
            safe_days = 90
        safe_days = max(1, min(safe_days, 3650))

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 50
        safe_limit = max(1, min(safe_limit, 500))

        cutoff_date = (now_datetime().date() - timedelta(days=safe_days))

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_where_clause(normalized, params)

            query = QUERY_REGISTRY['slow_moving'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, cutoff_date, safe_limit])
            rows = cursor.fetchall() or []

            items = []
            for r in rows:
                items.append(
                    {
                        "item_code": r[0],
                        "item_name": r[1],
                        "whscode": r[2],
                        "whsname": r[3],
                        "onhand_qty": float(r[4] or 0),
                        "stock_value": float(r[5] or 0),
                        "last_movement_date": str(r[6]) if r[6] else None,
                    }
                )

            return {"items": items, "filters": normalized, "days": safe_days, "cutoff_date": str(cutoff_date)}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_slow_moving: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_chart_data(filters=None, chart_type="warehouse_value", limit=10):
    """Return chart-friendly data structures for the inventory dashboard."""
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        chart_type = str(chart_type or "warehouse_value").lower()

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            if chart_type == "warehouse_value":
                params: list = []
                where = _build_where_clause(normalized, params)
                query = QUERY_REGISTRY['warehouse_breakdown'].format(schema=schema, where_clause=where)
                cursor.execute(query, params)
                rows = cursor.fetchall() or []
                
                labels = [r[0] for r in rows]  # whscode
                values = [float(r[4] or 0) for r in rows]  # stock_value
                qty = [float(r[3] or 0) for r in rows]  # onhand_qty
                return {"labels": labels, "datasets": {"stock_value": values, "onhand_qty": qty}}

            if chart_type == "top_items_value":
                try:
                    safe_limit = int(limit)
                except Exception:
                    safe_limit = 10
                safe_limit = max(1, min(safe_limit, 50))
                params: list = []
                where = _build_where_clause(normalized, params)
                query = QUERY_REGISTRY['top_items_value'].format(schema=schema, where_clause=where)
                cursor.execute(query, [*params, safe_limit])
                rows = cursor.fetchall() or []
                labels = [r[0] for r in rows]
                values = [float(r[3] or 0) for r in rows]
                return {"labels": labels, "datasets": {"stock_value": values}}

            return {"error": f"Unknown chart type: {chart_type}"}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_chart_data: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_expiry_summary(filters=None, days=90):
    """
    Expiry risk summary (batch-managed items), bucketed by remaining shelf life.

    Uses:
    - OBTQ (batch qty per warehouse)
    - OBTN (batch master: DistNumber, ExpDate)
    - OITW (AvgPrice for value estimation)
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_days = int(days)
        except Exception:
            safe_days = 90
        safe_days = max(1, min(safe_days, 3650))

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_batch_where_clause(normalized, params)

            # Buckets are fixed (management-friendly) but "days" controls the max forward-looking window.
            query = QUERY_REGISTRY['expiry_summary'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, safe_days])
            rows = cursor.fetchall() or []

            # Stable order for UI
            order = {"Expired": 0, "0-30 Days": 1, "31-60 Days": 2, "61-90 Days": 3, "90+ Days": 4, "No Expiry": 5}

            buckets = []
            for r in rows:
                buckets.append(
                    {
                        "bucket": r[0],
                        "sku_count": int(r[1] or 0),
                        "qty": float(r[2] or 0),
                        "stock_value": float(r[3] or 0),
                    }
                )
            buckets.sort(key=lambda x: order.get(x["bucket"], 99))

            totals = {
                "sku_count": sum(int(b["sku_count"]) for b in buckets),
                "qty": sum(float(b["qty"]) for b in buckets),
                "stock_value": sum(float(b["stock_value"]) for b in buckets),
            }

            return {"buckets": buckets, "totals": totals, "days": safe_days, "filters": normalized}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_expiry_summary: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_expiring_batches(filters=None, days=90, limit=100):
    """Batch-level expiring stock (for action lists)."""
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_days = int(days)
        except Exception:
            safe_days = 90
        safe_days = max(1, min(safe_days, 3650))

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 100
        safe_limit = max(1, min(safe_limit, 500))

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_batch_where_clause(normalized, params)

            query = QUERY_REGISTRY['expiring_batches'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, safe_days, safe_limit])
            rows = cursor.fetchall() or []

            out = []
            for r in rows:
                out.append(
                    {
                        "item_code": r[0],
                        "item_name": r[1],
                        "whscode": r[2],
                        "whsname": r[3],
                        "batch_number": r[4],
                        "exp_date": str(r[5]) if r[5] else None,
                        "remaining_days": int(r[6]) if r[6] is not None else None,
                        "qty": float(r[7] or 0),
                        "stock_value": float(r[8] or 0),
                    }
                )

            return {"batches": out, "filters": normalized, "days": safe_days, "limit": safe_limit}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_expiring_batches: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_abc_analysis(filters=None, limit=5000):
    """
    ABC analysis by stock value:
    - A: top 80% value
    - B: next 15% value (80-95)
    - C: remaining 5% value
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 5000
        safe_limit = max(100, min(safe_limit, 20000))

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_where_clause(normalized, params)

            query = QUERY_REGISTRY['abc_analysis'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, safe_limit])
            rows = cursor.fetchall() or []

            items = [
                {
                    "item_code": r[0],
                    "item_name": r[1],
                    "onhand_qty": float(r[2] or 0),
                    "stock_value": float(r[3] or 0),
                }
                for r in rows
            ]

            total_value = sum(float(i["stock_value"]) for i in items) or 0.0
            cumulative = 0.0
            for it in items:
                v = float(it["stock_value"])
                cumulative += v
                share = (cumulative / total_value) if total_value > 0 else 0
                if share <= 0.80:
                    cls = "A"
                elif share <= 0.95:
                    cls = "B"
                else:
                    cls = "C"
                it["class"] = cls
                it["cumulative_share"] = round(share * 100, 2)

            summary = {
                "A": {"count": 0, "stock_value": 0.0},
                "B": {"count": 0, "stock_value": 0.0},
                "C": {"count": 0, "stock_value": 0.0},
            }
            for it in items:
                cls = it["class"]
                summary[cls]["count"] += 1
                summary[cls]["stock_value"] += float(it["stock_value"])

            return {"items": items[:200], "summary": summary, "total_stock_value": total_value, "filters": normalized}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_abc_analysis: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_inventory_report_catalog():
    """
    Inventory Report Catalog (for the admin UI).
    Returns report metadata only (no heavy queries).
    """
    _require_admin()

    # NOTE: keep this list minimal + stable. Add new entries as you add reports.
    reports = [
        {
            "id": "overview",
            "name": "Inventory Overview",
            "description": "KPIs: SKUs with stock, on-hand qty, stock value, low-stock count.",
            "category": "Inventory",
            "anchor": "section-overview",
        },
        {
            "id": "warehouse_value",
            "name": "Stock Value by Warehouse",
            "description": "Warehouse-wise stock value and distribution chart.",
            "category": "Warehouse",
            "anchor": "section-warehouse-value",
        },
        {
            "id": "top_items",
            "name": "Top Items by Stock Value",
            "description": "Top-N items by stock value (and qty).",
            "category": "Inventory",
            "anchor": "section-top-items",
        },
        {
            "id": "warehouse_batches",
            "name": "Warehouse Batch Stock",
            "description": "Warehouse-wise batch quantity with batch number + manufacturing/expiry dates.",
            "category": "Batch",
            "anchor": "section-warehouse-batches",
        },
        {
            "id": "procurement_trace",
            "name": "Procurement Traceability",
            "description": "What was procured from which warehouse and which vendor, including item code + batch code (GRPO).",
            "category": "Procurement",
            "anchor": "section-procurement-trace",
        },
        {
            "id": "product_specs",
            "name": "Product Specs (Size/Flavour) + Moisture",
            "description": "Size (grams) + flavour from Item Master, warehouse-wise OnHand, and latest production order moisture + age (days).",
            "category": "Production",
            "anchor": "section-product-specs",
        },
        {
            "id": "slow_moving",
            "name": "Slow Moving Stock",
            "description": "OnHand > 0 and last movement date older than N days.",
            "category": "Movement",
            "anchor": "section-slow-moving",
        },
        {
            "id": "expiry_risk",
            "name": "Expiry Risk (Batch-wise)",
            "description": "Expiry buckets (Expired, 0-30, 31-60, 61-90, 90+).",
            "category": "Expiry",
            "anchor": "section-expiry-risk",
        },
        {
            "id": "expiring_batches",
            "name": "Expiring Batches (Action List)",
            "description": "Batch list sorted by earliest expiry with qty/value.",
            "category": "Expiry",
            "anchor": "section-expiring-batches",
        },
        {
            "id": "abc",
            "name": "ABC Value Concentration",
            "description": "Classify items into A/B/C by cumulative stock value.",
            "category": "Management",
            "anchor": "section-abc",
        },
        {
            "id": "batch_availability",
            "name": "Batch Availability",
            "description": "Batch stock with committed and on-order quantities to calculate available stock (PM/RM/FG items).",
            "category": "Batch",
            "anchor": "section-batch-availability",
        },
        {
            "id": "sap_b1_batch_inventory",
            "name": "SAP B1 Batch Inventory (Raw / FG)",
            "description": "Batch stock by item, warehouse, material type (Raw Material / Finished Good), with production/expiry dates and days from production. FIFO order.",
            "category": "Batch",
            "anchor": "section-sap-b1-batch-inventory",
        },
    ]

    return {
        "count": len(reports),
        "reports": reports,
    }


@frappe.whitelist()
def get_procurement_traceability(filters=None, limit=200, offset=0, include_summary=0):
    """
    Procurement traceability (GRPO): vendor + warehouse + item + batch at time of receipt.

    Uses SAP B1 purchasing receipt tables:
    - OPDN (Goods Receipt PO header)
    - PDN1 (lines)
    - OCRD (vendor master)
    - IBT1 (batch transactions; GRPO base type)
    - OBTN (batch master: DistNumber/MnfDate/ExpDate)
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_procurement_filters(raw)

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 200
        safe_limit = max(1, min(safe_limit, 2000))

        try:
            safe_offset = int(offset)
        except Exception:
            safe_offset = 0
        safe_offset = max(0, safe_offset)

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = ['h."CANCELED" = \'N\'']

            # Date range (force ISO strings to avoid driver/date coercion issues)
            start_s = str(normalized["start_date"])
            end_s = str(normalized["end_date"])
            where.append('h."DocDate" BETWEEN TO_DATE(?) AND TO_DATE(?)')
            params.extend([start_s, end_s])

            # Vendor filter
            if normalized.get("vendor_code"):
                where.append('h."CardCode" = ?')
                params.append(normalized["vendor_code"])

            # Warehouse filter (line warehouse)
            if normalized.get("warehouse_code"):
                where.append('l."WhsCode" = ?')
                params.append(normalized["warehouse_code"])

            # Material type filter (derived from item code prefix)
            # RM* => Raw Material, PM* => Packaging Material, else OTHER
            if normalized.get("material_type"):
                where.append(
                    """(
                        CASE
                            WHEN l."ItemCode" LIKE 'RM%%' THEN 'RM'
                            WHEN l."ItemCode" LIKE 'PM%%' THEN 'PM'
                            ELSE 'OTHER'
                        END
                    ) = ?"""
                )
                params.append(normalized["material_type"])

            # Item search filter (code/name)
            if normalized.get("search"):
                pattern = f'%{normalized["search"]}%'
                where.append('(UPPER(l."ItemCode") LIKE UPPER(?) OR UPPER(l."Dscription") LIKE UPPER(?))')
                params.extend([pattern, pattern])

            where_clause = " AND ".join(where)

            # NOTE:
            # - GRPO object type in SAP B1 is 20 (PDN). IBT1.BaseType stores that.
            # - On some schemas IBT1 does NOT have SysNumber; joining via BatchNum -> OBTN.DistNumber is the safest.
            query = QUERY_REGISTRY['procurement_rows'].format(schema=schema, where_clause=where_clause)

            cursor.execute(query, [*params, safe_limit, safe_offset])
            rows = cursor.fetchall() or []

            out = []
            for r in rows:
                out.append(
                    {
                        "doc_date": str(r[0]) if r[0] else None,
                        "doc_num": int(r[1]) if r[1] is not None else None,
                        "vendor_code": r[2],
                        "vendor_name": r[3],
                        "whscode": r[4],
                        "whsname": r[5],
                        "material_type": r[6],
                        "item_code": r[7],
                        "item_name": r[8],
                        "batch_number": r[9],
                        "mnf_date": str(r[10]) if r[10] else None,
                        "exp_date": str(r[11]) if r[11] else None,
                        "batch_qty": float(r[12] or 0),
                        "line_qty": float(r[13] or 0),
                        "line_total": float(r[14] or 0),
                    }
                )

            result = {
                "rows": out,
                "filters": {
                    "start_date": str(normalized["start_date"]),
                    "end_date": str(normalized["end_date"]),
                    "warehouse_code": normalized.get("warehouse_code") or "",
                    "vendor_code": normalized.get("vendor_code") or "",
                    "material_type": normalized.get("material_type") or "",
                    "search": normalized.get("search") or "",
                },
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": len(out) == safe_limit,
            }
            
            # OPTIMIZATION: If include_summary=1, compute summary in same connection (reuses WHERE clause)
            if include_summary:
                try:
                    # Reuse the same WHERE clause and params for summary aggregations
                    summary_params = params.copy()  # Same params as rows query
                    
                    # Quick aggregations using same filters (no need for full joins again)
                    summary_q = QUERY_REGISTRY['procurement_summary_totals'].format(schema=schema, where_clause=where_clause)
                    cursor.execute(summary_q, summary_params)
                    t = cursor.fetchone() or (0, 0, 0, 0)
                    result["totals"] = {
                        "grpo_count": int(t[0] or 0),
                        "sku_count": int(t[1] or 0),
                        "qty": float(t[2] or 0),
                        "value": float(t[3] or 0)
                    }
                    
                    # By vendor (top 12)
                    vendor_q = QUERY_REGISTRY['procurement_summary_vendor'].format(schema=schema, where_clause=where_clause)
                    cursor.execute(vendor_q, summary_params)
                    vendor_rows = cursor.fetchall() or []
                    result["by_vendor"] = [
                        {"vendor_code": r[0], "vendor_name": r[1], "qty": float(r[2] or 0), "value": float(r[3] or 0)}
                        for r in vendor_rows
                    ]
                    
                    # By warehouse
                    wh_q = QUERY_REGISTRY['procurement_summary_warehouse'].format(schema=schema, where_clause=where_clause)
                    cursor.execute(wh_q, summary_params)
                    wh_rows = cursor.fetchall() or []
                    result["by_warehouse"] = [
                        {"whscode": r[0], "whsname": r[1], "qty": float(r[2] or 0), "value": float(r[3] or 0)}
                        for r in wh_rows
                    ]
                    
                    # By material type
                    type_q = QUERY_REGISTRY['procurement_summary_material_type'].format(schema=schema, where_clause=where_clause)
                    cursor.execute(type_q, summary_params)
                    type_rows = cursor.fetchall() or []
                    result["by_material_type"] = [
                        {"material_type": r[0], "qty": float(r[1] or 0), "value": float(r[2] or 0)}
                        for r in type_rows
                    ]
                except Exception as summary_err:
                    # If summary fails, still return rows
                    frappe.log_error(f"Error computing summary in get_procurement_traceability: {str(summary_err)}", "Inventory Dashboard")
            
            return result
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_procurement_traceability: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_procurement_traceability_summary(filters=None):
    """
    Summary for procurement charts: by vendor and by warehouse (qty + value).
    
    OPTIMIZED: Uses single CTE-based query instead of 4 separate queries.
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_procurement_filters(raw)

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            # Date range (force ISO strings to avoid driver/date coercion issues)
            start_s = str(normalized["start_date"])
            end_s = str(normalized["end_date"])
            where = ['h."CANCELED" = \'N\'', 'h."DocDate" BETWEEN TO_DATE(?) AND TO_DATE(?)']
            params.extend([start_s, end_s])

            if normalized.get("vendor_code"):
                where.append('h."CardCode" = ?')
                params.append(normalized["vendor_code"])
            if normalized.get("warehouse_code"):
                where.append('l."WhsCode" = ?')
                params.append(normalized["warehouse_code"])
            if normalized.get("search"):
                pattern = f'%{normalized["search"]}%'
                where.append('(UPPER(l."ItemCode") LIKE UPPER(?) OR UPPER(l."Dscription") LIKE UPPER(?))')
                params.extend([pattern, pattern])
            if normalized.get("material_type"):
                where.append(
                    """(
                        CASE
                            WHEN l."ItemCode" LIKE 'RM%%' THEN 'RM'
                            WHEN l."ItemCode" LIKE 'PM%%' THEN 'PM'
                            ELSE 'OTHER'
                        END
                    ) = ?"""
                )
                params.append(normalized["material_type"])

            where_clause = " AND ".join(where)

            # OPTIMIZED: Use queries from registry (each uses shared CTE pattern)
            # Query 1: By vendor (top 12)
            by_vendor_q = QUERY_REGISTRY['procurement_summary_vendor'].format(schema=schema, where_clause=where_clause)
            cursor.execute(by_vendor_q, params)
            vendor_rows = cursor.fetchall() or []
            by_vendor = [
                {"vendor_code": r[0], "vendor_name": r[1], "qty": float(r[2] or 0), "value": float(r[3] or 0)}
                for r in vendor_rows
            ]

            # Query 2: By warehouse
            by_wh_q = QUERY_REGISTRY['procurement_summary_warehouse'].format(schema=schema, where_clause=where_clause)
            cursor.execute(by_wh_q, params)
            wh_rows = cursor.fetchall() or []
            by_warehouse = [
                {"whscode": r[0], "whsname": r[1], "qty": float(r[2] or 0), "value": float(r[3] or 0)}
                for r in wh_rows
            ]

            # Query 3: By material type
            by_type_q = QUERY_REGISTRY['procurement_summary_material_type'].format(schema=schema, where_clause=where_clause)
            cursor.execute(by_type_q, params)
            type_rows = cursor.fetchall() or []
            by_material_type = [{"material_type": r[0], "qty": float(r[1] or 0), "value": float(r[2] or 0)} for r in type_rows]

            # Query 4: Totals
            totals_q = QUERY_REGISTRY['procurement_summary_totals'].format(schema=schema, where_clause=where_clause)
            cursor.execute(totals_q, params)
            t = cursor.fetchone() or (0, 0, 0, 0)
            totals = {"grpo_count": int(t[0] or 0), "sku_count": int(t[1] or 0), "qty": float(t[2] or 0), "value": float(t[3] or 0)}
            
            return {
                "totals": totals,
                "by_vendor": by_vendor[:12],  # Top 12
                "by_warehouse": by_warehouse,
                "by_material_type": by_material_type,
                "filters": {"start_date": str(normalized["start_date"]), "end_date": str(normalized["end_date"])},
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_procurement_traceability_summary: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_product_specs_stock(filters=None, limit=200, offset=0):
    """
    Product Specs report:
    - Size (grams) + flavour (from OITM UDF if present, else inferred from item text)
    - Warehouse-wise OnHand qty (OITW)
    - Latest production order info (OWOR) + moisture content (WOR1/OWOR UDF if present) + age in days
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_product_specs_filters(raw)

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 200
        safe_limit = max(1, min(safe_limit, 2000))

        try:
            safe_offset = int(offset)
        except Exception:
            safe_offset = 0
        safe_offset = max(0, safe_offset)

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            # Detect optional UDF columns
            flavour_col = _hana_find_column(
                cursor,
                schema,
                "OITM",
                ["U_FLAVOUR", "U_FLAVOR", "U_Flavour", "U_Flavor", "U_FLAV", "U_FLAVR"],
            )
            moisture_line_col = _hana_find_column(
                cursor,
                schema,
                "WOR1",
                ["U_MOISTURE", "U_MOISTURECONTENT", "U_MC", "U_Moisture", "U_MoistureContent"],
            )
            moisture_head_col = _hana_find_column(
                cursor,
                schema,
                "OWOR",
                ["U_MOISTURE", "U_MOISTURECONTENT", "U_MC", "U_Moisture", "U_MoistureContent"],
            )

            params: list = []
            where = []
            if not normalized.get("include_zero"):
                where.append('w."OnHand" > 0')

            if normalized.get("warehouse_code"):
                where.append('w."WhsCode" = ?')
                params.append(normalized["warehouse_code"])

            if normalized.get("search"):
                pattern = f'%{normalized["search"]}%'
                where.append('(UPPER(i."ItemCode") LIKE UPPER(?) OR UPPER(i."ItemName") LIKE UPPER(?))')
                params.extend([pattern, pattern])

            where_clause = " AND ".join(where) if where else "1=1"

            flavour_select = f'i."{flavour_col}" AS flavour_udf' if flavour_col else "NULL AS flavour_udf"
            if moisture_line_col:
                moisture_select = f"""
                    (SELECT MAX(l."{moisture_line_col}")
                     FROM {schema}."WOR1" l
                     WHERE l."DocEntry" = po."DocEntry") AS moisture_content
                """
            elif moisture_head_col:
                moisture_select = f'po."{moisture_head_col}" AS moisture_content'
            else:
                moisture_select = "NULL AS moisture_content"

            # Product specs query uses dynamic UDF columns - inject them into the base query
            query_template = QUERY_REGISTRY['product_specs_rows']
            query = query_template.format(
                schema=schema,
                where_clause=where_clause,
                flavour_select=flavour_select,
                moisture_select=moisture_select
            )
            cursor.execute(query, [*params, safe_limit, safe_offset])
            rows = cursor.fetchall() or []

            out = []
            for r in rows:
                item_name = r[3]
                grams, size_raw = _extract_size_grams(item_name)
                flavour_udf = r[4]
                flavour = (
                    str(flavour_udf).strip()
                    if flavour_udf is not None and str(flavour_udf).strip()
                    else _infer_flavour_from_text(item_name)
                )
                # moisture may come as string/decimal
                moisture_raw = r[9]
                try:
                    moisture = float(moisture_raw) if moisture_raw is not None and str(moisture_raw).strip() else None
                except Exception:
                    moisture = None
                try:
                    age_days = int(r[8]) if r[8] is not None else None
                except Exception:
                    age_days = None

                out.append(
                    {
                        "whscode": r[0],
                        "whsname": r[1],
                        "item_code": r[2],
                        "item_name": item_name,
                        "size_grams": grams,
                        "size_raw": size_raw,
                        "flavour": flavour,
                        "onhand_qty": float(r[5] or 0),
                        "prod_doc_num": int(r[6]) if r[6] is not None else None,
                        "prod_post_date": str(r[7]) if r[7] else None,
                        "prod_age_days": age_days,
                        "moisture_content": moisture,
                    }
                )

            return {
                "rows": out,
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": len(out) == safe_limit,
                "filters": {
                    "warehouse_code": normalized.get("warehouse_code") or "",
                    "search": normalized.get("search") or "",
                    "include_zero": 1 if normalized.get("include_zero") else 0,
                },
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_product_specs_stock: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_product_specs_stock_summary(filters=None):
    """Summary for Product Specs charts (flavour/size/moisture age buckets)."""
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_product_specs_filters(raw)

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            flavour_col = _hana_find_column(
                cursor,
                schema,
                "OITM",
                ["U_FLAVOUR", "U_FLAVOR", "U_Flavour", "U_Flavor", "U_FLAV", "U_FLAVR"],
            )
            moisture_line_col = _hana_find_column(
                cursor,
                schema,
                "WOR1",
                ["U_MOISTURE", "U_MOISTURECONTENT", "U_MC", "U_Moisture", "U_MoistureContent"],
            )
            moisture_head_col = _hana_find_column(
                cursor,
                schema,
                "OWOR",
                ["U_MOISTURE", "U_MOISTURECONTENT", "U_MC", "U_Moisture", "U_MoistureContent"],
            )

            params: list = []
            where = []
            if not normalized.get("include_zero"):
                where.append('w."OnHand" > 0')
            if normalized.get("warehouse_code"):
                where.append('w."WhsCode" = ?')
                params.append(normalized["warehouse_code"])
            if normalized.get("search"):
                pattern = f'%{normalized["search"]}%'
                where.append('(UPPER(i."ItemCode") LIKE UPPER(?) OR UPPER(i."ItemName") LIKE UPPER(?))')
                params.extend([pattern, pattern])
            where_clause = " AND ".join(where) if where else "1=1"

            flavour_select = f'i."{flavour_col}" AS flavour_udf' if flavour_col else "NULL AS flavour_udf"
            if moisture_line_col:
                moisture_select = f"""
                    (SELECT MAX(l."{moisture_line_col}")
                     FROM {schema}."WOR1" l
                     WHERE l."DocEntry" = po."DocEntry") AS moisture_content
                """
            elif moisture_head_col:
                # Wrap in MAX() for GROUP BY compatibility (one PO per ItemCode via latest_po CTE)
                moisture_select = f'MAX(po."{moisture_head_col}") AS moisture_content'
            else:
                moisture_select = "NULL AS moisture_content"

            # Product specs summary query uses dynamic UDF columns - inject them into the base query
            query_template = QUERY_REGISTRY['product_specs_summary_flavour']
            flavour_group_by = f'i."{flavour_col}"' if flavour_col else 'NULL'
            query = query_template.format(
                schema=schema,
                where_clause=where_clause,
                flavour_select=flavour_select,
                moisture_select=moisture_select,
                flavour_group_by=flavour_group_by
            )
            cursor.execute(query, params)
            rows = cursor.fetchall() or []

            total_qty = 0.0
            sku_set: set[str] = set()
            by_flavour: dict[str, float] = {}
            by_size: dict[str, float] = {}
            moisture_age_sum: dict[str, float] = {}
            moisture_age_cnt: dict[str, int] = {}
            with_moisture = 0

            for r in rows:
                item_code = r[0]
                item_name = r[1]
                flavour_udf = r[2]
                qty = float(r[3] or 0)
                total_qty += qty
                if item_code:
                    sku_set.add(item_code)

                grams, _ = _extract_size_grams(item_name)
                size_bucket = _size_bucket(grams)
                by_size[size_bucket] = by_size.get(size_bucket, 0.0) + qty

                flavour = (
                    str(flavour_udf).strip()
                    if flavour_udf is not None and str(flavour_udf).strip()
                    else _infer_flavour_from_text(item_name)
                )
                flavour_key = flavour or "Unknown"
                by_flavour[flavour_key] = by_flavour.get(flavour_key, 0.0) + qty

                # Moisture by age bucket (avg)
                moisture_raw = r[6]
                try:
                    moisture = float(moisture_raw) if moisture_raw is not None and str(moisture_raw).strip() else None
                except Exception:
                    moisture = None
                try:
                    age_days = int(r[5]) if r[5] is not None else None
                except Exception:
                    age_days = None
                if moisture is not None:
                    with_moisture += 1
                    ab = _age_bucket(age_days)
                    moisture_age_sum[ab] = moisture_age_sum.get(ab, 0.0) + moisture
                    moisture_age_cnt[ab] = moisture_age_cnt.get(ab, 0) + 1

            by_flavour_list = [{"flavour": k, "qty": v} for k, v in by_flavour.items()]
            by_flavour_list.sort(key=lambda x: x["qty"], reverse=True)
            by_size_list = [{"size_bucket": k, "qty": v} for k, v in by_size.items()]
            # Keep size buckets in a stable order
            size_order = ["≤25g", "26–50g", "51–100g", "101–250g", "251–500g", "501–1000g", ">1000g", "Unknown"]
            by_size_list.sort(key=lambda x: size_order.index(x["size_bucket"]) if x["size_bucket"] in size_order else 999)

            moisture_by_age = []
            for k in ["0–7", "8–14", "15–30", "31–60", "61–90", "90+", "Unknown"]:
                if k in moisture_age_cnt and moisture_age_cnt[k] > 0:
                    moisture_by_age.append(
                        {"age_bucket": k, "avg_moisture": round(moisture_age_sum[k] / moisture_age_cnt[k], 3), "count": moisture_age_cnt[k]}
                    )

            return {
                "totals": {
                    "sku_count": len(sku_set),
                    "qty": total_qty,
                    "with_moisture": with_moisture,
                },
                "by_flavour": by_flavour_list[:20],
                "by_size_bucket": by_size_list,
                "moisture_by_age_bucket": moisture_by_age,
                "filters": {
                    "warehouse_code": normalized.get("warehouse_code") or "",
                    "search": normalized.get("search") or "",
                    "include_zero": 1 if normalized.get("include_zero") else 0,
                },
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_product_specs_stock_summary: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_warehouse_batch_stock(filters=None, limit=200, include_expired=1, min_qty=0):
    """
    Warehouse-wise batch stock report (batch-managed inventory).

    Tables:
    - OBTQ: batch qty by ItemCode + WhsCode + SysNumber
    - OBTN: batch master (DistNumber, MnfDate, ExpDate)
    - OITM: ItemName
    - OWHS: Warehouse name
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 200
        safe_limit = max(1, min(safe_limit, 2000))

        try:
            safe_min_qty = float(min_qty or 0)
        except Exception:
            safe_min_qty = 0.0
        safe_min_qty = max(0.0, safe_min_qty)

        include_expired = bool(int(include_expired)) if include_expired is not None else True

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_batch_where_clause(normalized, params)

            extra_where = []
            extra_params = []
            extra_where.append('q."Quantity" > ?')
            extra_params.append(safe_min_qty)

            if not include_expired:
                extra_where.append('(b."ExpDate" IS NULL OR b."ExpDate" >= CURRENT_DATE)')

            extra_clause = " AND ".join(extra_where)

            query = QUERY_REGISTRY['warehouse_batch_stock'].format(
                schema=schema,
                where_clause=where,
                extra_clause=extra_clause
            )

            cursor.execute(query, [*params, *extra_params, safe_limit])
            rows = cursor.fetchall() or []

            out = []
            for r in rows:
                out.append(
                    {
                        "whscode": r[0],
                        "whsname": r[1],
                        "item_code": r[2],
                        "item_name": r[3],
                        "batch_number": r[4],
                        "mnf_date": str(r[5]) if r[5] else None,
                        "exp_date": str(r[6]) if r[6] else None,
                        "qty": float(r[7] or 0),
                        "remaining_days": int(r[8]) if r[8] is not None else None,
                    }
                )

            return {
                "rows": out,
                "filters": normalized,
                "limit": safe_limit,
                "include_expired": include_expired,
                "min_qty": safe_min_qty,
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_warehouse_batch_stock: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_warehouse_batch_totals(filters=None, include_expired=1, min_qty=0):
    """
    Aggregated totals for Warehouse Batch Stock charts (accurate; not limited by pagination).
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_min_qty = float(min_qty or 0)
        except Exception:
            safe_min_qty = 0.0
        safe_min_qty = max(0.0, safe_min_qty)

        include_expired = bool(int(include_expired)) if include_expired is not None else True

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_batch_where_clause(normalized, params)

            extra_where = ['q."Quantity" > ?']
            extra_params = [safe_min_qty]
            if not include_expired:
                extra_where.append('(b."ExpDate" IS NULL OR b."ExpDate" >= CURRENT_DATE)')
            extra_clause = " AND ".join(extra_where)

            query = QUERY_REGISTRY['warehouse_batch_totals'].format(
                schema=schema,
                where_clause=where,
                extra_clause=extra_clause
            )
            cursor.execute(query, [*params, *extra_params])
            rows = cursor.fetchall() or []

            out = []
            for r in rows:
                out.append(
                    {
                        "whscode": r[0],
                        "whsname": r[1],
                        "sku_count": int(r[2] or 0),
                        "batch_count": int(r[3] or 0),
                        "qty": float(r[4] or 0),
                    }
                )

            return {"warehouses": out, "filters": normalized, "include_expired": include_expired, "min_qty": safe_min_qty}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_warehouse_batch_totals: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


def _normalize_sap_b1_batch_inventory_filters(filters: dict) -> dict:
    """Normalize filters for SAP B1 batch inventory (search, warehouse_code, material_type)."""
    normalized = _normalize_filters(filters)
    mt = filters.get("material_type") if isinstance(filters, dict) else None
    if mt in ("Raw Material", "Finished Good"):
        normalized["material_type"] = mt
    return normalized


@frappe.whitelist()
def get_sap_b1_batch_inventory(filters=None, limit=500, include_summary=1):
    """
    SAP B1 batch inventory: Raw Material & Finished Good batches only.

    Returns item code/name, material type, warehouse, batch number, quantity, UoM,
    production/expiry dates, and days from production. FIFO order per item.
    Excludes WASTE% items. Optional filters: search, warehouse_code, material_type.
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_sap_b1_batch_inventory_filters(raw)

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 500
        safe_limit = max(1, min(safe_limit, 2000))

        include_summary = bool(int(include_summary)) if include_summary is not None else True

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_sap_b1_batch_inventory_where_clause(normalized, params)

            rows_query = QUERY_REGISTRY["sap_b1_batch_inventory_rows"].format(
                schema=schema, where_clause=where
            )
            cursor.execute(rows_query, [*params, safe_limit])
            rows_raw = cursor.fetchall() or []

            rows = []
            for r in rows_raw:
                rows.append(
                    {
                        "item_code": r[0],
                        "item_name": r[1],
                        "material_type": r[2],
                        "whscode": r[3],
                        "whsname": r[4],
                        "batch_number": r[5],
                        "quantity": float(r[6] or 0),
                        "uom": r[7],
                        "production_date": str(r[8]) if r[8] else None,
                        "expiry_date": str(r[9]) if r[9] else None,
                        "days_from_production": int(r[10]) if r[10] is not None else None,
                    }
                )

            summary_list = []
            if include_summary:
                summary_query = QUERY_REGISTRY["sap_b1_batch_inventory_summary"].format(
                    schema=schema, where_clause=where
                )
                cursor.execute(summary_query, params)
                summary_rows = cursor.fetchall() or []
                for s in summary_rows:
                    summary_list.append(
                        {
                            "material_type": s[0],
                            "batch_count": int(s[1] or 0),
                            "total_qty": float(s[2] or 0),
                        }
                    )

            return {
                "rows": rows,
                "summary": summary_list,
                "filters": normalized,
                "limit": safe_limit,
                "has_more": len(rows) == safe_limit,
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_sap_b1_batch_inventory: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_expiring_stock_by_warehouse(filters=None, days=90):
    """
    Expiring stock distribution by warehouse (for charts).
    Uses OBTQ/OBTN for expiry + OITW AvgPrice for value.
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_days = int(days)
        except Exception:
            safe_days = 90
        safe_days = max(1, min(safe_days, 3650))

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_batch_where_clause(normalized, params)

            query = QUERY_REGISTRY['expiring_by_warehouse'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, safe_days])
            rows = cursor.fetchall() or []

            out = []
            for r in rows:
                out.append(
                    {
                        "whscode": r[0],
                        "whsname": r[1],
                        "sku_count": int(r[2] or 0),
                        "qty": float(r[3] or 0),
                        "stock_value": float(r[4] or 0),
                    }
                )
            return {"warehouses": out, "filters": normalized, "days": safe_days}
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_expiring_stock_by_warehouse: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_slow_moving_summary(filters=None, days=90):
    """
    Summary for Slow Moving report charts:
    - by warehouse (qty/value)
    - by age bucket (count/qty/value)
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)

        try:
            safe_days = int(days)
        except Exception:
            safe_days = 90
        safe_days = max(1, min(safe_days, 3650))

        cutoff_date = (now_datetime().date() - timedelta(days=safe_days))

        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where = _build_where_clause(normalized, params)

            # Use slow moving summary query from registry (returns both by_warehouse and by_bucket in one query)
            query = QUERY_REGISTRY['slow_moving_summary'].format(schema=schema, where_clause=where)
            cursor.execute(query, [*params, cutoff_date])
            all_rows = cursor.fetchall() or []
            
            # Parse unified results
            by_warehouse = []
            by_bucket = []
            
            for r in all_rows:
                agg_type = r[0] if len(r) > 0 else None
                if agg_type == 'by_warehouse':
                    by_warehouse.append({
                        "whscode": r[1],
                        "whsname": r[2],
                        "sku_count": int(r[3] or 0),
                        "qty": float(r[4] or 0),
                        "stock_value": float(r[5] or 0),
                    })
                elif agg_type == 'by_bucket':
                    by_bucket.append({
                        "bucket": r[3],  # bucket is at index 3 for by_bucket rows
                        "sku_count": int(r[4] or 0),
                        "qty": float(r[5] or 0),
                        "stock_value": float(r[6] or 0),
                    })
            
            # Sort results
            by_warehouse.sort(key=lambda x: x["stock_value"], reverse=True)
            order = {"Unknown": 0, "0-30 Days": 1, "31-60 Days": 2, "61-90 Days": 3, "91-180 Days": 4, "180+ Days": 5}
            by_bucket.sort(key=lambda x: order.get(x["bucket"], 99))
            b_rows = cursor.fetchall() or []
            order = {"Unknown": 0, "0-30 Days": 1, "31-60 Days": 2, "61-90 Days": 3, "91-180 Days": 4, "180+ Days": 5}
            by_bucket = [
                {
                    "bucket": r[0],
                    "sku_count": int(r[1] or 0),
                    "qty": float(r[2] or 0),
                    "stock_value": float(r[3] or 0),
                }
                for r in b_rows
            ]
            by_bucket.sort(key=lambda x: order.get(x["bucket"], 99))

            return {
                "by_warehouse": by_warehouse,
                "by_bucket": by_bucket,
                "filters": normalized,
                "days": safe_days,
                "cutoff_date": str(cutoff_date),
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_slow_moving_summary: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


def _build_batch_availability_where_clause(normalized: dict, params: list) -> str:
    """Build a safe WHERE clause for batch availability queries (OBTN/OBTQ/OITM)."""
    where = []
    
    # Always filter by item code patterns: PM%, RM%, FG%
    where.append("(T2.\"ItemCode\" LIKE 'PM%%' OR T2.\"ItemCode\" LIKE 'RM%%' OR T2.\"ItemCode\" LIKE 'FG%%')")
    
    if normalized.get("warehouse_code"):
        where.append('T1."WhsCode" = ?')
        params.append(normalized["warehouse_code"])
    
    if normalized.get("search"):
        pattern = f'%{normalized["search"]}%'
        where.append('(UPPER(T2."ItemCode") LIKE UPPER(?) OR UPPER(T2."ItemName") LIKE UPPER(?))')
        params.extend([pattern, pattern])
    
    return " AND ".join(where)


@frappe.whitelist()
def get_batch_availability(filters=None, limit=200, offset=0):
    """
    Batch Availability Report: Shows batch stock with committed and on-order quantities.
    
    Returns:
    - OnHand: Total batch stock from OBTQ
    - IsCommitted: Committed quantity from OITW
    - OnOrder: On-order quantity from OITW
    - Available: Calculated as OnHand - IsCommitted + OnOrder
    
    Filters by ItemCode patterns: PM%, RM%, FG%
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)
        
        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 200
        safe_limit = max(1, min(safe_limit, 2000))
        
        try:
            safe_offset = int(offset)
        except Exception:
            safe_offset = 0
        safe_offset = max(0, safe_offset)
        
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where_clause = _build_batch_availability_where_clause(normalized, params)
            
            query = QUERY_REGISTRY['batch_availability_rows'].format(
                schema=schema,
                where_clause=where_clause
            )
            cursor.execute(query, [*params, safe_limit, safe_offset])
            rows = cursor.fetchall() or []
            
            out = []
            for r in rows:
                out.append({
                    "item_code": r[0],
                    "item_name": r[1],
                    "whscode": r[2],
                    "whsname": r[3],
                    "onhand": float(r[4] or 0),
                    "is_committed": float(r[5] or 0),
                    "on_order": float(r[6] or 0),
                    "available": float(r[7] or 0),
                })
            
            return {
                "rows": out,
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": len(out) == safe_limit,
                "filters": {
                    "warehouse_code": normalized.get("warehouse_code") or "",
                    "search": normalized.get("search") or "",
                },
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_batch_availability: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def get_batch_availability_summary(filters=None):
    """
    Summary for Batch Availability charts (totals and by warehouse).
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_filters(raw)
        
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            params: list = []
            where_clause = _build_batch_availability_where_clause(normalized, params)
            
            # Query 1: Totals
            totals_q = QUERY_REGISTRY['batch_availability_summary'].format(
                schema=schema,
                where_clause=where_clause
            )
            cursor.execute(totals_q, params)
            t = cursor.fetchone() or (0, 0, 0, 0, 0, 0)
            totals = {
                "sku_count": int(t[0] or 0),
                "row_count": int(t[1] or 0),
                "total_onhand": float(t[2] or 0),
                "total_committed": float(t[3] or 0),
                "total_on_order": float(t[4] or 0),
                "total_available": float(t[5] or 0),
            }
            
            # Query 2: By warehouse
            by_wh_q = QUERY_REGISTRY['batch_availability_summary_warehouse'].format(
                schema=schema,
                where_clause=where_clause
            )
            cursor.execute(by_wh_q, params)
            wh_rows = cursor.fetchall() or []
            by_warehouse = [
                {
                    "whscode": r[0],
                    "whsname": r[1],
                    "sku_count": int(r[2] or 0),
                    "total_onhand": float(r[3] or 0),
                    "total_committed": float(r[4] or 0),
                    "total_on_order": float(r[5] or 0),
                    "total_available": float(r[6] or 0),
                }
                for r in wh_rows
            ]
            
            return {
                "totals": totals,
                "by_warehouse": by_warehouse[:20],  # Top 20 warehouses
                "filters": {
                    "warehouse_code": normalized.get("warehouse_code") or "",
                    "search": normalized.get("search") or "",
                },
            }
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_batch_availability_summary: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}


@frappe.whitelist()
def debug_production_trace_tables():
    """
    Debug function to check table structures for production trace.
    Returns column information for IBT1, OWOR, OWTR, OPDN, PDN1 tables.
    """
    _require_admin()
    try:
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            tables = ['IBT1', 'OWOR', 'OWTR', 'OPDN', 'PDN1']
            result = {}
            
            for table in tables:
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE_NAME, LENGTH
                        FROM SYS.TABLE_COLUMNS
                        WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?
                        ORDER BY POSITION
                    """, [schema, table])
                    columns = cursor.fetchall()
                    result[table] = [{'name': c[0], 'type': c[1], 'length': c[2]} for c in columns]
                except Exception as e:
                    result[table] = {'error': str(e)}
            
            return result
        finally:
            connector.close_hana_connection(connection, cursor)
    except Exception as e:
        return {'error': str(e)}


@frappe.whitelist()
def run_batch_genealogy(batch_num, item_code=None, max_depth=10, max_batches=500):
    """
    Run batch genealogy trace (forward from one batch) using real HANA via SAP Settings.
    Uses standalone batch_genealogy logic with SAPConnector.
    """
    _require_admin()
    batch_num = (batch_num or "").strip()
    if not batch_num:
        return {"error": "batch_num is required"}
    try:
        max_depth = max(1, min(int(max_depth or 10), 50))
        max_batches = max(1, min(int(max_batches or 500), 2000))
    except (TypeError, ValueError):
        max_depth, max_batches = 10, 500
    item_code = (item_code or "").strip() or None
    try:
        from batch_genealogy import run_trace_with_connection
    except ImportError:
        # App root (where batch_genealogy.py lives) = parent of khanal_tech_integrations package
        import os
        import sys
        _pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _app_root = os.path.dirname(_pkg_root)
        if _app_root not in sys.path:
            sys.path.insert(0, _app_root)
        from batch_genealogy import run_trace_with_connection
    connector = SAPConnector()
    connection, cursor, schema = connector.get_hana_connection()
    try:
        result = run_trace_with_connection(
            connection, schema, batch_num, item_code,
            max_depth=max_depth, max_batches=max_batches, include_yield=True,
        )
        return result
    finally:
        connector.close_hana_connection(connection, cursor)


@frappe.whitelist()
def get_production_trace(filters=None, root_batch_num=None, root_item_code=None, max_depth=10):
    """
    Production Genealogy / Batch Trace - Forward trace from root batch through all production stages.
    
    Matches SAP B1 "Forward Batches & Serials Trace" behavior exactly.
    Uses document-based linking via IBT1 table (no direct parent-child batch links).
    
    Algorithm:
    1. Start from root batch (GRPO)
    2. Find consumption movements (Direction=1, BaseType IN (60,67))
    3. From same document, find output batches (Direction=0, BaseType=59)
    4. Repeat recursively for each output batch
    
    Args:
        filters: Optional filters dict (vendor_code, start_date, end_date, etc.)
        root_batch_num: Specific batch to trace (optional, if not provided uses filters)
        root_item_code: Specific item code for root batch (optional)
        max_depth: Maximum recursion depth (default 10)
    
    Returns:
        List of trace rows with stage information
    """
    _require_admin()
    try:
        raw = _parse_filters(filters)
        normalized = _normalize_procurement_filters(raw)  # Reuse procurement filter normalization
        
        try:
            safe_max_depth = int(max_depth)
        except Exception:
            safe_max_depth = 10
        safe_max_depth = max(1, min(safe_max_depth, 50))
        
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        try:
            # Stage identification helper function
            def identify_stage(item_code: str) -> tuple[str, str]:
                """Identify processing stage from item code suffix."""
                if not item_code:
                    return "Unknown", "Unknown"
                
                item_upper = item_code.upper()
                
                # Finished Goods
                if item_upper.startswith("FG") or "FG" in item_upper:
                    return "Finished Goods", "FG"
                
                # Drying locations (check in order of specificity)
                if ".NHDR" in item_upper:
                    return "Drying - Nandi Hills", "NHDR"
                if ".MDR" in item_upper:
                    return "Drying - Malur", "MDR"
                if ".DR" in item_upper or item_upper.endswith("DR"):
                    return "Drying - Mahadevpura", "DR"
                
                # Processing stages
                if ".CU" in item_upper:
                    return "Cutting", "CU"
                if ".BR" in item_upper:
                    return "Brushing", "BR"
                if ".WA" in item_upper:
                    return "Washing", "WA"
                if ".MD" in item_upper:
                    return "Metal Detection", "MD"
                
                return "Production", "PROD"
            
            # Get root batches
            params: list = []
            where = ['h."CANCELED" = \'N\'']
            
            if root_batch_num:
                where.append('COALESCE(b2."DistNumber", bt."BatchNum") = ?')
                params.append(root_batch_num)
            
            if root_item_code:
                where.append('bt."ItemCode" = ?')
                params.append(root_item_code)
            
            # Date range filter
            # When searching by specific batch number, skip date filter to allow finding batches from any date
            # Only apply date filter if explicitly provided in filters AND not searching by batch number
            if normalized.get("start_date") and normalized.get("end_date"):
                # Check if dates were explicitly provided in filters (not just auto-generated defaults)
                filters_have_dates = (
                    raw.get("start_date") or raw.get("end_date") or 
                    raw.get("from_date") or raw.get("to_date") or
                    raw.get("date_from") or raw.get("date_to")
                )
                
                # Skip date filter when searching by batch number (unless explicitly requested)
                if filters_have_dates and root_batch_num:
                    # User explicitly provided dates AND batch number - apply both filters
                    start_s = str(normalized["start_date"])
                    end_s = str(normalized["end_date"])
                    where.append('h."DocDate" BETWEEN TO_DATE(?) AND TO_DATE(?)')
                    params.extend([start_s, end_s])
                elif not root_batch_num:
                    # No batch number search - apply date filter (default or explicit)
                    start_s = str(normalized["start_date"])
                    end_s = str(normalized["end_date"])
                    where.append('h."DocDate" BETWEEN TO_DATE(?) AND TO_DATE(?)')
                    params.extend([start_s, end_s])
                # else: root_batch_num provided but no explicit dates - skip date filter
            
            # Vendor filter
            if normalized.get("vendor_code"):
                where.append('h."CardCode" = ?')
                params.append(normalized["vendor_code"])
            
            where_clause = " AND ".join(where)
            
            root_query = QUERY_REGISTRY['production_trace_root_batches'].format(
                schema=schema,
                where_clause=where_clause
            )
            cursor.execute(root_query, params)
            root_rows = cursor.fetchall() or []
            
            if not root_rows:
                return {
                    "rows": [],
                    "message": "No root batches found matching criteria",
                    "filters": normalized
                }
            
            # Build trace tree recursively
            trace_rows = []
            processed_batches = set()  # Prevent infinite loops: {item_code|batch_num}
            processed_transfers = set()  # Track processed transfer documents: {batch_num|doc_entry}
            max_trace_rows = 5000  # Reduced limit for faster execution
            recursion_count = {}  # Track recursion depth per batch to prevent deep loops
            max_processed_batches = 500  # Limit total batches processed
            
            def trace_batch(batch_num: str, item_code: str, stage_level: int, parent_info: dict):
                """Recursive function to trace a batch through production."""
                # Early termination checks
                if stage_level > safe_max_depth:
                    return
                if len(trace_rows) >= max_trace_rows:
                    return  # Prevent excessive results
                if len(processed_batches) >= max_processed_batches:
                    return  # Prevent processing too many batches
                
                batch_key = f"{item_code}|{batch_num}"
                if batch_key in processed_batches:
                    return  # Already processed
                
                # Track recursion depth for this batch
                recursion_depth = recursion_count.get(batch_key, 0)
                if recursion_depth > 5:  # Max 5 recursions per batch to prevent deep loops
                    return
                recursion_count[batch_key] = recursion_depth + 1
                
                processed_batches.add(batch_key)
                
                # Find consumption movements
                # Note: UNION query requires batch_num parameter twice (once for each UNION part)
                # Result columns: doc_entry(0), doc_type(1), consumed_item_code(2), consumed_item_name(3), 
                #                consumed_batch_num(4), consumed_qty(5), warehouse_code(6), warehouse_name(7)
                consumption_query = QUERY_REGISTRY['production_trace_consumption_movements'].format(schema=schema)
                cursor.execute(consumption_query, [batch_num, batch_num])
                consumption_rows = cursor.fetchall() or []
                
                # Limit consumption rows to prevent excessive processing
                max_consumption_per_batch = 20
                if len(consumption_rows) > max_consumption_per_batch:
                    consumption_rows = consumption_rows[:max_consumption_per_batch]
                
                # Batch fetch document info for all consumption rows to avoid N+1 queries
                doc_entries_60 = [cons_row[0] for cons_row in consumption_rows if cons_row[1] == 60]
                doc_entries_67 = [cons_row[0] for cons_row in consumption_rows if cons_row[1] == 67]
                
                # Limit batch fetch sizes to prevent huge IN clauses
                max_doc_entries = 100
                if len(doc_entries_60) > max_doc_entries:
                    doc_entries_60 = doc_entries_60[:max_doc_entries]
                if len(doc_entries_67) > max_doc_entries:
                    doc_entries_67 = doc_entries_67[:max_doc_entries]
                
                # Create a dictionary to store document info: {doc_entry: (doc_num, doc_date)}
                doc_info_map = {}
                
                # Batch fetch for BaseType 60 (Production Orders)
                if doc_entries_60:
                    try:
                        placeholders = ','.join(['?' for _ in doc_entries_60])
                        doc_info_query_60 = f'SELECT "DocEntry", "DocNum", "DocDate" FROM {schema}."OWOR" WHERE "DocEntry" IN ({placeholders})'
                        cursor.execute(doc_info_query_60, doc_entries_60)
                        for row in cursor.fetchall():
                            doc_info_map[row[0]] = (row[1], row[2])  # (doc_num, doc_date)
                    except Exception as e:
                        frappe.log_error(f"Error batch fetching OWOR docs: {str(e)}", "Production Trace")
                
                # Batch fetch for BaseType 67 (Inventory Transfers)
                if doc_entries_67:
                    try:
                        placeholders = ','.join(['?' for _ in doc_entries_67])
                        doc_info_query_67 = f'SELECT "DocEntry", "DocNum", "DocDate" FROM {schema}."OWTR" WHERE "DocEntry" IN ({placeholders})'
                        cursor.execute(doc_info_query_67, doc_entries_67)
                        for row in cursor.fetchall():
                            doc_info_map[row[0]] = (row[1], row[2])  # (doc_num, doc_date)
                    except Exception as e:
                        frappe.log_error(f"Error batch fetching OWTR docs: {str(e)}", "Production Trace")
                
                # Enrich consumption rows with document info
                enriched_consumption = []
                for cons_row in consumption_rows:
                    doc_entry = cons_row[0]
                    doc_type = cons_row[1]
                    
                    # Get document info from map
                    doc_info = doc_info_map.get(doc_entry)
                    doc_num = doc_info[0] if doc_info else None
                    doc_date = doc_info[1] if doc_info else None
                    
                    # Create enriched row: (doc_entry, doc_type, doc_num, doc_date, ...rest of original row)
                    enriched_row = (doc_entry, doc_type, doc_num, doc_date) + cons_row[2:]
                    enriched_consumption.append(enriched_row)
                
                # Sort consumption rows: by doc_date DESC, doc_num DESC, doc_entry ASC
                def sort_consumption(row):
                    doc_date = row[3]  # doc_date (now at index 3 after enrichment)
                    doc_num = row[2]   # doc_num (now at index 2 after enrichment)
                    doc_entry = row[0]  # doc_entry
                    # Handle None values for sorting
                    if doc_date:
                        if isinstance(doc_date, date):
                            date_ord = doc_date.toordinal()
                        elif isinstance(doc_date, datetime):
                            date_ord = doc_date.date().toordinal()
                        else:
                            try:
                                date_ord = get_datetime(doc_date).date().toordinal()
                            except:
                                date_ord = 0
                    else:
                        date_ord = 0
                    num_val = doc_num if doc_num is not None else 0
                    entry_val = doc_entry if doc_entry is not None else 0
                    return (-date_ord, -num_val, entry_val)
                
                consumption_rows = sorted(enriched_consumption, key=sort_consumption)
                
                if not consumption_rows:
                    # No consumption found - this batch is a leaf node
                    stage_name, stage_code = identify_stage(item_code)
                    trace_rows.append({
                        "grpo_num": parent_info.get("grpo_num"),
                        "vendor_code": parent_info.get("vendor_code"),
                        "vendor_name": parent_info.get("vendor_name"),
                        "root_item_code": parent_info.get("root_item_code"),
                        "root_batch_num": parent_info.get("root_batch_num"),
                        "stage_level": stage_level,
                        "stage_name": stage_name,
                        "stage_code": stage_code,
                        "stage_item_code": item_code,
                        "stage_batch_num": batch_num,
                        "stage_doc_num": None,
                        "stage_date": None,
                        "stage_qty": None,
                        "days_from_milk": None,
                    })
                    return
                
                # For each consumption movement, find output batches
                for cons_row in consumption_rows:
                    doc_entry = cons_row[0]
                    doc_type = cons_row[1]
                    doc_num = cons_row[2]
                    doc_date = cons_row[3]
                    # Note: cons_row[4] onwards are: consumed_item_code, consumed_item_name, etc.
                    
                    # Inventory transfers (BaseType 67) don't create new batches, only move them
                    # Skip transfers in trace (they're just warehouse movements, not production stages)
                    # For transfers, we need to find where the batch was moved TO (output side of transfer)
                    if doc_type == 67:
                        transfer_key = f"{batch_num}|{doc_entry}"
                        if transfer_key not in processed_transfers:
                            processed_transfers.add(transfer_key)
                            # Find the output side of the transfer (where batch was received)
                            # In transfers, the batch moves from one warehouse to another
                            # We need to find the receipt side (Direction=0) for the same document
                            transfer_output_query = f"""
                                SELECT DISTINCT
                                    bt."ItemCode",
                                    bt."BatchNum"
                                FROM {schema}."IBT1" bt
                                WHERE bt."BaseEntry" = ?
                                    AND bt."Direction" = 0
                                    AND bt."BaseType" = 67
                                    AND bt."BatchNum" = ?
                            """
                            cursor.execute(transfer_output_query, [doc_entry, batch_num])
                            transfer_output = cursor.fetchone()
                            if transfer_output:
                                # Batch was received in transfer - continue tracing from there
                                # But use the same stage_level to avoid infinite loops
                                out_item_code = transfer_output[0]
                                out_batch_num = transfer_output[1]
                                # Only trace if we haven't processed this batch yet
                                batch_key_out = f"{out_item_code}|{out_batch_num}"
                                if batch_key_out not in processed_batches:
                                    trace_batch(out_batch_num, out_item_code, stage_level, parent_info)
                        continue
                    
                    # Get output batches from same document (only for production BaseType 60)
                    output_query = QUERY_REGISTRY['production_trace_output_batches'].format(schema=schema)
                    cursor.execute(output_query, [doc_entry])
                    output_rows = cursor.fetchall() or []
                    
                    # Fetch document date for sorting (all output batches share same document)
                    output_doc_date = doc_date  # Use the date we already fetched for consumption
                    
                    # Sort output rows: by doc_date DESC, item_code ASC, batch_num ASC
                    # Updated columns: doc_entry(0), item_code(1), item_name(2), batch_num(3), qty(4), ...
                    def sort_output(row):
                        item_code = row[1]  # output_item_code
                        batch_num = row[3]  # output_batch_num
                        # Use the document date we already have
                        if output_doc_date:
                            if isinstance(output_doc_date, date):
                                date_ord = output_doc_date.toordinal()
                            elif isinstance(output_doc_date, datetime):
                                date_ord = output_doc_date.date().toordinal()
                            else:
                                try:
                                    date_ord = get_datetime(output_doc_date).date().toordinal()
                                except:
                                    date_ord = 0
                        else:
                            date_ord = 0
                        item_code_str = str(item_code) if item_code else ""
                        batch_num_str = str(batch_num) if batch_num else ""
                        # Return tuple: (-date_ord, item_code_str, batch_num_str) for DESC, ASC, ASC
                        return (-date_ord, item_code_str, batch_num_str)
                    
                    output_rows = sorted(output_rows, key=sort_output)
                    
                    # Limit output rows per document to prevent excessive recursion
                    max_outputs_per_doc = 20
                    if len(output_rows) > max_outputs_per_doc:
                        output_rows = output_rows[:max_outputs_per_doc]
                    
                    if output_rows:
                        # Found production outputs
                        for out_row in output_rows:
                            # Updated columns: doc_entry(0), item_code(1), item_name(2), batch_num(3), qty(4), whs_code(5), whs_name(6), mnf_date(7), exp_date(8)
                            out_item_code = out_row[1]
                            out_batch_num = out_row[3]
                            out_qty = float(out_row[4] or 0)
                            out_date = output_doc_date  # Use document date we already fetched
                            
                            stage_name, stage_code = identify_stage(out_item_code)
                            
                            # Calculate days from milk
                            days_from_milk = None
                            if parent_info.get("grpo_date") and out_date:
                                try:
                                    # Handle date objects or strings
                                    grpo_date_val = parent_info["grpo_date"]
                                    if isinstance(grpo_date_val, str):
                                        grpo_dt = datetime.strptime(grpo_date_val, "%Y-%m-%d").date()
                                    elif isinstance(grpo_date_val, date):
                                        grpo_dt = grpo_date_val
                                    elif isinstance(grpo_date_val, datetime):
                                        grpo_dt = grpo_date_val.date()
                                    else:
                                        grpo_dt = get_datetime(grpo_date_val).date()
                                    
                                    out_date_val = out_date
                                    if isinstance(out_date_val, str):
                                        out_dt = datetime.strptime(out_date_val, "%Y-%m-%d").date()
                                    elif isinstance(out_date_val, date):
                                        out_dt = out_date_val
                                    elif isinstance(out_date_val, datetime):
                                        out_dt = out_date_val.date()
                                    else:
                                        out_dt = get_datetime(out_date_val).date()
                                    
                                    days_from_milk = (out_dt - grpo_dt).days
                                except Exception:
                                    pass
                            
                            trace_rows.append({
                                "grpo_num": parent_info.get("grpo_num"),
                                "vendor_code": parent_info.get("vendor_code"),
                                "vendor_name": parent_info.get("vendor_name"),
                                "root_item_code": parent_info.get("root_item_code"),
                                "root_batch_num": parent_info.get("root_batch_num"),
                                "stage_level": stage_level,
                                "stage_name": stage_name,
                                "stage_code": stage_code,
                                "stage_item_code": out_item_code,
                                "stage_batch_num": out_batch_num,
                                "stage_doc_num": int(doc_num) if doc_num else None,
                                "stage_date": str(out_date) if out_date else None,
                                "stage_qty": out_qty,
                                "days_from_milk": days_from_milk,
                            })
                            
                            # Recursively trace the output batch
                            trace_batch(out_batch_num, out_item_code, stage_level + 1, parent_info)
                    else:
                        # Consumption but no output (inventory transfer or waste)
                        # Still record the consumption
                        stage_name, stage_code = identify_stage(item_code)
                        trace_rows.append({
                            "grpo_num": parent_info.get("grpo_num"),
                            "vendor_code": parent_info.get("vendor_code"),
                            "vendor_name": parent_info.get("vendor_name"),
                            "root_item_code": parent_info.get("root_item_code"),
                            "root_batch_num": parent_info.get("root_batch_num"),
                            "stage_level": stage_level,
                            "stage_name": f"{stage_name} (Consumed)",
                            "stage_code": stage_code,
                            "stage_item_code": item_code,
                            "stage_batch_num": batch_num,
                            "stage_doc_num": int(doc_num) if doc_num else None,
                            "stage_date": str(doc_date) if doc_date else None,
                            "stage_qty": None,
                            "days_from_milk": None,
                        })
            
            # Process each root batch
            for root_row in root_rows:
                grpo_num = int(root_row[0]) if root_row[0] else None
                grpo_date = root_row[1]
                vendor_code = root_row[2]
                vendor_name = root_row[3]
                root_item_code = root_row[4]
                root_item_name = root_row[5]
                root_batch_num = root_row[6]  # COALESCE(b2."DistNumber", bt."BatchNum")
                root_batch_qty = float(root_row[7] or 0)
                
                parent_info = {
                    "grpo_num": grpo_num,
                    "grpo_date": grpo_date,
                    "vendor_code": vendor_code,
                    "vendor_name": vendor_name,
                    "root_item_code": root_item_code,
                    "root_batch_num": root_batch_num,
                }
                
                # Start trace from root batch
                trace_batch(root_batch_num, root_item_code, 0, parent_info)
            
            result = {
                "rows": trace_rows,
                "count": len(trace_rows),
                "filters": normalized,
                "max_depth": safe_max_depth,
            }
            
            # Add warning if we hit limits
            if len(trace_rows) >= max_trace_rows:
                result["warning"] = f"Trace limited to {max_trace_rows} rows. Consider using filters to narrow the search."
            if len(processed_batches) > 1000:
                result["warning"] = f"Processed {len(processed_batches)} unique batches. Trace may be incomplete."
            
            return result
        finally:
            connector.close_hana_connection(connection, cursor)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Error in inventory get_production_trace: {str(e)}", "Inventory Dashboard")
        return {"error": str(e)}

