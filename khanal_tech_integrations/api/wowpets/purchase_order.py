import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, today
from khanal_tech_integrations.api.wowpets.auth import (
	check_wowpets_access,
	get_user_team,
	is_manager,
	get_user_wowpets_roles,
)
from khanal_tech_integrations.api.wowpets import WOWPETS_WAREHOUSE, PO_WAREHOUSE, SHIPHERO_VENDOR_CODE
from khanal_tech_integrations.api.wowpets.inventory import increase_inventory
from khanal_tech_integrations.api.wowpets.sap_master import (
	create_po_and_grpo_from_wowpets,
	create_inventory_transfer_from_wowpets,
	create_grpo_for_wowpets_po,
)
from khanal_tech_integrations.api.wowpets.sap_log import log_wowpets_sap


_check_wowpets_access = check_wowpets_access


def _throw_if_warehouse_awaiting_kf(doc):
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(
			_(
				"This purchase order is on hold until Procurement team saves an update after your support ticket."
			)
		)


def _validate_po_header(data, for_submit=False):
	"""Validate header fields; for_submit=True requires vendor and vendor_ref_no."""
	if for_submit:
		if not (data.get("vendor_code") or data.get("supplier_name")):
			frappe.throw(_("Vendor is required"))
		if not (data.get("vendor_ref_no") or "").strip():
			frappe.throw(_("Vendor Reference No is required"))
	if not data.get("posting_date"):
		frappe.throw(_("Posting Date is required"))


def _validate_po_header_for_submit(doc):
	"""Validate doc before submit for approval."""
	if not (doc.vendor_code or doc.supplier_name):
		frappe.throw(_("Vendor is required"))
	if not (doc.vendor_ref_no or "").strip():
		frappe.throw(_("Vendor Reference No is required"))
	if not doc.posting_date:
		frappe.throw(_("Posting Date is required"))
	if not (doc.remarks or "").strip():
		frappe.throw(_("Remarks are required"))


WOWPETS_PO_TAX_CODE = "PA0"


def _validate_po_items(items):
	"""Validate each line has item_code, qty, unit_price/rate, and batch. Tax code is fixed as PA0. Units/box and number of boxes are optional."""
	if not items:
		frappe.throw(_("At least one item is required"))
	for i, row in enumerate(items):
		if not (row.get("item_code") or "").strip():
			frappe.throw(_("Row {0}: Item Code is required").format(i + 1))
		if row.get("rate") is None and row.get("unit_price") is None:
			frappe.throw(_("Row {0}: Unit Price is required").format(i + 1))
		qty = flt(row.get("qty") or 0)
		if qty <= 0:
			frappe.throw(_("Row {0}: Quantity must be greater than 0").format(i + 1))
		if not (row.get("batch_number") or "").strip():
			frappe.throw(_("Row {0}: Batch Number is required").format(i + 1))


