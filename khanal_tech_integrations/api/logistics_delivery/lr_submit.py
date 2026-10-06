"""
Submit LR tracking for a selected AR invoice:

**Default:** after Delhivery (or cached preview), the **Submit** HTTP request runs **Postgres snapshot upsert +
first RDS patch** on the Frappe server. **SAP** follow-up runs in the **same web request** by default
(``frappe.enqueue(..., now=True)``) so SAP still runs if ``bench worker`` is not running. Set
``logistics_delivery_sap_use_queue`` = ``1`` in ``site_config.json`` to push SAP to the **default** RQ
queue instead (faster HTTP response; **requires** a worker).

**Optional ``site_config``:**

- ``logistics_delivery_sap_use_queue`` = ``1`` — enqueue SAP follow-through on the worker (do not use ``now=True``).

- ``logistics_delivery_sap_patch_timeout_sec`` — Service Layer PATCH timeout in seconds (default **45**,
  clamped 15–120).

- ``logistics_delivery_sap_patch_prefer_representation`` = ``1`` — use ``Prefer: return=representation``
  on invoice PATCH (slower; for debugging only).

- ``logistics_delivery_async_snapshot_rds_after_delhivery`` = ``1`` — return after Delhivery only;
  snapshot + RDS + SAP all in one **queued** job (fastest click; **requires** ``bench worker``).

- ``logistics_delivery_full_sync_submit`` or ``logistics_delivery_inline_sap_after_submit`` = ``1`` —
  entire pipeline **synchronous** in the request (no worker; slowest).

**Check LR (portal):** ``verify_delhivery_lr_for_portal`` fetches Delhivery and caches the track JSON.
With ``doc_entry`` (and optional doc/series) it also **writes the tracking snapshot to Postgres and the first RDS patch**,
so **Submit** can skip repeating those steps when the same invoice + LR still match.

- ``logistics_delivery_verify_skip_delhivery_ttl_sec`` — seconds (default **90**) to reuse the
  last Delhivery track JSON from the portal Redis cache for **Check LR** when LR + DocEntry +
  DocNum/Series match, skipping a second Delhivery HTTP round trip. Set **0** to always call Delhivery.

- ``delhivery_lr_connect_timeout_sec`` — Postgres connect timeout for ``delhivery_lr`` (default **8**,
  max 60).

Credentials and URLs are read from Single DocType ``Delivery API Settings``.
``frappe.conf`` keys with the same names still override DocType when set.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import frappe
import requests
from frappe import _
from frappe.utils import cint

from khanal_tech_integrations.utils.logistics_delivery_portal import DELIVERY_LOGISTICS_ROLE
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.delivery_api_settings import (
    assert_delhivery_api_configured,
    assert_delhivery_lr_database_configured,
    get_delhivery_jwt_cache_ttl_sec,
    get_delhivery_ltl_password,
    get_delhivery_ltl_track_base_url,
    get_delhivery_ltl_username,
    get_delhivery_lr_database_url,
)

DELHIVERY_JWT_CACHE_KEY = "logistics_delivery:delhivery_ltl_jwt"
LR_PREVIEW_CACHE_PREFIX = "logistics_delivery:lr_track_preview_v1:"
LR_PREVIEW_CACHE_TTL_SEC = 600

_SAP_HEADERS = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    # Do not replace child collections on PATCH (we only send U_LRtrackno).
    "B1S-ReplaceCollectionsOnPatch": "false",
}


def _sap_patch_request_headers() -> dict:
    """
    Prefer ``return=minimal`` on PATCH so Service Layer often returns 204 / empty body faster
    than serializing the full invoice (``return=representation``).

    Set ``logistics_delivery_sap_patch_prefer_representation`` = ``1`` in site_config to restore
    the old Prefer header for troubleshooting.
    """
    if cint(frappe.conf.get("logistics_delivery_sap_patch_prefer_representation")):
        return _SAP_HEADERS
    h = dict(_SAP_HEADERS)
    h["Prefer"] = "return=minimal"
    return h


def _sap_patch_timeout_sec() -> int:
    v = frappe.conf.get("logistics_delivery_sap_patch_timeout_sec")
    if v is not None:
        try:
            return max(15, min(120, int(v)))
        except (TypeError, ValueError):
            pass
    return 45


def _require_logistics_portal():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)
    if DELIVERY_LOGISTICS_ROLE not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Not permitted."), frappe.PermissionError)


def _clip_lrnum(raw) -> str:
    s = (raw or "").strip()
    if not s:
        frappe.throw(_("LR number is required."), frappe.ValidationError)
    if len(s) > 64:
        frappe.throw(_("LR number is too long."), frappe.ValidationError)
    return s


def _lr_preview_cache_key(lr: str) -> str:
    return f"{LR_PREVIEW_CACHE_PREFIX}{frappe.session.user}:{lr}"


def _get_lr_portal_cache(lr: str) -> Optional[dict]:
    """Redis entry for LR portal flow. May be legacy (tracking JSON only) or structured dict."""
    key = _lr_preview_cache_key(lr)
    raw = frappe.cache().get_value(key)
    if not raw:
        return None
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed, dict):
            return None
    if "tracking_raw" not in parsed and "persisted_for_doc_entry" not in parsed:
        return {
            "tracking_raw": parsed,
            "persisted_for_doc_entry": None,
            "snapshot_postgres_done": False,
        }
    return parsed


def _set_lr_portal_cache(lr: str, entry: dict) -> None:
    key = _lr_preview_cache_key(lr)
    frappe.cache().set_value(key, json.dumps(entry), expires_in_sec=LR_PREVIEW_CACHE_TTL_SEC)


def _clear_lr_portal_cache(lr: str) -> None:
    key = _lr_preview_cache_key(lr)
    try:
        frappe.cache().delete_value(key)
    except Exception:
        frappe.cache().set_value(key, "", expires_in_sec=1)


def _verify_skip_delhivery_cache_ttl_sec() -> int:
    """0 = never reuse Delhivery JSON from portal cache for Check LR."""
    v = frappe.conf.get("logistics_delivery_verify_skip_delhivery_ttl_sec")
    if v is not None:
        try:
            return max(0, min(600, int(v)))
        except (TypeError, ValueError):
            pass
    return 90


def _portal_tracking_fresh_for_verify_skip(
    lr: str,
    de: int,
    doc_num_s: Optional[str],
    series_s: Optional[str],
    cached: Optional[dict],
) -> Optional[dict]:
    """Return ``tracking_raw`` when we may skip ``fetch_delhivery_tracking`` (same invoice + TTL)."""
    ttl = _verify_skip_delhivery_cache_ttl_sec()
    if ttl <= 0 or not isinstance(cached, dict):
        return None
    ts = cached.get("tracking_fetched_at")
    try:
        if ts is None or (time.time() - float(ts)) > ttl:
            return None
    except (TypeError, ValueError):
        return None
    tr = cached.get("tracking_raw")
    if not isinstance(tr, dict) or not _delhivery_envelope_has_lr(tr, lr):
        return None
    if not de:
        return tr
    if cint(cached.get("persisted_for_doc_entry")) != de:
        return None
    if (cached.get("doc_num") or None) != (doc_num_s or None):
        return None
    if (cached.get("series") or None) != (series_s or None):
        return None
    return tr


def _delhivery_lr_pg_connect_timeout_sec() -> int:
    v = frappe.conf.get("delhivery_lr_connect_timeout_sec")
    if v is not None:
        try:
            return max(2, min(60, int(v)))
        except (TypeError, ValueError):
            pass
    return 8


def _connect_delhivery_lr_postgres():
    import psycopg2

    conn = psycopg2.connect(
        _delhivery_lr_database_url(),
        connect_timeout=_delhivery_lr_pg_connect_timeout_sec(),
    )
    conn.autocommit = True
    return conn


def _delhivery_friendly_error(status_code: int, body: Any) -> str:
    """Map Delhivery API errors to plain-language messages for portal users."""
    msg = body.get("message") if isinstance(body, dict) else None
    if isinstance(msg, dict):
        msg = msg.get("message") or json.dumps(msg)
    msg_s = str(msg or body or "").lower()

    if status_code == 404 or "data not found" in msg_s:
        return _("The LR number was not found in Delhivery. Please check the number and try again.")

    if "validation error" in msg_s or ("lrnum" in msg_s and ("invalid" in msg_s or "regex" in msg_s)):
        return _(
            "Delhivery could not accept this LR number. Please verify the number on your LR document and try again."
        )

    if "invalid token" in msg_s:
        return _("Delhivery login failed. Please contact your system administrator.")

    if isinstance(msg, str) and msg.strip() and len(msg) < 200 and "{" not in msg:
        return msg.strip()

    return _("Delhivery tracking could not be completed. Please verify the LR number and try again.")


def _delhivery_base_url() -> str:
    return get_delhivery_ltl_track_base_url()


def _delhivery_login_credentials() -> tuple[str, str]:
    return get_delhivery_ltl_username(), get_delhivery_ltl_password()


def login_delhivery_ltl(force_refresh: bool = False) -> str:
    """
    POST /ums/login → JWT. Cached in Redis; Delhivery track uses ``Authorization: Bearer``.
    """
    if not force_refresh:
        cached = frappe.cache().get_value(DELHIVERY_JWT_CACHE_KEY)
        if cached:
            return str(cached)

    base = _delhivery_base_url()
    username, password = _delhivery_login_credentials()
    login_url = f"{base}/ums/login"

    try:
        response = requests.post(
            login_url,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=45,
        )
    except requests.RequestException as exc:
        frappe.log_error(frappe.get_traceback(), "Delhivery UMS login")
        frappe.throw(_("Failed to reach Delhivery login API: {0}").format(exc), frappe.ValidationError)

    try:
        body = response.json()
    except ValueError:
        body = {"raw_text": (response.text or "")[:2000]}

    if not response.ok:
        frappe.log_error(
            title="Delhivery UMS login error",
            message=f"status={response.status_code} body={json.dumps(body)[:4000]}",
        )
        frappe.throw(
            _("Delhivery login failed ({0}): {1}").format(
                response.status_code,
                body.get("message") or body.get("error") or response.text[:500] or _("Unknown error"),
            ),
            frappe.ValidationError,
        )

    data = body.get("data") if isinstance(body, dict) else None
    jwt = data.get("jwt") if isinstance(data, dict) else None
    if not jwt and isinstance(body, dict):
        jwt = body.get("jwt")
    if not jwt:
        frappe.throw(_("Delhivery login did not return a JWT."), frappe.ValidationError)

    frappe.cache().set_value(
        DELHIVERY_JWT_CACHE_KEY,
        jwt,
        expires_in_sec=get_delhivery_jwt_cache_ttl_sec(),
    )
    return str(jwt)


def _delhivery_track_headers(jwt: str) -> dict:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {jwt}",
    }


def _is_delhivery_token_error(status_code: int, body: dict) -> bool:
    if status_code not in (400, 401, 403):
        return False
    text = json.dumps(body).lower() if isinstance(body, dict) else str(body).lower()
    return "invalid token" in text or "token" in text


def _service_layer_base_url() -> str:
    cached = getattr(frappe.local, "logistics_delivery_sap_sl_base_url", None)
    if isinstance(cached, str) and cached:
        return cached
    doc_settings = frappe.get_single("SAP Settings")
    base_url = (doc_settings.sap_b1_url or "").rstrip("/")
    if not base_url:
        frappe.throw(_("SAP B1 URL is not configured in SAP Settings."), frappe.ValidationError)
    if not base_url.endswith("/b1s/v1"):
        base_url = f"{base_url}/b1s/v1"
    frappe.local.logistics_delivery_sap_sl_base_url = base_url
    return base_url


def _first_wbn(data: dict) -> dict:
    wbns = data.get("wbns")
    if isinstance(wbns, list) and wbns:
        first = wbns[0]
        return first if isinstance(first, dict) else {}
    return {}


def _unwrap_delhivery_payload(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    if isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def fetch_delhivery_tracking(lrnum: str) -> dict:
    """GET Delhivery LRN track; returns full JSON body."""
    base = _delhivery_base_url()
    url = f"{base}/lrn/track"
    jwt = login_delhivery_ltl()
    response = None
    body: dict | Any = {}

    for attempt in range(2):
        try:
            response = requests.get(
                url,
                params={"lrnum": lrnum},
                headers=_delhivery_track_headers(jwt),
                timeout=45,
            )
        except requests.RequestException as exc:
            frappe.log_error(frappe.get_traceback(), "Delhivery LRN track request")
            frappe.throw(_("Failed to reach Delhivery tracking API: {0}").format(exc), frappe.ValidationError)

        try:
            body = response.json()
        except ValueError:
            body = {"raw_text": (response.text or "")[:2000]}

        if response.ok:
            return body if isinstance(body, dict) else {"data": body}

        if attempt == 0 and _is_delhivery_token_error(response.status_code, body):
            jwt = login_delhivery_ltl(force_refresh=True)
            continue
        break

    frappe.log_error(
        title="Delhivery LRN track error",
        message=f"status={response.status_code} body={json.dumps(body)[:4000]}",
    )
    err_detail = body.get("message") if isinstance(body, dict) else None
    if isinstance(err_detail, dict):
        err_detail = err_detail.get("message") or json.dumps(err_detail)
    if not err_detail and isinstance(body, dict):
        err_detail = body.get("error")
    if not err_detail and response.text:
        err_detail = response.text[:500]
    if not err_detail:
        err_detail = _("Unknown error")
    user_msg = _delhivery_friendly_error(response.status_code, body if isinstance(body, dict) else {})
    frappe.throw(user_msg, frappe.ValidationError)


def _tracking_summary(tracking_raw: dict) -> dict:
    """Flattened fields for API response / logging (DB columns filled by Lambda)."""
    data = _unwrap_delhivery_payload(tracking_raw)
    wbn = _first_wbn(data)
    top_status = data.get("status")
    wbn_status = wbn.get("status")
    return {
        "delhivery_status": top_status or wbn_status,
        "status_type": wbn_status or top_status,
        "shipment_remark": wbn.get("scan_remark"),
        "location": wbn.get("location"),
        "waybill": wbn.get("wbn"),
    }


def _normalize_delhivery_track_envelope(tracking_raw: dict, lrnum: str) -> dict:
    """
    Lambda reads ``delhivery_track_response.data.lrnum`` (Delhivery /lrn/track JSON shape).
    """
    envelope = tracking_raw if isinstance(tracking_raw, dict) else {}
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else None
    if data is None:
        data = _unwrap_delhivery_payload(envelope)
        envelope = {
            "success": envelope.get("success", True),
            "request_id": envelope.get("request_id"),
            "data": data,
        }
    if lrnum:
        data["lrnum"] = str(lrnum).strip()
        envelope["data"] = data
    return envelope


def _delhivery_envelope_has_lr(tracking_raw: dict, lr: str) -> bool:
    envelope = _normalize_delhivery_track_envelope(tracking_raw, lr)
    tracked = (envelope.get("data") or {}).get("lrnum") if isinstance(envelope.get("data"), dict) else None
    return bool(tracked)


@frappe.whitelist()
def verify_delhivery_lr_for_portal(lrnum=None, doc_entry=None, doc_num=None, series=None):
    """
    Delhivery track + cache. If ``doc_entry`` is provided, also upsert tracking to Postgres and
    patch ``delhivery_lr`` invoice columns in one DB session so Submit can enqueue SAP only.

    When the portal Redis entry for this LR is still fresh and matches the same invoice keys,
    Delhivery ``/lrn/track`` may be skipped (see ``logistics_delivery_verify_skip_delhivery_ttl_sec``).
    """
    _require_logistics_portal()
    assert_delhivery_api_configured()
    lr = _clip_lrnum(lrnum)
    de = cint(doc_entry)
    doc_num_s = (str(doc_num).strip() if doc_num not in (None, "") else None) or None
    series_s = (str(series).strip() if series not in (None, "") else None) or None

    cached = _get_lr_portal_cache(lr)
    tracking_raw = _portal_tracking_fresh_for_verify_skip(lr, de, doc_num_s, series_s, cached)
    reused_delhivery_cache = tracking_raw is not None
    if tracking_raw is None:
        tracking_raw = fetch_delhivery_tracking(lr)
    if not _delhivery_envelope_has_lr(tracking_raw, lr):
        frappe.throw(
            _("Delhivery did not return tracking data for LR {0}.").format(lr),
            frappe.ValidationError,
        )
    summary = _tracking_summary(tracking_raw)
    if reused_delhivery_cache and isinstance(cached, dict):
        try:
            tracking_fetched_at = float(cached.get("tracking_fetched_at"))
        except (TypeError, ValueError):
            tracking_fetched_at = time.time()
    else:
        tracking_fetched_at = time.time()

    entry: dict[str, Any] = {
        "tracking_raw": tracking_raw,
        "persisted_for_doc_entry": None,
        "snapshot_postgres_done": False,
        "doc_num": None,
        "series": None,
        "db_response_initial": None,
        "snapshot_payload_initial": None,
        "postgres_patched": False,
        "tracking_fetched_at": tracking_fetched_at,
    }
    snapshot_saved_at_check = False
    if de:
        assert_delhivery_lr_database_configured()
        snapshot_before = build_snapshot_api_body(
            lrnum=lr,
            doc_entry=de,
            doc_num=doc_num_s,
            series=series_s,
            tracking_raw=tracking_raw,
            sap_response=None,
        )
        db_response_initial, postgres_patched = _save_tracking_snapshot_and_patch_lr_row_one_connection(
            snapshot_before,
            summary,
            de,
            doc_num_s,
            series_s,
            sap_response=None,
        )
        entry.update(
            {
                "persisted_for_doc_entry": de,
                "snapshot_postgres_done": True,
                "doc_num": doc_num_s,
                "series": series_s,
                "db_response_initial": db_response_initial,
                "snapshot_payload_initial": snapshot_before,
                "postgres_patched": postgres_patched,
            }
        )
        snapshot_saved_at_check = True
    _set_lr_portal_cache(lr, entry)
    return {
        "status": "ok",
        "lrnum": lr,
        "delhivery_status": summary.get("delhivery_status"),
        "waybill": summary.get("waybill"),
        "location": summary.get("location"),
        "shipment_remark": summary.get("shipment_remark"),
        "cache_ttl_sec": LR_PREVIEW_CACHE_TTL_SEC,
        "snapshot_saved_at_check_lr": snapshot_saved_at_check,
        "delhivery_from_cache": reused_delhivery_cache,
    }


def build_snapshot_api_body(
    lrnum: str,
    doc_entry: int,
    doc_num: Optional[str],
    series: Optional[str],
    tracking_raw: dict,
    sap_response: Optional[dict] = None,
) -> dict:
    """
    Record passed to ``save_tracking_snapshot`` (Postgres upsert of track JSON + metadata at root).

    - ``lrnum`` at **root** (required — avoids "Could not determine lrnum")
    - ``delhivery_track_response``: Delhivery track envelope ``{success, data: {lrnum, ...}}``
    - Flat columns at root for ``delhivery_lr`` table (used by follow-up ``patch_delhivery_lr_row_in_postgres``)
    """
    track_envelope = _normalize_delhivery_track_envelope(tracking_raw, lrnum)
    summary = _tracking_summary(track_envelope)
    return {
        "lrnum": lrnum,
        "delhivery_track_response": track_envelope,
        "delhivery_status": summary.get("delhivery_status"),
        "status_type": summary.get("status_type"),
        "shipment_remark": summary.get("shipment_remark"),
        "location": summary.get("location"),
        "waybill": summary.get("waybill"),
        "raw_tracking": track_envelope,
        "doc_entry": str(doc_entry),
        "doc_num": str(doc_num).strip() if doc_num not in (None, "") else None,
        "series": str(series).strip() if series not in (None, "") else None,
        "sap_response": sap_response,
    }


def _sap_error_message(sap_body: dict, status_code: int) -> str:
    if isinstance(sap_body.get("error"), dict):
        m = sap_body["error"].get("message")
        if isinstance(m, dict):
            val = m.get("value")
            if val and str(val).strip() and str(val).strip().lower() != "value":
                return str(val)
            lang = m.get("lang")
            if lang:
                return str(lang)
        elif isinstance(m, str) and m.strip():
            return m
    return _("SAP update failed ({0}). See Error Log for full response.").format(status_code)


def normalize_snapshot_payload(record: dict) -> dict:
    """
    Ensure root ``lrnum`` and Delhivery-shaped ``delhivery_track_response``.
    """
    if not isinstance(record, dict):
        frappe.throw(_("Invalid tracking snapshot payload."), frappe.ValidationError)

    body = dict(record)
    if "delhivery_track_response" not in body:
        frappe.throw(
            _("Tracking snapshot must include delhivery_track_response."),
            frappe.ValidationError,
        )

    if not body.get("lrnum"):
        inner = body.get("delhivery_track_response") or {}
        lr = None
        if isinstance(inner, dict):
            lr = inner.get("lrnum")
            data = inner.get("data")
            if not lr and isinstance(data, dict):
                lr = data.get("lrnum")
        if lr:
            body["lrnum"] = str(lr).strip()

    if not body.get("lrnum"):
        frappe.throw(_("LR number is missing from tracking snapshot payload."), frappe.ValidationError)

    dtr = body.get("delhivery_track_response")
    if isinstance(dtr, dict) and not isinstance(dtr.get("data"), dict):
        body["delhivery_track_response"] = _normalize_delhivery_track_envelope(
            dtr, str(body["lrnum"])
        )

    return body


UPSERT_DELHIVERY_TRACKING_SNAPSHOT_SQL = """
INSERT INTO delhivery_lr (
  lrnum, delhivery_status, raw_tracking, updated_at, created_at
) VALUES (
  %s, %s, %s::jsonb, now(), now()
)
ON CONFLICT (lrnum) DO UPDATE SET
  delhivery_status = EXCLUDED.delhivery_status,
  raw_tracking = EXCLUDED.raw_tracking,
  updated_at = now();
