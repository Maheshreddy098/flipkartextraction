"""API for WowPets Orders. KhanalFoods: create/edit/submit/approve; Warehouse: accept, packaging, complete (triggers SAP transfer from WO -FG)."""
import json
import frappe
from frappe import _
from frappe.utils import flt, cint
from khanal_tech_integrations.api.wowpets.auth import check_wowpets_access, get_user_team, is_manager, get_user_wowpets_roles
from khanal_tech_integrations.api.wowpets import ORDERS_FROM_WAREHOUSE


def _normalize_wh_for_compare(wh):
	"""Normalize warehouse code for from/to comparison."""
	return (wh or "").strip().upper().replace(" ", "")


def _validate_to_warehouse_not_from(to_warehouse):
	if not to_warehouse:
		return
	if _normalize_wh_for_compare(to_warehouse) == _normalize_wh_for_compare(ORDERS_FROM_WAREHOUSE):
		frappe.throw(
			_("To Warehouse cannot be the source warehouse (WO -FG). Please select a different destination.")
		)


_check_wowpets_access = check_wowpets_access


def _throw_if_warehouse_awaiting_kf(doc):
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(
			_(
				"This order is on hold until KhanalFoods saves an update after your support ticket."
			)
		)


@frappe.whitelist()
def get_list(status=None, page=1, page_size=20):
	_check_wowpets_access()

	filters = {}
	team = get_user_team()
	# Warehouse sees only Approved and beyond (no Draft / Pending Approval)
	if team == "warehouse":
		allowed = ["Approved", "Accepted", "Packaging", "Dispatched", "Sent to SAP", "Error"]
		filters["status"] = status if (status and status in allowed) else ["in", allowed]
	else:
		if status:
			filters["status"] = status

	orders = frappe.get_list(
		"WowPets Order",
		filters=filters,
		fields=[
			"name",
			"status",
			"fba_transfer_name",
			"doc_date",
			"to_warehouse",
			"comments",
			"accepted_by",
			"sap_request_doc_entry",
			"sap_doc_entry",
			"sap_doc_num",
			"sap_sync_error",
			"warehouse_awaiting_kf",
			"modified",
		],
		order_by="modified desc",
		start=(int(page) - 1) * int(page_size),
		page_length=int(page_size),
	)

	total = frappe.db.count("WowPets Order", filters=filters)
	return {"data": orders, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_wowpets_access()
	doc = frappe.get_doc("WowPets Order", name)
	return doc.as_dict()


def _validate_items(items):
	if not items:
		frappe.throw(_("At least one item is required"))
	for i, row in enumerate(items):
		if not (row.get("item_code") or "").strip():
			frappe.throw(_("Row {0}: Item Code is required").format(i + 1))
		qty = flt(row.get("quantity"))
		if qty is None or qty <= 0:
			frappe.throw(_("Row {0}: Quantity must be greater than 0").format(i + 1))
		if not (row.get("batch_number") or "").strip():
			frappe.throw(_("Row {0}: Select a batch from WO -FG (from SAP)").format(i + 1))


@frappe.whitelist()
def create(data):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create Orders"))

	if isinstance(data, str):
		data = json.loads(data)

	doc_date = data.get("doc_date") or frappe.utils.today()
	to_warehouse = (data.get("to_warehouse") or "").strip()
	if not to_warehouse:
		frappe.throw(_("To Warehouse is required"))
	_validate_to_warehouse_not_from(to_warehouse)
	comments = (data.get("comments") or "").strip() or None
	if not comments:
		frappe.throw(_("Comments are required"))
	# Address required (USA format; not sent to SAP)
	addr1 = (data.get("address_line1") or "").strip()
	city = (data.get("city") or "").strip()
	state = (data.get("state") or "").strip()
	zip_code = (data.get("zip_code") or "").strip()
	if not addr1:
		frappe.throw(_("Address Line 1 is required"))
	if not city:
		frappe.throw(_("City is required"))
	if not state:
		frappe.throw(_("State is required (e.g. CA)"))
	if not zip_code:
		frappe.throw(_("ZIP Code is required"))

	items = data.get("items", [])
	_validate_items(items)

	doc = frappe.new_doc("WowPets Order")
	doc.status = "Draft"
	doc.doc_date = doc_date
	doc.to_warehouse = to_warehouse
	doc.fba_transfer_name = (data.get("fba_transfer_name") or "").strip()
	doc.comments = comments
	# Address (USA format, stored in Frappe only – not sent to SAP)
	doc.address_line1 = addr1 or None
	doc.address_line2 = (data.get("address_line2") or "").strip() or None
	doc.city = city or None
	doc.state = state or None
	doc.zip_code = zip_code or None

	for row in items:
		doc.append("items", {
			"item_code": (row.get("item_code") or "").strip(),
			"item_name": (row.get("item_name") or "").strip(),
			"quantity": flt(row.get("quantity") or 0),
			"uom": (row.get("uom") or "Nos").strip() or "Nos",
			"number_of_units_per_box": cint(row.get("number_of_units_per_box") or 0),
			"number_of_boxes": cint(row.get("number_of_boxes") or 0),
			"batch_number": (row.get("batch_number") or "").strip() or None,
		})

	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update(name, data):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can update Orders"))

	if isinstance(data, str):
		data = json.loads(data)

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	can_resume = cint(getattr(doc, "warehouse_awaiting_kf", 0))
	if doc.status != "Draft" and not can_resume:
		frappe.throw(_("Only Draft orders can be updated"))

	doc.fba_transfer_name = (data.get("fba_transfer_name") or doc.fba_transfer_name or "").strip()
	doc.doc_date = data.get("doc_date") or doc.doc_date
	to_warehouse = (data.get("to_warehouse") or "").strip()
	if to_warehouse:
		_validate_to_warehouse_not_from(to_warehouse)
		doc.to_warehouse = to_warehouse
	doc.comments = (data.get("comments") or "").strip() or None
	if not doc.comments:
		frappe.throw(_("Comments are required"))
	if "address_line1" in data:
		doc.address_line1 = (data.get("address_line1") or "").strip() or None
	if "address_line2" in data:
		doc.address_line2 = (data.get("address_line2") or "").strip() or None
	if "city" in data:
		doc.city = (data.get("city") or "").strip() or None
	if "state" in data:
		doc.state = (data.get("state") or "").strip() or None
	if "zip_code" in data:
		doc.zip_code = (data.get("zip_code") or "").strip() or None

	items_data = data.get("items")  # None = not provided (keep existing); [] = explicitly cleared
	if items_data is not None:
		_validate_items(items_data)
		doc.items = []
		for row in items_data:
			doc.append("items", {
				"item_code": (row.get("item_code") or "").strip(),
				"item_name": (row.get("item_name") or "").strip(),
				"quantity": flt(row.get("quantity") or 0),
				"uom": (row.get("uom") or "Nos").strip() or "Nos",
				"number_of_units_per_box": cint(row.get("number_of_units_per_box") or 0),
				"number_of_boxes": cint(row.get("number_of_boxes") or 0),
				"batch_number": (row.get("batch_number") or "").strip() or None,
			})
	if can_resume:
		doc.warehouse_awaiting_kf = 0
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def warehouse_request_kf_assistance(name):
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can request KhanalFoods assistance"))
	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if doc.status not in ("Approved", "Accepted", "Packaging", "Dispatched", "Error"):
		frappe.throw(_("Assistance request is allowed only for active warehouse order statuses"))
	doc.warehouse_awaiting_kf = 1
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_release_warehouse_hold(name):
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods can release the warehouse hold"))
	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		doc.warehouse_awaiting_kf = 0
		doc.save()
		frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_update_for_warehouse_resume(name, data):
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods can apply this update"))
	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if not cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(_("Warehouse has not requested KhanalFoods assistance for this order"))
	return update(name, data)


@frappe.whitelist()
def submit_for_approval(name):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can submit Orders"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft orders can be submitted for approval"))

	if not doc.items or len(doc.items) == 0:
		frappe.throw(_("Cannot submit order without items"))

	doc.status = "Pending Approval"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve(name):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can approve Orders"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval orders can be approved"))

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def reject(name, reason=""):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can reject Orders"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval orders can be rejected"))

	doc.status = "Rejected"
	if reason:
		doc.comments = (doc.comments or "") + f"\nRejection reason: {reason}"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def revert_to_draft(name):
	"""Revert a rejected Order back to Draft for editing."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can revert Orders to Draft"))
	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	if doc.status != "Rejected":
		frappe.throw(_("Only Rejected orders can be reverted to Draft"))
	doc.status = "Draft"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def accept(name):
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can accept Orders"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Approved":
		frappe.throw(_("Only Approved orders can be accepted"))

	doc.status = "Accepted"
	doc.accepted_by = frappe.session.user
	doc.accepted_date = frappe.utils.today()

	# On accept, raise an Inventory Transfer Request in SAP (using ordered quantity).
	# If this fails we keep local status as Accepted and log the error; final transfer
	# is still posted when warehouse dispatches the order.
	try:
		from khanal_tech_integrations.api.wowpets.sap_master import create_stock_transfer_request_from_wowpets_order
		from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

		result = create_stock_transfer_request_from_wowpets_order(doc)
		doc.sap_request_doc_entry = str(result.get("doc_entry", ""))
		doc.sap_request_doc_num = str(result.get("doc_num", ""))
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order (Request)",
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		doc.sap_sync_error = str(e)
		from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order (Request)",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets Order SAP Request failed: {e}", "WowPets Order SAP Request")

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def retry_sap_request(name):
	"""Retry creating the SAP Inventory Transfer Request for an FBA Order.

	Pattern matches Shiphero transfers:
	- Warehouse-only.
	- Only when status is Accepted.
	- Only when no request doc entry exists yet.
	"""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can retry the SAP transfer request"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Accepted":
		frappe.throw(_("Only Accepted orders can have the SAP request retried"))
	if (doc.sap_request_doc_entry or "").strip():
		frappe.throw(_("SAP Transfer Request already exists (Doc Entry: {0})").format(doc.sap_request_doc_entry))

	from khanal_tech_integrations.api.wowpets.sap_master import create_stock_transfer_request_from_wowpets_order
	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

	try:
		result = create_stock_transfer_request_from_wowpets_order(doc)
		doc.sap_request_doc_entry = str(result.get("doc_entry", ""))
		doc.sap_request_doc_num = str(result.get("doc_num", ""))
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order (Request)",
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		raw_message = str(e)
		doc.sap_sync_error = raw_message
		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order (Request)",
			status="Failed",
			error_message=raw_message,
		)
		frappe.log_error(f"WowPets Order SAP Request retry failed: {raw_message}", "WowPets Order SAP Request")
		doc.save()
		frappe.db.commit()
		raise

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def start_packaging(name):
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can start packaging"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Accepted":
		frappe.throw(_("Only Accepted orders can be started for packaging"))

	doc.status = "Packaging"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def complete(name, data=None):
	"""Warehouse dispatches order. Posts the final Inventory Transfer to SAP.
	Packaging fields (units_per_box, number_of_boxes) are advisory and not validated here.
	"""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can complete Orders"))

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Packaging":
		frappe.throw(_("Only Packaging orders can be dispatched"))

	# Optional: update line-level packaging fields and batch before completing
	if data:
		if isinstance(data, str):
			data = json.loads(data)
		items_data = data.get("items", [])
		if items_data:
			doc.items = []
			for row in items_data:
				doc.append("items", {
					"item_code": (row.get("item_code") or "").strip(),
					"item_name": (row.get("item_name") or "").strip(),
					"quantity": flt(row.get("quantity") or 0),
					"uom": (row.get("uom") or "Nos").strip() or "Nos",
					"number_of_units_per_box": cint(row.get("number_of_units_per_box") or 0),
					"number_of_boxes": cint(row.get("number_of_boxes") or 0),
					"batch_number": (row.get("batch_number") or "").strip() or None,
				})
			doc.save()
	# Mark as Dispatched locally before posting the final Inventory Transfer.
	doc.status = "Dispatched"
	doc.completed_date = frappe.utils.today()
	doc.save()
	frappe.db.commit()

	# Post the final Inventory Transfer to SAP. If this fails, keep Dispatched locally but mark Error.
	try:
		_sync_order_to_sap(doc)
		doc.save()
		frappe.db.commit()
	except Exception as e:
		doc.sap_sync_error = str(e)
		doc.status = "Error"
		from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap
		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets Order SAP failed: {e}", "WowPets Order SAP")
		doc.save()
		frappe.db.commit()

	return doc.as_dict()


def _sync_order_to_sap(doc):
	"""Post order to SAP (inventory transfer WO-FG -> to_warehouse). Updates doc in place; caller must save/commit."""
	if (getattr(doc, "sap_doc_entry", None) or "").strip():
		return
	from khanal_tech_integrations.api.wowpets.sap_master import create_stock_transfer_from_wowpets_order
	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

	result = create_stock_transfer_from_wowpets_order(doc)
	doc.sap_doc_entry = str(result.get("doc_entry", ""))
	doc.sap_doc_num = str(result.get("doc_num", ""))
	doc.sap_sync_error = None
	doc.status = "Sent to SAP"
	log_wowpets_sap(
		reference_doctype="WowPets Order",
		reference_name=doc.name,
		operation="Stock Transfer - Order",
		status="Success",
		response_payload=result,
	)


@frappe.whitelist()
def preview_sap(name):
	"""KhanalFoods: preview what will be sent to SAP (from WO -FG to to_warehouse, lines)."""
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can preview SAP transfer"))

	doc = frappe.get_doc("WowPets Order", name)
	if doc.status not in ("Dispatched", "Error"):
		frappe.throw(_("Only Dispatched (or Error) orders can be previewed for SAP"))

	from_warehouse = (ORDERS_FROM_WAREHOUSE or "").strip()
	to_warehouse = (doc.to_warehouse or "").strip()
	lines = []
	for row in doc.items:
		lines.append({
			"item_code": row.get("item_code") if isinstance(row, dict) else getattr(row, "item_code", None),
			"item_name": row.get("item_name") if isinstance(row, dict) else getattr(row, "item_name", None),
			"quantity": float(row.get("quantity") or 0) if isinstance(row, dict) else float(getattr(row, "quantity", 0) or 0),
			"batch_number": (row.get("batch_number") or "").strip() if isinstance(row, dict) else (getattr(row, "batch_number", None) or "").strip(),
		})
	return {
		"from_warehouse": from_warehouse,
		"to_warehouse": to_warehouse,
		"doc_date": str(doc.doc_date) if doc.doc_date else None,
		"lines": lines,
	}


@frappe.whitelist()
def send_to_sap(name):
	"""Send order to SAP. Warehouse may call only when status is Error (retry). KhanalFoods may call when Completed or Error."""
	_check_wowpets_access()

	team = get_user_team()
	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status not in ("Dispatched", "Error"):
		frappe.throw(_("Only Dispatched or Error orders can be sent to SAP"))
	if (doc.sap_doc_entry or "").strip():
		frappe.throw(_("This order was already sent to SAP (Doc Entry: {0})").format((doc.sap_doc_entry or "").strip()))

	# Warehouse can only retry when SAP failed (Error); no manual Send to SAP in normal flow
	if team == "warehouse" and doc.status != "Error":
		frappe.throw(_("Only KhanalFoods can send to SAP first. Warehouse can use Retry to SAP only when sync failed."))

	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

	try:
		_sync_order_to_sap(doc)
	except Exception as e:
		doc.sap_sync_error = str(e)
		doc.status = "Error"
		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets Order SAP failed: {e}", "WowPets Order SAP")
		doc.save()
		frappe.db.commit()
		raise

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


_ORDER_USER_DELETABLE = {"Draft"}
_ORDER_MANAGER_DELETABLE = {"Draft", "Pending Approval", "Approved", "Rejected"}


@frappe.whitelist()
def delete_draft(name):
	"""Delete a WowPets Order. KhanalFoods team only.
	Regular user: own Draft records with no SAP data.
	Manager: Draft / Pending Approval / Approved / Rejected with no SAP data.
	"""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can delete orders"), frappe.PermissionError)

	doc = frappe.get_doc("WowPets Order", name)

	if (doc.sap_request_doc_entry or "").strip() or (doc.sap_doc_entry or "").strip():
		frappe.throw(_("Cannot delete: this order has already been sent to SAP"), frappe.ValidationError)

	user = frappe.session.user
	if is_manager():
		if doc.status not in _ORDER_MANAGER_DELETABLE:
			frappe.throw(
				_("Cannot delete: order is in '{0}' status. Managers can only delete orders the warehouse has not yet accepted.").format(doc.status),
				frappe.ValidationError,
			)
	else:
		if doc.owner != user:
			frappe.throw(_("You can only delete orders you created"), frappe.PermissionError)
		if doc.status not in _ORDER_USER_DELETABLE:
			frappe.throw(_("Only Draft orders can be deleted"), frappe.ValidationError)

	from khanal_tech_integrations.api.wowpets.kf_attachments import _delete_all_doc_attachments
	_delete_all_doc_attachments("WowPets Order", name)
	frappe.delete_doc("WowPets Order", name, ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def retry_sap(name):
	"""Retry sending order to SAP after Error (warehouse or KhanalFoods)."""
	_check_wowpets_access()

	doc = frappe.get_doc("WowPets Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status not in ("Error", "Dispatched"):
		frappe.throw(_("Only orders in Error or Dispatched status can retry SAP"))
	if doc.status == "Dispatched" and (doc.sap_doc_entry or "").strip():
		frappe.throw(_("Inventory Transfer already exists for this order (Doc Entry: {0})").format(doc.sap_doc_entry))

	doc.sap_sync_error = None

	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap
	try:
		_sync_order_to_sap(doc)
	except Exception as e:
		doc.sap_sync_error = str(e)
		doc.status = "Error"
		log_wowpets_sap(
			reference_doctype="WowPets Order",
			reference_name=doc.name,
			operation="Stock Transfer - Order",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets Order SAP retry failed: {e}", "WowPets Order SAP")
		doc.save()
		frappe.db.commit()
		raise

	doc.save()
	frappe.db.commit()
	return doc.as_dict()
