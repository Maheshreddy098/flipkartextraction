import frappe
import json
from frappe import _
from frappe.utils import cint, flt
from khanal_tech_integrations.api.wowpets import (
	WOWPETS_WAREHOUSE,
	SAP_PO_COMPONENT_WAREHOUSE,
	SAP_PO_FINISHED_WAREHOUSE,
	SAP_ISSUE_ACCOUNT_CODE,
)
from khanal_tech_integrations.api.wowpets.auth import (
	check_wowpets_access,
	get_user_team,
	is_manager,
	get_user_wowpets_roles,
)
from khanal_tech_integrations.api.wowpets.inventory import allocate_inventory, consume_allocated
from khanal_tech_integrations.api.wowpets.sap_master import _get_sap_session, _sap_post_with_retry, get_item_stock_from_sap, get_items_stock_from_sap_batch, _SAP_VERIFY_SSL
from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap


def _debug_log(title, data):
	"""Structured debug logging — writes to the application logger, NOT to Error Log.
	Set logger level to DEBUG in site_config or bench to see these messages.
	"""
	try:
		frappe.logger("wowpets").debug("%s: %s", title, json.dumps(data, default=str))
	except Exception:
		pass


def _get_batch_warehouse(item_code, batch_number):
	"""Return the SAP warehouse code where batch_number for item_code has positive stock (HANA OBTQ+OBTN).
	Used for Special WOs where components can live in any warehouse. Returns None if not found or HANA unavailable."""
	from khanal_tech_integrations.api.wowpets.sap_master import _get_inc_hana_connection, _close_inc_hana_connection
	connection, cursor, schema = _get_inc_hana_connection()
	if not (connection and cursor and schema):
		return None
	try:
		item_norm = str(item_code).strip().upper()
		batch_norm = str(batch_number).strip()
		cursor.execute(
			f'SELECT T0."WhsCode" FROM {schema}."OBTQ" T0'
			f' JOIN {schema}."OBTN" T1 ON T0."ItemCode" = T1."ItemCode" AND T0."SysNumber" = T1."SysNumber"'
			f' WHERE T0."ItemCode" = ? AND T1."DistNumber" = ? AND T0."Quantity" > 0'
			f' ORDER BY T0."Quantity" DESC',
			[item_norm, batch_norm]
		)
		row = cursor.fetchone()
		return str(row[0]).strip() if row else None
	except Exception as e:
		frappe.log_error(f"_get_batch_warehouse failed for {item_code}/{batch_number}: {e}", "WowPets WO SAP")
		return None
	finally:
		_close_inc_hana_connection(connection, cursor)


def _get_po_with_lines(session, b1_url, po_entry):
	"""GET Production Order with $expand=ProductionOrderLines. Returns (po_data, po_lines, session, b1_url)."""
	from khanal_tech_integrations.api.wowpets.sap_master import _sap_get_with_retry
	base_url = b1_url.rstrip("/") + f"/ProductionOrders({po_entry})"
	url = base_url + "?$expand=ProductionOrderLines"
	resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
	if resp.status_code != 200 or not (resp.json() or {}).get("ProductionOrderLines"):
		resp, session, b1_url = _sap_get_with_retry(base_url, session, b1_url)
	if resp.status_code != 200:
		return None, [], session, b1_url
	data = resp.json() or {}
	lines = data.get("ProductionOrderLines") or []
	return data, lines, session, b1_url


def _line_summary(pl, finished_item_code):
	"""One-line summary of a PO line for debug logging (ItemNo, LineNum, LineNumber)."""
	item = (pl.get("ItemNo") or pl.get("ItemCode") or "").strip()
	return {"ItemNo": item, "LineNum": pl.get("LineNum"), "LineNumber": pl.get("LineNumber"), "PlannedQuantity": pl.get("PlannedQuantity")}


def _qty(val):
	"""Return quantity as int if whole number, else float."""
	v = abs(float(val or 0))
	return int(v) if v == int(v) else v


def _item_to_po_line(po_lines, finished_item_code):
	"""Build map ItemNo -> LineNumber from PO lines (only pit_Item, exclude FG)."""
	out = {}
	fg = (finished_item_code or "").strip().upper()
	for pl in (po_lines or []):
		if pl.get("ItemType") and pl.get("ItemType") != "pit_Item":
			continue
		item_no = (pl.get("ItemNo") or pl.get("ItemCode") or "").strip()
		if not item_no or item_no.upper() == fg:
			continue
		ln = pl.get("LineNumber") if pl.get("LineNumber") is not None else pl.get("LineNum")
		if ln is not None:
			out[item_no.upper()] = int(ln)
	return out


def _build_issue_lines(doc, po_entry, po_lines):
	"""Build DocumentLines for Issue for Production. Returns (list of line dicts, error_message or None)."""
	item_map = _item_to_po_line(po_lines, doc.finished_item_code)
	fg = (doc.finished_item_code or "").strip().upper()
	is_special = (getattr(doc, "production_order_type", "") or "").strip() == "Special"
	lines = []
	for item in (doc.items or []):
		code = (item.item_code or "").strip()
		if not code or code.upper() == fg:
			continue
		qty = _qty(item.required_qty)
		if qty <= 0:
			continue
		base_line = item_map.get(code.upper())
		if base_line is None:
			return None, _("Component {0} not found on Production Order.").format(code)
		batch = (item.batch_number or "").strip()
		if not batch:
			return None, _("Batch required for {0}.").format(code)
		if is_special:
			wh = _get_batch_warehouse(code, batch) or SAP_PO_COMPONENT_WAREHOUSE
		else:
			wh = SAP_PO_COMPONENT_WAREHOUSE
		lines.append({
			"BaseEntry": po_entry,
			"BaseLine": base_line,
			"Quantity": qty,
			"WarehouseCode": wh,
			"BatchNumbers": [{"BatchNumber": batch, "Quantity": qty}],
		})
	if not lines:
		return None, _("No components to issue. Add components with batches.")
	return lines, None


def _get_bom_from_sap(session, b1_url, item_code):
	"""Fetch BOM (ProductTreeLines) from SAP for finished good item_code. Returns list of {ItemCode, Quantity}.
	Used to build ProductionOrderLines manually so SAP behaves like Production Kiosk (no auto-expand)."""
	from khanal_tech_integrations.api.wowpets.sap_master import _sap_get_with_retry
	item_esc = (item_code or "").strip().replace("'", "''")
	if not item_esc:
		frappe.throw(_("Item Code is required to fetch BOM"))
	# Try key access first, then filter (same as sap_master get_bom)
	url = b1_url.rstrip("/") + f"/ProductTrees('{item_esc}')?$expand=ProductTreeLines"
	resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
	if resp.status_code != 200:
		url2 = b1_url.rstrip("/") + f"/ProductTrees?$filter=TreeCode eq '{item_esc}'&$expand=ProductTreeLines"
		resp, session, b1_url = _sap_get_with_retry(url2, session, b1_url)
		if resp.status_code != 200:
			frappe.throw(_("Unable to fetch BOM for item {0}. Ensure BOM exists in SAP (Production → Bill of Materials).").format(item_code))
		data = resp.json() or {}
		trees = data.get("value", [])
		tree = trees[0] if trees else None
	else:
		tree = resp.json() or {}
	lines = (tree or {}).get("ProductTreeLines") or []
	if isinstance(lines, dict) and "value" in lines:
		lines = lines.get("value", [])
	return [{"ItemCode": (l.get("ItemCode") or "").strip(), "Quantity": float(l.get("Quantity") or 0)} for l in lines if (l.get("ItemCode") or "").strip()]


