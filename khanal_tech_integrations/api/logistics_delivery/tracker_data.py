"""
Tracker report data — reads delhivery_lr from AWS RDS PostgreSQL.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import frappe
from frappe import _
from frappe.utils import cint

from khanal_tech_integrations.utils.logistics_delivery_portal import DELIVERY_LOGISTICS_ROLE
from khanal_tech_integrations.utils.delivery_api_settings import (
    assert_delhivery_lr_database_configured,
    get_delhivery_lr_database_url,
)

_COLUMNS = [
    "lrnum",
    "delhivery_status",
    "status_type",
    "shipment_remark",
    "location",
    "waybill",
    "doc_entry",
    "doc_num",
    "series",
    "updated_at",
    "created_at",
    "raw_tracking",
    "sap_response",
    "last_status_webhook",
    "latest_pod_id",
    "pod_received",
]

# Full row for admin detail (includes legacy `test` when column exists).
_LR_ADMIN_COLUMNS = [
    "lrnum",
    "delhivery_status",
    "status_type",
    "shipment_remark",
    "location",
    "waybill",
    "raw_tracking",
    "last_status_webhook",
    "updated_at",
    "created_at",
    "test",
    "doc_entry",
    "doc_num",
    "series",
    "sap_response",
    "latest_pod_id",
    "pod_received",
]

_POD_EVENT_LIMIT = 500
_EPOD_B64_MAX_RETURN = 120_000  # avoid huge API payloads; UI can use raw_payload for metadata


def _require_portal():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)
    if DELIVERY_LOGISTICS_ROLE not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Not permitted."), frappe.PermissionError)


def _pg_dsn() -> str:
    return get_delhivery_lr_database_url()


def _pg_connect_timeout_sec() -> int:
    v = frappe.conf.get("delhivery_lr_connect_timeout_sec")
    if v is not None:
        try:
            return max(2, min(60, int(v)))
        except (TypeError, ValueError):
            pass
    return 8


def _serialize(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    # psycopg2 returns jsonb as dict/list already
    if isinstance(v, (dict, list)):
        return v
    return v


def _parse_sap_response_field(sap: Any) -> Optional[dict]:
    if isinstance(sap, dict):
        return sap
    if isinstance(sap, str) and sap.strip():
        try:
            parsed = json.loads(sap)
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return None


def _pod_date_from_raw_payload(raw: Any) -> Optional[str]:
    """Delhivery POD webhook JSON often has ``PODDate`` / variants."""
    if isinstance(raw, dict):
        for k in ("PODDate", "podDate", "POD_DATE", "pod_date"):
            v = raw.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()[:48]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return _pod_date_from_raw_payload(parsed) if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return None


def _sap_pod_posted_from_pod_response(sap_pod: Any) -> bool:
    """
    True when newest POD row's ``sap_pod_response`` indicates SAP accepted the POD PATCH
    (``ok`` + ``phase`` patch + HTTP 200 or 204), matching Lambda audit JSON.
    """
    d = _parse_sap_response_field(sap_pod)
    if not d:
        return False
    if d.get("ok") is not True:
        return False
    if str(d.get("phase") or "").lower() != "patch":
        return False
    st = d.get("http_status")
    try:
        h = int(st)
    except (TypeError, ValueError):
        return False
    return h in (200, 204)


def lr_row_expects_pod_sap(row: dict) -> bool:
    """True when a POD row is expected to be pushed to SAP (matches tracker UI logic)."""
    pr = row.get("pod_received")
    if pr is True or pr == 1:
        return True
    if isinstance(pr, str) and pr.strip().lower() == "true":
        return True
    lip = row.get("latest_pod_id")
    if lip is None:
        return False
    s = str(lip).strip()
    return bool(s) and s != "0"


def fetch_latest_sap_pod_response_for_lr(lrnum: str) -> Optional[Any]:
    """``sap_pod_response`` from the newest ``delhivery_lr_pod`` row, or ``None``."""
    lr = (lrnum or "").strip()
    if not lr:
        return None
    assert_delhivery_lr_database_configured()
    try:
        import psycopg2
        from psycopg2 import errors as pg_errors
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return None

    conn = None
    one = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sap_pod_response
                FROM delhivery_lr_pod
                WHERE lrnum = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (lr,),
            )
            one = cur.fetchone()
    except pg_errors.UndefinedTable:
        return None
    except Exception:
        frappe.log_error(frappe.get_traceback(), "fetch_latest_sap_pod_response_for_lr")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if not one:
        return None
    return _serialize(one.get("sap_pod_response"))


def _compute_sap_pod_tracker_columns(
    rec: dict,
    sap_latest: Any,
    latest_pod_url: Any,
) -> None:
    """
    Sets ``sap_pod_posted``, ``sap_pod_display``, ``sap_pod_fixable`` on list row dict.

    * ``posted`` — SAP accepted POD PATCH (ok + phase patch + 200/204).
    * ``failed_fixable`` — POD data exists, DocEntry + ``pod_url`` present, SAP POD not OK → show Fix it.
    * ``failed_blocked`` — POD exists but no DocEntry on ``delhivery_lr`` (cannot PATCH invoice).
    * ``pending`` — DocEntry set but no ``pod_url`` yet.
    * ``none`` — no POD row / flags suggesting POD.
    """
    posted = _sap_pod_posted_from_pod_response(sap_latest)
    rec["sap_pod_posted"] = posted
    url_s = (str(latest_pod_url).strip() if latest_pod_url not in (None, "") else "") or ""
    has_pod = lr_row_expects_pod_sap(rec) or bool(url_s)
    de = cint(rec.get("doc_entry"))

    if not has_pod:
        rec["sap_pod_display"] = "none"
        rec["sap_pod_fixable"] = False
        return
    if posted:
        rec["sap_pod_display"] = "posted"
        rec["sap_pod_fixable"] = False
        return
    if de and url_s:
        rec["sap_pod_display"] = "failed_fixable"
        rec["sap_pod_fixable"] = True
        return
    if de and not url_s:
        rec["sap_pod_display"] = "pending"
        rec["sap_pod_fixable"] = False
        return
    rec["sap_pod_display"] = "failed_blocked"
    rec["sap_pod_fixable"] = False


def fetch_latest_delhivery_lr_pod_row_dict(lrnum: str) -> Optional[dict]:
    """Newest ``delhivery_lr_pod`` row as plain dict (id, pod_url, raw_payload, sap_pod_response), or ``None``."""
    lr = (lrnum or "").strip()
    if not lr:
        return None
    assert_delhivery_lr_database_configured()
    try:
        import psycopg2
        from psycopg2 import errors as pg_errors
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return None

    conn = None
    one = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, pod_url, raw_payload, sap_pod_response
                FROM delhivery_lr_pod
                WHERE lrnum = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (lr,),
            )
            one = cur.fetchone()
    except pg_errors.UndefinedTable:
        return None
    except Exception:
        frappe.log_error(frappe.get_traceback(), "fetch_latest_delhivery_lr_pod_row_dict")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if not one:
        return None
    d = dict(one)
    return {
        "id": _serialize(d.get("id")),
        "pod_url": _serialize(d.get("pod_url")),
        "raw_payload": _serialize(d.get("raw_payload")),
        "sap_pod_response": _serialize(d.get("sap_pod_response")),
    }


def _sap_synced_for_doc(sap: Optional[dict], doc_entry: int) -> bool:
    if not isinstance(sap, dict):
        return False
    if sap.get("ok") is not True and sap.get("sap_sync_status") != "synced":
        return False
    stored_de = sap.get("doc_entry")
    if stored_de is not None and cint(stored_de) == doc_entry:
        return True
    url = sap.get("url") or ""
    return bool(url and f"Invoices({doc_entry})" in str(url))


def row_needs_sap_retry(row: dict) -> bool:
    """True if Tracker would show Failed, Stale, or SAP empty while doc_entry is set."""
    de = cint(row.get("doc_entry"))
    if not de:
        return False
    sap = _parse_sap_response_field(row.get("sap_response"))
    if not sap:
        return True
    if sap.get("ok") is False or sap.get("sap_sync_status") == "failed":
        return True
    if _sap_synced_for_doc(sap, de):
        return False
    stored_de = sap.get("doc_entry")
    if stored_de is not None and cint(stored_de) != de:
        return True
    m = re.search(r"Invoices\((\d+)\)", str(sap.get("url") or ""), re.I)
    if m and cint(m.group(1)) != de:
        return True
    return False


def _extract_status_from_webhook_payload(payload: Any) -> Optional[str]:
    """
    Read a human-readable shipment ``status`` from a status-webhook JSON payload (dict or JSON string).

    Checks root keys and ``data.*`` for Delhivery-shaped envelopes.
    """
    if payload is None:
        return None
    p: Any = payload
    if isinstance(p, str) and p.strip():
        try:
            p = json.loads(p)
        except (ValueError, TypeError):
            return None
    if not isinstance(p, dict):
        return None
    for key in ("status", "Status", "STATUS"):
        v = p.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    data = p.get("data")
    if isinstance(data, dict):
        for key in ("status", "Status", "STATUS"):
            v = data.get(key)
            if v is not None and str(v).strip():
                return str(v).strip()
    return None


def fetch_latest_status_from_status_events(lrnum: str) -> Optional[str]:
    """Best ``status`` from recent ``delhivery_lr_status_events`` rows (newest first), if the table exists."""
    lr = (lrnum or "").strip()
    if not lr:
        return None

    assert_delhivery_lr_database_configured()

    try:
        import psycopg2
        from psycopg2 import errors as pg_errors
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return None

    conn = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload FROM delhivery_lr_status_events
                WHERE lrnum = %s
                ORDER BY id DESC
                LIMIT 25
                """,
                (lr,),
            )
            for ev in cur.fetchall() or []:
                st = _extract_status_from_webhook_payload(ev.get("payload"))
                if st:
                    return st
            return None
    except pg_errors.UndefinedTable:
        return None
    except Exception:
        frappe.log_error(frappe.get_traceback(), "fetch_latest_status_from_status_events")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def resolve_status_for_fix_pod_grn_key(lrnum: str, row: dict) -> tuple[Optional[str], str]:
    """
    Status string used for ``U_FrappeGRNKey`` on tracker **Fix it** POD.

    Priority: ``delhivery_lr.last_status_webhook`` (denormalized last webhook), then recent
    ``delhivery_lr_status_events`` payloads, then column ``delhivery_status``.

    Returns ``(status_text_or_none, origin)`` where ``origin`` is
    ``last_status_webhook`` | ``status_events`` | ``delhivery_status`` | ``none``.
    """
    st_lw = _extract_status_from_webhook_payload(row.get("last_status_webhook"))
    if st_lw:
        return st_lw, "last_status_webhook"
    st_ev = fetch_latest_status_from_status_events(lrnum)
    if st_ev:
        return st_ev, "status_events"
    ds = row.get("delhivery_status")
    if ds is not None and str(ds).strip():
        return str(ds).strip(), "delhivery_status"
    return None, "none"


