"""
SAP Business One Service Layer: Issue for Production (WowPets Work Order flow).

Modular functions to login, fetch Production Order lines, build payload,
and post InventoryGenExits. Session cached in frappe.cache for 30 minutes.
Used by work_order.consume_and_issue and work_order.create_production_order_and_issue.
"""

import frappe
from frappe import _
import requests
from frappe.utils import nowdate
from khanal_tech_integrations.api.wowpets.sap_master import _SAP_VERIFY_SSL

CACHE_KEY = "sap_issue_session"
CACHE_EXPIRY_SEC = 30 * 60  # 30 minutes


def _get_base_url():
	"""SAP Service Layer base URL (trailing slash). Prefer frappe.conf, else INC SAP Settings."""
	url = frappe.conf.get("sap_b1_url") or ""
	if not url:
		url = (frappe.db.get_single_value("INC SAP Settings", "sap_b1_url") or "").strip()
	return (url or "").rstrip("/") + "/" if url else ""


def _get_login_creds():
	"""Return dict CompanyDB, UserName, Password for SAP Login. Prefer frappe.conf."""
	if getattr(frappe.conf, "sap_company", None) and getattr(frappe.conf, "sap_user", None):
		return {
			"CompanyDB": frappe.conf.sap_company,
			"UserName": frappe.conf.sap_user,
			"Password": frappe.conf.get("sap_password") or "",
		}
	doc = frappe.get_single("INC SAP Settings")
	return {
		"CompanyDB": doc.companydb or "",
		"UserName": doc.username or "",
		"Password": doc.get_password("password") or "",
	}


def sap_login():
	"""
	Login to SAP Service Layer via POST /Login.
	Store session cookies (B1SESSION, ROUTEID) in frappe.cache for 30 minutes.
	Returns cookies dict for use with requests.
	"""
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return cached

	base_url = _get_base_url()
	if not base_url:
		frappe.throw("SAP base URL not set. Set frappe.conf.sap_b1_url or INC SAP Settings.")

	creds = _get_login_creds()
	if not creds.get("CompanyDB") or not creds.get("UserName"):
		frappe.throw("SAP credentials not set. Set frappe.conf (sap_company, sap_user, sap_password) or INC SAP Settings.")

	r = requests.post(
		f"{base_url.rstrip('/')}/Login",
		json=creds,
		verify=_SAP_VERIFY_SSL,
		timeout=15,
		headers={"Content-Type": "application/json", "Accept": "*/*"},
	)
	if r.status_code != 200:
		frappe.throw("SAP Login Failed")

	cookies = r.cookies.get_dict()
	frappe.cache().set_value(CACHE_KEY, cookies, expires_in_sec=CACHE_EXPIRY_SEC)
	return cookies


def get_production_order_lines(po_id, cookies):
	"""
	Fetch production order lines from SAP.
	GET /b1s/v1/ProductionOrders({DocEntry})?$select=ProductionOrderLines
	Returns list of line objects.
	"""
	base_url = _get_base_url()
	if not base_url:
		frappe.throw("SAP base URL not set.")
	url = f"{base_url.rstrip('/')}/ProductionOrders({po_id})?$select=ProductionOrderLines"
	r = requests.get(url, cookies=cookies, verify=_SAP_VERIFY_SSL, timeout=30)
	if r.status_code != 200:
		frappe.throw("Failed to fetch Production Order from SAP")
	data = r.json()
	lines = data.get("ProductionOrderLines")
	if lines is None:
		frappe.throw("Production Order has no ProductionOrderLines in response")
	return lines


def build_item_line_map(lines):
	"""
	Create mapping ItemNo -> LineNumber for all lines where ItemType == "pit_Item".
	Keys are uppercase so lookup is case-insensitive.
	"""
	item_map = {}
	for line in lines or []:
		if line.get("ItemType") == "pit_Item":
			item_no = (line.get("ItemNo") or line.get("ItemCode") or "").strip()
			ln = line.get("LineNumber") if line.get("LineNumber") is not None else line.get("LineNum")
			if item_no and ln is not None:
				item_map[item_no.upper()] = int(ln)
	return item_map