def _post_receipt_from_production(session, b1_url, doc, po_entry, qty, fg_batch, posting_date):
	"""Post Receipt from Production to SAP. Flow: validate Issue exists → POST /InventoryGenEntries.
	Receipt line uses BaseType 202, BaseEntry only; BaseLine is null (matches working Postman payload).
	SAP applies the Issue to the Production Order when the Issue is created. Returns (session, b1_url, receipt_doc_entry or None, error_string or None)."""
	issue_doc_entry = getattr(doc, "sap_issue_doc_entry", None)
	if not issue_doc_entry:
		return session, b1_url, None, _("Issue for Production must exist before Receipt.")
	url_receipt = b1_url.rstrip("/") + "/InventoryGenEntries"
	# Receipt: BaseLine null (omit or null) as in working Postman; only BaseType and BaseEntry required. Never send negative values.
	qty_pos = abs(float(qty)) if qty is not None else 0
	receipt_line = {
		"Quantity": qty_pos,
		"WarehouseCode": SAP_PO_FINISHED_WAREHOUSE,
		"UseBaseUnits": "tYES",
		"BaseType": 202,
		"BaseEntry": po_entry,
		"LocationCode": 2,
		"BatchNumbers": [{"BatchNumber": fg_batch, "Quantity": qty_pos, "ItemCode": doc.finished_item_code}],
	}
	# Explicitly send BaseLine as null to match working Postman payload.
	receipt_line["BaseLine"] = None
	receipt_payload_po = {
		"JournalMemo": "Receipt from Production",
		"DocObjectCode": "oInventoryGenEntry",
		"DocDate": posting_date,
		"DocumentLines": [receipt_line],
	}
	resp, session, b1_url = _sap_post_with_retry(url_receipt, session, b1_url, receipt_payload_po)
	if resp.status_code in (200, 201):
		receipt_data = resp.json()
		return session, b1_url, receipt_data.get("DocEntry"), None
	err = _extract_sap_error(resp)
	hint = ""
	if err and "issued" in (err or "").lower() and "zero" in (err or "").lower():
		issue_entry = getattr(doc, "sap_issue_doc_entry", None)
		hint = _(
			" SAP requires the Production Order to show issued quantities before Receipt. "
			"In SAP: Production → Issue for Production → find document DocEntry {0} (or PO {1}) → Post the document. Then retry Complete in WowPets."
		).format(issue_entry or "?", po_entry)
	return session, b1_url, None, (err or "Receipt from Production failed") + hint


_check_wowpets_access = check_wowpets_access


