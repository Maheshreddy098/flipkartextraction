"""API for WowPets Inventory Transfer (Shiphero → WowPets). KhanalFoods: create/edit/submit/approve/send_to_sap; Warehouse: view + accept."""
import json
import frappe
from frappe import _
from khanal_tech_integrations.api.wowpets.auth import check_wowpets_access, get_user_team, is_manager, get_user_wowpets_roles
from khanal_tech_integrations.api.wowpets import SHIPHERO_IT_FROM_WAREHOUSE, SHIPHERO_IT_TO_WAREHOUSE


_check_wowpets_access = check_wowpets_access


def _throw_if_warehouse_awaiting_kf(doc):
	if frappe.utils.cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(
			_(
				"This transfer is on hold until KhanalFoods saves an update after your support ticket."
			)
		)


@frappe.whitelist()
def get_list(status=None, page=1, page_size=20):
	_check_wowpets_access()

	filters = {}
	if status:
		filters["status"] = status

	team = get_user_team()
	# Both teams see all; no status filter by team for list

	transfers = frappe.get_list(
		"WowPets Inventory Transfer",
		filters=filters,
		fields=[
			"name", "status", "inventory_transfer_name", "doc_date", "from_warehouse", "to_warehouse", "comments",
			"accepted_by", "sap_doc_entry", "sap_doc_num", "sap_sync_error", "modified",
			"warehouse_awaiting_kf",
		],
		order_by="modified desc",
		start=(int(page) - 1) * int(page_size),
		page_length=int(page_size),
	)

	# Aggregate ordered quantity and accepted quantity for list view (used by both teams).
	if transfers:
		names = [t["name"] for t in transfers]
		child_rows = frappe.get_all(
			"WowPets Inventory Transfer Item",
			filters={"parent": ["in", names]},
			fields=["parent", "quantity", "accepted_qty"],
		)
		from collections import defaultdict

		total_qty_by_parent = defaultdict(lambda: 0.0)
		total_accepted_by_parent = defaultdict(lambda: 0.0)

		for r in child_rows:
			parent = r["parent"]
			qty = float(r.get("quantity") or 0)  # ordered
			acc = float(r.get("accepted_qty") or 0)
			total_qty_by_parent[parent] += qty
			total_accepted_by_parent[parent] += acc

		for t in transfers:
			name = t["name"]
			t["total_qty"] = total_qty_by_parent.get(name, 0)
			# Use 0 when no accepted quantity yet, so the frontend can still display a number
			t["total_accepted_qty"] = total_accepted_by_parent.get(name, 0)

	total = frappe.db.count("WowPets Inventory Transfer", filters=filters)
	return {"data": transfers, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_wowpets_access()
	doc = frappe.get_doc("WowPets Inventory Transfer", name)
	return doc.as_dict()


def _validate_items(items):
	if not items:
		frappe.throw(_("At least one item is required"))
	for i, row in enumerate(items):
		if not (row.get("item_code") or "").strip():
			frappe.throw(_("Row {0}: Item Code is required").format(i + 1))
		try:
			qty = float(row.get("quantity") or 0)
		except (TypeError, ValueError):
			frappe.throw(_("Row {0}: Quantity must be a valid number").format(i + 1))
		if qty <= 0:
			frappe.throw(_("Row {0}: Quantity must be greater than 0").format(i + 1))


def _validate_items_batch(items):
	"""Require batch number on every line so the same batches are used when posting to SAP."""
	missing = []
	for i, row in enumerate(items):
		bn = (row.get("batch_number") or "").strip()
		if not bn:
			item_code = (row.get("item_code") or "").strip() or _("Row {0}").format(i + 1)
			missing.append(item_code)
	if missing:
		frappe.throw(
			_("Select a batch from the dropdown for every line before saving. Missing batch for: {0}").format(", ".join(missing))
		)


def _validate_batch_available(items, from_warehouse: str | None = None):
	"""Ensure requested quantity per (item_code, batch_number) does not exceed available batch quantity in SAP.

	This runs at creation/update time on the KhanalFoods side so obviously-invalid transfers
	(asking for more than is available in a batch) are blocked before warehouse ever sees them.
	"""
	from khanal_tech_integrations.api.wowpets.sap_master import get_batches_for_item

	from_wh = (from_warehouse or SHIPHERO_IT_FROM_WAREHOUSE or "").strip()
	if not from_wh:
		return

	for i, row in enumerate(items or []):
		item_code = (row.get("item_code") or "").strip()
		batch_number = (row.get("batch_number") or "").strip()
		try:
			qty = float(row.get("quantity") or 0)
		except (TypeError, ValueError):
			continue
		if not item_code or not batch_number or qty <= 0:
			continue

		res = get_batches_for_item(item_code, warehouse_code=from_wh)
		batch_list = res.get("data") or []
		available = 0.0
		for b in batch_list:
			if (b.get("batch_number") or "").strip() == batch_number:
				try:
					available += float(b.get("quantity") or 0)
				except (TypeError, ValueError):
					continue

		if available < qty:
			frappe.throw(
				_(
					"Row {0} ({1}): Quantity {2} exceeds available quantity {3} in batch {4}. "
					"Reduce quantity or choose other batch(es) before submitting."
				).format(i + 1, item_code, qty, available, batch_number)
			)


def _get_target_warehouse_for_item(item_code: str, default_to_warehouse: str) -> str:
	"""Determine target warehouse based on item code prefix, falling back to document-level to_warehouse.

	Routing rule (case-insensitive):
	- Codes starting with RM/PM/CO → WO-STR
	- Codes starting with FG       → WO-FG
	- Otherwise                    → default_to_warehouse
	"""
	code = (item_code or "").strip().upper()
	if not code:
		return (default_to_warehouse or "").strip()
	if code.startswith(("RM", "PM", "CO")):
		return "WO-STR"
	if code.startswith("FG"):
		return "WO-FG"
	return (default_to_warehouse or "").strip()


@frappe.whitelist()
def create(data):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create Shiphero Transfers"))

	if isinstance(data, str):
		data = json.loads(data)

	doc_date = data.get("doc_date") or frappe.utils.today()
	# Header warehouses must come from payload only (never from line items)
	from_warehouse = (data.get("from_warehouse") or "").strip()
	to_warehouse = (data.get("to_warehouse") or "").strip()
	if not from_warehouse:
		from_warehouse = SHIPHERO_IT_FROM_WAREHOUSE
	if not to_warehouse:
		to_warehouse = SHIPHERO_IT_TO_WAREHOUSE
	comments = (data.get("comments") or "").strip() or None
	if not comments:
		frappe.throw(_("Comments are required"))

	# Address required (USA format; not sent to SAP)
	addr1 = (data.get("address_line1") or "").strip()
	addr_city = (data.get("city") or "").strip()
	addr_state = (data.get("state") or "").strip()
	addr_zip = (data.get("zip_code") or "").strip()
	if not addr1:
		frappe.throw(_("Address Line 1 is required"))
	if not addr_city:
		frappe.throw(_("City is required"))
	if not addr_state:
		frappe.throw(_("State is required (e.g. CA)"))
	if not addr_zip:
		frappe.throw(_("ZIP Code is required"))

	items = data.get("items", [])
	_validate_items(items)
	_validate_items_batch(items)
	_validate_batch_available(items, from_warehouse)
	if items and (not from_warehouse or not to_warehouse):
		frappe.throw(_("From Warehouse and To Warehouse are required in the header."))

	doc = frappe.new_doc("WowPets Inventory Transfer")
	doc.status = "Draft"
	doc.doc_date = doc_date
	doc.from_warehouse = from_warehouse
	doc.to_warehouse = to_warehouse
	doc.inventory_transfer_name = (data.get("inventory_transfer_name") or "").strip()
	doc.comments = comments
	# Address (USA format, stored in Frappe only – not sent to SAP)
	doc.address_line1 = addr1 or None
	doc.address_line2 = (data.get("address_line2") or "").strip() or None
	doc.city = addr_city or None
	doc.state = addr_state or None
	doc.zip_code = addr_zip or None

	for row in items:
		item_code = (row.get("item_code") or "").strip()
		row_wh = (row.get("warehouse_code") or "").strip()
		if not row_wh:
			row_wh = _get_target_warehouse_for_item(item_code, to_warehouse)
		doc.append("items", {
			"item_code": item_code,
			"item_name": (row.get("item_name") or "").strip(),
			"quantity": float(row.get("quantity") or 0),
		"number_of_units_per_box": int(float(row.get("number_of_units_per_box") or 0)),
		"number_of_boxes": int(float(row.get("number_of_boxes") or 0)),
			"warehouse_code": row_wh,
			"batch_number": (row.get("batch_number") or "").strip() or None,
		})

	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update(name, data):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can update Shiphero Transfers"))

	if isinstance(data, str):
		data = json.loads(data)

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	can_resume = frappe.utils.cint(getattr(doc, "warehouse_awaiting_kf", 0))
	if doc.status not in ("Draft", "Error") and not can_resume:
		frappe.throw(
			_(
				"Only Draft or Error transfers can be updated. "
				"If status is Error, fix line items after the ticket is raised, Save, then warehouse retries Mark as Received or KhanalFoods retries Send to SAP."
			)
		)

	# When recovering from SAP failure, keep accepted qty/remarks on lines that still match (item + batch).
	old_accepted_by_batch = {}
	if doc.status == "Error":
		for r in doc.items:
			ic = (r.item_code or "").strip().lower()
			bn = (r.batch_number or "").strip().lower()
			if ic and bn:
				old_accepted_by_batch[(ic, bn)] = (r.accepted_qty, (r.acceptance_remarks or "").strip() or None)

	doc.doc_date = data.get("doc_date") or doc.doc_date
	# Header: only update from payload, never from line items
	payload_from = (data.get("from_warehouse") or "").strip()
	payload_to = (data.get("to_warehouse") or "").strip()
	doc.inventory_transfer_name = (data.get("inventory_transfer_name") or doc.inventory_transfer_name or "").strip()
	if payload_from:
		doc.from_warehouse = payload_from
	if payload_to:
		doc.to_warehouse = payload_to
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

	items_data = data.get("items", [])
	_validate_items(items_data)
	_validate_items_batch(items_data)
	_validate_batch_available(items_data, doc.from_warehouse)

	doc.items = []
	for row in items_data:
		item_code = (row.get("item_code") or "").strip()
		batch_key = (item_code.lower(), (row.get("batch_number") or "").strip().lower())
		acc_qty, acc_rem = (None, None)
		if old_accepted_by_batch and batch_key[1]:
			acc_qty, acc_rem = old_accepted_by_batch.get(batch_key, (None, None))
		row_wh = (row.get("warehouse_code") or "").strip()
		if not row_wh:
			row_wh = _get_target_warehouse_for_item(item_code, doc.to_warehouse)
		line = {
			"item_code": item_code,
			"item_name": (row.get("item_name") or "").strip(),
			"quantity": float(row.get("quantity") or 0),
			"number_of_units_per_box": int(float(row.get("number_of_units_per_box") or 0)),
			"number_of_boxes": int(float(row.get("number_of_boxes") or 0)),
			"warehouse_code": row_wh,
			"batch_number": (row.get("batch_number") or "").strip() or None,
		}
		if acc_qty is not None:
			line["accepted_qty"] = acc_qty
		if acc_rem:
			line["acceptance_remarks"] = acc_rem
		doc.append("items", line)
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
	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if doc.status not in ("Approved", "Accepted", "Sent to SAP", "Error"):
		frappe.throw(_("Assistance request is allowed only for active warehouse transfer statuses"))
	doc.warehouse_awaiting_kf = 1
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_release_warehouse_hold(name):
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods can release the warehouse hold"))
	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if frappe.utils.cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		doc.warehouse_awaiting_kf = 0
		doc.save()
		frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_update_for_warehouse_resume(name, data):
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods can apply this update"))
	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if not frappe.utils.cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(_("Warehouse has not requested KhanalFoods assistance for this transfer"))
	return update(name, data)


@frappe.whitelist()
def submit_for_approval(name):
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can submit Shiphero Transfers"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft transfers can be submitted for approval"))

	if not doc.items or len(doc.items) == 0:
		frappe.throw(_("Cannot submit transfer without items"))

	doc.status = "Pending Approval"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve(name):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can approve Shiphero Transfers"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval transfers can be approved"))

	# Re‑check batch availability against SAP at approval time so invalid transfers
	# are stopped before warehouse ever sees them.
	items_for_check = []
	for row in doc.items:
		items_for_check.append(
			{
				"item_code": (row.item_code or "").strip(),
				"batch_number": (row.batch_number or "").strip(),
				"quantity": float(row.quantity or 0),
			}
		)
	_validate_batch_available(items_for_check, doc.from_warehouse)

	doc.status = "Approved"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def reject(name, reason=""):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can reject Shiphero Transfers"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval transfers can be rejected"))

	doc.status = "Rejected"
	if reason:
		doc.comments = (doc.comments or "") + f"\nRejection reason: {reason}"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def revert_to_draft(name):
	"""Revert a rejected Shiphero Transfer back to Draft for editing."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can revert Shiphero Transfers to Draft"))
	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if doc.status != "Rejected":
		frappe.throw(_("Only Rejected transfers can be reverted to Draft"))
	doc.status = "Draft"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


def _sync_transfer_to_sap(doc):
	"""Post this inventory transfer to SAP (stock transfer). Updates doc in place; caller must save/commit."""
	from khanal_tech_integrations.api.wowpets.sap_master import create_stock_transfer_from_wowpets_inventory_transfer
	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

	result = create_stock_transfer_from_wowpets_inventory_transfer(doc)
	doc.sap_doc_entry = str(result.get("doc_entry", ""))
	doc.sap_doc_num = str(result.get("doc_num", ""))
	doc.sap_sync_error = None
	doc.status = "Sent to SAP"
	log_wowpets_sap(
		reference_doctype="WowPets Inventory Transfer",
		reference_name=doc.name,
		operation="Stock Transfer - Shiphero",
		status="Success",
		response_payload=result,
	)


_IT_USER_DELETABLE = {"Draft"}
_IT_MANAGER_DELETABLE = {"Draft", "Approved"}


@frappe.whitelist()
def delete_draft(name):
	"""Delete a WowPets Inventory Transfer. KhanalFoods team only.
	Regular user: own Draft records with no SAP data.
	Manager: Draft / Approved with no SAP data.
	"""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can delete transfers"), frappe.PermissionError)

	doc = frappe.get_doc("WowPets Inventory Transfer", name)

	if (doc.sap_request_doc_entry or "").strip() or (doc.sap_doc_entry or "").strip():
		frappe.throw(_("Cannot delete: this transfer has already been sent to SAP"), frappe.ValidationError)

	user = frappe.session.user
	if is_manager():
		if doc.status not in _IT_MANAGER_DELETABLE:
			frappe.throw(
				_("Cannot delete: transfer is in '{0}' status. Managers can only delete before warehouse accepts.").format(doc.status),
				frappe.ValidationError,
			)
	else:
		if doc.owner != user:
			frappe.throw(_("You can only delete transfers you created"), frappe.PermissionError)
		if doc.status not in _IT_USER_DELETABLE:
			frappe.throw(_("Only Draft transfers can be deleted"), frappe.ValidationError)

	from khanal_tech_integrations.api.wowpets.kf_attachments import _delete_all_doc_attachments
	_delete_all_doc_attachments("WowPets Inventory Transfer", name)
	frappe.delete_doc("WowPets Inventory Transfer", name, ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def update_accepted_quantities(name, items, remarks=None):
	"""Warehouse sets accepted quantity and optional remarks per line.

	Allowed when status is Approved (before Accept) or Accepted (after creating SAP request).
	"""
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can set accepted quantities"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status not in ("Approved", "Accepted"):
		frappe.throw(_("Only Approved or Accepted transfers can have accepted quantities updated"))

	if isinstance(items, str):
		items = json.loads(items)
	if not isinstance(items, (list, tuple)) or len(items) != len(doc.items):
		frappe.throw(_("Accepted quantities must be a list with one value per line item"))

	remarks_list = []
	if remarks is not None:
		if isinstance(remarks, str):
			remarks = json.loads(remarks)
		remarks_list = list(remarks) if isinstance(remarks, (list, tuple)) else []

	for i, row in enumerate(doc.items):
		val = items[i] if i < len(items) else None
		qty = float(val) if val is not None else 0
		if qty < 0:
			frappe.throw(_("Row {0}: Accepted quantity cannot be negative").format(i + 1))
		ordered = float(row.quantity or 0)
		if ordered > 0 and qty > ordered:
			frappe.throw(_("Row {0}: Accepted quantity ({1}) cannot exceed ordered quantity ({2})").format(i + 1, qty, ordered))
		row.accepted_qty = qty if qty > 0 else None
		if remarks is not None:
			rem = (remarks_list[i] if i < len(remarks_list) else None) or ""
			row.acceptance_remarks = (rem.strip() or None) if isinstance(rem, str) else None

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def accept(name, items=None, remarks=None):
	"""Warehouse accepts the transfer: optionally save accepted_qty/remarks per line, then set status to Accepted.

	On Accept we create an Inventory Transfer Request in SAP (using ordered quantity). The final Inventory Transfer
	with accepted quantity is posted only when warehouse clicks Mark as Received."""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can accept Shiphero Transfers"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Approved":
		frappe.throw(_("Only Approved transfers can be accepted"))

	# If items (accepted quantities) and optional remarks provided, save them before accepting
	if items is not None:
		if isinstance(items, str):
			items = json.loads(items)
		if isinstance(items, (list, tuple)) and len(items) == len(doc.items):
			remarks_list = []
			if remarks is not None:
				if isinstance(remarks, str):
					remarks = json.loads(remarks)
				remarks_list = list(remarks) if isinstance(remarks, (list, tuple)) else []
			for i, row in enumerate(doc.items):
				val = items[i] if i < len(items) else None
				qty = float(val) if val is not None else 0
				if qty < 0:
					frappe.throw(_("Row {0}: Accepted quantity cannot be negative").format(i + 1))
				ordered = float(row.quantity or 0)
				if ordered > 0 and qty > ordered:
					frappe.throw(_("Row {0}: Accepted quantity ({1}) cannot exceed ordered quantity ({2})").format(i + 1, qty, ordered))
				row.accepted_qty = qty if qty > 0 else None
				if remarks is not None:
					rem = (remarks_list[i] if i < len(remarks_list) else None) or ""
					row.acceptance_remarks = (rem.strip() or None) if isinstance(rem, str) else None

	doc.status = "Accepted"
	doc.accepted_by = frappe.session.user
	doc.accepted_date = frappe.utils.today()

	# Best-effort: create Inventory Transfer Request in SAP when warehouse accepts.
	# If this fails we log the error but keep the local status as Accepted; the final transfer
	# (with accepted_qty) is still posted when warehouse marks as Received.
	try:
		from khanal_tech_integrations.api.wowpets.sap_master import create_stock_transfer_request_from_wowpets_inventory_transfer
		from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

		result = create_stock_transfer_request_from_wowpets_inventory_transfer(doc)
		doc.sap_request_doc_entry = str(result.get("doc_entry", ""))
		doc.sap_request_doc_num = str(result.get("doc_num", ""))
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Inventory Transfer",
			reference_name=doc.name,
			operation="Stock Transfer - Shiphero",
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		# Do not block the Accept flow on SAP request creation; just log the failure.
		doc.sap_sync_error = str(e)
		from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

		log_wowpets_sap(
			reference_doctype="WowPets Inventory Transfer",
			reference_name=doc.name,
			operation="Stock Transfer - Shiphero",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets Shiphero Transfer SAP Request failed: {e}", "WowPets Shiphero Transfer SAP Request")

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def send_to_sap(name):
	"""Retry posting to SAP (used when status is Error or when auto-sync on accept did not run)."""
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can send Shiphero Transfers to SAP"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	if doc.status not in ("Accepted", "Error", "Received"):
		frappe.throw(_("Only Accepted, failed (Error), or Received transfers can be sent to SAP"))
	if (doc.sap_doc_entry or "").strip():
		frappe.throw(_("This transfer was already sent to SAP (Doc Entry: {0})").format((doc.sap_doc_entry or "").strip()))

	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

	try:
		_sync_transfer_to_sap(doc)
	except Exception as e:
		doc.sap_sync_error = str(e)
		doc.status = "Error"
		log_wowpets_sap(
			reference_doctype="WowPets Inventory Transfer",
			reference_name=doc.name,
			operation="Stock Transfer - Shiphero",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets Shiphero Transfer SAP failed: {e}", "WowPets Shiphero Transfer SAP")
		doc.save()
		frappe.db.commit()
		raise

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def retry_sap_request(name):
	"""Retry creating the SAP Inventory Transfer Request when the initial attempt on Accept failed."""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can retry the SAP transfer request"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Accepted":
		frappe.throw(_("Only Accepted transfers can have the SAP request retried"))
	if (doc.sap_request_doc_entry or "").strip():
		frappe.throw(_("SAP Transfer Request already exists (Doc Entry: {0})").format(doc.sap_request_doc_entry))

	from khanal_tech_integrations.api.wowpets.sap_master import create_stock_transfer_request_from_wowpets_inventory_transfer
	from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap

	try:
		result = create_stock_transfer_request_from_wowpets_inventory_transfer(doc)
		doc.sap_request_doc_entry = str(result.get("doc_entry", ""))
		doc.sap_request_doc_num = str(result.get("doc_num", ""))
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Inventory Transfer",
			reference_name=doc.name,
			operation="Stock Transfer - Shiphero",
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		raw_message = str(e)
		doc.sap_sync_error = raw_message
		log_wowpets_sap(
			reference_doctype="WowPets Inventory Transfer",
			reference_name=doc.name,
			operation="Stock Transfer - Shiphero",
			status="Failed",
			error_message=raw_message,
		)
		frappe.log_error(f"WowPets Shiphero Transfer SAP Request retry failed: {raw_message}", "WowPets Shiphero Transfer SAP Request")
		doc.save()
		frappe.db.commit()

		# Map known SAP errors to friendly, warehouse-facing messages.
		lower_msg = raw_message.lower()

		# Case: batch quantity already allocated in other SAP documents.
		if "quantity already allocated" in lower_msg:
			# Try to preserve item / batch from the original text without SAP wording.
			user_detail = ""
			if "For item" in raw_message:
				user_detail = raw_message.split("For item", 1)[1].strip()

			# Append the raw item/batch tail (if any) in parentheses.
			extra = f" ({user_detail})" if user_detail else ""
			frappe.throw(
				_(
					"This batch is already fully used in other transfers. "
					"Select a different batch or split the quantity across batches."
				) + extra
			)

		# Fallback: generic sync failure (no SAP jargon for warehouse).
		frappe.throw(
			_(
				"Transfer request could not be created due to a sync issue. "
				"Please review item batches and try again or contact KhanalFoods."
			)
		)

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def mark_received(name):
	"""Warehouse marks transfer as received. Posts the final Inventory Transfer to SAP with accepted quantity."""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can mark Shiphero Transfers as received"))

	doc = frappe.get_doc("WowPets Inventory Transfer", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status not in ("Accepted", "Sent to SAP", "Error"):
		frappe.throw(_("Only Accepted, Sent to SAP, or Error (after KhanalFoods fix) transfers can be marked as received"))

	if doc.status == "Error":
		if (doc.sap_doc_entry or "").strip():
			frappe.throw(_("This transfer is already posted to SAP. Refresh the page."))
		if not (doc.sap_request_doc_entry or "").strip():
			frappe.throw(
				_(
					"Cannot mark as received: SAP transfer request is missing. "
					"Ask KhanalFoods to fix the transfer or wait for the request to be created."
				)
			)

	# Block if the Inventory Transfer Request was never created in SAP
	if not (doc.sap_request_doc_entry or "").strip():
		frappe.throw(_(
			"Cannot mark as received: the SAP Inventory Transfer Request has not been created yet. "
			"Please use 'Retry SAP Request' first."
		))

	# Post the final Inventory Transfer to SAP with accepted quantity
	if not (doc.sap_doc_entry or "").strip():
		from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap
		try:
			_sync_transfer_to_sap(doc)
		except Exception as e:
			doc.sap_sync_error = str(e)
			doc.status = "Error"
			log_wowpets_sap(
				reference_doctype="WowPets Inventory Transfer",
				reference_name=doc.name,
				operation="Stock Transfer - Shiphero",
				status="Failed",
				error_message=str(e),
			)
			frappe.log_error(f"WowPets Shiphero Transfer SAP failed: {e}", "WowPets Shiphero Transfer SAP")
			doc.save()
			frappe.db.commit()
			frappe.throw(_("SAP post failed: {0}").format(str(e)))

	doc.status = "Received"
	doc.received_date = frappe.utils.today()
	doc.save()
	frappe.db.commit()
	return doc.as_dict()
