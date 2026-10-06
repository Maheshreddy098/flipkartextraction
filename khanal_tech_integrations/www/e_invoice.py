# Copyright (c) 2026, Khanal Tech and Contributors
# MIT License
"""Context for the E-invoice portal page (/e-invoice).

Lists SAP B1 AR Invoices and lets the user generate the NIC e-invoice JSON for
manual upload on the GST e-invoice portal. Requires a logged-in user.
"""
from __future__ import unicode_literals

import frappe
from frappe.sessions import get_csrf_token

no_cache = 1


def get_context(context):
	# Logged-in users only; guests must authenticate before calling the API.
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/e-invoice"
		raise frappe.Redirect

	context.csrf_token = get_csrf_token()
	context.session_user = frappe.session.user
	return context