"""


def _save_tracking_snapshot_and_patch_lr_row_one_connection(
    record: dict,
    summary: dict,
    doc_entry: int,
    doc_num_s: Optional[str],
    series_s: Optional[str],
    sap_response: Optional[dict] = None,
) -> tuple[dict, bool]:
    """
    Upsert ``raw_tracking`` then patch doc/series/WBN columns in **one** Postgres session.

    Avoids two sequential ``psycopg2.connect`` calls (noticeable latency to remote RDS).
    """
    post_body = normalize_snapshot_payload(record)
    assert_delhivery_lr_database_configured()
    lrnum = str(post_body["lrnum"]).strip()
    track = post_body["delhivery_track_response"]
    if not isinstance(track, dict):
        frappe.throw(
            _("delhivery_track_response must be an object."),
            frappe.ValidationError,
        )

    status = None
    data = track.get("data")
    if isinstance(data, dict):
        st = data.get("status")
        if isinstance(st, str):
            status = st

    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        frappe.log_error(
            title="Delhivery tracking snapshot skipped",
            message="Install psycopg2-binary on the bench env to persist raw_tracking.",
        )
        frappe.throw(
            _("psycopg2 is required to save the tracking snapshot to PostgreSQL."),
            frappe.ValidationError,
        )

    conn = None
    patched = False
    try:
        conn = _connect_delhivery_lr_postgres()
        with conn.cursor() as cur:
            cur.execute(
                UPSERT_DELHIVERY_TRACKING_SNAPSHOT_SQL,
                (lrnum, status, Json(track)),
            )
            if sap_response is not None:
                cur.execute(
                    """
                    UPDATE delhivery_lr SET
                        doc_entry = %s,
                        doc_num = %s,
                        series = %s,
                        status_type = COALESCE(%s, status_type),
                        shipment_remark = COALESCE(%s, shipment_remark),
                        location = COALESCE(%s, location),
                        waybill = COALESCE(%s, waybill),
                        sap_response = %s::jsonb,
                        updated_at = now()
                    WHERE lrnum = %s
                    """,
                    (
                        str(doc_entry),
                        doc_num_s,
                        series_s,
                        summary.get("status_type"),
                        summary.get("shipment_remark"),
                        summary.get("location"),
                        summary.get("waybill"),
                        Json(sap_response),
                        lrnum,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE delhivery_lr SET
                        doc_entry = %s,
                        doc_num = %s,
                        series = %s,
                        status_type = COALESCE(%s, status_type),
                        shipment_remark = COALESCE(%s, shipment_remark),
                        location = COALESCE(%s, location),
                        waybill = COALESCE(%s, waybill),
                        updated_at = now()
                    WHERE lrnum = %s
                    """,
                    (
                        str(doc_entry),
                        doc_num_s,
                        series_s,
                        summary.get("status_type"),
                        summary.get("shipment_remark"),
                        summary.get("location"),
                        summary.get("waybill"),
                        lrnum,
                    ),
                )
            if cur.rowcount == 0:
                frappe.log_error(
                    title="Delhivery LR Postgres patch — no row",
                    message=f"lrnum={lrnum} not found in delhivery_lr after snapshot.",
                )
            else:
                patched = True
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "Delhivery LR snapshot+patch Postgres")
        frappe.throw(
            _("Failed to save tracking snapshot to PostgreSQL: {0}").format(exc),
            frappe.ValidationError,
        )
    finally:
        if conn is not None:
            conn.close()

    return {"ok": True, "lrnum": lrnum}, patched


