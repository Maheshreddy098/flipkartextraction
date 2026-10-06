import json
import urllib3
import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_REPORT_CODE = "RCRI0033"
_CR_SESSION_TIMEOUT_MINUTES = 30


def _cr_settings():
    """Read CR credentials and URL from Consumables SAP Settings in one DB call
    — consumables' own isolated settings Single, separate from the shared
    "SAP Settings" every other vertical reads.
    Returns (s, base_url, creds) so callers can pass s to _get_cached_session without re-querying.
    """
    s = frappe.get_single("Consumables SAP Settings")
    base_url = (getattr(s, "sap_crystal_report_url", None) or "").strip().rstrip("/")
    company_db = (getattr(s, "cr_companydb", None) or "").strip()
    username = (getattr(s, "cr_username", None) or "").strip()
    password = (getattr(s, "cr_password", None) or "").strip()

    if not base_url or not company_db or not username or not password:
        frappe.throw(_("SAP Crystal Reports credentials not fully configured in Consumables SAP Settings."))

    return s, base_url, {"CompanyDB": company_db, "UserName": username, "Password": password}


def _get_cached_session(s):
    """Restore CR session from already-loaded Consumables SAP Settings doc. Returns session or None."""
    import requests

    try:
        cr_session_str = s.cr_session
        cr_expires_on = s.cr_expires_on

        if not cr_session_str or not cr_expires_on:
            return None
        if get_datetime(cr_expires_on) <= now_datetime():
            return None

        cookies = json.loads(cr_session_str)
        if not cookies:
            return None

        session = requests.Session()
        session.verify = False
        for name, value in cookies.items():
            session.cookies.set(name, value)
        return session
    except Exception:
        return None


def _renew_session(base_url, creds):
    """Login to CR, persist session cookies + expiry to Consumables SAP Settings. Returns session."""
    import requests

    session = requests.Session()
    session.verify = False

    resp = session.post(f"{base_url}/login", json=creds, timeout=30)
    if not resp.ok:
        frappe.throw(
            _("SAP Crystal Reports login failed ({0}): {1}").format(resp.status_code, resp.text[:200])
        )
    try:
        body = resp.json()
        if body.get("code", 0) < 0:
            err = body.get("message", {}).get("value", resp.text[:200])
            frappe.throw(_("SAP Crystal Reports login failed: {0}").format(err))
    except (ValueError, AttributeError):
        pass

    cookies = {c.name: c.value for c in session.cookies}
    frappe.db.set_value(
        "Consumables SAP Settings",
        "Consumables SAP Settings",
        {
            "cr_session": json.dumps(cookies),
            "cr_expires_on": add_to_date(now_datetime(), minutes=_CR_SESSION_TIMEOUT_MINUTES),
        },
        update_modified=False,
    )
    frappe.db.commit()
    return session


@frappe.whitelist()
def initiate_cr_session():
    """Manually trigger CR session renewal from Consumables SAP Settings form button."""
    try:
        _s, base_url, creds = _cr_settings()
        _renew_session(base_url, creds)
        return {"status": "success", "message": "CR session initiated successfully."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "CR Initiate Session Error")
        return {"status": "error", "message": str(e)}


def get_delivery_challan_base64(doc_entry: str) -> str:
    """Export delivery challan PDF from SAP Crystal Reports.
    Returns base64-encoded PDF string. No file stored.

    SAP CR returns Content-Type: application/octet-stream but body is already
    base64-encoded PDF text (confirmed: JVBERi0x = base64 of %PDF-1.).
    """
    s, base_url, creds = _cr_settings()

    session = _get_cached_session(s) or _renew_session(base_url, creds)
    doc_entry = str(doc_entry).strip()

    url = f"{base_url}/rs/v1/ExportPDFData"
    params = {"DocCode": _REPORT_CODE, "DocKey": doc_entry}
    body = [{"name": "DocKey@", "type": "xsd:string", "value": [[doc_entry]]}]

    resp = session.post(url, params=params, json=body, timeout=60)

    if resp.status_code == 401:
        session = _renew_session(base_url, creds)
        resp = session.post(url, params=params, json=body, timeout=60)

    if not resp.ok:
        frappe.throw(
            _("Delivery challan export failed ({0}): {1}").format(resp.status_code, resp.text[:300])
        )
    if not resp.content:
        frappe.throw(_("SAP Crystal Reports returned empty response for DocEntry {0}.").format(doc_entry))

    return resp.text.strip().replace("\r", "").replace("\n", "").replace(" ", "")
