import frappe
from frappe import _

ROLE_HIERARCHY = [
	"Consumables Super Admin",
	"Consumables Store Manager",
	"Consumables Inventory Manager",
	"Consumables Store User",
	"Consumables Procurement User",
]


@frappe.whitelist()
def get_current_user_context():
	"""
	Returns session context for StoreOps SPA.
	Called on every page load to hydrate the Vue auth store.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not logged in"), frappe.AuthenticationError)

	user_doc = frappe.get_doc("User", user)
	user_roles = frappe.get_roles(user)

	# All consumables roles the user has (order matches hierarchy). Used by the SPA
	# for capability checks — a user may hold both Store Manager and Inventory Manager;
	# the single `role` field below still picks one for display only.
	consumables_roles = [r for r in ROLE_HIERARCHY if r in user_roles]

	# Highest consumables role wins (display / default context)
	role = consumables_roles[0] if consumables_roles else None

	is_super_admin = "Consumables Super Admin" in user_roles
	is_procurement_user = "Consumables Procurement User" in user_roles

	is_inventory_manager = "Consumables Inventory Manager" in user_roles

	# physical_records: user's own assigned plants (Consumables User Plant) — used for
	# receive-button gating and plant selectors when creating CMRs/CTRs.
	if is_super_admin or is_procurement_user:
		physical_records = frappe.get_all(
			"Consumables Plant",
			filters={"is_active": 1},
			fields=["plant_code", "plant_name"],
		)
	else:
		user_plant_links = frappe.get_all(
			"Consumables User Plant",
			filters={"user": user, "is_active": 1},
			fields=["plant"],
		)
		plant_names = [r.plant for r in user_plant_links]
		physical_records = frappe.get_all(
			"Consumables Plant",
			filters={"name": ["in", plant_names], "is_active": 1},
			fields=["plant_code", "plant_name"],
		) if plant_names else []

	# source_records: plants visible for fulfillment stock lookup — all plants for
	# Inventory Managers and Super Admins so they see the full stock picture.
	if is_super_admin or is_inventory_manager:
		source_records = frappe.get_all(
			"Consumables Plant",
			filters={"is_active": 1},
			fields=["plant_code", "plant_name"],
		)
	else:
		source_records = physical_records

	def _enrich(records):
		result = []
		for p in records:
			try:
				if not (p.plant_code or "").strip():
					continue
				plant_doc = frappe.get_doc("Consumables Plant", p.plant_code)
				warehouses = [
					{
						"warehouse_code": w.warehouse_code,
						"warehouse_name": w.warehouse_name,
						"warehouse_type": w.warehouse_type,
						"is_active": w.is_active,
					}
					for w in plant_doc.warehouses
					if w.is_active
				]
			except Exception:
				warehouses = []
			result.append({
				"plant_code": p.plant_code,
				"plant_name": p.plant_name,
				"warehouses": warehouses,
			})
		return result

	plants = _enrich(physical_records)
	source_plants = _enrich(source_records)

	return {
		"user": user,
		"full_name": user_doc.full_name or user_doc.first_name or user,
		"role": role,
		"consumables_roles": consumables_roles,
		"is_super_admin": is_super_admin,
		"is_procurement_user": is_procurement_user,
		"plants": plants,
		"source_plants": source_plants,
	}
