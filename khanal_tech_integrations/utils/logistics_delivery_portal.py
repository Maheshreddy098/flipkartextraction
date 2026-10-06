"""
Access control for the /logistics_delivery website portal.
"""

from urllib.parse import quote

import frappe
from frappe import _

# Role assigned in Frappe User → Roles for portal access (create the Role in Desk if missing)
DELIVERY_LOGISTICS_ROLE = "delivery_logistics"


def _redirect_path() -> str:
    try:
        return frappe.local.request.path or "/logistics_delivery"
    except Exception:
        return "/logistics_delivery"


def ensure_logistics_portal_access():
    """
    Require logged-in user with role `delivery_logistics` only.
    Guest → /login with redirect back. Logged-in without role → 403.
    """
    if frappe.session.user == "Guest":
        target = quote(_redirect_path(), safe="/")
        frappe.redirect(f"/login?redirect-to={target}")

    if DELIVERY_LOGISTICS_ROLE in frappe.get_roles(frappe.session.user):
        return

    frappe.throw(
        _(
            "You need the <strong>{0}</strong> role to open this portal. "
            "Ask a System Manager to assign it on your User record."
        ).format(DELIVERY_LOGISTICS_ROLE),
        frappe.PermissionError,
    )