@frappe.whitelist()
def get_list(status=None, page=1, page_size=20):
	_check_wowpets_access()

	filters = {}
	team = get_user_team()

	if team == "warehouse":
		allowed = ["Approved", "In Progress", "Completed"]
		filters["status"] = status if (status and status in allowed) else ["in", allowed]
	elif status:
		filters["status"] = status

	orders = frappe.get_list(
		"WowPets Work Order",
		filters=filters,
		fields=[
			"name", "status", "work_order_name", "finished_item_code", "finished_item_name",
			"bom_no", "qty_to_produce", "produced_qty", "posting_date",
			"created_by_user", "approved_by", "warehouse", "modified",
			"warehouse_consumed", "warehouse_completed", "warehouse_awaiting_kf",
			"sap_production_order_doc_entry", "sap_production_order_doc_num", "sap_production_order_series",
			"sap_issue_doc_entry", "sap_receipt_doc_entry", "sap_sync_status", "sap_sync_error",
			"finished_goods_batch", "remarks",
		],
		order_by="modified desc",
		start=((int(page) - 1) * int(page_size)),
		page_length=int(page_size),
	)

	total = frappe.db.count("WowPets Work Order", filters=filters)
	return {"data": orders, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_wowpets_access()
	doc = frappe.get_doc("WowPets Work Order", name)
	result = doc.as_dict()

	# Fetch stock for all components in a single batch query instead of N serial SAP calls.
	items = result.get("items", [])
	if items:
		item_codes = [i["item_code"] for i in items if i.get("item_code")]
		stock_map = get_items_stock_from_sap_batch(item_codes)
		for item in items:
			item["current_available"] = stock_map.get(item.get("item_code") or "", 0)
			item["current_allocated"] = item.get("allocated_qty") or 0

	return result


@frappe.whitelist()
def create(data):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create Work Orders"))

	if isinstance(data, str):
		import json
		data = json.loads(data)

	if not data.get("finished_item_code"):
		frappe.throw(_("Finished Item Code is required"))

	fg_batch = (data.get("finished_goods_batch") or "").strip()
	if not fg_batch:
		frappe.throw(_("Finished Goods Batch is required"))

	if not (data.get("remarks") or "").strip():
		frappe.throw(_("Remarks are required"))

	if not data.get("items"):
		frappe.throw(_("Work Order must have BOM components"))

	for idx, item in enumerate(data.get("items", []), start=1):
		if not (item.get("item_code") or "").strip():
			continue
		bn = (item.get("batch_number") or "").strip()
		if not bn:
			frappe.throw(
				_("Row {0} ({1}): Batch number is required for all components. Select a batch from WO - STR.")
				.format(idx, item.get("item_code") or "")
			)

	doc = frappe.new_doc("WowPets Work Order")
	doc.status = "Draft"
	doc.work_order_name = (data.get("work_order_name") or "").strip()
	doc.finished_item_code = data.get("finished_item_code")
	doc.finished_item_name = data.get("finished_item_name", "")
	doc.bom_no = data.get("bom_no")
	doc.qty_to_produce = data.get("qty_to_produce", 0)
	doc.posting_date = data.get("posting_date") or frappe.utils.today()
	doc.warehouse = WOWPETS_WAREHOUSE
	doc.remarks = data.get("remarks", "")
	doc.finished_goods_batch = fg_batch
	doc.production_order_type = data.get("production_order_type") or "Standard"

	for item in data.get("items", []):
		doc.append("items", {
			"item_code": item.get("item_code"),
			"item_name": item.get("item_name"),
			"required_qty": item.get("required_qty", 0),
			"number_of_units_per_box": cint(item.get("number_of_units_per_box") or 0),
			"number_of_boxes": cint(item.get("number_of_boxes") or 0),
			"uom": item.get("uom", ""),
			"warehouse": WOWPETS_WAREHOUSE,
			"batch_number": (item.get("batch_number") or "").strip() or None,
		})

	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update(name, data):
	"""Update a Draft work order (e.g. edit components, item codes)."""
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can update Work Orders"))

	if isinstance(data, str):
		import json
		data = json.loads(data)

	# Enforce batch presence on all components when updating as well.
	if not data.get("items"):
		frappe.throw(_("Work Order must have BOM components"))

	for idx, item in enumerate(data.get("items", []), start=1):
		if not (item.get("item_code") or "").strip():
			continue
		bn = (item.get("batch_number") or "").strip()
		if not bn:
			frappe.throw(
				_("Row {0} ({1}): Batch number is required for all components. Select a batch from WO - STR.")
				.format(idx, item.get("item_code") or "")
			)

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft work orders can be updated"))

	doc.work_order_name = (data.get("work_order_name") or doc.work_order_name or "").strip()
	doc.qty_to_produce = data.get("qty_to_produce", doc.qty_to_produce)
	doc.posting_date = data.get("posting_date", doc.posting_date) or doc.posting_date
	doc.remarks = data.get("remarks", doc.remarks)
	if not (doc.remarks or "").strip():
		frappe.throw(_("Remarks are required"))
	doc.production_order_type = data.get("production_order_type") or doc.production_order_type or "Standard"
	fg_batch = (data.get("finished_goods_batch") or "").strip()
	if fg_batch:
		doc.finished_goods_batch = fg_batch
	if not (doc.finished_goods_batch or "").strip():
		frappe.throw(_("Finished Goods Batch is required"))

	doc.items = []
	for item in data.get("items", []):
		doc.append("items", {
			"item_code": item.get("item_code"),
			"item_name": item.get("item_name"),
			"required_qty": item.get("required_qty", 0),
			"number_of_units_per_box": cint(item.get("number_of_units_per_box") or 0),
			"number_of_boxes": cint(item.get("number_of_boxes") or 0),
			"uom": item.get("uom", ""),
			"warehouse": WOWPETS_WAREHOUSE,
			"batch_number": (item.get("batch_number") or "").strip() or None,
		})
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


def _throw_if_warehouse_awaiting_kf(doc):
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(
			_(
				"This work order is on hold until KhanalFoods saves an update after your support ticket. "
				"They will correct batches or master data and save — then you can continue."
			)
		)


def _apply_wo_items_from_data(doc, items):
	doc.items = []
	for item in items:
		doc.append(
			"items",
			{
				"item_code": item.get("item_code"),
				"item_name": item.get("item_name"),
				"required_qty": item.get("required_qty", 0),
				"number_of_units_per_box": cint(item.get("number_of_units_per_box") or 0),
				"number_of_boxes": cint(item.get("number_of_boxes") or 0),
				"uom": item.get("uom", ""),
				"warehouse": WOWPETS_WAREHOUSE,
				"batch_number": (item.get("batch_number") or "").strip() or None,
			},
		)


@frappe.whitelist()
def warehouse_request_kf_assistance(name):
	"""Warehouse: after raising a WowPets ticket, call this to pause the work order until KhanalFoods saves."""
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only the Warehouse team can request KhanalFoods assistance."))
	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status not in ("Approved", "In Progress", "Completed"):
		frappe.throw(_("Assistance request is only for Approved, In Progress, or Completed work orders."))
	if doc.status == "Completed" and getattr(doc, "sap_receipt_doc_entry", None):
		frappe.throw(_("This work order is already receipt-posted in SAP — no hold needed."))
	doc.warehouse_awaiting_kf = 1
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_release_warehouse_hold(name):
	"""KhanalFoods: clear hold when SAP was fixed without changing work order lines (e.g. Retry PO only)."""
	_check_wowpets_access()
	if get_user_team() not in ("khanalfoods", "procurement"):
		frappe.throw(_("Only KhanalFoods or Procurement team can release the warehouse hold."))
	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if not cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		return doc.as_dict()
	doc.warehouse_awaiting_kf = 0
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_update_for_warehouse_resume(name, data):
	"""KhanalFoods: edit work order while warehouse is waiting (after ticket); clears hold on save."""
	_check_wowpets_access()
	if get_user_team() not in ("khanalfoods", "procurement"):
		frappe.throw(_("Only KhanalFoods or Procurement team can apply this update."))
	if isinstance(data, str):
		data = json.loads(data)
	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if not cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(
			_(
				"The warehouse has not put this work order on hold. "
				"They must open the work order in the Warehouse app, raise a ticket, and confirm — then you can edit here."
			)
		)

	status = doc.status
	if status == "Approved":
		if not data.get("items"):
			frappe.throw(_("Work Order must have BOM components"))
		for idx, item in enumerate(data.get("items", []), start=1):
			if not (item.get("item_code") or "").strip():
				continue
			if not (item.get("batch_number") or "").strip():
				frappe.throw(
					_("Row {0} ({1}): Batch number is required.").format(idx, item.get("item_code") or "")
				)
		doc.work_order_name = (data.get("work_order_name") or doc.work_order_name or "").strip()
		doc.qty_to_produce = data.get("qty_to_produce", doc.qty_to_produce)
		doc.posting_date = data.get("posting_date", doc.posting_date) or doc.posting_date
		doc.remarks = data.get("remarks", doc.remarks)
		fg_batch = (data.get("finished_goods_batch") or "").strip()
		if fg_batch:
			doc.finished_goods_batch = fg_batch
		if not (doc.finished_goods_batch or "").strip():
			frappe.throw(_("Finished Goods Batch is required"))
		_apply_wo_items_from_data(doc, data.get("items", []))

	elif status == "In Progress":
		po = getattr(doc, "sap_production_order_doc_entry", None)
		issue = getattr(doc, "sap_issue_doc_entry", None)
		completed_wh = cint(getattr(doc, "warehouse_completed", 0))

		if completed_wh or issue:
			fg = (data.get("finished_goods_batch") or doc.finished_goods_batch or "").strip()
			if not fg:
				frappe.throw(_("Finished Goods Batch is required for receipt retry."))
			doc.finished_goods_batch = fg
			if data.get("remarks") is not None:
				doc.remarks = data.get("remarks")
		elif po:
			new_items = data.get("items") or []
			if len(new_items) != len(doc.items):
				frappe.throw(
					_(
						"A Production Order exists in SAP — you cannot add or remove lines. "
						"Only batch numbers (and remarks) can be corrected."
					)
				)
			for i, row in enumerate(doc.items):
				ni = new_items[i]
				if ((ni.get("item_code") or "").strip() != (row.item_code or "").strip()):
					frappe.throw(_("Row {0}: item code cannot be changed; only batch.").format(i + 1))
				if abs(flt(ni.get("required_qty")) - flt(row.required_qty)) > 0.001:
					frappe.throw(_("Row {0}: quantity cannot be changed; only batch.").format(i + 1))
				bn = (ni.get("batch_number") or "").strip()
				if not bn:
					frappe.throw(_("Row {0}: batch is required.").format(i + 1))
				row.batch_number = bn
			if data.get("remarks") is not None:
				doc.remarks = data.get("remarks")
		else:
			if not data.get("items"):
				frappe.throw(_("Work Order must have BOM components"))
			for idx, item in enumerate(data.get("items", []), start=1):
				if not (item.get("item_code") or "").strip():
					continue
				if not (item.get("batch_number") or "").strip():
					frappe.throw(
						_("Row {0} ({1}): Batch number is required.").format(idx, item.get("item_code") or "")
					)
			doc.work_order_name = (data.get("work_order_name") or doc.work_order_name or "").strip()
			doc.qty_to_produce = data.get("qty_to_produce", doc.qty_to_produce)
			doc.posting_date = data.get("posting_date", doc.posting_date) or doc.posting_date
			doc.remarks = data.get("remarks", doc.remarks)
			fg_batch = (data.get("finished_goods_batch") or "").strip()
			if fg_batch:
				doc.finished_goods_batch = fg_batch
			if not (doc.finished_goods_batch or "").strip():
				frappe.throw(_("Finished Goods Batch is required"))
			_apply_wo_items_from_data(doc, data.get("items", []))
			doc.sap_sync_error = None

	elif status == "Completed":
		fg = (data.get("finished_goods_batch") or doc.finished_goods_batch or "").strip()
		if not fg:
			frappe.throw(_("Finished Goods Batch is required."))
		doc.finished_goods_batch = fg
		if data.get("remarks") is not None:
			doc.remarks = data.get("remarks")
	else:
		frappe.throw(_("Cannot apply resume update in status {0}.").format(status))

	doc.warehouse_awaiting_kf = 0
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def submit_for_approval(name):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can submit Work Orders for approval"))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft work orders can be submitted"))

	if not doc.items:
		frappe.throw(_("Cannot submit Work Order without items"))

	doc.status = "Pending Approval"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve(name):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can approve Work Orders"))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval work orders can be approved"))

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def reject(name, reason=""):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can reject Work Orders"))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval work orders can be rejected"))

	doc.status = "Rejected"
	if reason:
		doc.remarks = (doc.remarks or "") + f"\nRejection reason: {reason}"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


