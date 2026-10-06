# Copyright (c) 2026, Khanal Tech and Contributors
# MIT License

import frappe

no_cache = 1


def get_context(context):
    """Boot context for the Amazon US Ops Console SPA (/amazonus)."""
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/amazonus"
        raise frappe.Redirect

    if not context:
        context = frappe._dict()

    context.boot = frappe._dict(
        {
            "csrf_token": frappe.sessions.get_csrf_token(),
            "session_user": frappe.session.user,
            "site_name": frappe.local.site,
        }
    )
    return context
