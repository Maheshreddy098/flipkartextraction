"""API for Real Aquatics Dispatch Orders. Create Sales Order in SAP B1 on manager approval; warehouse accepts, prepares, dispatches."""
import json
import frappe
from frappe import _
from frappe.utils import flt, cint
from khanal_tech_integrations.api.real_aquatics.auth import check_real_aquatics_access, get_user_team, is_manager, get_user_real_aquatics_roles


_check_real_aquatics_access = check_real_aquatics_access


def _throw_if_warehouse_awaiting_kf(doc):
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(
			_(
				"This dispatch order is on hold until KhanalFoods saves an update after your support ticket."
			)
		)


@frappe.whitelist()
def get_list(status=None, page=1, page_size=20):
	_check_real_aquatics_access()

	filters = {}
	team = get_user_team()
	if team == "warehouse":
		# Warehouse sees operational statuses including Error, but cannot fix SAP issues themselves.
		allowed = ["Approved", "Accepted", "In Preparation", "Dispatched", "Error"]
		filters["status"] = status if (status and status in allowed) else ["in", allowed]
	else:
		if status:
			filters["status"] = status

	orders = frappe.get_list(
		"Real Aquatics Dispatch Order",
		filters=filters,
		fields=[
			"name",
			"dispatch_order_name",
			"status",
			"card_code",
			"card_name",
			"doc_date",
			"doc_due_date",
			"num_at_card",
			"ship_to_code",
			"bill_to_code",
			"comments",
			"approved_by",
			"accepted_by",
			"dispatched_at",
			"sap_doc_entry",
			"sap_doc_num",
			"sap_delivery_doc_num",
			"sap_invoice_doc_num", "warehouse_awaiting_kf",
			"sap_sync_error", "modified",
			"mobile_number",
		],
		order_by="modified desc",
		start=(int(page) - 1) * int(page_size),
		page_length=int(page_size),
	)
	total = frappe.db.count("Real Aquatics Dispatch Order", filters=filters)
	return {"data": orders, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_real_aquatics_access()
	doc = frappe.get_doc("Real Aquatics Dispatch Order", name)
	return doc.as_dict()


@frappe.whitelist()
def reconcile_status(name):
	"""Explicitly reconcile a dispatch order whose local status is out of sync with SAP.
	Call this when a SO exists in SAP but the local status is stuck on Approved or Error.
	KhanalFoods managers and warehouse team can call this.
	"""
	_check_real_aquatics_access()
	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)

	if not (doc.sap_doc_entry or "").strip():
		frappe.throw(_("Cannot reconcile: no SAP Sales Order DocEntry recorded on this dispatch order"))

	if doc.status not in ("Approved", "Error"):
		frappe.throw(_("Reconciliation is only needed for Approved or Error dispatch orders that already have a SAP SO"))

	doc.status = "Accepted"
	doc.sap_sync_error = None
	if not (doc.accepted_by or "").strip():
		doc.accepted_by = frappe.session.user
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


def _validate_items(items):
	if not items:
		frappe.throw(_("At least one line item is required"))
	for i, row in enumerate(items):
		if not (row.get("item_code") or "").strip():
			frappe.throw(_("Row {0}: Item Code is required").format(i + 1))
		qty = flt(row.get("quantity"))
		if qty is None or qty <= 0:
			frappe.throw(_("Row {0}: Quantity must be greater than 0").format(i + 1))
		price = flt(row.get("unit_price"))
		if price is None or price <= 0:
			frappe.throw(_("Row {0}: Unit Price is required and must be greater than 0").format(i + 1))
		if not (row.get("batch_number") or "").strip():
			frappe.throw(_("Row {0}: Select a batch from RP-STR or RP-FG (from SAP)").format(i + 1))