@frappe.whitelist()
def get_list(status=None, page=1, page_size=20):
	_check_wowpets_access()

	filters = {}
	team = get_user_team()

	if team == "warehouse":
		allowed = ["Approved", "Accepted", "Received"]
		filters["status"] = status if (status and status in allowed) else ["in", allowed]
	elif status:
		filters["status"] = status

	orders = frappe.get_list(
		"WowPets Purchase Order",
		filters=filters,
		fields=[
			"name", "status", "purchase_order_name", "vendor_code", "vendor_name", "supplier_name", "posting_date", "vendor_ref_no",
			"total_qty", "total_amount", "created_by_user", "remarks",
			"approved_by", "accepted_by", "warehouse_awaiting_kf", "modified",
			"sap_sync_status",
			"sap_po_doc_entry", "sap_po_doc_num",
			"sap_grpo_doc_entry", "sap_grpo_doc_num",
			"sap_inventory_transfer_doc_entry",
		],
		order_by="modified desc",
		start=((int(page) - 1) * int(page_size)),
		page_length=int(page_size),
	)

	# Add total_accepted_qty from child table for list display (when PO submitted to SAP / accepted)
	if orders:
		names = [o["name"] for o in orders]
		rows = frappe.get_all(
			"WowPets Purchase Order Item",
			filters={"parent": ["in", names]},
			fields=["parent", "accepted_qty"],
		)
		from collections import defaultdict
		sums = defaultdict(lambda: 0)
		for r in rows:
			sums[r["parent"]] += (cint(r.get("accepted_qty")) or 0)
		for o in orders:
			o["total_accepted_qty"] = sums.get(o["name"])
		# Show 0 for Accepted/Received when order has no item rows (sums missing)
		for o in orders:
			if o.get("total_accepted_qty") is None and o.get("status") in ("Accepted", "Received"):
				o["total_accepted_qty"] = 0
	total = frappe.db.count("WowPets Purchase Order", filters=filters)
	return {"data": orders, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_wowpets_access()
	doc = frappe.get_doc("WowPets Purchase Order", name)
	return doc.as_dict()


@frappe.whitelist()
def create(data):
	_check_wowpets_access()

	if get_user_team() != "procurement":
		frappe.throw(_("Only Procurement team can create Purchase Orders"))

	if isinstance(data, str):
		import json
		data = json.loads(data)

	_validate_po_header(data, for_submit=True)
	if not (data.get("remarks") or "").strip():
		frappe.throw(_("Remarks are required"))
	_validate_po_items(data.get("items", []))

	doc = frappe.new_doc("WowPets Purchase Order")
	doc.status = "Draft"
	doc.purchase_order_name = (data.get("purchase_order_name") or "").strip()
	doc.vendor_code = data.get("vendor_code", "")
	doc.vendor_name = data.get("vendor_name", "")
	doc.supplier_name = data.get("supplier_name", data.get("vendor_name", ""))
	doc.posting_date = data.get("posting_date") or frappe.utils.today()
	doc.vendor_ref_no = data.get("vendor_ref_no", "")
	doc.remarks = data.get("remarks", "")

	for item in data.get("items", []):
		doc.append("items", {
			"item_code": item.get("item_code"),
			"item_name": item.get("item_name"),
			"qty": item.get("qty", 0),
			"uom": item.get("uom", ""),
			"number_of_units_per_box": cint(item.get("number_of_units_per_box") or 0),
			"number_of_boxes": cint(item.get("number_of_boxes") or 0),
			"weight_pcs": flt(item.get("weight_pcs") or 0),
			"pcs": flt(item.get("pcs") or 0),
			"rate": item.get("rate", item.get("unit_price", 0)),
			"tax_code": WOWPETS_PO_TAX_CODE,
			"warehouse": item.get("warehouse") or PO_WAREHOUSE,
			"batch_number": (item.get("batch_number") or "").strip() or None,
		})

	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update(name, data):
	_check_wowpets_access()
	if get_user_team() != "procurement":
		frappe.throw(_("Only Procurement team can edit Purchase Orders"))

	if isinstance(data, str):
		import json
		data = json.loads(data)

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)

	can_resume = cint(getattr(doc, "warehouse_awaiting_kf", 0))
	# Procurement managers can also edit POs that are Pending Approval
	editable_in_pending = is_manager() and doc.status == "Pending Approval"
	if doc.status != "Draft" and not can_resume and not editable_in_pending:
		frappe.throw(_("Can only edit Purchase Orders in Draft or Pending Approval status"))

	_validate_po_header(data, for_submit=False)
	if "items" in data:
		_validate_po_items(data["items"])
		doc.items = []
		for item in data["items"]:
			doc.append("items", {
				"item_code": item.get("item_code"),
				"item_name": item.get("item_name"),
				"qty": item.get("qty", 0),
				"uom": item.get("uom", ""),
				"number_of_units_per_box": cint(item.get("number_of_units_per_box") or 0),
				"number_of_boxes": cint(item.get("number_of_boxes") or 0),
				"weight_pcs": flt(item.get("weight_pcs") or 0),
				"pcs": flt(item.get("pcs") or 0),
				"rate": item.get("rate", item.get("unit_price", 0)),
				"tax_code": WOWPETS_PO_TAX_CODE,
				"warehouse": item.get("warehouse") or PO_WAREHOUSE,
				"batch_number": (item.get("batch_number") or "").strip() or None,
			})

	doc.purchase_order_name = (data.get("purchase_order_name") or doc.purchase_order_name or "").strip()
	doc.vendor_code = data.get("vendor_code", doc.vendor_code)
	doc.vendor_name = data.get("vendor_name", doc.vendor_name)
	doc.supplier_name = data.get("supplier_name", doc.supplier_name)
	doc.posting_date = data.get("posting_date", doc.posting_date)
	doc.vendor_ref_no = data.get("vendor_ref_no", doc.vendor_ref_no)
	doc.remarks = data.get("remarks", doc.remarks)
	if not (doc.remarks or "").strip():
		frappe.throw(_("Remarks are required"))

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
	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status not in ("Approved", "Accepted", "Received"):
		frappe.throw(_("Assistance request is allowed only for Approved, Accepted, or Received purchase orders"))
	doc.warehouse_awaiting_kf = 1
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_release_warehouse_hold(name):
	_check_wowpets_access()
	if get_user_team() not in ("khanalfoods", "procurement"):
		frappe.throw(_("Only KhanalFoods or Procurement team can release the warehouse hold"))
	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		doc.warehouse_awaiting_kf = 0
		doc.save()
		frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def kf_update_for_warehouse_resume(name, data):
	_check_wowpets_access()
	if get_user_team() != "procurement":
		frappe.throw(_("Only Procurement team can apply this update"))
	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if not cint(getattr(doc, "warehouse_awaiting_kf", 0)):
		frappe.throw(_("Warehouse has not requested KhanalFoods assistance for this purchase order"))
	return update(name, data)