def _create_and_release_production_order(doc, series=None, planned_qty=None):
	"""Create SAP Production Order and release it. Uses INC SAP Settings. Returns (po_entry, po_doc_num, po_series) or raises. DocEntry is unique; DocumentNumber can repeat across Series.
	Payload is built from the Work Order's items (user inputs). BOM is not fetched from SAP here; user can load BOM in the UI and then add/delete/edit components before posting.
	series: optional int from HANA NNM1 (get_production_order_series_from_hana) to force a specific numbering series.
	planned_qty: optional override (e.g. produced_qty when WO is Completed); else uses doc.qty_to_produce."""
	session, b1_url = _get_sap_session()
	if not session or not b1_url:
		frappe.throw(_("SAP session not available. Check INC SAP Settings."))
	posting_date = (doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date or frappe.utils.today())
	due_date = posting_date  # same as posting for simplicity
	qty = abs(float(planned_qty if planned_qty is not None else doc.qty_to_produce or 0))
	if qty <= 0:
		frappe.throw(_("Qty to produce must be greater than zero"))
	finished_item = (doc.finished_item_code or "").strip()
	if not finished_item:
		frappe.throw(_("Finished Item Code is required for Production Order"))
	# Build ProductionOrderLines from Work Order components only. SAP: header = production item (FG); lines = components only. Do NOT add FG to lines (SAP rejects "Component cannot be equal to the production item"). Never send negative values.
	production_order_lines = []
	for item in (doc.items or []):
		item_code = (item.item_code or "").strip()
		if not item_code or item_code.upper() == finished_item.upper():
			continue
		required_qty = abs(float(item.required_qty or 0))
		if required_qty <= 0:
			continue
		production_order_lines.append({
			"ItemNo": item_code,
			"PlannedQuantity": required_qty,
			"Warehouse": SAP_PO_COMPONENT_WAREHOUSE,
			"LocationCode": 2,
			"ProductionOrderIssueType": "im_Manual",
		})
	if not production_order_lines:
		frappe.throw(_("Work Order must have at least one component. Add components (or load BOM and edit) before posting to SAP."))
	_po_type_raw = (getattr(doc, "production_order_type", None) or "Standard").strip()
	_sap_po_type = "bopotSpecial" if _po_type_raw == "Special" else "bopotStandard"
	production_order = {
		"ItemNo": finished_item,
		"PlannedQuantity": qty,
		"ProductionOrderType": _sap_po_type,
		"PostingDate": posting_date,
		"DueDate": due_date,
		"Warehouse": SAP_PO_FINISHED_WAREHOUSE,
		# SAP Remarks = user remarks entered on the WowPets Work Order (mandatory upstream).
		# SAP Production Order Remarks field allows up to 254 chars.
		"Remarks": ((doc.remarks or "").strip()[:254]) or f"WowPets WO {doc.name}",
		"ProductionOrderLines": production_order_lines,
	}
	if series is not None:
		try:
			production_order["Series"] = int(series)
		except (TypeError, ValueError):
			pass
	url_po = b1_url.rstrip("/") + "/ProductionOrders"
	_debug_log("WowPets WO SAP Production Order payload", {"wo": doc.name, "payload": production_order})
	resp, session, b1_url = _sap_post_with_retry(url_po, session, b1_url, production_order)
	if resp.status_code not in (200, 201):
		err = _extract_sap_error(resp)
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Production Order Create",
			status="Failed",
			error_message=err,
		)
		_debug_log("WowPets WO SAP Production Order failed", {"wo": doc.name, "error": err, "payload": production_order})
		hint = _sap_po_error_hint(err, finished_item, production_order)
		frappe.throw(_("SAP Production Order failed: {0}{1}").format(err, hint))
	resp_data = resp.json()
	# DocEntry (AbsoluteEntry) is the unique key; DocumentNumber can repeat across Series
	po_entry = resp_data.get("AbsoluteEntry") or resp_data.get("DocEntry")
	po_doc_num = resp_data.get("DocumentNumber", "")
	po_series = resp_data.get("Series") or resp_data.get("SeriesNumber")
	if isinstance(po_series, dict):
		po_series = po_series.get("SeriesCode") or po_series.get("Number")
	if not po_entry:
		frappe.throw(_("SAP did not return Production Order entry"))
	url_patch = b1_url.rstrip("/") + f"/ProductionOrders({po_entry})"
	payload_release = json.dumps({"ProductionOrderStatus": "boposReleased"})
	patch_resp = session.patch(url_patch, data=payload_release, verify=_SAP_VERIFY_SSL, timeout=30, headers={"Content-Type": "application/json"})
	if patch_resp.status_code == 401:
		session, b1_url = _get_sap_session(force_login=True)
		if session:
			patch_resp = session.patch(url_patch, data=payload_release, verify=_SAP_VERIFY_SSL, timeout=30, headers={"Content-Type": "application/json"})
	if patch_resp.status_code not in (200, 204):
		err = _extract_sap_error(patch_resp)
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Production Order Create",
			status="Failed",
			error_message=err or "Release failed",
		)
		frappe.log_error(f"WO: {doc.name}\nSAP Release failed: {err}", "WowPets WO SAP Release failed")
		frappe.throw(_("SAP release failed: {0}").format(err or "Unknown"))
	log_wowpets_sap(
		reference_doctype="WowPets Work Order",
		reference_name=doc.name,
		operation="Production Order Create",
		status="Success",
		response_payload={"DocEntry": po_entry, "DocumentNumber": po_doc_num, "Series": po_series},
	)
	return po_entry, po_doc_num, po_series


