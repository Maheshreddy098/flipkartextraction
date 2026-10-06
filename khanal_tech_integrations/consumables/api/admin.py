import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from khanal_tech_integrations.consumables.services.role_guard import require_consumables_role

CONSUMABLES_ROLES = [
    "Consumables Store User",
    "Consumables Store Manager",
    "Consumables Procurement User",
    "Consumables Super Admin",
]


def _require_admin():
    require_consumables_role()
    if "Consumables Super Admin" not in frappe.get_roles():
        frappe.throw(_("Only Super Admin can perform this action."), frappe.PermissionError)


# ── SAP Settings ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def initiate_consumables_sap_session():
    """Manually trigger a SAP B1 Service Layer login using Consumables SAP
    Settings, from that doctype's "Initiate Session" button. Isolated from
    the shared utils.sap.renew_sap_session() (used by ~76 other files against
    the shared "SAP Settings") — consumables' own SAPClient usage never goes
    through that shared helper, so this doesn't touch it either."""
    _require_admin()
    from khanal_tech_integrations.unicommerce.client.sap import SAPClient

    try:
        SAPClient(settings_doctype="Consumables SAP Settings").login()
        return {"status": "success", "message": "SAP session initiated successfully."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Consumables SAP Initiate Session Error")
        return {"status": "error", "message": str(e)}


# ── Plants ────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_plants():
    _require_admin()
    plants = frappe.get_all(
        "Consumables Plant",
        fields=["name", "plant_code", "plant_name", "location", "is_active", "delivery_customer_code"],
        order_by="plant_code asc",
    )
    result = []
    for p in plants:
        try:
            doc = frappe.get_doc("Consumables Plant", p.name)
            warehouses = [
                {
                    "name": w.name,
                    "warehouse_code": w.warehouse_code or "",
                    "warehouse_name": w.warehouse_name or "",
                    "warehouse_type": w.warehouse_type or "",
                    "is_active": w.is_active,
                }
                for w in (doc.warehouses or [])
            ]
        except Exception:
            warehouses = []
        result.append({
            "name": p.name,
            "plant_code": p.plant_code or "",
            "plant_name": p.plant_name or "",
            "location": p.location or "",
            "is_active": p.is_active,
            "delivery_customer_code": p.delivery_customer_code or "",
            "warehouses": warehouses,
        })
    return result


@frappe.whitelist()
def save_plant(plant_code, plant_name, location="", is_active=1, delivery_customer_code="", warehouses=None):
    _require_admin()
    import json
    if isinstance(warehouses, str):
        warehouses = json.loads(warehouses)
    warehouses = warehouses or []

    plant_code = (plant_code or "").strip()
    plant_name = (plant_name or "").strip()
    if not plant_code:
        frappe.throw(_("Plant Code is required."), frappe.ValidationError)
    if not plant_name:
        frappe.throw(_("Plant Name is required."), frappe.ValidationError)

    if frappe.db.exists("Consumables Plant", plant_code):
        doc = frappe.get_doc("Consumables Plant", plant_code)
    else:
        doc = frappe.new_doc("Consumables Plant")
        doc.plant_code = plant_code

    doc.plant_name = plant_name
    doc.location = location or ""
    doc.is_active = int(is_active)
    doc.delivery_customer_code = delivery_customer_code or ""

    # Rebuild warehouses child table
    doc.warehouses = []
    for wh in warehouses:
        wc = (wh.get("warehouse_code") or "").strip()
        if not wc:
            continue
        doc.append("warehouses", {
            "warehouse_code": wc,
            "warehouse_name": wh.get("warehouse_name") or wc,
            "warehouse_type": wh.get("warehouse_type") or "Main",
            "is_active": int(wh.get("is_active", 1)),
        })

    doc.save(ignore_permissions=True)
    return {"name": doc.name, "plant_code": doc.plant_code}


# ── User Assignments ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_user_plant_mappings(plant=None):
    _require_admin()
    filters = {}
    if plant:
        filters["plant"] = plant
    rows = frappe.get_all(
        "Consumables User Plant",
        filters=filters,
        fields=["name", "user", "plant", "is_active", "notes"],
        order_by="plant asc, user asc",
    )
    result = []
    for r in rows:
        full_name = frappe.db.get_value("User", r.user, "full_name") or r.user
        result.append({
            "name": r.name,
            "user": r.user,
            "full_name": full_name,
            "plant": r.plant or "",
            "is_active": r.is_active,
            "notes": r.notes or "",
        })
    return result


@frappe.whitelist()
def get_eligible_users():
    """Return all users who have at least one Consumables role."""
    _require_admin()
    all_users = frappe.get_all("User", filters={"enabled": 1}, fields=["name", "full_name", "email"])
    result = []
    for u in all_users:
        user_roles = frappe.get_roles(u.name)
        consumables_role = next((r for r in CONSUMABLES_ROLES if r in user_roles), None)
        if consumables_role:
            result.append({
                "user": u.name,
                "full_name": u.full_name or u.name,
                "email": u.email or "",
                "role": consumables_role,
            })
    return result


@frappe.whitelist()
def save_user_plant_mapping(user, plant, is_active=1, notes=""):
    _require_admin()
    user = (user or "").strip()
    plant = (plant or "").strip()
    if not user or not plant:
        frappe.throw(_("User and Plant are required."), frappe.ValidationError)

    # Check for existing mapping
    existing = frappe.db.get_value(
        "Consumables User Plant",
        {"user": user, "plant": plant},
        "name",
    )
    if existing:
        doc = frappe.get_doc("Consumables User Plant", existing)
    else:
        doc = frappe.new_doc("Consumables User Plant")
        doc.user = user
        doc.plant = plant

    doc.is_active = int(is_active)
    doc.notes = notes or ""
    doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def delete_user_plant_mapping(name):
    _require_admin()
    if not frappe.db.exists("Consumables User Plant", name):
        frappe.throw(_("Mapping not found."), frappe.DoesNotExistError)
    frappe.delete_doc("Consumables User Plant", name, ignore_permissions=True)
    return {"deleted": name}


# ── Settings ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_settings():
    _require_admin()
    if not frappe.db.exists("Consumables Settings", "Consumables Settings"):
        return {
            "hana_schema": "",
            "default_delivery_customer": "",
            "sap_posting_queue": "long",
            "enable_realtime_notifications": 1,
        }
    doc = frappe.get_doc("Consumables Settings", "Consumables Settings")
    return {
        "hana_schema": doc.hana_schema or "",
        "default_delivery_customer": doc.default_delivery_customer or "",
        "sap_posting_queue": doc.sap_posting_queue or "long",
        "enable_realtime_notifications": doc.enable_realtime_notifications,
    }


@frappe.whitelist()
def save_settings(hana_schema="", default_delivery_customer="", sap_posting_queue="long", enable_realtime_notifications=1):
    _require_admin()
    if not frappe.db.exists("Consumables Settings", "Consumables Settings"):
        doc = frappe.new_doc("Consumables Settings")
    else:
        doc = frappe.get_doc("Consumables Settings", "Consumables Settings")
    if hana_schema and not re.match(r'^[A-Za-z0-9_]+$', hana_schema):
        frappe.throw(_("HANA Schema name must contain only letters, numbers, and underscores."), frappe.ValidationError)
    doc.hana_schema = hana_schema or ""
    doc.default_delivery_customer = default_delivery_customer or ""
    doc.sap_posting_queue = sap_posting_queue or "long"
    doc.enable_realtime_notifications = int(enable_realtime_notifications)
    doc.save(ignore_permissions=True)
    return {"saved": True}
