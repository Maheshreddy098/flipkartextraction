# Copyright (c) 2025, Khanal Tech Integrations and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

HEADERS = {
	"Accept": "*/*",
	"User-Agent": "Khanal Tech",
	"Content-Type": "application/json",
}


class SAPTestLayer(Document):
	pass


@frappe.whitelist()
def login():
	"""Log into the test SAP B1 Service Layer and persist the session on this doctype."""
	doc = frappe.get_doc("SAP Test Layer")
	credentials_json = {
		"CompanyDB": doc.companydb,
		"Password": doc.get_password("password"),
		"UserName": doc.username,
	}
	response = requests.request(
		"POST", doc.sap_b1_url + "Login",
		data=json.dumps(credentials_json), headers=HEADERS, verify=False,
	)
	cookies = response.cookies.get_dict()
	try:
		body = response.json()
	except Exception:
		body = {}

	if not response.ok:
		err_msg = "Unknown"
		if isinstance(body.get("error"), dict):
			m = body["error"].get("message")
			err_msg = m.get("value", err_msg) if isinstance(m, dict) else (m or err_msg)
		else:
			err_msg = response.text[:500] if response.text else err_msg
		raise Exception(f"Test SAP Login failed ({response.status_code}): {err_msg}")

	b1session = cookies.get("B1SESSION") or body.get("SessionId")
	routeid = cookies.get("ROUTEID")
	if not b1session or not routeid:
		raise Exception("Test SAP Login did not return session cookies. Check URL/CompanyDB/credentials.")

	doc.b1session = b1session
	doc.routeid = routeid
	session_timeout = body.get("SessionTimeout", 30)
	try:
		doc.expires_on = add_to_date(now_datetime(), minutes=int(session_timeout))
	except (TypeError, ValueError):
		doc.expires_on = add_to_date(now_datetime(), minutes=30)
	doc.save(ignore_permissions=True)
	return {"success": True, "message": f"Logged in. Session valid until {doc.expires_on}"}


@frappe.whitelist()
def check_connection():
	"""Test both HANA and Service Layer connectivity for the test SAP box. Read-only for HANA."""
	doc = frappe.get_doc("SAP Test Layer")
	result = {
		"hana": {"ok": False, "message": ""},
		"service_layer": {"ok": False, "message": ""},
	}

	try:
		import hdbcli.dbapi as hana_db

		conn = hana_db.connect(
			address=doc.hana_host,
			port=int(doc.hana_port),
			user=doc.hana_user,
			password=doc.get_password("hana_password"),
			autocommit=False,
		)
		conn.close()
		result["hana"]["ok"] = True
		result["hana"]["message"] = f"Connected to {doc.hana_host}:{doc.hana_port} (schema {doc.hana_schema})"
	except Exception as e:
		result["hana"]["message"] = str(e)

	try:
		login_result = login()
		result["service_layer"]["ok"] = True
		result["service_layer"]["message"] = login_result["message"]
	except Exception as e:
		result["service_layer"]["message"] = str(e)

	return result