@frappe.whitelist()
def submit_for_approval(name):
	_check_wowpets_access()
	if get_user_team() != "procurement":
		frappe.throw(_("Only Procurement team can submit Purchase Orders for approval"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft orders can be submitted for approval"))

	if not doc.items:
		frappe.throw(_("Cannot submit PO without items"))

	_validate_po_header_for_submit(doc)

	doc.status = "Pending Approval"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve(name):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "procurement":
		frappe.throw(_("Only Procurement Managers can approve Purchase Orders"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval orders can be approved"))

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.save()
	frappe.db.commit()

	# SAP PO is created at approval time (not at warehouse accept)
	try:
		_sync_po_to_sap(doc)
		doc.save()
		frappe.db.commit()
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		doc.save()
		frappe.db.commit()
		raise

	return doc.as_dict()


@frappe.whitelist()
def reject(name, reason=""):
	_check_wowpets_access()

	if not is_manager() or get_user_team() != "procurement":
		frappe.throw(_("Only Procurement Managers can reject Purchase Orders"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only Pending Approval orders can be rejected"))

	doc.status = "Rejected"
	if reason:
		doc.remarks = (doc.remarks or "") + f"\nRejection reason: {reason}"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def accept(name):
	"""WowPets warehouse team accepts an approved PO. SAP PO was already created at approval."""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can accept Purchase Orders"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Approved":
		frappe.throw(_("Only Approved orders can be accepted"))
	if not getattr(doc, "sap_po_doc_entry", None) and getattr(doc, "sap_sync_status", None) == "Error":
		frappe.throw(_("SAP PO sync failed at approval. Use 'Retry SAP Sync' before accepting."))

	doc.status = "Accepted"
	doc.accepted_by = frappe.session.user
	doc.save()
	frappe.db.commit()

	return doc.as_dict()


def _sync_po_to_sap(doc):
	"""Create SAP PO or Inventory Transfer when PO is received. Idempotent."""
	if getattr(doc, "sap_po_doc_entry", None) or getattr(doc, "sap_grpo_doc_entry", None):
		return
	if getattr(doc, "sap_inventory_transfer_doc_entry", None):
		return

	vendor_code = (doc.vendor_code or doc.supplier_name or "").strip()
	is_shiphero = vendor_code.upper() == SHIPHERO_VENDOR_CODE.upper()

	operation = "Stock Transfer - Shiphero" if is_shiphero else "PO Create"
	try:
		if is_shiphero:
			result = create_inventory_transfer_from_wowpets(doc)
			doc.sap_inventory_transfer_doc_entry = result.get("doc_entry")
			doc.sap_sync_status = "Inventory Transfer Created"
			doc.sap_sync_error = None
		else:
			result = create_po_and_grpo_from_wowpets(doc)
			doc.sap_po_doc_entry = result.get("po_doc_entry")
			doc.sap_po_doc_num = result.get("po_doc_num")
			# GRPO is now created manually in SAP; we only track the PO here unless user posts GRN from WowPets.
			doc.sap_grpo_doc_entry = None
			doc.sap_grpo_doc_num = None
			doc.sap_sync_status = "PO Created"
			doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Purchase Order",
			reference_name=doc.name,
			operation=operation,
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		log_wowpets_sap(
			reference_doctype="WowPets Purchase Order",
			reference_name=doc.name,
			operation=operation,
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets SAP sync failed: {e}", "WowPets SAP Sync")
		raise


def _sync_grn_to_sap(doc):
	"""Create SAP GRN (GRPO) for a PO that already has sap_po_doc_entry. Idempotent. No-op for Shiphero."""
	if getattr(doc, "sap_grpo_doc_entry", None):
		return
	vendor_code = (doc.vendor_code or doc.supplier_name or "").strip()
	if vendor_code.upper() == SHIPHERO_VENDOR_CODE.upper():
		return
	if not getattr(doc, "sap_po_doc_entry", None):
		return

	if getattr(doc, "sap_sync_status", None) == "Error":
		doc.sap_sync_error = None
		doc.sap_sync_status = None

	try:
		result = create_grpo_for_wowpets_po(doc)
		doc.sap_grpo_doc_entry = result.get("doc_entry")
		doc.sap_grpo_doc_num = result.get("doc_num")
		doc.sap_sync_status = "PO + GRN Created"
		doc.sap_sync_error = None
		log_wowpets_sap(
			reference_doctype="WowPets Purchase Order",
			reference_name=doc.name,
			operation="GRN Create",
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		log_wowpets_sap(
			reference_doctype="WowPets Purchase Order",
			reference_name=doc.name,
			operation="GRN Create",
			status="Failed",
			error_message=str(e),
		)
		frappe.log_error(f"WowPets SAP GRN failed: {e}", "WowPets SAP GRN")
		raise


def _received_qty(item):
	"""Quantity to use for receive/GRN: accepted_qty if set and > 0, else ordered qty."""
	accepted = flt(getattr(item, "accepted_qty", None) or 0)
	if accepted > 0:
		return accepted
	return flt(item.qty or 0)


@frappe.whitelist()
def update_accepted_quantities(name, items, remarks=None):
	"""Warehouse sets accepted quantity and optional remarks per line (by index). Only when status is Accepted."""
	_check_wowpets_access()
	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can set accepted quantities"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Accepted":
		frappe.throw(_("Only Accepted orders can have accepted quantities updated"))

	if isinstance(items, str):
		import json
		items = json.loads(items)
	if not isinstance(items, (list, tuple)) or len(items) != len(doc.items):
		frappe.throw(_("Accepted quantities must be a list with one value per line item"))

	remarks_list = []
	if remarks is not None:
		if isinstance(remarks, str):
			import json
			remarks = json.loads(remarks)
		remarks_list = list(remarks) if isinstance(remarks, (list, tuple)) else []

	for i, row in enumerate(doc.items):
		val = items[i] if i < len(items) else None
		qty = flt(val)
		if qty < 0:
			frappe.throw(_("Row {0}: Accepted quantity cannot be negative").format(i + 1))
		ordered = flt(row.qty or 0)
		if ordered > 0 and qty > ordered:
			frappe.throw(_("Row {0}: Accepted quantity ({1}) cannot exceed ordered quantity ({2})").format(i + 1, qty, ordered))
		# Store as integer so GRPO and batch quantities stay whole numbers
		row.accepted_qty = cint(round(qty)) if qty > 0 else None
		if remarks is not None:
			rem = (remarks_list[i] if i < len(remarks_list) else None) or ""
			row.acceptance_remarks = (rem.strip() or None) if isinstance(rem, str) else None

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def receive(name):
	"""Mark PO as received and update inventory. SAP GRN must be posted manually by KhanalFoods team."""
	_check_wowpets_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can receive Purchase Orders"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	_throw_if_warehouse_awaiting_kf(doc)
	if doc.status != "Accepted":
		frappe.throw(_("Only Accepted orders can be received"))

	for item in doc.items:
		qty = _received_qty(item)
		if qty <= 0:
			continue
		increase_inventory(
			item_code=item.item_code,
			item_name=item.item_name,
			qty=qty,
			warehouse=WOWPETS_WAREHOUSE,
		)

	doc.status = "Received"
	doc.received_date = frappe.utils.today()
	doc.save()

	try:
		_sync_po_to_sap(doc)
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		doc.save()
		frappe.db.commit()
		raise

	doc.save()
	frappe.db.commit()

	return doc.as_dict()


@frappe.whitelist()
def retry_sap_sync(name):
	"""Retry sending PO to SAP. GRN for Received POs must be posted manually via create_grn. Idempotent."""
	_check_wowpets_access()

	if get_user_team() not in ("warehouse", "khanalfoods", "procurement"):
		frappe.throw(_("Only Warehouse, KhanalFoods, or Procurement team can sync to SAP"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status not in ("Approved", "Accepted", "Received"):
		frappe.throw(_("Only Approved, Accepted, or Received orders can retry SAP sync"))

	# Already has a SAP PO (or Shiphero transfer) — nothing to retry here
	if getattr(doc, "sap_po_doc_entry", None) or getattr(doc, "sap_inventory_transfer_doc_entry", None):
		return doc.as_dict()

	# Clear previous error state and retry PO sync only
	doc.sap_sync_error = None
	doc.sap_sync_status = None
	doc.save()

	try:
		_sync_po_to_sap(doc)
		doc.save()
		frappe.db.commit()
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		doc.save()
		frappe.db.commit()
		raise

	return doc.as_dict()


@frappe.whitelist()
def create_grn(name):
	"""Create SAP GRN (GRPO) for a Received PO that already has a SAP PO DocEntry."""
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can post GRNs to SAP"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Received":
		frappe.throw(_("Only Received orders can be posted as GRN"))

	if not getattr(doc, "sap_po_doc_entry", None):
		frappe.throw(_("SAP PO DocEntry is missing. Send the PO to SAP before creating GRN."))

	# Idempotent: if GRPO already exists, just return the doc
	if getattr(doc, "sap_grpo_doc_entry", None):
		return doc.as_dict()

	# Retry: clear previous error state so we can call SAP again
	if getattr(doc, "sap_sync_status", None) == "Error":
		doc.sap_sync_error = None
		doc.sap_sync_status = None

	try:
		result = create_grpo_for_wowpets_po(doc)
		doc.sap_grpo_doc_entry = result.get("doc_entry")
		doc.sap_grpo_doc_num = result.get("doc_num")
		doc.sap_sync_status = "PO + GRN Created"
		doc.sap_sync_error = None
		doc.save()
		frappe.db.commit()
		log_wowpets_sap(
			reference_doctype="WowPets Purchase Order",
			reference_name=doc.name,
			operation="GRN Create",
			status="Success",
			response_payload=result,
		)
	except Exception as e:
		doc.sap_sync_status = "Error"
		doc.sap_sync_error = str(e)
		doc.save()
		frappe.db.commit()
		log_wowpets_sap(
			reference_doctype="WowPets Purchase Order",
			reference_name=doc.name,
			operation="GRN Create",
			status="Failed",
			error_message=str(e),
		)
		raise

	return doc.as_dict()


@frappe.whitelist()
def retry_grn(name):
	"""Retry creating SAP GRN for a Received PO after a previous failure. Same permissions as create_grn."""
	return create_grn(name)


@frappe.whitelist()
def revert_grn(name):
	"""Clear a posted GRN reference so create_grn/retry_grn can post a fresh one.

	Caller must have already cancelled the GRPO in SAP B1 directly — this only
	clears the WowPets-side reference, it does not call SAP. The linked PO
	(sap_po_doc_entry) is left untouched.
	"""
	_check_wowpets_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can revert GRNs"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Received":
		frappe.throw(_("Only Received orders can have their GRN reverted"))

	if not getattr(doc, "sap_grpo_doc_entry", None):
		frappe.throw(_("No GRN is posted for this order. Nothing to revert."))

	reverted_grpo_entry = doc.sap_grpo_doc_entry
	reverted_grpo_num = doc.sap_grpo_doc_num

	doc.sap_grpo_doc_entry = None
	doc.sap_grpo_doc_num = None
	doc.sap_sync_status = "PO Created" if getattr(doc, "sap_po_doc_entry", None) else None
	doc.sap_sync_error = None
	doc.save()
	frappe.db.commit()

	log_wowpets_sap(
		reference_doctype="WowPets Purchase Order",
		reference_name=doc.name,
		operation="GRN Revert",
		status="Success",
		response_payload={"reverted_grpo_doc_entry": reverted_grpo_entry, "reverted_grpo_doc_num": reverted_grpo_num},
	)

	return doc.as_dict()


@frappe.whitelist()
def kf_update_grn_details(name, data):
	"""KhanalFoods: update GRN-relevant fields on a Received PO before posting GRN to SAP."""
	_check_wowpets_access()
	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can update GRN details"))

	if isinstance(data, str):
		import json
		data = json.loads(data)

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Received":
		frappe.throw(_("GRN details can only be updated on Received orders"))
	if getattr(doc, "sap_grpo_doc_entry", None):
		frappe.throw(_("GRN already posted to SAP. Cannot modify."))
	vendor_code = (doc.vendor_code or doc.supplier_name or "").strip()
	if vendor_code.upper() == SHIPHERO_VENDOR_CODE.upper():
		frappe.throw(_("Shiphero inventory transfers do not use GRN. No action required."))

	if "vendor_ref_no" in data:
		doc.vendor_ref_no = (data["vendor_ref_no"] or "").strip() or doc.vendor_ref_no
	if "remarks" in data:
		doc.remarks = (data["remarks"] or "").strip() or doc.remarks
	if "received_date" in data:
		raw_date = data["received_date"]
		if not raw_date:
			frappe.throw(_("GRN date is required"))
		grn_date = getdate(raw_date)
		if grn_date > getdate(today()):
			frappe.throw(_("GRN date cannot be in the future"))
		doc.received_date = grn_date

	items = data.get("items") or []
	if items:
		if len(items) != len(doc.items):
			frappe.throw(_("Items count mismatch"))
		for i, row in enumerate(doc.items):
			item_data = items[i] if i < len(items) else {}
			if "accepted_qty" in item_data:
				qty = flt(item_data["accepted_qty"])
				if qty < 0:
					frappe.throw(_("Row {0}: Accepted quantity cannot be negative").format(i + 1))
				ordered = flt(row.qty or 0)
				if ordered > 0 and qty > ordered:
					frappe.throw(_("Row {0}: Accepted quantity ({1}) cannot exceed ordered quantity ({2})").format(i + 1, qty, ordered))
				row.accepted_qty = cint(round(qty)) if qty > 0 else None
			if "batch_number" in item_data:
				row.batch_number = (item_data["batch_number"] or "").strip() or None
			if "acceptance_remarks" in item_data:
				row.acceptance_remarks = (item_data["acceptance_remarks"] or "").strip() or None

	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def revert_to_draft(name):
	"""Revert a rejected PO back to Draft for editing"""
	_check_wowpets_access()
	if get_user_team() != "procurement":
		frappe.throw(_("Only Procurement team can revert Purchase Orders to Draft"))

	doc = frappe.get_doc("WowPets Purchase Order", name, for_update=True)
	if doc.status != "Rejected":
		frappe.throw(_("Only Rejected orders can be reverted to Draft"))

	doc.status = "Draft"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


_PO_USER_DELETABLE = {"Draft"}
_PO_MANAGER_DELETABLE = {"Draft", "Pending Approval", "Approved", "Rejected"}


@frappe.whitelist()
def delete_draft(name):
	"""Delete a WowPets Purchase Order. Procurement team only.
	Regular user: own Draft records with no SAP data.
	Manager: Draft / Pending Approval / Approved / Rejected with no SAP data.
	"""
	_check_wowpets_access()
	if get_user_team() != "procurement":
		frappe.throw(_("Only Procurement team can delete purchase orders"), frappe.PermissionError)

	doc = frappe.get_doc("WowPets Purchase Order", name)

	if (
		getattr(doc, "sap_po_doc_entry", None)
		or getattr(doc, "sap_grpo_doc_entry", None)
		or getattr(doc, "sap_inventory_transfer_doc_entry", None)
	):
		frappe.throw(_("Cannot delete: this purchase order has already been sent to SAP"), frappe.ValidationError)

	user = frappe.session.user
	if is_manager():
		if doc.status not in _PO_MANAGER_DELETABLE:
			frappe.throw(
				_("Cannot delete: purchase order is in '{0}' status. Managers can only delete orders the warehouse has not yet accepted.").format(doc.status),
				frappe.ValidationError,
			)
	else:
		if doc.owner != user:
			frappe.throw(_("You can only delete purchase orders you created"), frappe.PermissionError)
		if doc.status not in _PO_USER_DELETABLE:
			frappe.throw(_("Only Draft purchase orders can be deleted"), frappe.ValidationError)

	from khanal_tech_integrations.api.wowpets.kf_attachments import _delete_all_doc_attachments
	_delete_all_doc_attachments("WowPets Purchase Order", name)
	frappe.delete_doc("WowPets Purchase Order", name, ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}