def _validate_batch_quantity(items):
	"""Ensure each line's quantity does not exceed the selected batch's available quantity in SAP."""
	# from khanal_tech_integrations.api.real_aquatics.sap_master import get_batches_for_dispatch_item

	# for i, row in enumerate(items):
	# 	item_code = (row.get("item_code") or "").strip()
	# 	batch_number = (row.get("batch_number") or "").strip()
	# 	qty = flt(row.get("quantity") or 0)
	# 	if not item_code or not batch_number or qty <= 0:
	# 		continue
	# 	res = get_batches_for_dispatch_item(item_code)
	# 	batch_list = res.get("data") or []
	# 	# Same batch can exist in RP-STR and RP-FG; sum quantity for this batch_number
	# 	available = sum(flt(b.get("quantity") or 0) for b in batch_list if (b.get("batch_number") or "").strip() == batch_number)
	# 	if available < qty:
	# 		frappe.throw(
	# 			_("Row {0} ({1}): Quantity {2} exceeds available quantity {3} in batch {4}. Reduce quantity or select another batch.").format(
	# 				i + 1, item_code, qty, available, batch_number
	# 			)
	# 		)


@frappe.whitelist()
def create(data):
	_check_real_aquatics_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create Dispatch Orders"))

	if isinstance(data, str):
		data = json.loads(data)

	card_code = (data.get("card_code") or "").strip()
	if not card_code:
		frappe.throw(_("Customer Code (SAP) is required"))
	card_name = (data.get("card_name") or "").strip() or card_code
	doc_date = data.get("doc_date") or frappe.utils.today()
	doc_due_date = data.get("doc_due_date") or doc_date
	num_at_card = (data.get("num_at_card") or "").strip()
	if not num_at_card:
		frappe.throw(_("Reference (Num at Card) is required"))
	num_at_card = num_at_card
	comments = (data.get("comments") or "").strip() or None
	dispatch_order_name = (data.get("dispatch_order_name") or "").strip() or None
	ship_to_code = (data.get("ship_to_code") or "").strip() or None
	bill_to_code = (data.get("bill_to_code") or "").strip() or None

	items = [r for r in (data.get("items") or []) if (r.get("item_code") or "").strip()]
	if not items:
		frappe.throw(_("At least one line item with Item Code is required"))
	_validate_items(items)
	_validate_batch_quantity(items)

	doc = frappe.new_doc("Real Aquatics Dispatch Order")
	doc.status = "Draft"
	doc.dispatch_order_name = dispatch_order_name
	doc.card_code = card_code
	doc.card_name = card_name
	doc.doc_date = doc_date
	doc.doc_due_date = doc_due_date
	doc.num_at_card = num_at_card
	doc.comments = comments
	doc.ship_to_code = ship_to_code
	doc.bill_to_code = bill_to_code
	doc.mobile_number = (data.get("mobile_number") or "").strip() or None

	for row in items:
		doc.append("items", {
			"item_code": (row.get("item_code") or "").strip(),
			"item_name": (row.get("item_name") or "").strip(),
			"quantity": flt(row.get("quantity") or 0),
			"uom": (row.get("uom") or "Nos").strip() or "Nos",
			"number_of_units_per_box": cint(row.get("number_of_units_per_box") or 0),
			"number_of_boxes": cint(row.get("number_of_boxes") or 0),
			"batch_number": (row.get("batch_number") or "").strip() or None,
			"warehouse_code": (row.get("warehouse_code") or "").strip() or None,
			"unit_price": flt(row.get("unit_price") or 0),
		})

	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update(name, data):
	_check_real_aquatics_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can update Dispatch Orders"))

	if isinstance(data, str):
		data = json.loads(data)

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	can_resume = cint(getattr(doc, "warehouse_awaiting_kf", 0))
	if doc.status not in ("Draft", "Error") and not can_resume:
		frappe.throw(_("Only Draft or Error dispatch orders can be updated (Error: fix data after ticket, then Retry SAP)."))

	if "card_code" in data:
		doc.card_code = (data.get("card_code") or "").strip() or doc.card_code
	if "card_name" in data:
		doc.card_name = (data.get("card_name") or "").strip() or doc.card_name
	if "doc_date" in data:
		doc.doc_date = data.get("doc_date") or doc.doc_date
	if "doc_due_date" in data:
		doc.doc_due_date = data.get("doc_due_date") or doc.doc_due_date
	if "num_at_card" in data:
		num_at_card = (data.get("num_at_card") or "").strip()
		if not num_at_card:
			frappe.throw(_("Reference (Num at Card) is required"))
		doc.num_at_card = num_at_card
	if "ship_to_code" in data:
		doc.ship_to_code = (data.get("ship_to_code") or "").strip() or None
	if "bill_to_code" in data:
		doc.bill_to_code = (data.get("bill_to_code") or "").strip() or None
	if "comments" in data:
		doc.comments = (data.get("comments") or "").strip() or None
	if "mobile_number" in data:
		doc.mobile_number = (data.get("mobile_number") or "").strip() or None
	if "dispatch_order_name" in data:
		doc.dispatch_order_name = (data.get("dispatch_order_name") or "").strip() or None

	items_data = [r for r in (data.get("items") or []) if (r.get("item_code") or "").strip()]
	if items_data:
		_validate_items(items_data)
		_validate_batch_quantity(items_data)
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
				"warehouse_code": (row.get("warehouse_code") or "").strip() or None,
				"unit_price": flt(row.get("unit_price") or 0),
			})

	if can_resume:
		doc.warehouse_awaiting_kf = 0
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def warehouse_request_kf_assistance(name):
	_check_real_aquatics_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can request KhanalFoods assistance"))
	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if doc.status not in ("Approved", "Accepted", "In Preparation", "Dispatched", "Error"):
		frappe.throw(_("Assistance request is allowed only for active warehouse dispatch statuses"))
	doc.warehouse_awaiting_kf = 1
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_release_warehouse_hold(name):
	_check_real_aquatics_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods can release the warehouse hold"))
	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		doc.warehouse_awaiting_kf = 0
		doc.save()
		frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_update_for_warehouse_resume(name, data):
	_check_real_aquatics_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods can apply this update"))
	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if not cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(_("Warehouse has not requested KhanalFoods assistance for this dispatch order"))
	return update(name, data)


