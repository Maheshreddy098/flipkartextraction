# Copyright (c) 2024, Khanal Tech and Contributors
# MIT License

from __future__ import unicode_literals
import frappe

no_cache = 1


def get_context(context):
	"""
	Provide boot context for Kiosk SPA
	"""
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()
	
	if not context:
		context = frappe._dict()
	
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	
	return context


def get_boot():
	"""
	Build boot object with Frappe configuration
	"""
	return frappe._dict({
		"frappe_version": frappe.__version__,
		"site_name": frappe.local.site,
		"session_user": frappe.session.user,
		"lang": frappe.local.lang or "en",
	})