def build_issue_payload(po_id, items, item_map, doc_date=None):
	"""
	Build payload for POST /InventoryGenExits.

	items: list of dicts with item_code, qty, warehouse, batch_no (optional).
	Each DocumentLine: BaseEntry, BaseLine, Quantity, WarehouseCode, BatchNumbers (BatchNumber, Quantity only).
	No ItemCode in BatchNumbers. No AccountCode or UseBaseUnits.
	"""
	doc_date = doc_date or nowdate()
	document_lines = []
	for item in items:
		code = (item.get("item_code") or "").strip()
		if not code:
			continue
		base_line = item_map.get(code.upper())
		if base_line is None:
			frappe.throw(f"Item {code} not found in SAP Production Order")
		qty = abs(float(item.get("qty") or 0))
		if qty == int(qty):
			qty = int(qty)
		line = {
			"BaseEntry": int(po_id),
			"BaseLine": base_line,
			"Quantity": qty,
			"WarehouseCode": (item.get("warehouse") or "").strip(),
		}
		batch_no = (item.get("batch_no") or "").strip()
		if batch_no:
			line["BatchNumbers"] = [{"BatchNumber": batch_no, "Quantity": qty}]
		document_lines.append(line)

	return {
		"JournalMemo": "Issue for Production",
		"DocDate": doc_date,
		"DocumentLines": document_lines,
	}


def post_inventory_issue(payload, cookies):
	"""
	Post payload to POST /InventoryGenExits.
	On 401: clear cache, login again, retry once.
	On error: extract error.message.value and frappe.throw.
	Returns SAP response JSON.
	"""
	base_url = _get_base_url()
	if not base_url:
		frappe.throw("SAP base URL not set.")
	url = f"{base_url.rstrip('/')}/InventoryGenExits"
	headers = {"Content-Type": "application/json", "Accept": "application/json"}

	r = requests.post(url, json=payload, cookies=cookies, verify=_SAP_VERIFY_SSL, timeout=60, headers=headers)

	if r.status_code == 401:
		frappe.cache().delete_value(CACHE_KEY)
		cookies = sap_login()
		r = requests.post(url, json=payload, cookies=cookies, verify=_SAP_VERIFY_SSL, timeout=60, headers=headers)

	if r.status_code not in (200, 201):
		try:
			err_body = r.json()
			msg = (err_body.get("error") or {}).get("message") or {}
			value = msg.get("value") if isinstance(msg, dict) else str(msg)
		except Exception:
			value = r.text or f"HTTP {r.status_code}"
		frappe.throw(f"SAP Issue for Production failed: {value}")

	return r.json()


@frappe.whitelist()
def issue_for_production(po_id, items, doc_date=None):
	"""
	Post Issue for Production to SAP. Uses cached session; on 401 re-login and retry.

	po_id: SAP Production Order DocEntry (int or string).
	items: list of dicts with item_code, qty, warehouse, batch_no (optional).
	doc_date: optional (default today).

	Example items:
	[
		{"item_code": "PMDC1126", "qty": 1, "warehouse": "WO - STR", "batch_no": "OR01263XL"},
		{"item_code": "FGDC0629", "qty": 1, "warehouse": "WO - STR", "batch_no": "NU0724OL"}
	]

	Returns SAP response JSON (e.g. DocEntry, DocumentNumber).
	"""
	from khanal_tech_integrations.api.wowpets.auth import check_wowpets_access, get_user_team
	check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can post Issue for Production"), frappe.PermissionError)

	if isinstance(items, str):
		import json
		items = json.loads(items)
	po_id = int(po_id)
	cookies = sap_login()
	lines = get_production_order_lines(po_id, cookies)
	item_map = build_item_line_map(lines)
	payload = build_issue_payload(po_id, items, item_map, doc_date=doc_date)
	response = post_inventory_issue(payload, cookies)
	return response