@frappe.whitelist()
def submit_for_approval(name):
	_check_real_aquatics_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can submit Dispatch Orders for approval"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft dispatch orders can be submitted for approval"))

	# Ignore rows with no item_code (blank lines)
	doc_items = [r for r in (doc.items or []) if (getattr(r, "item_code", None) or (r.get("item_code") if isinstance(r, dict) else "")) and (getattr(r, "item_code", "") or (r.get("item_code") or "")).strip()]
	if not doc_items:
		frappe.throw(_("Cannot submit without line items"))

	# Validate batch and packaging (units per box × number of boxes = quantity)
	rows = [
		{
			"quantity": getattr(r, "quantity", 0),
			"number_of_units_per_box": getattr(r, "number_of_units_per_box", 0),
			"number_of_boxes": getattr(r, "number_of_boxes", 0),
			"batch_number": getattr(r, "batch_number", "") or (r.get("batch_number") if isinstance(r, dict) else ""),
			"item_code": (getattr(r, "item_code", "") or "").strip(),
			# Ensure unit_price is present so _validate_items' price check passes on submit.
			"unit_price": getattr(r, "unit_price", 0),
		}
		for r in doc_items
	]
	if not rows:
		frappe.throw(_("Cannot submit without line items"))
	_validate_items(rows)
	_validate_batch_quantity(rows)

	ship_to = (getattr(doc, "ship_to_code", None) or "").strip()
	if not ship_to:
		frappe.throw(_("Ship-To address (SAP) is required. Select an address for the customer or add one in SAP, then save and submit again."))
	bill_to = (getattr(doc, "bill_to_code", None) or "").strip()
	num_at_card = (getattr(doc, "num_at_card", None) or "").strip()
	if not num_at_card:
		frappe.throw(_("Reference (Num at Card) is required before submitting. Please fill it in and save again."))
	if not bill_to:
		frappe.throw(_("Bill-To address (SAP) is required. Select an address for the customer or add one in SAP, then save and submit again."))

	doc.status = "Pending Approval"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve(name):
	_check_real_aquatics_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can approve Dispatch Orders"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if doc.status == "Approved":
		# Idempotent: already approved (e.g. double-click or stale list)
		return doc.as_dict()
	if doc.status == "Draft":
		frappe.throw(_("Submit for approval first. Only Pending Approval orders can be approved."))
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval dispatch orders can be approved."))

	doc.status = "Approved"
	doc.approved_by = frappe.session.user

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def reject(name, reason=""):
	_check_real_aquatics_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can reject Dispatch Orders"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval dispatch orders can be rejected"))

	doc.status = "Rejected"
	if reason:
		doc.comments = (doc.comments or "") + f"\nRejection reason: {reason}"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def revert_to_draft(name):
	"""Revert a rejected Dispatch Order back to Draft for editing."""
	_check_real_aquatics_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can revert Dispatch Orders to Draft"))
	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if doc.status != "Rejected":
		frappe.throw(_("Only Rejected dispatch orders can be reverted to Draft"))
	doc.status = "Draft"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def accept(name):
	_check_real_aquatics_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can accept Dispatch Orders"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Approved":
		frappe.throw(_("Only Approved dispatch orders can be accepted"))

	# from khanal_tech_integrations.api.real_aquatics.sap_master import create_sales_order_from_dispatch_order
	# from khanal_tech_integrations.api.real_aquatics.sap_log import log_real_aquatics_sap

	# try:
	# 	result = create_sales_order_from_dispatch_order(doc)
	# 	doc.sap_doc_entry = str(result.get("doc_entry", ""))
	# 	doc.sap_doc_num = str(result.get("doc_num", ""))
	# 	doc.sap_sync_error = None
	# 	doc.accepted_by = frappe.session.user
	# 	doc.status = "Accepted"
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="Sales Order",
	# 		status="Success",
	# 		response_payload=result,
	# 	)
	# except Exception as e:
	# 	doc.sap_sync_error = str(e)
	# 	doc.status = "Error"
	# 	doc.accepted_by = None
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="Sales Order",
	# 		status="Failed",
	# 		error_message=str(e),
	# 	)
	# 	doc.save()
	# 	frappe.db.commit()
	# 	raise

	doc.accepted_by = frappe.session.user
	doc.status = "Accepted"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def start_preparation(name):
	_check_real_aquatics_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can start preparation"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Accepted":
		frappe.throw(_("Only Accepted dispatch orders can be started for preparation"))

	doc.status = "In Preparation"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def dispatch(name):
	_check_real_aquatics_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can mark Dispatch Orders as dispatched"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "In Preparation":
		frappe.throw(_("Only In Preparation dispatch orders can be marked as dispatched"))
	# if not (doc.sap_doc_entry or "").strip():
	# 	frappe.throw(_("SAP Sales Order DocEntry is missing. Accept the dispatch order (to create Sales Order in SAP) before dispatching."))

	# from khanal_tech_integrations.api.real_aquatics.sap_master import (
	# 	create_delivery_from_dispatch_order,
	# 	create_ar_invoice_from_delivery,
	# )
	# from khanal_tech_integrations.api.real_aquatics.sap_log import log_real_aquatics_sap

	# _dispatch_step = "Delivery"
	# try:
	# 	# 1) Create Delivery from Sales Order
	# 	delivery = create_delivery_from_dispatch_order(doc.name)
	# 	doc.sap_delivery_doc_entry = str(delivery.get("doc_entry", ""))
	# 	doc.sap_delivery_doc_num = str(delivery.get("doc_num", ""))
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="Delivery",
	# 		status="Success",
	# 		response_payload=delivery,
	# 	)

	# 	# 2) Create AR Invoice from Delivery
	# 	_dispatch_step = "AR Invoice"
	# 	invoice = create_ar_invoice_from_delivery(doc.sap_delivery_doc_entry)
	# 	doc.sap_invoice_doc_entry = str(invoice.get("doc_entry", ""))
	# 	doc.sap_invoice_doc_num = str(invoice.get("doc_num", ""))
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="AR Invoice",
	# 		status="Success",
	# 		response_payload=invoice,
	# 	)
	# except Exception as e:
	# 	# Keep status as In Preparation, but record error
	# 	doc.sap_sync_error = (doc.sap_sync_error or "") + f"\nDispatch SAP error: {e}"
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation=_dispatch_step,
	# 		status="Failed",
	# 		error_message=str(e),
	# 	)
	# 	doc.save()
	# 	frappe.db.commit()
	# 	raise

	doc.status = "Dispatched"
	doc.dispatched_at = frappe.utils.now()
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def retry_sap(name):
	"""Retry creating Sales Order in SAP when status is Error (KhanalFoods manager only)."""
	_check_real_aquatics_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can retry SAP for Dispatch Orders"))

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name, for_update=True)
	if doc.status != "Error":
		frappe.throw(_("Only dispatch orders in Error status can retry SAP"))

	# # SO already exists (e.g. first post succeeded; retry hit duplicate NumAtCard) — reconcile, do not post again
	# if (doc.sap_doc_entry or "").strip():
	# 	from khanal_tech_integrations.api.real_aquatics.sap_log import log_real_aquatics_sap

	# 	doc.sap_sync_error = None
	# 	doc.status = "Accepted"
	# 	if not (doc.accepted_by or "").strip():
	# 		doc.accepted_by = frappe.session.user
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="Sales Order (Retry – use existing)",
	# 		status="Success",
	# 		response_payload={"doc_entry": doc.sap_doc_entry, "doc_num": doc.sap_doc_num, "note": "Reconciled existing SAP SO"},
	# 	)
	# 	doc.save()
	# 	frappe.db.commit()
	# 	return doc.as_dict()

	# doc.sap_sync_error = None
	# from khanal_tech_integrations.api.real_aquatics.sap_master import create_sales_order_from_dispatch_order
	# from khanal_tech_integrations.api.real_aquatics.sap_log import log_real_aquatics_sap

	# try:
	# 	result = create_sales_order_from_dispatch_order(doc)
	# 	doc.sap_doc_entry = str(result.get("doc_entry", ""))
	# 	doc.sap_doc_num = str(result.get("doc_num", ""))
	# 	# SO is live in SAP — same as successful warehouse Accept; warehouse should see Start Preparation next
	# 	doc.status = "Accepted"
	# 	if not (doc.accepted_by or "").strip():
	# 		doc.accepted_by = frappe.session.user
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="Sales Order (Retry)",
	# 		status="Success",
	# 		response_payload=result,
	# 	)
	# except Exception as e:
	# 	doc.sap_sync_error = str(e)
	# 	log_real_aquatics_sap(
	# 		reference_doctype="Real Aquatics Dispatch Order",
	# 		reference_name=doc.name,
	# 		operation="Sales Order (Retry)",
	# 		status="Failed",
	# 		error_message=str(e),
	# 	)
	# 	doc.save()
	# 	frappe.db.commit()
	# 	raise

	doc.sap_sync_error = None
	doc.status = "Accepted"
	if not (doc.accepted_by or "").strip():
		doc.accepted_by = frappe.session.user
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