def save_tracking_snapshot(record: dict) -> dict:
    """
    Upsert Delhivery GET /lrn/track JSON into ``delhivery_lr`` (same row semantics as the
    former ``delivery-api`` snapshot Lambda / ``delhivery_store.upsert_tracking_snapshot``).
    """
    post_body = normalize_snapshot_payload(record)
    assert_delhivery_lr_database_configured()
    lrnum = str(post_body["lrnum"]).strip()
    track = post_body["delhivery_track_response"]
    if not isinstance(track, dict):
        frappe.throw(
            _("delhivery_track_response must be an object."),
            frappe.ValidationError,
        )

    status = None
    data = track.get("data")
    if isinstance(data, dict):
        st = data.get("status")
        if isinstance(st, str):
            status = st

    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        frappe.log_error(
            title="Delhivery tracking snapshot skipped",
            message="Install psycopg2-binary on the bench env to persist raw_tracking.",
        )
        frappe.throw(
            _("psycopg2 is required to save the tracking snapshot to PostgreSQL."),
            frappe.ValidationError,
        )

    conn = None
    try:
        conn = _connect_delhivery_lr_postgres()
        with conn.cursor() as cur:
            cur.execute(
                UPSERT_DELHIVERY_TRACKING_SNAPSHOT_SQL,
                (lrnum, status, Json(track)),
            )
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "Delhivery tracking snapshot Postgres upsert")
        frappe.throw(
            _("Failed to save tracking snapshot to PostgreSQL: {0}").format(exc),
            frappe.ValidationError,
        )
    finally:
        if conn is not None:
            conn.close()

    return {"ok": True, "lrnum": lrnum}