@frappe.whitelist()
def start_processing(name):
	"""Warehouse: accept WO – allocate and set In Progress. KhanalFoods then posts Production Order to SAP."""
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can start (accept) work orders."))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Approved":
		frappe.throw(_("Only Approved work orders can be started"))
	_throw_if_warehouse_awaiting_kf(doc)

	for item in doc.items:
		wh_used = allocate_inventory(item.item_code, item.required_qty)
		item.warehouse = wh_used
		item.allocated_qty = item.required_qty
		sap_stock = get_item_stock_from_sap(item.item_code)
		item.available_qty = sap_stock.get("available_qty", 0)

	doc.status = "In Progress"

	try:
		po_entry, po_doc_num, po_series = _create_and_release_production_order(doc)
		doc.sap_production_order_doc_entry = po_entry
		doc.sap_production_order_doc_num = po_doc_num
		doc.sap_production_order_series = po_series
		doc.sap_sync_status = "Production Order Created"
		doc.sap_sync_error = None
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Production Order Create",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WO {doc.name}: Auto Production Order failed: {e}", "WowPets WO SAP")

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def retry_create_production_order(name, series=None):
	"""KhanalFoods: create and release Production Order in SAP when WO is In Progress but PO was never created (e.g. after a previous SAP error).
	series: optional int from get_production_order_series_from_hana to use a specific numbering series."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create Production Orders in SAP."))
	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status not in ("In Progress", "Completed"):
		frappe.throw(_("Work order must be In Progress or Completed to retry creating Production Order"))
	if getattr(doc, "sap_production_order_doc_entry", None):
		return doc.as_dict()
	try:
		po_entry, po_doc_num, po_series = _create_and_release_production_order(doc, series=series)
		doc.sap_production_order_doc_entry = po_entry
		doc.sap_production_order_doc_num = po_doc_num
		doc.sap_production_order_series = po_series
		doc.sap_sync_status = "Production Order Created"
		doc.sap_sync_error = None
		doc.save()
		frappe.db.commit()
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Production Order Create",
			status="Failed",
			error_message=str(e),
		)
		doc.save()
		frappe.db.commit()
		raise
	return doc.as_dict()


@frappe.whitelist()
def retry_issue_for_production(name):
	"""KhanalFoods: retry posting Issue for Production when PO exists but Issue failed. Same as consume_and_issue when WO has no sap_issue_doc_entry."""
	return consume_and_issue(name)


def _post_issue_for_production_internal(doc):
	"""Internal: post Issue for Production to SAP. Updates doc fields in place; caller must save/commit.
	Returns True on success, False on failure (error stored in doc.sap_sync_error)."""
	po_entry = getattr(doc, "sap_production_order_doc_entry", None)
	if not po_entry:
		doc.sap_sync_error = _("Production Order not created in SAP. Create it first.")
		return False
	if getattr(doc, "sap_issue_doc_entry", None):
		return True

	posting_date = (doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date or frappe.utils.today())
	finished_code = (doc.finished_item_code or "").strip().upper()
	is_special = (getattr(doc, "production_order_type", "") or "").strip() == "Special"
	items = []
	for item in (doc.items or []):
		item_code = (item.item_code or "").strip()
		if not item_code or item_code.upper() == finished_code:
			continue
		qty = abs(float(item.required_qty or 0))
		if qty <= 0:
			continue
		batch_no = (item.batch_number or "").strip()
		if not batch_no:
			doc.sap_sync_status = "Error"
			doc.sap_sync_error = _("Batch number is required for component {0}.").format(item_code)
			return False
		qty_val = int(qty) if qty == int(qty) else qty
		if is_special:
			wh = _get_batch_warehouse(item_code, batch_no) or SAP_PO_COMPONENT_WAREHOUSE
		else:
			wh = SAP_PO_COMPONENT_WAREHOUSE
		items.append({
			"item_code": item_code,
			"qty": qty_val,
			"warehouse": wh,
			"batch_no": batch_no,
		})
	if not items:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = _("No components to issue. Ensure Work Order has components with batches.")
		return False

	from khanal_tech_integrations.api.wowpets.sap_issue_for_production import issue_for_production as sap_issue_for_production
	try:
		response = sap_issue_for_production(po_id=po_entry, items=items, doc_date=posting_date)
		doc.sap_issue_doc_entry = response.get("DocEntry")
		doc.sap_sync_status = "Issue Created"
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Issue for Production",
			status="Success",
			response_payload=response,
		)
		return True
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Issue for Production",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WO {doc.name}: Issue for Production failed: {e}", "WowPets WO SAP")
		return False


@frappe.whitelist()
def warehouse_mark_consumed(name):
	"""Warehouse: mark that components have been consumed. Auto-posts Issue for Production to SAP."""
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can mark work order as consumed."))
	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "In Progress":
		frappe.throw(_("Only In Progress work orders can be marked consumed."))
	_throw_if_warehouse_awaiting_kf(doc)
	doc.warehouse_consumed = 1

	_post_issue_for_production_internal(doc)

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def warehouse_complete(name):
	"""Warehouse: mark work order complete (FG ready). Auto-posts Receipt from Production using stored FG batch.
	Status goes to Completed regardless of SAP success. KhanalFoods retries if receipt fails."""
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can complete work orders."))
	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "In Progress":
		frappe.throw(_("Only In Progress work orders can be completed by warehouse."))
	_throw_if_warehouse_awaiting_kf(doc)
	doc.warehouse_completed = 1
	doc.status = "Completed"
	doc.produced_qty = doc.qty_to_produce

	_auto_post_receipt(doc)

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


def _auto_post_receipt(doc):
	"""Try to auto-post Receipt from Production to SAP. Non-blocking on failure."""
	po_entry = getattr(doc, "sap_production_order_doc_entry", None)
	issue_entry = getattr(doc, "sap_issue_doc_entry", None)
	if not po_entry or not issue_entry:
		doc.sap_sync_error = _("Cannot auto-post Receipt: Production Order or Issue missing in SAP. KhanalFoods must retry.")
		return
	if getattr(doc, "sap_receipt_doc_entry", None):
		return
	fg_batch = (doc.finished_goods_batch or "").strip()
	if not fg_batch:
		doc.sap_sync_error = _("Cannot auto-post Receipt: Finished Goods Batch not set on Work Order.")
		return
	try:
		session, b1_url = _get_sap_session()
		if not session or not b1_url:
			doc.sap_sync_error = _("SAP session not available for Receipt from Production.")
			return
		posting_date = (doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date or frappe.utils.today())
		qty = float(doc.qty_to_produce or 0)
		session, b1_url, receipt_doc_entry, receipt_error = _post_receipt_from_production(session, b1_url, doc, po_entry, qty, fg_batch, posting_date)
		if receipt_error:
			doc.sap_sync_status = "Error"
			doc.sap_sync_error = receipt_error
			log_wowpets_sap(
				reference_doctype="WowPets Work Order",
				reference_name=doc.name,
				operation="Receipt from Production",
				status="Failed",
				error_message=receipt_error,
			)
			frappe.log_error(f"WO {doc.name}: Auto Receipt failed: {receipt_error}", "WowPets WO SAP")
			return
		doc.sap_receipt_doc_entry = receipt_doc_entry
		doc.sap_sync_status = "Receipt Posted"
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Receipt from Production",
			status="Success",
			response_payload={"DocEntry": receipt_doc_entry},
		)
		try:
			url_patch = b1_url.rstrip("/") + f"/ProductionOrders({po_entry})"
			session.patch(url_patch, data=json.dumps({"ProductionOrderStatus": "boposClosed"}), verify=_SAP_VERIFY_SSL, timeout=30, headers={"Content-Type": "application/json"})
		except Exception:
			pass
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		frappe.log_error(f"WO {doc.name}: Auto Receipt exception: {e}", "WowPets WO SAP")


@frappe.whitelist()
def get_production_order_lines(name=None, po_entry=None, doc_number=None):
	"""
	Fetch Production Order lines directly from SAP API.
	Call with either:
	  - name: Work Order name (uses doc.sap_production_order_doc_entry)
	  - po_entry: SAP Production Order DocEntry (integer)
	  - doc_number: SAP DocumentNumber (string); resolved to DocEntry via GET then used
	Returns the exact structure SAP returns (line numbers LineNum, LineNumber, items).
	"""
	_check_wowpets_access()
	finished_code = None
	if po_entry is not None:
		po_entry = int(po_entry)
	elif doc_number is not None:
		# Resolve DocumentNumber to DocEntry via SAP (filter ProductionOrders by DocumentNumber)
		session, b1_url = _get_sap_session(force_login=True)
		if not session or not b1_url:
			return {"ok": False, "error": "SAP session not available.", "production_order_lines": []}
		from khanal_tech_integrations.api.wowpets.sap_master import _sap_get_with_retry
		doc_num_esc = str(doc_number).replace("'", "''")
		url = b1_url.rstrip("/") + f"/ProductionOrders?$filter=DocumentNumber eq '{doc_num_esc}'&$top=1"
		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code != 200:
			return {"ok": False, "error": "SAP GET ProductionOrders failed.", "production_order_lines": []}
		data = resp.json() or {}
		value = data.get("value") or []
		if not value:
			return {"ok": False, "error": f"No Production Order with DocumentNumber '{doc_number}' in SAP.", "production_order_lines": []}
		po_entry = value[0].get("DocEntry")
		if po_entry is None:
			return {"ok": False, "error": "SAP response missing DocEntry.", "production_order_lines": []}
		po_entry = int(po_entry)
	elif name:
		doc = frappe.get_doc("WowPets Work Order", name)
		po_entry = getattr(doc, "sap_production_order_doc_entry", None)
		finished_code = (doc.finished_item_code or "").strip().upper()
	else:
		return {"ok": False, "error": "Provide name (WO name), po_entry (SAP DocEntry), or doc_number (SAP DocumentNumber).", "production_order_lines": []}
	if not po_entry:
		return {"ok": False, "error": "Production Order not created in SAP. Post Production Order first.", "production_order_lines": []}
	session, b1_url = _get_sap_session(force_login=True)
	if not session or not b1_url:
		return {"ok": False, "error": "SAP session not available.", "production_order_lines": []}
	po_data, po_lines, session, b1_url = _get_po_with_lines(session, b1_url, po_entry)
	if not po_lines:
		return {
			"ok": True,
			"po_entry": po_entry,
			"production_order_lines": [],
			"summary": [],
			"message": "No ProductionOrderLines in SAP response (GET may not have expanded lines).",
		}
	# Build summary with every key SAP might use for line number (LineNum, LineNumber, VisOrder, etc.)
	if finished_code is None and po_data:
		# Header ItemNo is the finished good
		finished_code = (po_data.get("ItemNo") or po_data.get("ItemCode") or "").strip().upper()
	summary = []
	for idx, pl in enumerate(po_lines):
		item_no = (pl.get("ItemNo") or pl.get("ItemCode") or "").strip()
		line_num = pl.get("LineNum")
		line_number = pl.get("LineNumber")
		vis_order = pl.get("VisOrder")
		planned_qty = pl.get("PlannedQuantity")
		summary.append({
			"index": idx,
			"ItemNo": item_no,
			"LineNum": line_num,
			"LineNumber": line_number,
			"VisOrder": vis_order,
			"PlannedQuantity": planned_qty,
			"is_finished_good": (item_no.upper() == finished_code) if (item_no and finished_code) else False,
		})
	return {
		"ok": True,
		"po_entry": po_entry,
		"document_number": po_data.get("DocumentNumber") if po_data else None,
		"production_order_lines": po_lines,
		"summary": summary,
		"message": "Use LineNum or LineNumber from summary as BaseLine for Issue (exclude FG lines).",
	}


@frappe.whitelist()
def consume_and_issue(name):
	"""KhanalFoods: retry posting Issue for Production to SAP. Allowed after warehouse has marked consumed."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can post Issue for Production to SAP."))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status not in ("In Progress", "Completed"):
		frappe.throw(_("Work order must be In Progress or Completed to retry Issue for Production"))
	if not getattr(doc, "warehouse_consumed", None) and not getattr(doc, "sap_issue_doc_entry", None):
		frappe.throw(_("Warehouse must mark the work order as consumed first."))
	po_entry = getattr(doc, "sap_production_order_doc_entry", None)
	if not po_entry:
		frappe.throw(_("Production Order not created in SAP. Retry creating Production Order first."))
	if getattr(doc, "sap_issue_doc_entry", None):
		return doc.as_dict()

	success = _post_issue_for_production_internal(doc)
	doc.save()
	frappe.db.commit()
	if not success:
		frappe.throw(_(doc.sap_sync_error or "Issue for Production failed"))
	return doc.as_dict()


