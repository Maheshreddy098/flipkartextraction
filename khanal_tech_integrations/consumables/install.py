import frappe

ROLE_NAME = "Consumables Inventory Manager"


def ensure_consumables_inventory_manager_role():
    if frappe.db.exists("Role", ROLE_NAME):
        return

    role = frappe.new_doc("Role")
    role.role_name = ROLE_NAME
    role.desk_access = 1
    role.insert(ignore_permissions=True)
    frappe.db.commit()