def _delhivery_lr_database_url() -> str:
    return get_delhivery_lr_database_url()


def _sap_patch_audit_failure(
    doc_entry: int,
    lrnum: str,
    error: str,
    url: Optional[str] = None,
) -> dict:
    """Persisted when SAP PATCH fails so Tracker does not show stale success."""
    return {
        "ok": False,
        "sap_sync_status": "failed",
        "doc_entry": doc_entry,
        "patch": {"U_LRtrackno": lrnum},
        "url": url,
        "error": (error or "")[:2000],
    }


def _sap_patch_audit_success(sap_body: dict, doc_entry: int) -> dict:
    """Tag successful SAP audit JSON with DocEntry for Tracker validation."""
    body = dict(sap_body) if isinstance(sap_body, dict) else {}
    body["ok"] = True
    body["sap_sync_status"] = "synced"
    body["doc_entry"] = doc_entry
    return body


def patch_delhivery_lr_row_in_postgres(
    lrnum: str,
    doc_entry: int,
    doc_num: Optional[str],
    series: Optional[str],
    summary: dict,
    sap_response: Optional[dict] = None,
) -> bool:
    """
    After ``save_tracking_snapshot``, fill ``doc_entry``, ``doc_num``, ``series``, wbn fields,
    and ``sap_response`` on the same ``delhivery_lr`` row (UPDATE).
    """
    assert_delhivery_lr_database_configured()

    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        frappe.log_error(
            title="Delhivery LR Postgres patch skipped",
            message="Install psycopg2-binary on the bench env to persist doc_entry/doc_num/series.",
        )
        return False

    conn = None
    try:
        conn = _connect_delhivery_lr_postgres()
        with conn.cursor() as cur:
            if sap_response is not None:
                cur.execute(
                    """
                    UPDATE delhivery_lr SET
                        doc_entry = %s,
                        doc_num = %s,
                        series = %s,
                        status_type = COALESCE(%s, status_type),
                        shipment_remark = COALESCE(%s, shipment_remark),
                        location = COALESCE(%s, location),
                        waybill = COALESCE(%s, waybill),
                        sap_response = %s::jsonb,
                        updated_at = now()
                    WHERE lrnum = %s
                    """,
                    (
                        str(doc_entry),
                        doc_num,
                        series,
                        summary.get("status_type"),
                        summary.get("shipment_remark"),
                        summary.get("location"),
                        summary.get("waybill"),
                        Json(sap_response),
                        lrnum,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE delhivery_lr SET
                        doc_entry = %s,
                        doc_num = %s,
                        series = %s,
                        status_type = COALESCE(%s, status_type),
                        shipment_remark = COALESCE(%s, shipment_remark),
                        location = COALESCE(%s, location),
                        waybill = COALESCE(%s, waybill),
                        updated_at = now()
                    WHERE lrnum = %s
                    """,
                    (
                        str(doc_entry),
                        doc_num,
                        series,
                        summary.get("status_type"),
                        summary.get("shipment_remark"),
                        summary.get("location"),
                        summary.get("waybill"),
                        lrnum,
                    ),
                )
            if cur.rowcount == 0:
                frappe.log_error(
                    title="Delhivery LR Postgres patch — no row",
                    message=f"lrnum={lrnum} not found in delhivery_lr after snapshot.",
                )
                return False
        return True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Delhivery LR Postgres patch failed")
        return False
    finally:
        if conn is not None:
            conn.close()


def patch_sap_invoice_lr(doc_entry: int, lrnum: str) -> tuple[dict, dict, str]:
    """
    PATCH SAP Service Layer Invoices(DocEntry) with U_LRtrackno.

    If SAP returns e.g. ``Invalid attachment entry [OINV.AtcEntry]``, the invoice row in SAP
    references a broken attachment (OINV vs ATC1 mismatch). Fix or clear that attachment in
    SAP B1 for this DocEntry; the Service Layer validates the whole document on PATCH.

    Returns:
        (sap_payload, sap_response_body, request_url)
    """
    session = AuthenticateSAPB1()
    base_url = _service_layer_base_url()
    url = f"{base_url}/Invoices({doc_entry})"
    sap_payload = {"U_LRtrackno": lrnum}

    try:
        response = session.patch(
            url,
            json=sap_payload,
            headers=_sap_patch_request_headers(),
            verify=False,
            timeout=_sap_patch_timeout_sec(),
        )
    except requests.RequestException as exc:
        frappe.log_error(frappe.get_traceback(), "SAP Invoices PATCH")
        frappe.throw(_("Failed to reach SAP Service Layer: {0}").format(exc), frappe.ValidationError)

    sap_body: dict = {}
    if response.text:
        try:
            parsed = response.json()
            sap_body = parsed if isinstance(parsed, dict) else {"result": parsed}
        except ValueError:
            sap_body = {"raw_text": response.text[:2000]}

    if not response.ok:
        err_msg = _sap_error_message(sap_body, response.status_code)
        frappe.log_error(
            title="SAP Invoices PATCH error",
            message=f"url={url} payload={json.dumps(sap_payload)} status={response.status_code} body={json.dumps(sap_body)[:4000]}",
        )
        frappe.throw(err_msg, frappe.ValidationError)

    # Service Layer often returns 204 / empty body on PATCH; persist audit JSON (not proof field changed in SAP UI).
    if not sap_body:
        sap_body = {
            "ok": True,
            "sap_sync_status": "synced",
            "http_status": response.status_code,
            "doc_entry": doc_entry,
            "patch": sap_payload,
            "url": url,
            "note": _(
                "HTTP {0} — Service Layer accepted PATCH with no body. "
                "Confirm U_LRtrackno on DocEntry {1} in SAP."
            ).format(response.status_code, doc_entry),
        }
    else:
        sap_body = _sap_patch_audit_success(sap_body, doc_entry)

    return sap_payload, sap_body, url


def patch_sap_invoice_pod_link_and_date(
    doc_entry: int,
    lrnum: str,
    pod_url: str,
    pod_date: Optional[str],
    *,
    frappe_grn_key: Optional[int] = None,
) -> tuple[dict, dict, str]:
    """
    PATCH SAP Service Layer ``Invoices(DocEntry)`` with ``U_Pod_Link``, optional ``U_POD_DATE``,
    ``U_LRtrackno`` (same invoice as tracking PATCH), and optional ``U_FrappeGRNKey`` (tracker Fix it).
    """
    session = AuthenticateSAPB1()
    base_url = _service_layer_base_url()
    url = f"{base_url}/Invoices({doc_entry})"
    sap_payload: dict[str, Any] = {
        "U_LRtrackno": (lrnum or "").strip(),
        "U_Pod_Link": (pod_url or "").strip(),
    }
    pdate = (str(pod_date).strip() if pod_date not in (None, "") else "") or ""
    if pdate:
        sap_payload["U_POD_DATE"] = pdate
    if frappe_grn_key is not None:
        sap_payload["U_FrappeGRNKey"] = int(frappe_grn_key)

    try:
        response = session.patch(
            url,
            json=sap_payload,
            headers=_sap_patch_request_headers(),
            verify=False,
            timeout=_sap_patch_timeout_sec(),
        )
    except requests.RequestException as exc:
        frappe.log_error(frappe.get_traceback(), "SAP Invoices POD PATCH")
        frappe.throw(_("Failed to reach SAP Service Layer: {0}").format(exc), frappe.ValidationError)

    sap_body: dict = {}
    if response.text:
        try:
            parsed = response.json()
            sap_body = parsed if isinstance(parsed, dict) else {"result": parsed}
        except ValueError:
            sap_body = {"raw_text": response.text[:2000]}

    if not response.ok:
        err_msg = _sap_error_message(sap_body, response.status_code)
        frappe.log_error(
            title="SAP Invoices POD PATCH error",
            message=f"url={url} payload={json.dumps(sap_payload)} status={response.status_code}",
        )
        frappe.throw(err_msg, frappe.ValidationError)

    if not sap_body:
        sap_body = {
            "ok": True,
            "sap_sync_status": "synced",
            "http_status": response.status_code,
            "doc_entry": doc_entry,
            "patch": sap_payload,
            "url": url,
        }
    else:
        sap_body = _sap_patch_audit_success(sap_body, doc_entry)

    return sap_payload, sap_body, url


def _update_delhivery_lr_pod_sap_response(pod_id: int, audit: dict) -> None:
    """Persist ``sap_pod_response`` JSON on ``delhivery_lr_pod``."""
    assert_delhivery_lr_database_configured()
    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        frappe.throw(_("psycopg2-binary is not installed."), frappe.ValidationError)

    conn = None
    try:
        conn = _connect_delhivery_lr_postgres()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE delhivery_lr_pod
                SET sap_pod_response = %s::jsonb
                WHERE id = %s
                """,
                (Json(audit), pod_id),
            )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _frappe_grn_key_from_status_text(status: Any) -> Optional[int]:
    """
    Map a Delhivery-style status string to SAP invoice UDF ``U_FrappeGRNKey`` for Fix-it POD PATCH.

    ``2`` when status looks like RTO (substring ``rto``, case-insensitive); ``1`` when it looks
    delivered (substring ``deliver``). RTO is checked first so values like "RTO Delivered" map to ``2``.
    Other / empty statuses: omit field (``None``).
    """
    raw = str(status or "").strip().lower()
    if not raw:
        return None
    if "rto" in raw:
        return 2
    if "deliver" in raw:
        return 1
    return None


def _sync_delhivery_lr_delhivery_status_if_distinct(lrnum: str, new_status: Optional[str]) -> bool:
    """
    Set ``delhivery_lr.delhivery_status`` to ``new_status`` when non-empty and different
    (trim, case-insensitive). Used after **Fix it** from ``last_status_webhook.status``.
    """
    if not new_status or not str(new_status).strip():
        return False
    new_status = str(new_status).strip()
    assert_delhivery_lr_database_configured()

    conn = None
    try:
        conn = _connect_delhivery_lr_postgres()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE delhivery_lr
                SET delhivery_status = %s, updated_at = now()
                WHERE lrnum = %s
                  AND lower(btrim(COALESCE(delhivery_status::text, '')))
                      <> lower(btrim(%s))
                """,
                (new_status, lrnum, new_status),
            )
            return cur.rowcount > 0
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "delhivery_lr delhivery_status sync from last_status_webhook after Fix it POD",
        )
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _pod_url_from_raw_payload(raw: Any) -> str:
    if isinstance(raw, dict):
        for k in ("pod_url", "podUrl", "POD_URL", "epod_url", "EPODUrl"):
            v = raw.get(k)
            if v and str(v).strip().startswith("http"):
                return str(v).strip()
    if isinstance(raw, str) and raw.strip():
        try:
            d = json.loads(raw)
            return _pod_url_from_raw_payload(d) if isinstance(d, dict) else ""
        except ValueError:
            return ""
    return ""


def _sap_pod_audit_from_tracker_fix(
    ok: bool,
    lrnum: str,
    doc_entry: int,
    *,
    http_status: Optional[int] = None,
    has_pod_date: bool = False,
    error: Optional[str] = None,
    phase: str = "patch",
    reason: Optional[str] = None,
) -> dict:
    from frappe.utils import now_datetime

    base: dict[str, Any] = {
        "ok": ok,
        "lrnum": lrnum,
        "phase": phase,
        "doc_entry": doc_entry,
        "synced_at": now_datetime().isoformat(),
        "source": "frappe_tracker_fix_pod",
    }
    if http_status is not None:
        base["http_status"] = http_status
    base["has_pod_date"] = bool(has_pod_date)
    base["response_preview"] = None
    if error:
        base["error"] = error[:2000]
    if reason:
        base["reason"] = reason
    return base


@frappe.whitelist()
def fix_delhivery_pod_sap_from_rds(lrnum=None):
    """
    Re-send POD from RDS (``delhivery_lr_pod.pod_url`` + ``PODDate`` from ``raw_payload``) to SAP
    when webhooks stored POD before DocEntry existed (e.g. ``sap_pod_response`` skip / no_doc_entry).
    """
    _require_logistics_portal()
    from khanal_tech_integrations.api.logistics_delivery.tracker_data import (
        _extract_status_from_webhook_payload,
        _pod_date_from_raw_payload,
        _sap_pod_posted_from_pod_response,
        fetch_delhivery_lr_row,
        fetch_latest_delhivery_lr_pod_row_dict,
        resolve_status_for_fix_pod_grn_key,
    )

    lr = _clip_lrnum(lrnum or "")
    row = fetch_delhivery_lr_row(lr)
    if not row:
        frappe.throw(_("LR not found in database."), frappe.ValidationError)
    de = cint(row.get("doc_entry"))
    if not de:
        frappe.throw(
            _("DocEntry is missing on this LR. Submit the LR from Delivery first so the invoice is linked."),
            frappe.ValidationError,
        )

    pod = fetch_latest_delhivery_lr_pod_row_dict(lr)
    if not pod:
        frappe.throw(_("No POD row in RDS for this LR."), frappe.ValidationError)
    if _sap_pod_posted_from_pod_response(pod.get("sap_pod_response")):
        return {"status": "already_ok", "message": _("POD is already posted to SAP."), "lrnum": lr}

    pod_url = str(pod.get("pod_url") or "").strip()
    if not pod_url:
        pod_url = _pod_url_from_raw_payload(pod.get("raw_payload"))
    if not pod_url:
        frappe.throw(_("No POD URL on the RDS row or in raw_payload."), frappe.ValidationError)

    pod_date = _pod_date_from_raw_payload(pod.get("raw_payload"))
    pod_id = cint(pod.get("id"))
    if not pod_id:
        frappe.throw(_("Invalid POD row id."), frappe.ValidationError)

    resolved_status, status_origin = resolve_status_for_fix_pod_grn_key(lr, row)
    grn_key = _frappe_grn_key_from_status_text(resolved_status)
    last_webhook_status = _extract_status_from_webhook_payload(row.get("last_status_webhook"))

    try:
        sap_payload, sap_body, _req_url = patch_sap_invoice_pod_link_and_date(
            de, lr, pod_url, pod_date, frappe_grn_key=grn_key
        )
    except frappe.ValidationError as exc:
        audit = _sap_pod_audit_from_tracker_fix(
            False,
            lr,
            de,
            has_pod_date=bool(pod_date),
            error=str(exc),
            phase="patch",
        )
        try:
            _update_delhivery_lr_pod_sap_response(pod_id, audit)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "fix_delhivery_pod_sap_from_rds persist failure")
        raise

    http_st = sap_body.get("http_status") if isinstance(sap_body, dict) else None
    try:
        hs = int(http_st) if http_st is not None else 204
    except (TypeError, ValueError):
        hs = 204

    audit = _sap_pod_audit_from_tracker_fix(
        True,
        lr,
        de,
        http_status=hs,
        has_pod_date=bool(pod_date),
    )
    audit["patch_keys"] = list(sap_payload.keys()) if isinstance(sap_payload, dict) else []
    audit["fix_pod_resolved_status"] = resolved_status
    audit["fix_pod_status_basis"] = status_origin
    audit["fix_pod_last_webhook_status"] = last_webhook_status

    _update_delhivery_lr_pod_sap_response(pod_id, audit)

    rds_status_synced = _sync_delhivery_lr_delhivery_status_if_distinct(lr, last_webhook_status)

    return {
        "status": "success",
        "lrnum": lr,
        "doc_entry": de,
        "message": _("POD fields sent to SAP for DocEntry {0}.").format(de),
        "sap_pod_response": audit,
        "u_frappe_grn_key": grn_key,
        "fix_pod_resolved_status": resolved_status,
        "fix_pod_status_basis": status_origin,
        "fix_pod_last_webhook_status": last_webhook_status,
        "delhivery_status_rds_synced": bool(rds_status_synced),
    }


def _run_sap_follow_through(
    doc_entry: int,
    lrnum: str,
    doc_num: Optional[str],
    series: Optional[str],
    tracking_raw: dict,
    summary: dict,
    postgres_patched: bool,
) -> dict:
    """
    SAP Service Layer PATCH and dependent second snapshot / Postgres ``sap_response`` updates.

    Called from ``_sap_follow_through_job`` (background) or inline when ``full_sync`` / enqueue fails.
    """
    sap_payload = None
    sap_response = None
    sap_url = None
    sap_error = None
    try:
        sap_payload, sap_response, sap_url = patch_sap_invoice_lr(doc_entry, lrnum)
    except (frappe.ValidationError, ValueError) as exc:
        sap_error = str(exc)
        frappe.log_error(
            title="Logistics delivery SAP PATCH skipped",
            message=f"doc_entry={doc_entry} lrnum={lrnum} error={sap_error}",
        )
    except Exception as exc:
        sap_error = str(exc)
        frappe.log_error(frappe.get_traceback(), "Logistics delivery SAP PATCH failed")

    if sap_error:
        sap_response = _sap_patch_audit_failure(
            doc_entry,
            lrnum,
            sap_error,
            url=f"{_service_layer_base_url()}/Invoices({doc_entry})",
        )
        if patch_delhivery_lr_row_in_postgres(
            lrnum, doc_entry, doc_num, series, summary, sap_response=sap_response
        ):
            postgres_patched = True

    snapshot_after = None
    db_response_final = None
    if sap_error is None and sap_response is not None:
        snapshot_after = build_snapshot_api_body(
            lrnum=lrnum,
            doc_entry=doc_entry,
            doc_num=doc_num,
            series=series,
            tracking_raw=tracking_raw,
            sap_response=sap_response,
        )
        db_response_final, did_patch = _save_tracking_snapshot_and_patch_lr_row_one_connection(
            snapshot_after,
            summary,
            doc_entry,
            doc_num,
            series,
            sap_response=sap_response,
        )
        if did_patch:
            postgres_patched = True

    return {
        "sap_payload": sap_payload,
        "sap_response": sap_response,
        "sap_url": sap_url,
        "sap_error": sap_error,
        "snapshot_after": snapshot_after,
        "db_response_final": db_response_final,
        "postgres_patched": postgres_patched,
    }


def _return_submit_with_sap_result(
    base: dict, ft: dict, de: int, lr: str, used_delhivery_preview_cache: bool = False
) -> dict:
    """Merge ``_run_sap_follow_through`` output into the portal API response dict."""
    sap_error = ft["sap_error"]
    merged = {
        **base,
        "snapshot_payload_final": ft["snapshot_after"],
        "db_response_final": ft["db_response_final"],
        "sap_request": {
            "method": "PATCH",
            "url": ft["sap_url"],
            "payload": ft["sap_payload"] or {"U_LRtrackno": lr},
        },
        "sap_response": ft["sap_response"],
        "sap_error": sap_error,
        "postgres_columns_patched": ft["postgres_patched"],
        "sap_queued": False,
        "used_delhivery_preview_cache": used_delhivery_preview_cache,
    }
    if sap_error:
        if ft["postgres_patched"]:
            msg = _(
                "Delhivery tracking saved for LR {0}. SAP could not update DocEntry {1}: {2}. "
                "Fix the issue in SAP and submit again for this invoice."
            ).format(lr, de, sap_error)
        else:
            msg = _(
                "Delhivery tracking fetched but the database row could not be updated. "
                "SAP could not update DocEntry {0}: {1}."
            ).format(de, sap_error)
        return {**merged, "status": "partial", "message": msg}
    return {
        **merged,
        "status": "success",
        "message": _("LR saved to database and SAP invoice updated."),
    }


def _sap_follow_through_enqueue_now() -> bool:
    """If True (default), SAP job runs in-process via ``enqueue(..., now=True)`` (no worker required)."""
    return not bool(cint(frappe.conf.get("logistics_delivery_sap_use_queue")))


def _sap_follow_through_job(
    doc_entry=None,
    lrnum=None,
    doc_num=None,
    series=None,
    tracking_raw: Any = None,
    postgres_patched=None,
):
    """RQ job: SAP PATCH + second snapshot + Postgres ``sap_response`` (after portal saved snapshot/RDS)."""
    try:
        raw: Any = tracking_raw
        if isinstance(raw, str):
            raw = frappe.parse_json(raw)
        if not isinstance(raw, dict):
            raw = {}
        de = cint(doc_entry)
        lr = _clip_lrnum(lrnum)
        doc_num_s = (str(doc_num).strip() if doc_num not in (None, "") else None) or None
        series_s = (str(series).strip() if series not in (None, "") else None) or None
        pp = bool(postgres_patched) if postgres_patched is not None else False
        summary = _tracking_summary(raw)
        _run_sap_follow_through(de, lr, doc_num_s, series_s, raw, summary, pp)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Logistics delivery background SAP follow-through")


def _enqueue_sap_follow_through(
    de: int,
    lr: str,
    doc_num_s: Optional[str],
    series_s: Optional[str],
    tracking_raw: dict,
    postgres_patched: bool,
) -> bool:
    try:
        frappe.enqueue(
            "khanal_tech_integrations.api.logistics_delivery.lr_submit._sap_follow_through_job",
            queue="default",
            doc_entry=de,
            lrnum=lr,
            doc_num=doc_num_s,
            series=series_s,
            tracking_raw=tracking_raw,
            postgres_patched=postgres_patched,
            job_name=f"ld-sap-{de}-{lr}"[:100],
            now=_sap_follow_through_enqueue_now(),
        )
        return True
    except Exception as exc:
        frappe.log_error(
            title="Logistics delivery SAP enqueue failed",
            message=str(exc),
        )
        return False


def _complete_logistics_delivery_submit_job(
    doc_entry=None,
    lrnum=None,
    doc_num=None,
    series=None,
    tracking_raw: Any = None,
) -> dict:
    """
    Postgres snapshot + patch, then SAP, then final snapshot + ``sap_response`` in Postgres.

    Used as the **default** background job after Delhivery, or inline when enqueue fails.
    """
    assert_delhivery_api_configured()

    raw: Any = tracking_raw
    if isinstance(raw, str):
        raw = frappe.parse_json(raw)
    if not isinstance(raw, dict):
        raw = {}

    de = cint(doc_entry)
    if not de:
        frappe.throw(_("DocEntry is required."), frappe.ValidationError)

    lr = _clip_lrnum(lrnum)
    doc_num_s = (str(doc_num).strip() if doc_num not in (None, "") else None) or None
    series_s = (str(series).strip() if series not in (None, "") else None) or None

    snapshot_before = build_snapshot_api_body(
        lrnum=lr,
        doc_entry=de,
        doc_num=doc_num_s,
        series=series_s,
        tracking_raw=raw,
        sap_response=None,
    )
    summary = _tracking_summary(raw)
    db_response_initial, postgres_patched = _save_tracking_snapshot_and_patch_lr_row_one_connection(
        snapshot_before,
        summary,
        de,
        doc_num_s,
        series_s,
        sap_response=None,
    )

    ft = _run_sap_follow_through(de, lr, doc_num_s, series_s, raw, summary, postgres_patched)
    sap_payload = ft["sap_payload"]
    sap_response = ft["sap_response"]
    sap_url = ft["sap_url"]
    sap_error = ft["sap_error"]
    snapshot_after = ft["snapshot_after"]
    db_response_final = ft["db_response_final"]
    postgres_patched = ft["postgres_patched"]

    base = {
        "lrnum": lr,
        "doc_entry": de,
        "doc_num": doc_num_s,
        "series": series_s,
        "delhivery_status": summary.get("delhivery_status"),
        "waybill": summary.get("waybill"),
        "location": summary.get("location"),
        "shipment_remark": summary.get("shipment_remark"),
        "snapshot_payload_initial": snapshot_before,
        "snapshot_payload_final": snapshot_after,
        "db_response_initial": db_response_initial,
        "db_response_final": db_response_final,
        "sap_request": {
            "method": "PATCH",
            "url": sap_url,
            "payload": sap_payload or {"U_LRtrackno": lr},
        },
        "sap_response": sap_response,
        "sap_error": sap_error,
        "postgres_columns_patched": postgres_patched,
        "sap_queued": False,
    }

    if sap_error:
        if postgres_patched:
            msg = _(
                "Delhivery tracking saved for LR {0}. SAP could not update DocEntry {1}: {2}. "
                "Fix the issue in SAP and submit again for this invoice."
            ).format(lr, de, sap_error)
        else:
            msg = _(
                "Delhivery tracking fetched but the database row could not be updated. "
                "SAP could not update DocEntry {0}: {1}."
            ).format(de, sap_error)
        return {**base, "status": "partial", "message": msg}

    return {
        **base,
        "status": "success",
        "message": _("LR saved to database and SAP invoice updated."),
    }


def _enqueue_complete_logistics_submit(
    de: int,
    lr: str,
    doc_num_s: Optional[str],
    series_s: Optional[str],
    tracking_raw: dict,
) -> bool:
    try:
        frappe.enqueue(
            "khanal_tech_integrations.api.logistics_delivery.lr_submit._complete_logistics_delivery_submit_job",
            queue="default",
            doc_entry=de,
            lrnum=lr,
            doc_num=doc_num_s,
            series=series_s,
            tracking_raw=tracking_raw,
            job_name=f"ld-submit-{de}-{lr}"[:100],
        )
        return True
    except Exception as exc:
        frappe.log_error(
            title="Logistics delivery submit enqueue failed",
            message=str(exc),
        )
        return False


@frappe.whitelist()
def submit_lr_and_sync_sap(doc_entry=None, doc_num=None, series=None, lrnum=None):
    """
    Default: snapshot + first RDS patch during Submit; SAP + follow-up in background.

    See module docstring for ``logistics_delivery_async_snapshot_rds_after_delhivery`` and full-sync flags.
    """
    _require_logistics_portal()
    assert_delhivery_api_configured()

    de = cint(doc_entry)
    if not de:
        frappe.throw(_("DocEntry is required."), frappe.ValidationError)

    lr = _clip_lrnum(lrnum)
    doc_num_s = (str(doc_num).strip() if doc_num not in (None, "") else None) or None
    series_s = (str(series).strip() if series not in (None, "") else None) or None

    portal_entry = _get_lr_portal_cache(lr)
    tracking_raw: Any = None
    used_preview_cache = False
    skip_snapshot_rds = False
    cached_db_response_initial: Any = None
    cached_snapshot_before: Any = None
    cached_postgres_patched = False

    if portal_entry:
        tr = portal_entry.get("tracking_raw")
        if isinstance(tr, dict):
            tracking_raw = tr
            used_preview_cache = True
        if (
            portal_entry.get("snapshot_postgres_done")
            and cint(portal_entry.get("persisted_for_doc_entry")) == de
            and (portal_entry.get("doc_num") or None) == doc_num_s
            and (portal_entry.get("series") or None) == series_s
        ):
            skip_snapshot_rds = True
            cached_db_response_initial = portal_entry.get("db_response_initial")
            cached_snapshot_before = portal_entry.get("snapshot_payload_initial")
            if isinstance(cached_snapshot_before, str):
                try:
                    cached_snapshot_before = json.loads(cached_snapshot_before)
                except (TypeError, ValueError):
                    cached_snapshot_before = None
            cached_postgres_patched = bool(portal_entry.get("postgres_patched"))

    if tracking_raw is not None and not _delhivery_envelope_has_lr(tracking_raw, lr):
        _clear_lr_portal_cache(lr)
        tracking_raw = None
        used_preview_cache = False
        skip_snapshot_rds = False
    if tracking_raw is None:
        tracking_raw = fetch_delhivery_tracking(lr)
        used_preview_cache = False
        skip_snapshot_rds = False

    if skip_snapshot_rds and not isinstance(cached_snapshot_before, dict):
        skip_snapshot_rds = False

    envelope = _normalize_delhivery_track_envelope(tracking_raw, lr)
    tracked_lr = (envelope.get("data") or {}).get("lrnum") if isinstance(envelope.get("data"), dict) else None
    if not tracked_lr:
        frappe.throw(
            _("Delhivery did not return tracking data for LR {0}.").format(lr),
            frappe.ValidationError,
        )

    summary = _tracking_summary(tracking_raw)

    full_sync = cint(frappe.conf.get("logistics_delivery_full_sync_submit")) or cint(
        frappe.conf.get("logistics_delivery_inline_sap_after_submit")
    )
    async_snapshot_rds = cint(frappe.conf.get("logistics_delivery_async_snapshot_rds_after_delhivery"))

    if full_sync:
        snapshot_before = build_snapshot_api_body(
            lrnum=lr,
            doc_entry=de,
            doc_num=doc_num_s,
            series=series_s,
            tracking_raw=tracking_raw,
            sap_response=None,
        )
        db_response_initial, postgres_patched = _save_tracking_snapshot_and_patch_lr_row_one_connection(
            snapshot_before,
            summary,
            de,
            doc_num_s,
            series_s,
            sap_response=None,
        )
        base = {
            "lrnum": lr,
            "doc_entry": de,
            "doc_num": doc_num_s,
            "series": series_s,
            "delhivery_status": summary.get("delhivery_status"),
            "waybill": summary.get("waybill"),
            "location": summary.get("location"),
            "shipment_remark": summary.get("shipment_remark"),
            "snapshot_payload_initial": snapshot_before,
            "snapshot_payload_final": None,
            "db_response_initial": db_response_initial,
            "db_response_final": None,
            "sap_request": {
                "method": "PATCH",
                "url": f"{_service_layer_base_url()}/Invoices({de})",
                "payload": {"U_LRtrackno": lr},
            },
            "sap_response": None,
            "sap_error": None,
            "postgres_columns_patched": postgres_patched,
        }
        ft = _run_sap_follow_through(
            de, lr, doc_num_s, series_s, tracking_raw, summary, postgres_patched
        )
        return _return_submit_with_sap_result(base, ft, de, lr, used_preview_cache)

    if async_snapshot_rds:
        if _enqueue_complete_logistics_submit(de, lr, doc_num_s, series_s, tracking_raw):
            sap_url_placeholder = f"{_service_layer_base_url()}/Invoices({de})"
            return {
                "lrnum": lr,
                "doc_entry": de,
                "doc_num": doc_num_s,
                "series": series_s,
                "delhivery_status": summary.get("delhivery_status"),
                "waybill": summary.get("waybill"),
                "location": summary.get("location"),
                "shipment_remark": summary.get("shipment_remark"),
                "snapshot_payload_initial": None,
                "snapshot_payload_final": None,
                "db_response_initial": None,
                "db_response_final": None,
                "sap_request": {
                    "method": "PATCH",
                    "url": sap_url_placeholder,
                    "payload": {"U_LRtrackno": lr},
                },
                "sap_response": None,
                "sap_error": None,
                "postgres_columns_patched": False,
                "status": "accepted",
                "message": _(
                    "LR verified with Delhivery. Saving snapshot, database row, and SAP are processing in the background — "
                    "open the Tracker report in a moment to confirm."
                ),
                "sap_queued": True,
                "used_delhivery_preview_cache": used_preview_cache,
            }

        out = _complete_logistics_delivery_submit_job(de, lr, doc_num_s, series_s, tracking_raw)
        out["used_delhivery_preview_cache"] = used_preview_cache
        return out

    if skip_snapshot_rds:
        snapshot_before = cached_snapshot_before or build_snapshot_api_body(
            lrnum=lr,
            doc_entry=de,
            doc_num=doc_num_s,
            series=series_s,
            tracking_raw=tracking_raw,
            sap_response=None,
        )
        db_response_initial = cached_db_response_initial if cached_db_response_initial is not None else {}
        postgres_patched = cached_postgres_patched
    else:
        snapshot_before = build_snapshot_api_body(
            lrnum=lr,
            doc_entry=de,
            doc_num=doc_num_s,
            series=series_s,
            tracking_raw=tracking_raw,
            sap_response=None,
        )
        db_response_initial, postgres_patched = _save_tracking_snapshot_and_patch_lr_row_one_connection(
            snapshot_before,
            summary,
            de,
            doc_num_s,
            series_s,
            sap_response=None,
        )
    base = {
        "lrnum": lr,
        "doc_entry": de,
        "doc_num": doc_num_s,
        "series": series_s,
        "delhivery_status": summary.get("delhivery_status"),
        "waybill": summary.get("waybill"),
        "location": summary.get("location"),
        "shipment_remark": summary.get("shipment_remark"),
        "snapshot_payload_initial": snapshot_before,
        "snapshot_payload_final": None,
        "db_response_initial": db_response_initial,
        "db_response_final": None,
        "sap_request": {
            "method": "PATCH",
            "url": f"{_service_layer_base_url()}/Invoices({de})",
            "payload": {"U_LRtrackno": lr},
        },
        "sap_response": None,
        "sap_error": None,
        "postgres_columns_patched": postgres_patched,
        "skipped_snapshot_rds_on_submit": skip_snapshot_rds,
    }
    if _enqueue_sap_follow_through(de, lr, doc_num_s, series_s, tracking_raw, postgres_patched):
        return {
            **base,
            "status": "accepted",
            "message": _(
                "Tracking saved to the database. SAP invoice update is processing in the background — "
                "open the Tracker report in a moment to confirm."
            ),
            "sap_queued": True,
            "used_delhivery_preview_cache": used_preview_cache,
        }
    ft = _run_sap_follow_through(
        de, lr, doc_num_s, series_s, tracking_raw, summary, postgres_patched
    )
    return _return_submit_with_sap_result(base, ft, de, lr, used_preview_cache)


def _summary_from_lr_row(row: dict) -> dict:
    return {
        "delhivery_status": row.get("delhivery_status"),
        "status_type": row.get("status_type"),
        "shipment_remark": row.get("shipment_remark"),
        "location": row.get("location"),
        "waybill": row.get("waybill"),
    }


def _tracking_raw_from_row(row: dict) -> Optional[dict]:
    raw = row.get("raw_tracking")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return None


def _retry_sap_sync_core(lrnum: str) -> dict:
    """Retry SAP for one LR; returns result dict (does not throw on SAP failure)."""
    from khanal_tech_integrations.api.logistics_delivery.tracker_data import (
        _parse_sap_response_field,
        _sap_synced_for_doc,
        fetch_delhivery_lr_row,
        row_needs_sap_retry,
    )

    lr = _clip_lrnum(lrnum)
    row = fetch_delhivery_lr_row(lr)
    if not row:
        return {
            "status": "skipped",
            "lrnum": lr,
            "message": _("LR {0} was not found in the database.").format(lr),
        }

    de = cint(row.get("doc_entry"))
    if not de:
        return {
            "status": "skipped",
            "lrnum": lr,
            "message": _("DocEntry is missing for LR {0}.").format(lr),
        }

    doc_num_s = (str(row.get("doc_num")).strip() if row.get("doc_num") not in (None, "") else None) or None
    series_s = (str(row.get("series")).strip() if row.get("series") not in (None, "") else None) or None
    sap_existing = _parse_sap_response_field(row.get("sap_response"))

    if _sap_synced_for_doc(sap_existing, de):
        return {
            "status": "already_synced",
            "lrnum": lr,
            "doc_entry": de,
            "message": _("Already synced (DocEntry {0}).").format(de),
            "sap_response": sap_existing,
        }

    if not row_needs_sap_retry(row):
        return {
            "status": "skipped",
            "lrnum": lr,
            "doc_entry": de,
            "message": _("No SAP retry needed for LR {0}.").format(lr),
        }

    summary = _summary_from_lr_row(row)
    sap_error = None
    sap_payload = None
    sap_response = None
    sap_url = None

    try:
        sap_payload, sap_response, sap_url = patch_sap_invoice_lr(de, lr)
    except (frappe.ValidationError, ValueError) as exc:
        sap_error = str(exc)
    except Exception as exc:
        sap_error = str(exc)
        frappe.log_error(frappe.get_traceback(), "Logistics delivery SAP retry failed")

    if sap_error:
        sap_response = _sap_patch_audit_failure(
            de,
            lr,
            sap_error,
            url=f"{_service_layer_base_url()}/Invoices({de})",
        )
        patch_delhivery_lr_row_in_postgres(lr, de, doc_num_s, series_s, summary, sap_response=sap_response)
        return {
            "status": "failed",
            "lrnum": lr,
            "doc_entry": de,
            "message": sap_error,
            "sap_response": sap_response,
        }

    patch_delhivery_lr_row_in_postgres(lr, de, doc_num_s, series_s, summary, sap_response=sap_response)

    tracking_raw = _tracking_raw_from_row(row)
    if tracking_raw:
        try:
            snapshot_after = build_snapshot_api_body(
                lrnum=lr,
                doc_entry=de,
                doc_num=doc_num_s,
                series=series_s,
                tracking_raw=tracking_raw,
                sap_response=sap_response,
            )
            save_tracking_snapshot(snapshot_after)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "SAP retry snapshot POST skipped")

    return {
        "status": "success",
        "lrnum": lr,
        "doc_entry": de,
        "doc_num": doc_num_s,
        "message": _("SAP updated (DocEntry {0}).").format(de),
        "sap_response": sap_response,
        "sap_request": {
            "method": "PATCH",
            "url": sap_url,
            "payload": sap_payload or {"U_LRtrackno": lr},
        },
    }


@frappe.whitelist()
def portal_lr_row_sap_state(lrnum=None, doc_entry=None):
    """
    For the delivery portal while polling after Submit: read ``delhivery_lr.sap_response``
    so we can detect a background SAP PATCH failure without waiting on SAP invoice GET alone.
    """
    _require_logistics_portal()
    from khanal_tech_integrations.api.logistics_delivery.tracker_data import (
        _parse_sap_response_field,
        fetch_delhivery_lr_row,
    )

    lr = _clip_lrnum(lrnum)
    de = cint(doc_entry)
    if not de:
        frappe.throw(_("DocEntry is required."), frappe.ValidationError)

    row = fetch_delhivery_lr_row(lr)
    if not row:
        return {
            "lr_found": False,
            "sap_failed_for_submit": False,
            "sap_error": None,
        }

    row_de = cint(row.get("doc_entry"))
    if row_de != de:
        return {
            "lr_found": True,
            "doc_entry_match": False,
            "sap_failed_for_submit": False,
            "sap_error": None,
        }

    sap = _parse_sap_response_field(row.get("sap_response"))
    if not isinstance(sap, dict):
        return {
            "lr_found": True,
            "doc_entry_match": True,
            "sap_failed_for_submit": False,
            "sap_error": None,
        }

    failed = sap.get("ok") is False or sap.get("sap_sync_status") == "failed"
    patch = sap.get("patch") if isinstance(sap.get("patch"), dict) else {}
    patch_lr = (patch.get("U_LRtrackno") or "").strip() if patch else ""
    matches_lr = not patch_lr or patch_lr == lr

    sap_error = None
    if isinstance(sap.get("error"), str):
        sap_error = sap["error"].strip() or None

    return {
        "lr_found": True,
        "doc_entry_match": True,
        "sap_failed_for_submit": bool(failed and matches_lr),
        "sap_error": sap_error,
    }


@frappe.whitelist()
def retry_sap_sync_for_lr(lrnum=None):
    """
    Retry SAP PATCH U_LRtrackno only (no Delhivery). Used from Tracker report.
    """
    _require_logistics_portal()
    result = _retry_sap_sync_core(lrnum or "")
    if result.get("status") == "failed":
        frappe.throw(
            _("SAP could not be updated for DocEntry {0}: {1}").format(
                result.get("doc_entry") or "?", result.get("message")
            ),
            frappe.ValidationError,
        )
    if result.get("status") == "skipped" and not result.get("doc_entry"):
        frappe.throw(result.get("message") or _("Retry skipped."), frappe.ValidationError)
    return result


@frappe.whitelist()
def retry_sap_sync_all_failed(max_rows=None):
    """
    Retry SAP PATCH for all failed/stale rows (up to max_rows, default 50).
    """
    _require_logistics_portal()

    from khanal_tech_integrations.api.logistics_delivery.tracker_data import fetch_sap_retry_candidates

    lim = min(max(cint(max_rows) or 50, 1), 100)
    candidates = fetch_sap_retry_candidates(lim)

    if not candidates:
        return {
            "status": "done",
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "already_synced": 0,
            "message": _("No records need SAP retry."),
            "results": [],
        }

    results = []
    counts = {"success": 0, "failed": 0, "skipped": 0, "already_synced": 0}

    for row in candidates:
        lr = row.get("lrnum") or ""
        try:
            item = _retry_sap_sync_core(lr)
        except Exception as exc:
            item = {
                "status": "failed",
                "lrnum": lr,
                "message": str(exc),
            }
        st = item.get("status") or "failed"
        if st in counts:
            counts[st] += 1
        else:
            counts["failed"] += 1
        results.append(item)

    msg = _("Retried {0} record(s): {1} succeeded, {2} failed.").format(
        len(results),
        counts["success"],
        counts["failed"],
    )
    if counts["skipped"] or counts["already_synced"]:
        msg += " " + _("{0} skipped, {1} already synced.").format(
            counts["skipped"],
            counts["already_synced"],
        )

    return {
        "status": "done",
        "total": len(results),
        **counts,
        "message": msg,
        "results": results,
    }