@frappe.whitelist()
def complete(name, produced_qty=None, finished_goods_batch=None):
	"""KhanalFoods: retry posting Receipt from Production to SAP. Used when auto-post on warehouse_complete failed."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can post Receipt from Production to SAP."))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status not in ("Completed", "In Progress"):
		frappe.throw(_("Work order must be Completed or In Progress to retry Receipt from Production."))
	if not getattr(doc, "sap_issue_doc_entry", None):
		frappe.throw(_("Issue for Production must be posted to SAP first. Retry Issue if it failed."))
	fg_batch = (finished_goods_batch or "").strip() or (doc.finished_goods_batch or "").strip()
	if not fg_batch:
		frappe.throw(_("Finished goods batch is required for Receipt from Production."))

	actual_qty = float(produced_qty) if produced_qty else doc.qty_to_produce
	# No local inventory; receipt is posted to SAP only
	doc.produced_qty = actual_qty
	doc.finished_goods_batch = fg_batch or None

	po_entry = getattr(doc, "sap_production_order_doc_entry", None)
	if not po_entry or getattr(doc, "sap_receipt_doc_entry", None):
		doc.status = "Completed"
		doc.save()
		frappe.db.commit()
		return doc.as_dict()

	session, b1_url = _get_sap_session()
	if not session or not b1_url:
		frappe.throw(_("SAP session not available. Check INC SAP Settings."))

	posting_date = (doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date or frappe.utils.today())
	session, b1_url, receipt_doc_entry, receipt_error = _post_receipt_from_production(session, b1_url, doc, po_entry, actual_qty, fg_batch, posting_date)
	if receipt_error:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = receipt_error
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Receipt from Production",
			status="Failed",
			error_message=receipt_error,
		)
		frappe.log_error(f"WO: {doc.name}\nSAP Receipt failed: {receipt_error}", "WowPets WO SAP Receipt failed")
		doc.save()
		frappe.db.commit()
		frappe.throw(_("SAP Receipt from Production failed: {0}").format(receipt_error))
	doc.sap_receipt_doc_entry = receipt_doc_entry
	doc.sap_sync_status = "Receipt Posted"
	doc.sap_sync_error = None
	log_wowpets_sap(
		reference_doctype="WowPets Work Order",
		reference_name=doc.name,
		operation="Receipt from Production",
		status="Success",
		response_payload={"DocEntry": receipt_doc_entry},
	)
	try:
		url_patch = b1_url.rstrip("/") + f"/ProductionOrders({po_entry})"
		session.patch(url_patch, data=json.dumps({"ProductionOrderStatus": "boposClosed"}), verify=_SAP_VERIFY_SSL, timeout=30, headers={"Content-Type": "application/json"})
	except Exception:
		pass
	doc.status = "Completed"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def revert_to_draft(name):
	"""Revert a rejected Work Order back to Draft for editing"""
	_check_wowpets_access()

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Rejected":
		frappe.throw(_("Only Rejected work orders can be reverted to Draft"))

	doc.status = "Draft"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


_WO_USER_DELETABLE = {"Draft"}
_WO_MANAGER_DELETABLE = {"Draft", "Approved"}


@frappe.whitelist()
def delete_draft(name):
	"""Delete a WowPets Work Order. KhanalFoods team only.
	Regular user: own Draft records with no SAP data.
	Manager: Draft / Approved with no SAP data.
	"""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can delete work orders"), frappe.PermissionError)

	doc = frappe.get_doc("WowPets Work Order", name)

	if cint(doc.sap_production_order_doc_entry) > 0 or cint(doc.sap_issue_doc_entry) > 0 or cint(doc.sap_receipt_doc_entry) > 0:
		frappe.throw(_("Cannot delete: this work order has already been sent to SAP"), frappe.ValidationError)

	user = frappe.session.user
	if is_manager():
		if doc.status not in _WO_MANAGER_DELETABLE:
			frappe.throw(
				_("Cannot delete: work order is in '{0}' status. Managers can only delete before warehouse starts processing.").format(doc.status),
				frappe.ValidationError,
			)
	else:
		if doc.owner != user:
			frappe.throw(_("You can only delete work orders you created"), frappe.PermissionError)
		if doc.status not in _WO_USER_DELETABLE:
			frappe.throw(_("Only Draft work orders can be deleted"), frappe.ValidationError)

	from khanal_tech_integrations.api.wowpets.kf_attachments import _delete_all_doc_attachments
	_delete_all_doc_attachments("WowPets Work Order", name)
	frappe.delete_doc("WowPets Work Order", name, ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def create_production_order_and_issue(name, series=None):
	"""Create SAP Production Order from Work Order items, release it, and post Issue for Production. KhanalFoods only, WO must be Completed. Idempotent. If PO exists but Issue failed, runs only Issue step."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create Production Order and Issue in SAP"))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status != "Completed":
		frappe.throw(_("Work Order must be Completed before posting to SAP"))
	po_entry = getattr(doc, "sap_production_order_doc_entry", None)
	issue_doc_entry = getattr(doc, "sap_issue_doc_entry", None)
	if po_entry and issue_doc_entry:
		return doc.as_dict()

	# 1) Create and release PO only if not already created (so retry after Issue failure does not duplicate PO)
	if not po_entry:
		planned_qty = float(doc.produced_qty or doc.qty_to_produce or 0)
		if planned_qty <= 0:
			frappe.throw(_("Produced quantity must be greater than zero"))
		try:
			po_entry, po_doc_num, po_series = _create_and_release_production_order(doc, series=series, planned_qty=planned_qty)
		except Exception as e:
			doc.sap_sync_status = "Error"
			doc.sap_sync_error = str(e)
			log_wowpets_sap(
				reference_doctype="WowPets Work Order",
				reference_name=doc.name,
				operation="Production Order Create",
				status="Failed",
				error_message=str(e),
			)
			doc.save()
			frappe.db.commit()
			raise
		# Save PO to doc immediately so retry after Issue failure only runs Issue step
		doc.sap_production_order_doc_entry = po_entry
		doc.sap_production_order_doc_num = po_doc_num
		doc.sap_production_order_series = po_series
		doc.sap_sync_status = "Production Order Created"
		doc.sap_sync_error = None
		doc.save()
		frappe.db.commit()

	# 2) Post Issue for Production (idempotent if already done)
	if issue_doc_entry:
		return doc.as_dict()
	posting_date = (doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date or frappe.utils.today())
	finished_code = (doc.finished_item_code or "").strip().upper()
	is_special = (getattr(doc, "production_order_type", "") or "").strip() == "Special"
	items = []
	for item in (doc.items or []):
		item_code = (item.item_code or "").strip()
		if not item_code or item_code.upper() == finished_code:
			continue
		qty = abs(float(item.required_qty or 0))
		if qty <= 0:
			continue
		batch_no = (item.batch_number or "").strip()
		if not batch_no:
			doc.sap_sync_status = "Error"
			doc.sap_sync_error = _("Row: Batch number required for {0}").format(item_code)
			doc.save()
			frappe.db.commit()
			frappe.throw(_(doc.sap_sync_error))
		qty_val = int(qty) if qty == int(qty) else qty
		if is_special:
			wh = _get_batch_warehouse(item_code, batch_no) or SAP_PO_COMPONENT_WAREHOUSE
		else:
			wh = SAP_PO_COMPONENT_WAREHOUSE
		items.append({
			"item_code": item_code,
			"qty": qty_val,
			"warehouse": wh,
			"batch_no": batch_no,
		})
	if not items:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = _("No components to issue. Ensure WO has components with batches.")
		doc.save()
		frappe.db.commit()
		frappe.throw(_(doc.sap_sync_error))

	from khanal_tech_integrations.api.wowpets.sap_issue_for_production import issue_for_production as sap_issue_for_production
	try:
		response = sap_issue_for_production(po_id=po_entry, items=items, doc_date=posting_date)
		issue_doc_entry = response.get("DocEntry")
		doc.sap_issue_doc_entry = issue_doc_entry
		doc.sap_sync_status = "Issue Created"
		doc.sap_sync_error = None
		doc.save()
		frappe.db.commit()
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Issue for Production",
			status="Success",
			response_payload=response,
		)
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		log_wowpets_sap(
			reference_doctype="WowPets Work Order",
			reference_name=doc.name,
			operation="Issue for Production",
			status="Failed",
			error_message=str(e),
		)
		doc.save()
		frappe.db.commit()
		raise
	return doc.as_dict()


