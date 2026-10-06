import frappe
from frappe import _

WOWPETS_ROLES = {
	"khanalfoods": ["WowPets KhanalFoods User", "WowPets KhanalFoods Manager"],
	"warehouse": ["WowPets Warehouse User", "WowPets Warehouse Manager"],
	"procurement": ["WowPets Procurement User", "WowPets Procurement Manager"],
}

MANAGER_ROLES = ["WowPets KhanalFoods Manager", "WowPets Warehouse Manager", "WowPets Procurement Manager"]


def get_user_wowpets_roles(user=None):
	user = user or frappe.session.user
	user_roles = frappe.get_roles(user)
	return [r for r in user_roles if r.startswith("WowPets")]


def get_user_team(user=None):
	roles = get_user_wowpets_roles(user)
	if not roles:
		return None

	has_khanalfoods = any("KhanalFoods" in r for r in roles)
	has_warehouse = any("Warehouse" in r for r in roles)
	has_procurement = any("Procurement" in r for r in roles)

	team_count = sum([has_khanalfoods, has_warehouse, has_procurement])
	if team_count > 1:
		frappe.log_error(
			f"User {user or frappe.session.user} has roles from multiple WowPets teams. "
			"Remove conflicting roles. Defaulting to highest-privilege team.",
			"WowPets Dual-Role User Detected",
		)
		if has_procurement:
			return "procurement"
		return "khanalfoods"

	if has_procurement:
		return "procurement"
	if has_khanalfoods:
		return "khanalfoods"
	if has_warehouse:
		return "warehouse"
	return None


def is_manager(user=None):
	roles = get_user_wowpets_roles(user)
	return any(r in MANAGER_ROLES for r in roles)


def check_wowpets_access():
	"""Raise PermissionError if the current user has no WowPets roles.
	Single canonical implementation — import this instead of redefining locally.
	"""
	roles = get_user_wowpets_roles()
	if not roles:
		frappe.throw(_("No WowPets access"), frappe.PermissionError)


@frappe.whitelist(allow_guest=True)
def verify_wowpets_access(user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return {"has_access": False}

	roles = get_user_wowpets_roles(user)
	if not roles:
		return {"has_access": False}

	team = get_user_team(user)
	return {
		"has_access": True,
		"user": user,
		"team": team,
		"roles": roles,
		"is_manager": is_manager(user),
		"full_name": frappe.db.get_value("User", user, "full_name"),
	}


@frappe.whitelist(allow_guest=True)
def get_wowpets_user_info():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Not logged in"), frappe.AuthenticationError)

	roles = get_user_wowpets_roles(user)
	if not roles:
		frappe.throw(_("No WowPets access"), frappe.PermissionError)

	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name"),
		"team": get_user_team(user),
		"roles": roles,
		"is_manager": is_manager(user),
	}
