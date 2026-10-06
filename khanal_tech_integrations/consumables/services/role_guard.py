import frappe
from frappe import _

ROLE_HIERARCHY = [
    "Consumables Super Admin",
    "Consumables Store Manager",
    "Consumables Inventory Manager",
    "Consumables Store User",
    "Consumables Procurement User",
]


def require_consumables_role(user=None):
    """Raise AuthenticationError/PermissionError if user has no consumables role."""
    user = user or frappe.session.user
    if user == "Guest":
        frappe.throw(_("Not logged in."), frappe.AuthenticationError)
    roles = frappe.get_roles(user)
    if not any(r in roles for r in ROLE_HIERARCHY):
        frappe.throw(_("You do not have access to StoreOps."), frappe.PermissionError)


def get_accessible_plants(user=None) -> list:
    """Return list of plant_codes the user can access.

    Super Admin, Inventory Manager, Procurement User → all active plants.
    Store Manager, Store User → only their assigned plants
    (Consumables User Plant records represent physical location).
    """
    user = user or frappe.session.user
    roles = frappe.get_roles(user)

    if any(r in roles for r in ("Consumables Super Admin", "Consumables Inventory Manager", "Consumables Procurement User")):
        return [
            r.plant_code
            for r in frappe.get_all("Consumables Plant", filters={"is_active": 1}, fields=["plant_code"])
        ]

    links = frappe.get_all(
        "Consumables User Plant",
        filters={"user": user, "is_active": 1},
        fields=["plant"],
    )
    return [r.plant for r in links]


def assert_plant_access(plant_code: str, user=None):
    """Raise PermissionError if user cannot access plant_code."""
    user = user or frappe.session.user
    accessible = get_accessible_plants(user)
    if plant_code not in accessible:
        frappe.throw(
            _("You do not have access to plant {0}.").format(plant_code),
            frappe.PermissionError,
        )


def require_super_admin(user=None):
    """Raise PermissionError if current user is not a Consumables Super Admin."""
    user = user or frappe.session.user
    require_consumables_role(user)
    roles = frappe.get_roles(user)
    if "Consumables Super Admin" not in roles:
        frappe.throw(
            _("Only a Super Admin can perform this action."),
            frappe.PermissionError,
        )


def require_manager_or_admin():
    """Raise PermissionError if current user is not a Store/Inventory Manager or Super Admin."""
    require_consumables_role()
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Store Manager", "Consumables Inventory Manager", "Consumables Super Admin")):
        frappe.throw(
            _("Only a Store Manager, Inventory Manager or Super Admin can perform this action."),
            frappe.PermissionError,
        )


def require_transfer_module_access(user=None):
    """Allow Store Managers, Inventory Managers, Procurement Users, Super Admin to create/view/submit transfers."""
    user = user or frappe.session.user
    require_consumables_role(user)
    roles = frappe.get_roles(user)
    
    if not any(r in roles for r in ("Consumables Store Manager", "Consumables Inventory Manager", "Consumables Procurement User", "Consumables Super Admin")):
        frappe.throw(
            _("You do not have access to inventory transfers."),
            frappe.PermissionError,
        )


def require_transfer_approval_access(user=None):
    """Approving/rejecting transfers requires BOTH Store Manager and Inventory Manager roles, or Super Admin."""
    user = user or frappe.session.user
    require_consumables_role(user)
    roles = frappe.get_roles(user)

    if "Consumables Super Admin" in roles:
        return

    has_store = "Consumables Store Manager" in roles
    has_inventory = "Consumables Inventory Manager" in roles
    if not (has_store and has_inventory):
        frappe.throw(
            _("Approving transfer requests requires both the Store Manager and Inventory Manager roles."),
            frappe.PermissionError,
        )


def require_transfer_approver():
    """Raise PermissionError if current user is not an Inventory Manager or Super Admin."""
    require_consumables_role()
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Inventory Manager", "Consumables Super Admin")):
        frappe.throw(
            _("Only an Inventory Manager or Super Admin can perform this action."),
            frappe.PermissionError,
        )
