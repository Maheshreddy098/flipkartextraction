import frappe
from frappe import _
from khanal_tech_integrations.api.real_aquatics.auth import (
	check_real_aquatics_access,
	get_user_team,
	is_manager,
	get_user_real_aquatics_roles,
)
from khanal_tech_integrations.api.real_aquatics.inventory import increase_inventory


_check_real_aquatics_access = check_real_aquatics_access


@frappe.whitelist()
def get_list(status=None, return_type=None, page=1, page_size=20):
	_check_real_aquatics_access()

	filters = {}
	if status:
		filters["status"] = status
	if return_type:
		filters["return_type"] = return_type

	returns = frappe.get_list(
		"Real Aquatics Return",
		filters=filters,
		fields=[
			"name", "status", "return_type", "posting_date",
			"reference_doctype", "reference_name",
			"created_by_user", "modified",
		],
		order_by="modified desc",
		start=((int(page) - 1) * int(page_size)),
		page_length=int(page_size),
	)

	total = frappe.db.count("Real Aquatics Return", filters=filters)
	return {"data": returns, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_real_aquatics_access()
	doc = frappe.get_doc("Real Aquatics Return", name)
	return doc.as_dict()


@frappe.whitelist()
def create(data):
	_check_real_aquatics_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can create returns"))

	if isinstance(data, str):
		import json
		data = json.loads(data)

	if not data.get("return_type"):
		frappe.throw(_("Return Type is required"))

	items = data.get("items", [])
	if not items:
		frappe.throw(_("At least one item is required"))
	for i, item in enumerate(items):
		if not (item.get("item_code") or "").strip():
			frappe.throw(_("Row {0}: Item Code is required").format(i + 1))
		from frappe.utils import flt
		if flt(item.get("qty") or 0) <= 0:
			frappe.throw(_("Row {0}: Quantity must be greater than 0").format(i + 1))

	doc = frappe.new_doc("Real Aquatics Return")
	doc.status = "Draft"
	doc.return_type = data.get("return_type")
	doc.posting_date = data.get("posting_date") or frappe.utils.today()
	doc.reference_doctype = data.get("reference_doctype", "")
	doc.reference_name = data.get("reference_name", "")
	doc.remarks = data.get("remarks", "")

	for item in items:
		doc.append("items", {
			"item_code": item.get("item_code"),
			"item_name": item.get("item_name"),
			"qty": item.get("qty", 0),
			"uom": item.get("uom", ""),
			"reason": item.get("reason", ""),
		})

	doc.created_by_user = frappe.session.user
	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def submit_return(name):
	_check_real_aquatics_access()

	if get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can submit returns"))

	doc = frappe.get_doc("Real Aquatics Return", name, for_update=True)
	if doc.status != "Draft":
		frappe.throw(_("Only Draft returns can be submitted"))

	doc.status = "Pending"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def approve_return(name):
	_check_real_aquatics_access()

	if not is_manager() or get_user_team() != "khanalfoods":
		frappe.throw(_("Only KhanalFoods Managers can approve returns"))

	doc = frappe.get_doc("Real Aquatics Return", name, for_update=True)
	if doc.status != "Pending":
		frappe.throw(_("Only Pending returns can be approved"))

	doc.status = "Approved"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def process_return(name):
	"""Process an approved return - adjusts inventory"""
	_check_real_aquatics_access()

	if get_user_team() != "warehouse":
		frappe.throw(_("Only Warehouse team can process returns"))

	doc = frappe.get_doc("Real Aquatics Return", name, for_update=True)
	if doc.status != "Approved":
		frappe.throw(_("Only Approved returns can be processed"))

	for item in doc.items:
		increase_inventory(item.item_code, item.item_name, item.qty)

	doc.status = "Processed"
	doc.save()
	frappe.db.commit()
	return doc.as_dict()
