"""
SAP Business One Service Layer: Issue for Production (Real Aquatics Work Order flow).

Modular functions to fetch Production Order lines, build payload, and post
InventoryGenExits. Uses the shared SAP session from sap_master (no separate
session pool). Called by work_order._post_issue_for_production_internal.
"""

import frappe
from frappe import _
from frappe.utils import nowdate
from khanal_tech_integrations.api.real_aquatics.sap_master import (
	_get_sap_session,
	_sap_get_with_retry,
	_sap_post_with_retry,
)


def get_production_order_lines(po_id, session, b1_url):
	"""
	Fetch production order lines from SAP.
	GET /b1s/v1/ProductionOrders({DocEntry})?$select=ProductionOrderLines
	Returns list of line objects.
	"""
	url = f"{b1_url.rstrip('/')}/ProductionOrders({po_id})?$select=ProductionOrderLines"
	resp, session, b1_url = _sap_get_with_retry(url, session, b1_url, timeout=30)
	if resp.status_code != 200:
		frappe.throw("Failed to fetch Production Order from SAP")
	data = resp.json()
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


def post_inventory_issue(payload, session, b1_url):
	"""
	Post payload to POST /InventoryGenExits via shared sap_master session.
	Retry on 401 handled by _sap_post_with_retry.
	On error: extract error.message.value and frappe.throw.
	Returns SAP response JSON.
	"""
	url = f"{b1_url.rstrip('/')}/InventoryGenExits"
	resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, payload, timeout=60)

	if resp.status_code not in (200, 201):
		try:
			err_body = resp.json()
			msg = (err_body.get("error") or {}).get("message") or {}
			value = msg.get("value") if isinstance(msg, dict) else str(msg)
		except Exception:
			value = resp.text or f"HTTP {resp.status_code}"
		frappe.throw(f"SAP Issue for Production failed: {value}")

	return resp.json()


@frappe.whitelist()
def issue_for_production(po_id, items, doc_date=None):
	"""
	Post Issue for Production to SAP using the shared SAP session.

	po_id: SAP Production Order DocEntry (int or string).
	items: list of dicts with item_code, qty, warehouse, batch_no (optional).
	doc_date: optional (default today).

	Example items:
	[
		{"item_code": "PMDC1126", "qty": 1, "warehouse": "RA - STR", "batch_no": "OR01263XL"},
		{"item_code": "FGDC0629", "qty": 1, "warehouse": "RA - STR", "batch_no": "NU0724OL"}
	]

	Returns SAP response JSON (e.g. DocEntry, DocumentNumber).
	"""
	from khanal_tech_integrations.api.real_aquatics.auth import check_real_aquatics_access, get_user_team
	check_real_aquatics_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can post Issue for Production"), frappe.PermissionError)

	if isinstance(items, str):
		import json
		items = json.loads(items)
	po_id = int(po_id)

	session, b1_url = _get_sap_session()
	if not session or not b1_url:
		frappe.throw("SAP session not available. Check Real Aquatics SAP Settings.")

	lines = get_production_order_lines(po_id, session, b1_url)
	item_map = build_item_line_map(lines)
	payload = build_issue_payload(po_id, items, item_map, doc_date=doc_date)
	response = post_inventory_issue(payload, session, b1_url)
	return response
