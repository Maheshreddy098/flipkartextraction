"""
Read Delivery / Delhivery / Postgres settings from Single DocType ``Delivery API Settings``.

``frappe.conf`` / ``site_config.json`` keys with the same field names override the DocType
when set (e.g. for Docker secrets or CI). No secrets are stored in this repository.
"""

from __future__ import annotations

import frappe
from frappe import _

_DEFAULT_JWT_CACHE_TTL_SEC = 50 * 60  # technical default only, not a secret


def _doc():
    if not frappe.db.exists("DocType", "Delivery API Settings"):
        return None
    return frappe.get_single("Delivery API Settings")


def _str_field(doc, fieldname: str) -> str:
    if not doc:
        return ""
    v = doc.get(fieldname)
    return (str(v).strip() if v not in (None, "") else "") or ""


def _password_field(doc, fieldname: str) -> str:
    if not doc:
        return ""
    try:
        return (doc.get_password(fieldname) or "").strip()
    except Exception:
        return ""


def get_delhivery_ltl_track_base_url() -> str:
    v = (frappe.conf.get("delhivery_ltl_track_base_url") or "").strip()
    if v:
        return v.rstrip("/")
    return _str_field(_doc(), "delhivery_ltl_track_base_url").rstrip("/")


def get_delhivery_ltl_username() -> str:
    v = (frappe.conf.get("delhivery_ltl_username") or "").strip()
    if v:
        return v
    return _str_field(_doc(), "delhivery_ltl_username")


def get_delhivery_ltl_password() -> str:
    v = (frappe.conf.get("delhivery_ltl_password") or "").strip()
    if v:
        return v
    return _password_field(_doc(), "delhivery_ltl_password")


def get_delhivery_jwt_cache_ttl_sec() -> int:
    conf = frappe.conf.get("delhivery_jwt_cache_ttl_sec")
    if conf is not None:
        try:
            return max(60, int(conf))
        except (TypeError, ValueError):
            pass
    d = _doc()
    if d and getattr(d, "delhivery_jwt_cache_ttl_sec", None):
        try:
            return max(60, int(d.delhivery_jwt_cache_ttl_sec))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_JWT_CACHE_TTL_SEC


def get_delhivery_tracking_snapshot_url() -> str:
    """Deprecated: tracking snapshots are written directly to PostgreSQL from Frappe."""
    v = (frappe.conf.get("delhivery_tracking_snapshot_url") or "").strip()
    if v:
        return v.rstrip("/")
    return _str_field(_doc(), "delhivery_tracking_snapshot_url").rstrip("/")


def get_delhivery_tracking_snapshot_api_key() -> str:
    """Deprecated: was used for the removed snapshot Lambda (X-Api-Key); unused."""
    v = (frappe.conf.get("delhivery_tracking_snapshot_api_key") or "").strip()
    if v:
        return v
    return _password_field(_doc(), "delhivery_tracking_snapshot_api_key")


def get_delhivery_lr_database_url() -> str:
    v = (frappe.conf.get("delhivery_lr_database_url") or "").strip()
    if v:
        return v
    return _str_field(_doc(), "delhivery_lr_database_url")


def assert_delhivery_lr_database_configured() -> None:
    if not get_delhivery_lr_database_url().strip():
        frappe.throw(
            _(
                "Delhivery LR database URL is not set. Add it in **Delivery API Settings** "
                "or in `site_config.json` as `delhivery_lr_database_url`."
            ),
            frappe.ValidationError,
        )


def assert_delhivery_api_configured() -> None:
    """All settings required for Delhivery track + Postgres snapshot/patch."""
    missing = []
    if not get_delhivery_ltl_track_base_url():
        missing.append(_("Delhivery LTL track base URL"))
    if not get_delhivery_ltl_username():
        missing.append(_("Delhivery LTL username"))
    if not get_delhivery_ltl_password():
        missing.append(_("Delhivery LTL password"))
    if not get_delhivery_lr_database_url().strip():
        missing.append(_("Delhivery LR database URL"))
    if missing:
        frappe.throw(
            _("Missing delivery integration settings: {0}. Configure **Delivery API Settings** or site_config.").format(
                ", ".join(missing)
            ),
            frappe.ValidationError,
        )


def assert_delivery_api_configured() -> None:
    """Alias for full Delhivery + DB check (same as assert_delhivery_api_configured)."""
    assert_delhivery_api_configured()
