import frappe
from frappe import _
from frappe.utils import now_datetime

from khanal_tech_integrations.consumables.services.role_guard import (
    assert_plant_access,
    get_accessible_plants,
    require_consumables_role,
)


def _cir_to_dict(doc):
    return {
        "name": doc.name,
        "status": doc.status,
        "requesting_plant": doc.requesting_plant or "",
        "item_name_requested": doc.item_name_requested or "",
        "description": doc.description or "",
        "requested_by": doc.requested_by or "",
        "requested_on": str(doc.requested_on or ""),
        "resolved_by": doc.resolved_by or "",
        "resolved_on": str(doc.resolved_on or ""),
        "sap_item_code": doc.sap_item_code or "",
        "notes": doc.notes or "",
    }


@frappe.whitelist()
def create_item_request(plant, item_name_requested, description=""):
    require_consumables_role()
    plant = (plant or "").strip()
    item_name_requested = (item_name_requested or "").strip()
    if not plant:
        frappe.throw(_("Plant is required."), frappe.ValidationError)
    if not item_name_requested:
        frappe.throw(_("Item name is required."), frappe.ValidationError)
    assert_plant_access(plant)

    doc = frappe.new_doc("Consumables Item Request")
    doc.requesting_plant = plant
    doc.item_name_requested = item_name_requested
    doc.description = description or ""
    doc.status = "Pending"
    doc.requested_by = frappe.session.user
    doc.requested_on = now_datetime()
    doc.insert(ignore_permissions=True)

    _notify_admins_new_item_request(doc)
    return _cir_to_dict(doc)


@frappe.whitelist()
def get_item_requests(status=None, plant=None, page=1, page_size=20):
    require_consumables_role()
    roles = frappe.get_roles()
    is_admin = "Consumables Super Admin" in roles

    filters = {}
    if status:
        filters["status"] = status
    if plant:
        if not is_admin:
            assert_plant_access(plant)
        filters["requesting_plant"] = plant
    elif not is_admin:
        accessible = get_accessible_plants()
        if accessible:
            filters["requesting_plant"] = ["in", accessible]

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        page, page_size = 1, 20

    total = frappe.db.count("Consumables Item Request", filters)
    rows = frappe.get_all(
        "Consumables Item Request",
        filters=filters,
        fields=[
            "name", "status", "requesting_plant", "item_name_requested",
            "requested_by", "requested_on", "sap_item_code",
        ],
        order_by="requested_on desc",
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "name": r.name,
                "status": r.status,
                "requesting_plant": r.requesting_plant or "",
                "item_name_requested": r.item_name_requested or "",
                "requested_by": r.requested_by or "",
                "requested_on": str(r.requested_on or ""),
                "sap_item_code": r.sap_item_code or "",
            }
            for r in rows
        ],
    }


@frappe.whitelist()
def get_item_request(name):
    require_consumables_role()
    if not frappe.db.exists("Consumables Item Request", name):
        frappe.throw(_("Item request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Item Request", name)
    roles = frappe.get_roles()
    if "Consumables Super Admin" not in roles:
        assert_plant_access(doc.requesting_plant)
    return _cir_to_dict(doc)


@frappe.whitelist()
def resolve_item_request(name, sap_item_code, notes=""):
    """Mark item as created in SAP. Super Admin only."""
    require_consumables_role()
    if "Consumables Super Admin" not in frappe.get_roles():
        frappe.throw(_("Only Super Admin can resolve item requests."), frappe.PermissionError)

    sap_item_code = (sap_item_code or "").strip()
    if not sap_item_code:
        frappe.throw(_("SAP Item Code is required to resolve the request."), frappe.ValidationError)

    if not frappe.db.exists("Consumables Item Request", name):
        frappe.throw(_("Item request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Item Request", name)
    if doc.status in ("Created", "Rejected"):
        frappe.throw(_("Request is already {0}.").format(doc.status), frappe.ValidationError)

    doc.status = "Created"
    doc.sap_item_code = sap_item_code
    doc.resolved_by = frappe.session.user
    doc.resolved_on = now_datetime()
    doc.notes = notes or doc.notes or ""
    doc.save(ignore_permissions=True)

    _notify_requester_resolved(doc)
    return _cir_to_dict(doc)


@frappe.whitelist()
def reject_item_request(name, notes=""):
    """Reject a new item request. Super Admin only."""
    require_consumables_role()
    if "Consumables Super Admin" not in frappe.get_roles():
        frappe.throw(_("Only Super Admin can reject item requests."), frappe.PermissionError)

    if not frappe.db.exists("Consumables Item Request", name):
        frappe.throw(_("Item request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Item Request", name)
    if doc.status in ("Created", "Rejected"):
        frappe.throw(_("Request is already {0}.").format(doc.status), frappe.ValidationError)

    doc.status = "Rejected"
    doc.resolved_by = frappe.session.user
    doc.resolved_on = now_datetime()
    doc.notes = notes or ""
    doc.save(ignore_permissions=True)

    _notify_requester_rejected(doc)
    return _cir_to_dict(doc)


def _notify_admins_new_item_request(doc):
    users = frappe.get_all("User", filters={"enabled": 1}, fields=["name"])
    msg = f"New item request from {doc.requesting_plant}: '{doc.item_name_requested}' (CIR: {doc.name})"
    for row in users:
        user = (row.get("name") or "").strip()
        if not user:
            continue
        if "Consumables Super Admin" not in frappe.get_roles(user):
            continue
        frappe.publish_realtime(
            "storeops_update",
            {"doc_type": "Consumables Item Request", "doc_name": doc.name, "new_status": "Pending", "message": msg, "level": "info"},
            user=user,
        )


def _notify_requester_resolved(doc):
    requester = (doc.requested_by or "").strip()
    if not requester:
        return
    msg = f"Item '{doc.item_name_requested}' has been created in SAP. SAP Code: {doc.sap_item_code}"
    frappe.publish_realtime(
        "storeops_update",
        {"doc_type": "Consumables Item Request", "doc_name": doc.name, "new_status": "Created", "message": msg, "level": "success"},
        user=requester,
    )


def _notify_requester_rejected(doc):
    requester = (doc.requested_by or "").strip()
    if not requester:
        return
    msg = f"Item request '{doc.item_name_requested}' was not approved. Notes: {doc.notes or 'None'}"
    frappe.publish_realtime(
        "storeops_update",
        {"doc_type": "Consumables Item Request", "doc_name": doc.name, "new_status": "Rejected", "message": msg, "level": "error"},
        user=requester,
    )