_DO_USER_DELETABLE = {"Draft"}
_DO_MANAGER_DELETABLE = {"Draft", "Pending Approval", "Approved", "Rejected"}


@frappe.whitelist()
def delete_draft(name):
	"""Delete a Real Aquatics Dispatch Order. KhanalFoods team only.
	Regular user: own Draft records with no SAP data.
	Manager: Draft / Pending Approval / Approved / Rejected with no SAP data.
	"""
	_check_real_aquatics_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can delete dispatch orders"), frappe.PermissionError)

	doc = frappe.get_doc("Real Aquatics Dispatch Order", name)

	if (doc.sap_doc_entry or "").strip():
		frappe.throw(_("Cannot delete: this dispatch order has already been sent to SAP"), frappe.ValidationError)

	user = frappe.session.user
	if is_manager():
		if doc.status not in _DO_MANAGER_DELETABLE:
			frappe.throw(
				_("Cannot delete: dispatch order is in '{0}' status. Managers can only delete before the warehouse accepts.").format(doc.status),
				frappe.ValidationError,
			)
	else:
		if doc.owner != user:
			frappe.throw(_("You can only delete dispatch orders you created"), frappe.PermissionError)
		if doc.status not in _DO_USER_DELETABLE:
			frappe.throw(_("Only Draft dispatch orders can be deleted"), frappe.ValidationError)

	from khanal_tech_integrations.api.real_aquatics.kf_attachments import _delete_all_doc_attachments
	_delete_all_doc_attachments("Real Aquatics Dispatch Order", name)
	frappe.delete_doc("Real Aquatics Dispatch Order", name, ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}
