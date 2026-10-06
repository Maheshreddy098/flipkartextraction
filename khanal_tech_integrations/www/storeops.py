# Copyright (c) 2026, Khanal Tech and Contributors
# MIT License

from __future__ import unicode_literals
import frappe

no_cache = 1


def get_context(context):
	"""
	Provide boot context for StoreOps SPA
	"""
	csrf_token = frappe.sessions.get_csrf_token()

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
		# socketio_port must be present so the frontend connects to the correct
		# socket server port. In dev Frappe runs web on 8000/8001 and socket on
		# 9000/9001 (web+1000). In prod nginx proxies /socket.io on the same port
		# as the site, so the frontend port-resolution logic handles that case.
		"socketio_port": frappe.conf.get("socketio_port") or 9000,
	})