def fetch_delhivery_lr_row(lrnum: str) -> Optional[dict]:
    """Load one row from delhivery_lr by exact LR number."""
    lr = (lrnum or "").strip()
    if not lr:
        return None

    assert_delhivery_lr_database_configured()

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        frappe.throw(
            _("psycopg2-binary is not installed. Run: pip install psycopg2-binary"),
            frappe.ValidationError,
        )

    col_sql = ", ".join(f'"{c}"' for c in _COLUMNS)
    conn = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {col_sql} FROM delhivery_lr WHERE lrnum = %s LIMIT 1",
                (lr,),
            )
            row = cur.fetchone()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "fetch_delhivery_lr_row")
        frappe.throw(_("Failed to load LR record from database."), frappe.ValidationError)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if not row:
        return None
    return {c: _serialize(row[c]) for c in _COLUMNS}


def fetch_sap_retry_candidates(limit: int = 50) -> list[dict]:
    """Rows that need SAP PATCH retry (failed, stale, or missing sap sync)."""
    lim = min(max(cint(limit) or 50, 1), 100)

    assert_delhivery_lr_database_configured()

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        frappe.throw(
            _("psycopg2-binary is not installed. Run: pip install psycopg2-binary"),
            frappe.ValidationError,
        )

    col_sql = ", ".join(f'"{c}"' for c in _COLUMNS)
    conn = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {col_sql}
                FROM delhivery_lr
                WHERE doc_entry IS NOT NULL
                  AND TRIM(COALESCE(doc_entry::text, '')) <> ''
                ORDER BY updated_at DESC
                LIMIT 500
                """
            )
            rows = cur.fetchall()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "fetch_sap_retry_candidates")
        frappe.throw(_("Failed to load retry candidates from database."), frappe.ValidationError)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    out = []
    for row in rows:
        rec = {c: _serialize(row[c]) for c in _COLUMNS}
        if row_needs_sap_retry(rec):
            out.append(rec)
            if len(out) >= lim:
                break
    return out


@frappe.whitelist()
def count_sap_retry_pending():
    """How many rows in DB need SAP retry (cap 100 for scan)."""
    _require_portal()
    return {"count": len(fetch_sap_retry_candidates(100))}


@frappe.whitelist()
def get_tracker_records(
    lrnum: Optional[str] = None,
    doc_entry: Optional[str] = None,
    doc_num: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """
    Paginated records from delhivery_lr.

    Each record includes ``sap_pod_posted``, ``sap_pod_display`` (``posted`` | ``failed_fixable`` |
    ``failed_blocked`` | ``pending`` | ``none``), and ``sap_pod_fixable`` for the Fix it action.

    Filters: lrnum, doc_entry, doc_num, status (delhivery_status ILIKE).
    """
    _require_portal()

    assert_delhivery_lr_database_configured()

    try:
        import psycopg2
        from psycopg2 import errors as pg_errors
        from psycopg2.extras import RealDictCursor
    except ImportError:
        frappe.throw(
            _("psycopg2-binary is not installed. Run: pip install psycopg2-binary"),
            frappe.ValidationError,
        )

    pg = cint(page) or 1
    ps = min(max(cint(page_size) or 50, 1), 200)
    offset = (pg - 1) * ps

    where = []
    params = []

    if lrnum and str(lrnum).strip():
        where.append("drlr.lrnum ILIKE %s")
        params.append("%" + str(lrnum).strip() + "%")
    if doc_entry and str(doc_entry).strip():
        where.append("drlr.doc_entry = %s")
        params.append(str(doc_entry).strip())
    if doc_num and str(doc_num).strip():
        where.append("drlr.doc_num = %s")
        params.append(str(doc_num).strip())
    if status and str(status).strip():
        where.append("drlr.delhivery_status ILIKE %s")
        params.append("%" + str(status).strip() + "%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    col_sql = ", ".join(f'"{c}"' for c in _COLUMNS)
    sql_with_pod = f"""
        SELECT drlr.*, lp.sap_pod_response AS sap_pod_response_latest,
               lp.pod_url AS latest_pod_url_latest
        FROM delhivery_lr drlr
        LEFT JOIN LATERAL (
            SELECT p.sap_pod_response, p.pod_url
            FROM delhivery_lr_pod p
            WHERE p.lrnum = drlr.lrnum
            ORDER BY p.id DESC
            LIMIT 1
        ) lp ON TRUE
        {where_sql}
        ORDER BY drlr.updated_at DESC
        LIMIT %s OFFSET %s
    """
    sql_lr_only = f"""
        SELECT {col_sql}
        FROM delhivery_lr drlr
        {where_sql}
        ORDER BY drlr.updated_at DESC
        LIMIT %s OFFSET %s
    """
    count_sql = f"SELECT COUNT(*) FROM delhivery_lr drlr {where_sql}"

    params_with_paging = params + [ps, offset]

    conn = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            total = cur.fetchone()["count"]

        rows = []
        with conn.cursor() as cur:
            try:
                cur.execute(sql_with_pod, params_with_paging)
                rows = cur.fetchall()
            except pg_errors.UndefinedTable as exc:
                if "delhivery_lr_pod" not in str(exc).lower():
                    raise
                cur.execute(sql_lr_only, params_with_paging)
                rows = cur.fetchall()

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Tracker report DB error")
        frappe.throw(_("Failed to load tracker data. See Error Log."), frappe.ValidationError)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    records = []
    for row in rows:
        rd = dict(row)
        sap_latest = rd.pop("sap_pod_response_latest", None)
        latest_pod_url = rd.pop("latest_pod_url_latest", None)
        rec = {c: _serialize(rd[c]) for c in _COLUMNS}
        _compute_sap_pod_tracker_columns(rec, sap_latest, latest_pod_url)
        records.append(rec)

    return {
        "records": records,
        "total": int(total),
        "page": pg,
        "page_size": ps,
        "pages": max(1, -(-int(total) // ps)),
    }


def _append_report_alert(
    alerts: list[dict],
    seen: set[tuple[str, str]],
    *,
    lrnum: str,
    kind: str,
    severity: str,
    title: str,
    message: str,
    updated_at: Any,
    lim_out: int,
) -> None:
    if len(alerts) >= lim_out:
        return
    lr = (lrnum or "").strip()
    if not lr:
        return
    key = (lr, kind)
    if key in seen:
        return
    seen.add(key)
    alerts.append(
        {
            "lrnum": lr,
            "kind": kind,
            "severity": severity,
            "title": title,
            "message": message,
            "updated_at": _serialize(updated_at),
        }
    )


@frappe.whitelist()
def get_logistics_report_alerts(limit: Optional[int] = None):
    """
    Open tracker issues for the logistics portal: SAP LR tracking gaps and SAP-POD gaps.

    Used by the dashboard / header notifications and the tracker page banner.
    """
    _require_portal()
    assert_delhivery_lr_database_configured()

    lim_out = min(max(cint(limit) or 35, 1), 80)
    scan_limit = min(500, max(120, lim_out * 18))

    try:
        import psycopg2
        from psycopg2 import errors as pg_errors
        from psycopg2.extras import RealDictCursor
    except ImportError:
        frappe.throw(
            _("psycopg2-binary is not installed. Run: pip install psycopg2-binary"),
            frappe.ValidationError,
        )

    col_sql = ", ".join(f'"{c}"' for c in _COLUMNS)
    sql_with_pod = f"""
        SELECT drlr.*, lp.sap_pod_response AS sap_pod_response_latest,
               lp.pod_url AS latest_pod_url_latest
        FROM delhivery_lr drlr
        LEFT JOIN LATERAL (
            SELECT p.sap_pod_response, p.pod_url
            FROM delhivery_lr_pod p
            WHERE p.lrnum = drlr.lrnum
            ORDER BY p.id DESC
            LIMIT 1
        ) lp ON TRUE
        ORDER BY drlr.updated_at DESC
        LIMIT %s
    """
    sql_lr_only = f"""
        SELECT {col_sql}
        FROM delhivery_lr drlr
        ORDER BY drlr.updated_at DESC
        LIMIT %s
    """

    conn = None
    rows = []
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            try:
                cur.execute(sql_with_pod, (scan_limit,))
                rows = cur.fetchall()
            except pg_errors.UndefinedTable as exc:
                if "delhivery_lr_pod" not in str(exc).lower():
                    raise
                cur.execute(sql_lr_only, (scan_limit,))
                rows = cur.fetchall()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_logistics_report_alerts")
        frappe.throw(_("Failed to load report alerts. See Error Log."), frappe.ValidationError)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    alerts: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        if len(alerts) >= lim_out:
            break
        rd = dict(row)
        sap_latest = rd.pop("sap_pod_response_latest", None)
        latest_pod_url = rd.pop("latest_pod_url_latest", None)
        rec = {c: _serialize(rd[c]) for c in _COLUMNS}
        _compute_sap_pod_tracker_columns(rec, sap_latest, latest_pod_url)

        lr = str(rec.get("lrnum") or "").strip()
        if not lr:
            continue
        de = cint(rec.get("doc_entry"))
        up = rec.get("updated_at")

        if de and row_needs_sap_retry(rec):
            _append_report_alert(
                alerts,
                seen,
                lrnum=lr,
                kind="sap_track",
                severity="warning",
                title=_("SAP LR tracking"),
                message=_("LR {0}: SAP invoice tracking is failed, stale, or not synced.").format(lr),
                updated_at=up,
                lim_out=lim_out,
            )

        pod_d = rec.get("sap_pod_display") or "none"
        if pod_d == "failed_fixable":
            _append_report_alert(
                alerts,
                seen,
                lrnum=lr,
                kind="sap_pod_fix",
                severity="warning",
                title=_("SAP POD"),
                message=_("LR {0}: POD is not posted to SAP — use Fix it on the tracker.").format(lr),
                updated_at=up,
                lim_out=lim_out,
            )
        elif pod_d == "failed_blocked":
            _append_report_alert(
                alerts,
                seen,
                lrnum=lr,
                kind="sap_pod_blocked",
                severity="danger",
                title=_("SAP POD"),
                message=_("LR {0}: POD received but DocEntry is missing — complete delivery submit first.").format(lr),
                updated_at=up,
                lim_out=lim_out,
            )

    return {"alerts": alerts, "count": len(alerts)}


def _serialize_pod_admin_row(row: dict) -> dict:
    """POD row for API; cap EPOD base64 so responses stay bounded."""
    out: dict[str, Any] = {
        "id": _serialize(row.get("id")),
        "lrnum": _serialize(row.get("lrnum")),
        "waybill": _serialize(row.get("waybill")),
        "order_id": _serialize(row.get("order_id")),
        "pod_url": _serialize(row.get("pod_url")),
        "pod_format": _serialize(row.get("pod_format")),
        "raw_payload": _serialize(row.get("raw_payload")),
        "sap_pod_response": _serialize(row.get("sap_pod_response")),
        "received_at": _serialize(row.get("received_at")),
    }
    b64 = row.get("epod_b64")
    if isinstance(b64, str) and b64.strip():
        raw_len = len(b64)
        if raw_len > _EPOD_B64_MAX_RETURN:
            out["epod_b64"] = b64[:_EPOD_B64_MAX_RETURN]
            out["epod_b64_truncated"] = True
            out["epod_b64_total_length"] = raw_len
        else:
            out["epod_b64"] = b64
            out["epod_b64_truncated"] = False
    else:
        out["epod_b64"] = None
        out["epod_b64_truncated"] = False
    return out


def _select_delhivery_lr_admin_row(cur, lr: str) -> Optional[dict]:
    """Load full delhivery_lr row for admin; omit ``test`` if column is missing."""
    admin_cols = list(_LR_ADMIN_COLUMNS)
    while admin_cols:
        col_sql = ", ".join(f'"{c}"' for c in admin_cols)
        try:
            cur.execute(
                f"SELECT {col_sql} FROM delhivery_lr WHERE lrnum = %s LIMIT 1",
                (lr,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {c: _serialize(row[c]) for c in admin_cols}
        except Exception as exc:
            msg = str(exc).lower()
            if "test" in admin_cols and ("test" in msg and ("column" in msg or "does not exist" in msg)):
                admin_cols = [c for c in admin_cols if c != "test"]
                continue
            raise


@frappe.whitelist()
def get_tracker_lr_admin_detail(lrnum: Optional[str] = None):
    """
    Admin: one LR from ``delhivery_lr``, status webhook history, POD history.

    Tables: ``delhivery_lr``, ``delhivery_lr_status_events``, ``delhivery_lr_pod``.
    """
    _require_portal()
    assert_delhivery_lr_database_configured()

    lr = (lrnum or "").strip()
    if not lr:
        frappe.throw(_("LR number is required."), frappe.ValidationError)

    try:
        import psycopg2
        from psycopg2 import errors as pg_errors
        from psycopg2.extras import RealDictCursor
    except ImportError:
        frappe.throw(
            _("psycopg2-binary is not installed. Run: pip install psycopg2-binary"),
            frappe.ValidationError,
        )

    warnings: list[str] = []
    lr_row: Optional[dict] = None
    status_events: list[dict] = []
    pods: list[dict] = []

    conn = None
    try:
        conn = psycopg2.connect(
            _pg_dsn(),
            connect_timeout=_pg_connect_timeout_sec(),
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            lr_row = _select_delhivery_lr_admin_row(cur, lr)

            if lr_row is None:
                return {
                    "lr": None,
                    "status_events": [],
                    "pods": [],
                    "sap_pod_posted": False,
                    "sap_pod_display": "none",
                    "sap_pod_fixable": False,
                    "warnings": [_("No row in delhivery_lr for this LR.")],
                }

            try:
                cur.execute(
                    """
                    SELECT id, lrnum, payload, received_at
                    FROM delhivery_lr_status_events
                    WHERE lrnum = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (lr, _POD_EVENT_LIMIT),
                )
                for ev in cur.fetchall() or []:
                    status_events.append(
                        {
                            "id": _serialize(ev.get("id")),
                            "lrnum": _serialize(ev.get("lrnum")),
                            "payload": _serialize(ev.get("payload")),
                            "received_at": _serialize(ev.get("received_at")),
                        }
                    )
            except pg_errors.UndefinedTable:
                warnings.append(
                    _("Table delhivery_lr_status_events is missing; status history is unavailable.")
                )
            except Exception:
                frappe.log_error(frappe.get_traceback(), "get_tracker_lr_admin_detail status_events")
                raise

            try:
                cur.execute(
                    """
                    SELECT id, lrnum, waybill, order_id, epod_b64, pod_url, pod_format, raw_payload,
                           sap_pod_response, received_at
                    FROM delhivery_lr_pod
                    WHERE lrnum = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (lr, _POD_EVENT_LIMIT),
                )
                for pod in cur.fetchall() or []:
                    pods.append(_serialize_pod_admin_row(dict(pod)))
            except pg_errors.UndefinedTable:
                warnings.append(_("Table delhivery_lr_pod is missing; POD history is unavailable."))
            except Exception:
                frappe.log_error(frappe.get_traceback(), "get_tracker_lr_admin_detail pods")
                raise

    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_tracker_lr_admin_detail")
        frappe.throw(_("Failed to load admin LR detail. See Error Log."), frappe.ValidationError)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    tmp_disp = dict(lr_row) if lr_row else {}
    sap_latest_ad = pods[0].get("sap_pod_response") if pods else None
    pod_url_ad = pods[0].get("pod_url") if pods else None
    _compute_sap_pod_tracker_columns(tmp_disp, sap_latest_ad, pod_url_ad)

    return {
        "lr": lr_row,
        "status_events": status_events,
        "pods": pods,
        "sap_pod_posted": bool(tmp_disp.get("sap_pod_posted")),
        "sap_pod_display": tmp_disp.get("sap_pod_display") or "none",
        "sap_pod_fixable": bool(tmp_disp.get("sap_pod_fixable")),
        "warnings": warnings,
    }