def _post_sap_issue_documents(session, b1_url, issue_lines, posting_date, wo_name, po_entry=None):
	"""Create one InventoryGenExits document in SAP (replicate ApprovalPage). Send all lines in one document; do not send BaseType on lines; BaseLine = PO line (0,1,2). Quantities must be positive.
	"""
	from khanal_tech_integrations.api.wowpets.sap_master import _sap_post_with_retry

	url_issue = b1_url.rstrip("/") + "/InventoryGenExits"

	# Minimal payload: JournalMemo, DocDate, DocumentLines. Lines: BaseEntry, BaseLine, Quantity, WarehouseCode, BatchNumbers (BatchNumber + Quantity only).
	lines_payload = []
	for line in issue_lines:
		q = line.get("Quantity")
		qty = abs(float(q)) if q is not None else 0
		if qty == int(qty):
			qty = int(qty)
		bn_list = line.get("BatchNumbers") or []
		bn_clean = []
		for b in bn_list:
			if not b.get("BatchNumber"):
				continue
			bq = abs(float(b.get("Quantity") or 0))
			bn_clean.append({"BatchNumber": b.get("BatchNumber"), "Quantity": int(bq) if bq == int(bq) else bq})
		lines_payload.append({
			"BaseEntry": line.get("BaseEntry"),
			"BaseLine": line.get("BaseLine"),
			"Quantity": qty,
			"WarehouseCode": line.get("WarehouseCode"),
			"BatchNumbers": bn_clean,
		})

	payload = {
		"JournalMemo": "Issue for Production",
		"DocDate": posting_date,
		"DocumentLines": lines_payload,
	}
	_debug_log("WowPets WO SAP Issue payload (single document)", {"wo": wo_name, "url": url_issue, "payload": payload})
	resp, session, b1_url = _sap_post_with_retry(url_issue, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = _extract_sap_error(resp)
		frappe.throw(_("SAP Issue for Production failed: {0}").format(err or "Unknown"))
	primary_doc_entry = resp.json().get("DocEntry")
	return primary_doc_entry, session, b1_url


def _get_sap_issue_doc_status(session, b1_url, issue_doc_entry):
	"""GET InventoryGenExits document and return normalised DocStatus string (uppercase), or None if unavailable."""
	from khanal_tech_integrations.api.wowpets.sap_master import _sap_get_with_retry
	try:
		url = b1_url.rstrip("/") + f"/InventoryGenExits({issue_doc_entry})"
		resp, _, _ = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code != 200:
			return None
		data = resp.json() or {}
		raw = data.get("DocStatus") or data.get("DocumentStatus") or ""
		return raw.strip().upper() if raw else None
	except Exception:
		return None


def _ensure_sap_issue_posted(session, b1_url, issue_doc_entry, wo_name):
	"""Before Receipt: ensure the Issue for Production is posted in SAP.
	Throws only when the document is confirmed OPEN and cannot be closed. Returns (session, b1_url)."""
	_close_sap_issue_document(session, b1_url, issue_doc_entry, wo_name, raise_if_confirmed_open=True)
	return session, b1_url


def _close_sap_issue_document(session, b1_url, issue_doc_entry, wo_name, raise_if_confirmed_open=False):
	"""Attempt to close/post the InventoryGenExits document in SAP.

	Strategy:
	  1. Check current SAP status — return immediately if already closed/posted.
	  2. Try /Close (v1, then v2 if applicable).
	  3. Re-check SAP status after close attempt — return if now closed.
	  4. If confirmed still OPEN: log + throw only when raise_if_confirmed_open=True.
	     If status unknown (GET failed): log warning and return (non-blocking).

	Many SAP B1 versions auto-post InventoryGenExits on creation, so /Close may fail
	even though the document is already in the correct state.
	"""
	if not issue_doc_entry:
		return

	# 1. Check current status first — skip the Close round-trip if already posted
	status = _get_sap_issue_doc_status(session, b1_url, issue_doc_entry)
	_CLOSED = {"C", "CLOSED", "BOST_CLOSE", "BOST_CLOSED"}
	_OPEN = {"O", "OPEN", "BOST_OPEN"}
	if status in _CLOSED:
		return  # Already posted, nothing to do

	# 2. Attempt Post then Close (some SAP versions use Post to apply Issue to PO and update IssuedQuantity)
	base = b1_url.rstrip("/") + f"/InventoryGenExits({issue_doc_entry})"
	actions_to_try = [
		(base + "/Post", "Post"),
		(base + "/Close", "Close"),
	]
	if "/b1s/v1" in base.lower():
		base_v2 = base.replace("/b1s/v1", "/b1s/v2")
		actions_to_try.extend([(base_v2 + "/Post", "Post"), (base_v2 + "/Close", "Close")])

	close_err = ""
	try:
		for url, action_name in actions_to_try:
			resp = session.post(url, json={}, verify=_SAP_VERIFY_SSL, timeout=30, headers={"Content-Type": "application/json"})
			if resp.status_code in (200, 201, 204):
				# Verify document is actually CLOSED (proxy may return 204 while doc stays OPEN)
				status_after = _get_sap_issue_doc_status(session, b1_url, issue_doc_entry)
				if status_after in _CLOSED:
					return  # Posted/Closed successfully
				close_err = _extract_sap_error(resp) or str(resp.status_code)
				_debug_log("WowPets WO Issue Post/Close attempt", {"wo": wo_name, "action": action_name, "url": url, "status": resp.status_code, "status_after": status_after, "error": close_err})
				continue
			err = _extract_sap_error(resp) or str(resp.status_code)
			close_err = err
			_debug_log("WowPets WO Issue Post/Close attempt", {"wo": wo_name, "action": action_name, "url": url, "status": resp.status_code, "error": err})
			if "already" in err.lower() and ("close" in err.lower() or "post" in err.lower()):
				return  # Already closed/posted
			if "invalid entityset" in err.lower() or "not found" in err.lower():
				continue
	except Exception as e:
		close_err = str(e)
		_debug_log("WowPets WO Issue Post/Close exception", {"wo": wo_name, "error": str(e)})

	# 2b. Fallback: try PATCH DocumentStatus/DocStatus to closed (some SL versions allow this)
	for status_field in ("DocumentStatus", "DocStatus", "Status"):
		for status_value in ("bost_Close", "bost_Closed", "C", "Closed", "CLOSED"):
			try:
				patch_resp = session.patch(
					base,
					data=json.dumps({status_field: status_value}),
					verify=_SAP_VERIFY_SSL,
					timeout=30,
					headers={"Content-Type": "application/json"},
				)
				if patch_resp.status_code in (200, 204):
					status_after = _get_sap_issue_doc_status(session, b1_url, issue_doc_entry)
					if status_after in _CLOSED:
						return
				if patch_resp.status_code not in (400, 404, 422):
					close_err = _extract_sap_error(patch_resp) or str(patch_resp.status_code)
			except Exception:
				pass

	# 3. Re-check actual SAP status after close attempt
	status_after = _get_sap_issue_doc_status(session, b1_url, issue_doc_entry)
	if status_after in _CLOSED:
		return  # Document is now (or was already) closed — close "failure" was harmless

	# 4. Close truly failed — log and optionally throw
	# Detect network/proxy failures (502/503/504/connection errors) — don't block the user for infrastructure issues
	_network_error_signals = ("502", "503", "504", "proxy error", "connection", "timeout", "gateway", "upstream")
	is_network_error = any(s in (close_err or "").lower() for s in _network_error_signals)

	if status_after in _OPEN:
		# Confirmed still open
		frappe.log_error(
			message=f"WO: {wo_name} – Issue DocEntry {issue_doc_entry} is OPEN in SAP after Close attempt ({close_err}). Must be posted manually.",
			title="WowPets WO SAP Issue Close failed",
		)
		if raise_if_confirmed_open and not is_network_error:
			# Only hard-block on SAP application rejections, not transient network failures
			frappe.throw(
				_("Issue for Production (DocEntry {0}) is still open in SAP and could not be posted automatically ({1}). "
				  "Post it manually in SAP: Production → Issue for Production → find DocEntry {0} → Post. "
				  "Then retry Receipt from Production.").format(issue_doc_entry, close_err)
			)
		elif raise_if_confirmed_open and is_network_error:
			# Network error — warn but let Receipt attempt proceed (SAP will give its own error if issue isn't applied)
			frappe.log_error(
				message=f"WO: {wo_name} – Proceeding to Receipt despite open Issue DocEntry {issue_doc_entry} because Close failed with a network/proxy error ({close_err}). SAP will reject Receipt if issue is not applied.",
				title="WowPets WO SAP Issue Close network error",
			)
	else:
		# Status unknown (GET failed) — log warning but do not block
		frappe.log_error(
			message=f"WO: {wo_name} – Close Issue DocEntry {issue_doc_entry} returned error ({close_err}) and status could not be verified. Proceeding.",
			title="WowPets WO SAP Issue Close warning",
		)


def _sap_po_error_hint(err, finished_item, production_order):
	"""Return a user-friendly hint for common SAP Production Order errors."""
	if not err:
		return ""
	err_lower = (err or "").lower()
	hint = ""
	if "itemno" in err_lower or "itemcode" in err_lower or "item" in err_lower and "not found" in err_lower:
		hint = _(" Check in SAP: finished item '{0}' exists, has a BOM (ProductTree), and is set up for production. Use items with FGDC prefix if BOM exists.").format(finished_item)
	elif "bom" in err_lower or "producttree" in err_lower:
		hint = _(" The finished item must have a BOM in SAP (Production > Bill of Materials). Ensure BOM components match the Work Order.")
	elif "warehouse" in err_lower or "whs" in err_lower:
		hint = _(" Verify warehouses 'WO - STR' (components) and 'WO -FG' (finished goods) exist in SAP.")
	elif "internal" in err_lower or "500" in str(err):
		hint = _(" SAP internal error. Check INC SAP Settings (CompanyDB, credentials). Try again after a short delay.")
	elif "unauthorized" in err_lower or "401" in str(err):
		hint = _(" SAP session expired. Re-login to WowPets or refresh INC SAP Settings session.")
	return hint


def _extract_sap_error(resp):
	"""Extract human-readable error from SAP B1 Service Layer response. Handles multiple formats."""
	try:
		ct = resp.headers.get("Content-Type") or ""
		if "json" not in ct.lower():
			return resp.text[:500] if resp.text else str(resp.status_code)
		data = resp.json()
		if not isinstance(data, dict):
			return resp.text[:500] or str(resp.status_code)
		# SAP B1 format: {"error": {"message": {"value": "..."}}}
		err_obj = data.get("error") or {}
		msg = err_obj.get("message")
		if isinstance(msg, dict):
			out = msg.get("value") or msg.get("message") or ""
		elif isinstance(msg, str):
			out = msg
		else:
			out = err_obj.get("message", {}).get("value", "") if isinstance(err_obj.get("message"), dict) else ""
		if out:
			return str(out).strip()
		# Fallback: inner message or code
		code = err_obj.get("code", "")
		if code:
			return f"{code}: {resp.text[:300]}"
		return resp.text[:500] if resp.text else str(resp.status_code)
	except Exception:
		return (resp.text[:500] if resp.text else str(resp.status_code))


@frappe.whitelist()
def receipt_from_production(name, finished_goods_batch=None):
	"""Post Receipt from Production in SAP for the finished item. KhanalFoods only. Idempotent. FG batch from param or doc."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can post Receipt from Production"))

	doc = frappe.get_doc("WowPets Work Order", name, for_update=True)
	if doc.status not in ("Completed", "In Progress"):
		frappe.throw(_("Work Order must be Completed or In Progress"))
	po_entry = getattr(doc, "sap_production_order_doc_entry", None)
	if not po_entry:
		frappe.throw(_("Create Production Order and Issue first"))
	if getattr(doc, "sap_receipt_doc_entry", None):
		return doc.as_dict()

	fg_batch = (finished_goods_batch or "").strip() or (doc.finished_goods_batch or "").strip()
	if not fg_batch:
		frappe.throw(_("Finished goods batch is required for Receipt from Production. Enter it when posting (KhanalFoods)."))
	doc.finished_goods_batch = fg_batch

	session, b1_url = _get_sap_session()
	if not session or not b1_url:
		frappe.throw(_("SAP session not available. Check INC SAP Settings."))

	posting_date = (doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.posting_date, "strftime") else str(doc.posting_date or frappe.utils.today())
	qty = float(doc.produced_qty or doc.qty_to_produce or 0)
	if qty <= 0:
		frappe.throw(_("Produced quantity must be greater than zero"))

	session, b1_url, receipt_doc_entry, receipt_error = _post_receipt_from_production(session, b1_url, doc, po_entry, qty, fg_batch, posting_date)
	if receipt_error:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = receipt_error
		doc.save()
		frappe.db.commit()
		frappe.throw(_("SAP Receipt from Production failed: {0}").format(receipt_error))
	doc.sap_receipt_doc_entry = receipt_doc_entry
	doc.sap_sync_status = "Receipt Posted"
	doc.sap_sync_error = None
	doc.save()
	try:
		url_patch = b1_url.rstrip("/") + f"/ProductionOrders({po_entry})"
		session.patch(url_patch, data=json.dumps({"ProductionOrderStatus": "boposClosed"}), verify=_SAP_VERIFY_SSL, timeout=30, headers={"Content-Type": "application/json"})
	except Exception:
		pass
	frappe.db.commit()
	return doc.as_dict()
