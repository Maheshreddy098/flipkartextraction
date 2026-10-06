import json

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime, nowdate

from khanal_tech_integrations.consumables.services.role_guard import (
    assert_plant_access,
    get_accessible_plants,
    require_consumables_role,
    require_manager_or_admin,
)
from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
from khanal_tech_integrations.consumables.hana.inventory_queries import search_consumable_items


def _parse_json(value):
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _parse_line_items(line_items):
    rows = _parse_json(line_items) or []
    if not isinstance(rows, list):
        frappe.throw(_("line_items must be a list."), frappe.ValidationError)
    return rows


def _extract_urgency_from_title(title):
    text = (title or "").strip()
    for chunk in text.split("]"):
        chunk = chunk.strip()
        if chunk.startswith("[") and not chunk.startswith("[State:") and not chunk.startswith("[Plant:"):
            return chunk[1:].strip() or "Medium"
    return "Medium"


def _extract_reason_from_title(title):
    text = (title or "").strip()
    parts = []
    for chunk in text.split("]"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("[State:") or chunk.startswith("[Plant:") or (chunk.startswith("[") and len(chunk) < 20):
            continue
        parts.append(chunk[1:].strip() if chunk.startswith("[") else chunk)
    if parts:
        return " ".join(parts).strip()
    return text


def _extract_plant_from_title(title):
    text = (title or "").strip()
    marker = "[Plant:"
    if marker in text and "]" in text.split(marker, 1)[1]:
        return text.split(marker, 1)[1].split("]", 1)[0].strip()
    return ""


def _extract_state_from_title(title):
    text = (title or "").strip()
    marker = "[State:"
    if marker in text and "]" in text.split(marker, 1)[1]:
        return text.split(marker, 1)[1].split("]", 1)[0].strip()
    return ""


def _set_state_in_title(doc, state):
    title = doc.title or ""
    if "[State:" in title:
        prefix, rest = title.split("[State:", 1)
        if "]" in rest:
            rest = rest.split("]", 1)[1]
        title = f"{prefix}{rest}".strip()
    doc.title = f"[State:{state}] {title}".strip()


def _has_cmr_doctype():
    return bool(frappe.db.exists("DocType", "Consumables Material Request"))


def _urgency_for_cmr(raw):
    v = (raw or "").strip().lower()
    if v in ("critical",):
        return "Critical"
    if v in ("high", "urgent"):
        return "Urgent"
    if v in ("medium", "normal", "low"):
        return "Normal"
    return "Normal"


def _default_requesting_plant(plant_code=None):
    code = (plant_code or "").strip()
    if code:
        return code
    plants = [p for p in (get_accessible_plants() or []) if (p or "").strip()]
    if not plants:
        frappe.throw(_("No accessible plant mapped for current user."), frappe.PermissionError)
    return plants[0]


def _normalize_plant_key(value):
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _assert_cmr_reviewer_can_act(doc):
    """Block review/fulfill actions for unauthorized roles and request creator.

    Reviewer must hold BOTH Store Manager and Inventory Manager roles simultaneously.
    Super Admin bypasses this requirement.
    """
    roles = frappe.get_roles()
    if "Consumables Super Admin" in roles:
        return
    has_store = "Consumables Store Manager" in roles
    has_inventory = "Consumables Inventory Manager" in roles
    if not (has_store and has_inventory):
        frappe.throw(
            _("Reviewing and fulfilling material requests requires both the Store Manager and Inventory Manager roles."),
            frappe.PermissionError,
        )
    user = (frappe.session.user or "").strip().lower()
    req_by = (getattr(doc, "requested_by", None) or "").strip().lower()
    creator = (getattr(doc, "owner", None) or "").strip().lower()
    effective_requester = req_by or creator
    if effective_requester and effective_requester == user:
        frappe.throw(
            _("You cannot review or fulfill a material request you raised."),
            frappe.PermissionError,
        )


def _users_with_any_role(roles):
    """Return user names of enabled users holding at least one of the given roles (single query)."""
    placeholders = ", ".join(["%s"] * len(roles))
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT u.name
        FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
        WHERE u.enabled = 1 AND r.role IN ({placeholders})
        """,
        roles,
        as_dict=True,
    )
    return [(row.name or "").strip() for row in rows if (row.name or "").strip()]


def _users_with_all_roles(roles):
    """Return user names of enabled users holding ALL of the given roles (one query per role, intersected)."""
    if not roles:
        return []
    sets = []
    for role in roles:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT u.name
            FROM `tabUser` u
            JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
            WHERE u.enabled = 1 AND r.role = %s
            """,
            role,
            as_dict=True,
        )
        sets.append({(row.name or "").strip() for row in rows if (row.name or "").strip()})
    result = sets[0]
    for s in sets[1:]:
        result = result & s
    return list(result)


def _notify_managers_super_admins_physical_receipt(doc, confirming_user):
    """Notify all store managers and super admins when destination confirms receipt."""
    plant = (doc.requesting_plant or "").strip()
    msg = _("Material request {0}: physical receipt confirmed for plant {1} by {2}.").format(
        doc.name, plant, confirming_user
    )
    target_users = _users_with_any_role(["Consumables Store Manager", "Consumables Super Admin"])
    for user in target_users:
        if user == confirming_user:
            continue
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Material Request",
                "doc_name": doc.name,
                "new_status": doc.status or "",
                "message": msg,
                "level": "success",
            },
            user=user,
        )


def _notify_dc_str_mahadevpura_store_managers(doc, new_status="Submitted", message=None, level="info"):
    """Notify CMR reviewers (users with BOTH Store Manager + Inventory Manager roles) and Super Admins."""
    reviewer_users = set(_users_with_all_roles(["Consumables Store Manager", "Consumables Inventory Manager"]))
    super_admin_users = set(_users_with_any_role(["Consumables Super Admin"]))
    target_users = reviewer_users | super_admin_users
    session_user = frappe.session.user
    for user in target_users:
        if user == session_user:
            continue
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Material Request",
                "doc_name": doc.name,
                "new_status": new_status,
                "message": message or f"Material request {doc.name} moved to {new_status}.",
                "level": level,
            },
            user=user,
        )


def _ensure_purchase_request_for_rejected_transfers(doc):
    rejected_qty = {}
    for row in (doc.transfer_links or []):
        link_name = (row.transfer_request or "").strip()
        if not link_name or not frappe.db.exists("Consumables Transfer Request", link_name):
            continue
        ctr = frappe.get_doc("Consumables Transfer Request", link_name)
        if (ctr.status or "").strip() != "Rejected":
            continue
        for li in (ctr.line_items or []):
            code = (li.item_code or "").strip()
            if code:
                rejected_qty[code] = rejected_qty.get(code, 0.0) + float(li.quantity or 0)
    if not rejected_qty:
        return

    existing_po_qty = {}
    for row in (doc.purchase_links or []):
        link_name = (row.purchase_request or "").strip()
        if not link_name or not frappe.db.exists("Consumables Purchase Request", link_name):
            continue
        pr = frappe.get_doc("Consumables Purchase Request", link_name)
        if (pr.status or "").strip() == "Cancelled":
            continue
        for li in (pr.line_items or []):
            code = (li.item_code or "").strip()
            if code:
                existing_po_qty[code] = existing_po_qty.get(code, 0.0) + float(li.quantity or 0)

    add_rows = []
    for li in (doc.line_items or []):
        code = (li.item_code or "").strip()
        if not code:
            continue
        target_po_total = float(li.quantity_to_order or 0) + float(rejected_qty.get(code, 0.0))
        already_po = float(existing_po_qty.get(code, 0.0))
        extra = target_po_total - already_po
        if extra > 0.0001:
            add_rows.append(
                {
                    "item_code": code,
                    "qty": extra,
                    "uom": li.uom or None,
                    "item_name": li.item_name or code,
                }
            )
    if not add_rows:
        return

    cpr = frappe.new_doc("Consumables Purchase Request")
    cpr.naming_series = "CPR-.YYYY.-.#####"
    cpr.cmr_reference = doc.name
    cpr.requesting_plant = doc.requesting_plant
    cpr.status = "Submitted"
    cpr.requested_by = (getattr(doc, "requested_by", None) or doc.owner or "").strip()
    cpr.requested_on = now_datetime()
    for row in add_rows:
        cpr.append(
            "line_items",
            {
                "item_code": row["item_code"],
                "item_name": row["item_name"],
                "quantity": row["qty"],
                "uom": row["uom"] or "",
            },
        )
    cpr.insert(ignore_permissions=True)
    if hasattr(doc, "purchase_links"):
        doc.append(
            "purchase_links",
            {
                "purchase_request": cpr.name,
                "quantity": sum(float(r["qty"] or 0) for r in add_rows),
                "status": "Submitted",
            },
        )
    doc.add_comment("Comment", text=f"Fallback purchase request {cpr.name} created for rejected transfer quantities.")


def _is_whole_number(value):
    return abs(float(value) - round(float(value))) <= 0.000001


def _is_procurement_user(user=None):
    return "Consumables Procurement User" in frappe.get_roles(user or frappe.session.user)


def _plant_warehouses(plant_code):
    rows = frappe.get_all(
        "Consumables Plant Warehouse",
        filters={"parent": plant_code, "is_active": 1},
        fields=["warehouse_code"],
        order_by="idx asc",
    )
    return [str(r.get("warehouse_code") or "").strip() for r in rows if str(r.get("warehouse_code") or "").strip()]


def _sap_item_info(plant_code, item_code):
    """Look up an item in the SAP item master (OITM), regardless of current stock.

    A Material Request is a request for items the store doesn't have, so this must
    not require on-hand quantity — it previously went through get_warehouse_inventory
    (which filters Quantity > 0), so every item at a zero-stock warehouse/plant was
    wrongly rejected as "not found in SAP".
    """
    code = (item_code or "").strip()
    if not code:
        return None

    settings = frappe.get_single("Consumables Settings")
    configured_codes = [
        str(row.item_group_code).strip()
        for row in (settings.consumable_item_groups or [])
        if getattr(row, "is_active", 1) and getattr(row, "item_group_code", None)
    ]

    with ConsumablesHANAClient() as client:
        rows = search_consumable_items(client, code, configured_codes)
        for r in rows:
            if str(r.get("item_code") or "").strip().upper() == code.upper():
                return {
                    "item_code": str(r.get("item_code") or "").strip(),
                    "item_name": str(r.get("item_name") or "").strip(),
                    "uom": str(r.get("uom") or "").strip(),
                }
    return None


def _get_request_doc(name):
    if _has_cmr_doctype() and frappe.db.exists("Consumables Material Request", name):
        return "CMR", frappe.get_doc("Consumables Material Request", name)
    return "MR", frappe.get_doc("Material Request", name)


def _get_linked_docs(doc):
    ctr_name = (doc.get("custom_sap_doc_entry") or "").strip()
    cpr_name = (doc.get("custom_sap_doc_num") or "").strip()
    return ctr_name, cpr_name


def _derive_status(doc):
    tagged = _extract_state_from_title(doc.get("title"))
    if tagged:
        return tagged
    ctr_name, cpr_name = _get_linked_docs(doc)
    if doc.docstatus == 2:
        return "Rejected"
    if doc.docstatus == 0:
        return "Draft"
    if ctr_name or cpr_name:
        sync = _sync_snapshot(doc, ctr_name, cpr_name)
        return sync["status"]
    return "Under Review"


def _sync_snapshot(doc, ctr_name="", cpr_name=""):
    if not ctr_name or not cpr_name:
        a, b = _get_linked_docs(doc)
        ctr_name = ctr_name or a
        cpr_name = cpr_name or b

    ctr_status = None
    cpr_status = None
    ctr_done = False
    cpr_done = False
    fulfilled = {}
    status = "Pending"

    if ctr_name and frappe.db.exists("Consumables Transfer Request", ctr_name):
        ctr = frappe.get_doc("Consumables Transfer Request", ctr_name)
        ctr_status = ctr.status
        ctr_done = ctr.status in ("Completed", "Received")
        for row in ctr.line_items or []:
            code = (row.item_code or "").strip()
            if not code:
                continue
            fulfilled[code] = fulfilled.get(code, 0.0) + float(row.quantity or 0)

    if cpr_name and frappe.db.exists("Material Request", cpr_name):
        cpr = frappe.get_doc("Material Request", cpr_name)
        cpr_status = "Submitted" if cpr.docstatus == 1 else ("Draft" if cpr.docstatus == 0 else "Cancelled")
        cpr_done = cpr.docstatus != 2
        for row in cpr.items or []:
            code = (row.item_code or "").strip()
            if not code:
                continue
            fulfilled[code] = fulfilled.get(code, 0.0) + float(row.qty or 0)

        status = "Fulfilling"
    if ctr_done and cpr_done:
        status = "Completed"
    elif not ctr_name and not cpr_name:
        status = "Under Review" if doc.docstatus == 1 else ("Draft" if doc.docstatus == 0 else "Rejected")

    return {
        "status": status,
        "ctr_status": ctr_status,
        "cpr_status": cpr_status,
        "fulfilled_qty_by_item": fulfilled,
    }


@frappe.whitelist()
def get_material_requests(status=None, plant_code=None, from_date=None, to_date=None, page=1, page_size=20):
    require_consumables_role()
    is_procurement = _is_procurement_user()

    if _has_cmr_doctype():
        filters = {}
        if plant_code:
            assert_plant_access(plant_code)
            filters["requesting_plant"] = plant_code
        else:
            # Enforce plant access — Super Admin sees all; others see only their plants
            roles = frappe.get_roles()
            if "Consumables Super Admin" not in roles:
                accessible = get_accessible_plants()
                if not accessible:
                    return {"material_requests": [], "total": 0, "page": 1, "page_size": int(page_size)}
                filters["requesting_plant"] = ["in", accessible]

        if status:
            filters["status"] = status
        if from_date and to_date:
            filters["requested_on"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["requested_on"] = [">=", from_date]
        elif to_date:
            filters["requested_on"] = ["<=", to_date]
        if is_procurement:
            filters["requested_by"] = frappe.session.user

        page = max(1, int(page))
        page_size = max(1, min(200, int(page_size)))
        start = (page - 1) * page_size

        rows = frappe.get_all(
            "Consumables Material Request",
            filters=filters,
            fields=[
                "name",
                "status",
                "requesting_plant",
                "urgency",
                "reason",
                "requested_by",
                "requested_on",
                "creation",
            ],
            order_by="creation desc",
            start=start,
            page_length=page_size,
        )
        out = [
            {
                "name": r.get("name"),
                "status": r.get("status") or "Draft",
                "plant_code": r.get("requesting_plant") or "",
                "urgency": r.get("urgency") or "Normal",
                "reason": r.get("reason") or "",
                "requested_by": r.get("requested_by") or "",
                "transaction_date": r.get("requested_on"),
                "creation": r.get("creation"),
            }
            for r in rows
        ]
        total = frappe.db.count("Consumables Material Request", filters=filters)
        return {"material_requests": out, "total": total, "page": page, "page_size": page_size}

    filters = {"material_request_type": "Purchase"}
    filters["title"] = ["not like", "[CPR]%"]
    if from_date and to_date:
        filters["transaction_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["transaction_date"] = [">=", from_date]
    elif to_date:
        filters["transaction_date"] = ["<=", to_date]
    if is_procurement:
        filters["owner"] = frappe.session.user

    page = max(1, int(page))
    page_size = max(1, min(200, int(page_size)))
    start = (page - 1) * page_size

    rows = frappe.get_all(
        "Material Request",
        filters=filters,
        fields=[
            "name",
            "docstatus",
            "owner",
            "creation",
            "transaction_date",
            "title",
            "set_warehouse",
            "custom_sap_doc_entry",
            "custom_sap_doc_num",
        ],
        order_by="creation desc",
        start=start,
        page_length=page_size,
    )

    out = []
    for row in rows:
        mr = frappe._dict(row)
        status_value = _derive_status(mr)
        if status and status_value.lower() != str(status).lower():
            continue
        if plant_code:
            assert_plant_access(plant_code)
            wh = (mr.set_warehouse or "").strip()
            if wh and not wh.startswith(plant_code):
                continue
        out.append(
            {
                "name": mr.name,
                "status": status_value,
                "plant_code": _extract_plant_from_title(mr.title) or ((mr.set_warehouse or "").split("-")[0] if mr.set_warehouse else ""),
                "urgency": _extract_urgency_from_title(mr.title),
                "reason": _extract_reason_from_title(mr.title),
                "transaction_date": mr.transaction_date,
                "creation": mr.creation,
                "requested_by": mr.owner,
                "linked_ctr": (mr.custom_sap_doc_entry or "").strip(),
                "linked_cpr": (mr.custom_sap_doc_num or "").strip(),
            }
        )

    total = frappe.db.count("Material Request", filters=filters)
    return {"material_requests": out, "total": total, "page": page, "page_size": page_size}


@frappe.whitelist()
def get_material_request(name):
    require_consumables_role()
    is_procurement = _is_procurement_user()

    if _has_cmr_doctype():
        doc = frappe.get_doc("Consumables Material Request", name)
        assert_plant_access(doc.requesting_plant)
        if is_procurement and (doc.requested_by or doc.owner) != frappe.session.user:
            frappe.throw(_("You do not have access to this material request."), frappe.PermissionError)
        transfer_links = []
        purchase_links = []
        for row in (doc.transfer_links or []):
            link_name = (row.transfer_request or "").strip()
            status = row.status or ""
            sap_last_error = ""
            if link_name and frappe.db.exists("Consumables Transfer Request", link_name):
                status = frappe.db.get_value("Consumables Transfer Request", link_name, "status") or status
                sap_last_error = frappe.db.get_value("Consumables Transfer Request", link_name, "sap_last_error") or ""
            transfer_links.append(
                {
                    "name": link_name,
                    "from_plant": row.from_plant,
                    "from_warehouse": row.from_warehouse,
                    "quantity": float(row.quantity or 0),
                    "status": status,
                    "sap_last_error": sap_last_error,
                }
            )
        for row in (doc.purchase_links or []):
            link_name = (row.purchase_request or "").strip()
            status = row.status or ""
            sap_po_number = getattr(row, "sap_po_number", "") or ""
            sap_grpo_number = ""
            if link_name and frappe.db.exists("Consumables Purchase Request", link_name):
                cpr_vals = frappe.db.get_value(
                    "Consumables Purchase Request",
                    link_name,
                    ["status", "sap_po_doc_num", "sap_grpo_doc_num"],
                    as_dict=True,
                ) or {}
                if cpr_vals.get("status"):
                    status = cpr_vals["status"]
                if cpr_vals.get("sap_po_doc_num"):
                    sap_po_number = cpr_vals["sap_po_doc_num"]
                if cpr_vals.get("sap_grpo_doc_num"):
                    sap_grpo_number = cpr_vals["sap_grpo_doc_num"]
            purchase_links.append(
                {
                    "name": link_name,
                    "quantity": float(row.quantity or 0),
                    "status": status,
                    "sap_po_number": sap_po_number,
                    "sap_grpo_number": sap_grpo_number,
                }
            )
        return {
            "name": doc.name,
            "status": doc.status or "Draft",
            "plant_code": doc.requesting_plant or "",
            "requesting_warehouses": _plant_warehouses(doc.requesting_plant),
            "urgency": doc.urgency or "Normal",
            "reason": doc.reason or "",
            "requested_by": doc.requested_by or doc.owner,
            "creation": str(doc.creation or ""),
            "transaction_date": str(doc.requested_on or ""),
            "submitted_on": str(doc.requested_on or ""),
            "reviewed_on": str(doc.reviewed_on or ""),
            "fulfilling_on": str(doc.modified or "") if (doc.status or "") == "Fulfilling" else "",
            "linked_ctr": ", ".join([x["name"] for x in transfer_links if x.get("name")]),
            "linked_cpr": ", ".join([x["name"] for x in purchase_links if x.get("name")]),
            "ctr_status": None,
            "cpr_status": None,
            "transfer_links": transfer_links,
            "purchase_links": purchase_links,
            "line_items": [
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "quantity": float(row.quantity_requested or 0),
                    "uom": row.uom,
                    "fulfilled_quantity": min(
                        float(row.quantity_received or 0),
                        float(row.quantity_requested or 0),
                    ),
                }
                for row in (doc.line_items or [])
            ],
        }

    doc = frappe.get_doc("Material Request", name)
    if doc.material_request_type != "Purchase":
        frappe.throw(_("Only StoreOps purchase requests are supported in this endpoint."), frappe.ValidationError)
    if is_procurement and doc.owner != frappe.session.user:
        frappe.throw(_("You do not have access to this material request."), frappe.PermissionError)
    _legacy_plant = _extract_plant_from_title(doc.title) or ((doc.set_warehouse or "").split("-")[0].strip() if doc.set_warehouse else "")
    if _legacy_plant:
        assert_plant_access(_legacy_plant)

    ctr_name, cpr_name = _get_linked_docs(doc)
    sync = _sync_snapshot(doc, ctr_name, cpr_name)

    line_items = []
    for item in doc.items or []:
        code = (item.item_code or "").strip()
        line_items.append(
            {
                "item_code": code,
                "item_name": item.item_name,
                "quantity": float(item.qty or 0),
                "uom": item.uom,
                "fulfilled_quantity": float(sync["fulfilled_qty_by_item"].get(code, 0)),
            }
        )

    return {
        "name": doc.name,
        "status": _derive_status(doc),
        "plant_code": _extract_plant_from_title(doc.title) or ((doc.set_warehouse or "").split("-")[0] if doc.set_warehouse else ""),
        "urgency": _extract_urgency_from_title(doc.title),
        "reason": _extract_reason_from_title(doc.title),
        "requested_by": doc.owner,
        "creation": str(doc.creation or ""),
        "transaction_date": str(doc.transaction_date or ""),
        "submitted_on": str(doc.modified or ""),
        "linked_ctr": ctr_name,
        "linked_cpr": cpr_name,
        "ctr_status": sync["ctr_status"],
        "cpr_status": sync["cpr_status"],
        "line_items": line_items,
    }


@frappe.whitelist()
def create_material_request(plant_code=None, urgency="Medium", reason="", line_items=None, **kwargs):
    require_consumables_role()
    plant_code = _default_requesting_plant(plant_code)
    assert_plant_access(plant_code)
    remarks = (kwargs.get("remarks") or reason or "").strip()

    rows = _parse_line_items(line_items)
    if not rows:
        frappe.throw(_("Add at least one line item."), frappe.ValidationError)

    if _has_cmr_doctype():
        doc = frappe.new_doc("Consumables Material Request")
        doc.requesting_plant = plant_code
        doc.requested_by = frappe.session.user
        doc.requested_on = now_datetime()
        doc.urgency = _urgency_for_cmr(urgency)
        doc.reason = remarks
        doc.status = "Draft"

        for row in rows:
            raw_qty = row.get("quantity")
            qty = float(raw_qty or 0)
            if qty <= 0:
                frappe.throw(_("Quantity must be greater than zero for all items."), frappe.ValidationError)
            item_code = (row.get("item_code") or "").strip()
            sap = _sap_item_info(plant_code, item_code)
            allow_new_item = bool(row.get("create_new_item"))
            if not sap and not allow_new_item:
                frappe.throw(
                    _("Item {0} is not found in SAP inventory for plant {1}.").format(item_code or "?", plant_code),
                    frappe.ValidationError,
                )
            if not sap and allow_new_item:
                if not item_code:
                    frappe.throw(_("Item code is required when creating a new item request."), frappe.ValidationError)
                sap = {
                    "item_code": item_code,
                    "item_name": (row.get("item_name") or item_code).strip(),
                    "uom": (row.get("uom") or "").strip(),
                }
            # Keep integer quantity strict when caller sends whole-number quantity.
            if raw_qty is not None and isinstance(raw_qty, int):
                if not _is_whole_number(qty):
                    frappe.throw(_("Quantity for item {0} must be an integer.").format(item_code), frappe.ValidationError)
                qty = int(round(qty))
            doc.append(
                "line_items",
                {
                    "item_code": sap["item_code"],
                    "item_name": sap["item_name"] or row.get("item_name") or sap["item_code"],
                    "quantity_requested": qty,
                    "uom": sap["uom"] or row.get("uom") or "",
                    "fulfillment_status": "Pending",
                },
            )

        doc.insert(ignore_permissions=True)
        return {"name": doc.name, "status": doc.status or "Draft"}

    title_reason = remarks[:120] or "StoreOps Material Request"
    title = f"[State:Draft] [{(urgency or 'Medium').strip() or 'Medium'}] [Plant:{plant_code}] {title_reason}"

    doc = frappe.new_doc("Material Request")
    doc.material_request_type = "Purchase"
    doc.transaction_date = nowdate()
    doc.schedule_date = add_days(nowdate(), 1)
    doc.title = title
    # set_warehouse is intentionally not forced here because some sites use
    # non-Link custom values that fail link validation on insert.

    for row in rows:
        qty = float(row.get("quantity") or 0)
        if qty <= 0:
            frappe.throw(_("Quantity must be greater than zero for all items."), frappe.ValidationError)
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            frappe.throw(_("Item code is required for all line items."), frappe.ValidationError)
        if not frappe.db.exists("Item", item_code):
            frappe.throw(
                _("Item {0} does not exist in ERPNext Item master. Use a valid Item code.").format(item_code),
                frappe.ValidationError,
            )
        item_uom = frappe.db.get_value("Item", item_code, "stock_uom")
        doc.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "uom": item_uom or None,
                "schedule_date": doc.schedule_date,
            },
        )

    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": "Draft"}


@frappe.whitelist()
def submit_material_request(name):
    require_consumables_role()
    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        assert_plant_access(doc.requesting_plant)
        current = (doc.status or "").strip().lower()
        if current == "rejected":
            frappe.throw(_("Rejected request cannot be submitted."), frappe.ValidationError)
        if current not in ("draft",):
            frappe.throw(_("Only Draft request can be sent."), frappe.ValidationError)
        doc.status = "Submitted"
        doc.save(ignore_permissions=True)
        _notify_dc_str_mahadevpura_store_managers(
            doc,
            new_status="Submitted",
            message=f"Material request {doc.name} submitted for review.",
            level="info",
        )
        try:
            from khanal_tech_integrations.consumables.api.notifications import notify_cmr_submitted
            frappe.enqueue(notify_cmr_submitted, queue="short", cmr_name=doc.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Email notify: CMR submitted {doc.name}")
        return {"name": doc.name, "status": "Submitted"}
    if _derive_status(doc).lower() not in ("draft",):
        frappe.throw(_("Only Draft request can be sent."), frappe.ValidationError)
    _set_state_in_title(doc, "Submitted")
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": "Submitted"}


@frappe.whitelist()
def start_review(name):
    require_manager_or_admin()
    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        _assert_cmr_reviewer_can_act(doc)
        current = (doc.status or "").strip().lower()
        if current != "submitted":
            frappe.throw(_("Only Submitted request can be moved to Under Review."), frappe.ValidationError)
        doc.status = "Under Review"
        doc.reviewed_by = frappe.session.user
        doc.reviewed_on = now_datetime()
        doc.save(ignore_permissions=True)
        _notify_dc_str_mahadevpura_store_managers(
            doc,
            new_status="Under Review",
            message=f"Material request {doc.name} is under review.",
            level="info",
        )
        return {"name": doc.name, "status": "Under Review"}
    if _derive_status(doc).lower() != "submitted":
        frappe.throw(_("Only Submitted request can be moved to Under Review."), frappe.ValidationError)
    _set_state_in_title(doc, "Under Review")
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": "Under Review"}


@frappe.whitelist()
def reject_material_request(name, rejection_reason=""):
    require_manager_or_admin()
    reason = (rejection_reason or "").strip()
    if not reason:
        frappe.throw(_("Rejection reason is required."), frappe.ValidationError)

    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        _assert_cmr_reviewer_can_act(doc)
        current = (doc.status or "").strip().lower()
        if current not in ("submitted", "under review"):
            frappe.throw(_("Only Submitted or Under Review request can be rejected."), frappe.ValidationError)
        doc.status = "Rejected"
        doc.rejection_reason = reason
        doc.reviewed_by = frappe.session.user
        doc.reviewed_on = now_datetime()
        doc.save(ignore_permissions=True)
        doc.add_comment("Comment", text=f"Rejected by {frappe.session.user}: {reason}")
        _notify_dc_str_mahadevpura_store_managers(
            doc,
            new_status="Rejected",
            message=f"Material request {doc.name} was rejected. Reason: {reason}",
            level="warning",
        )
        try:
            from khanal_tech_integrations.consumables.api.notifications import notify_cmr_rejected
            frappe.enqueue(notify_cmr_rejected, queue="short", cmr_name=doc.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Email notify: CMR rejected {doc.name}")
        return {"name": doc.name, "status": "Rejected"}
    if _derive_status(doc).lower() not in ("submitted", "under review"):
        frappe.throw(_("Only Submitted or Under Review request can be rejected."), frappe.ValidationError)
    _set_state_in_title(doc, "Rejected")
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", text=f"Rejected by {frappe.session.user}: {reason}")
    return {"name": doc.name, "status": "Rejected"}


@frappe.whitelist()
def decide_fulfillment(name, decisions=None):
    require_manager_or_admin()
    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        _assert_cmr_reviewer_can_act(doc)
        status = (doc.status or "").strip()
        if status.lower() in ("draft", "submitted"):
            frappe.throw(_("Start review before deciding fulfillment."), frappe.ValidationError)
        if status.lower() == "rejected":
            frappe.throw(_("Rejected request cannot be fulfilled."), frappe.ValidationError)
        if status.lower() != "under review":
            frappe.throw(_("Fulfillment decision is allowed only in Under Review."), frappe.ValidationError)

        parsed = _parse_json(decisions) or []
        grouped = {}
        for d in parsed:
            code = (d.get("item_code") or "").strip()
            if not code:
                continue
            po = float(d.get("po_qty") or 0)
            if code not in grouped:
                grouped[code] = {"po_qty": 0.0, "transfers": []}
            grouped[code]["po_qty"] += max(0.0, po)
            transfers = d.get("transfers") or []
            if not transfers and float(d.get("transfer_qty") or 0) > 0:
                transfers = [
                    {
                        "from_plant": d.get("from_plant"),
                        "from_warehouse": d.get("from_warehouse"),
                        "transfer_qty": d.get("transfer_qty"),
                    }
                ]
            for t in transfers:
                qty = float(t.get("transfer_qty") or 0)
                if qty <= 0:
                    continue
                grouped[code]["transfers"].append(
                    {
                        "from_plant": (t.get("from_plant") or "").strip(),
                        "from_warehouse": (t.get("from_warehouse") or "").strip(),
                        "transfer_qty": qty,
                    }
                )

        any_alloc = False
        ctr_groups = {}
        cpr_rows = []
        req_plant = (doc.requesting_plant or "").strip()
        for item in doc.line_items or []:
            code = (item.item_code or "").strip()
            requested = float(item.quantity_requested or 0)
            d = grouped.get(code, {"po_qty": 0.0, "transfers": []})
            transfer_qty = 0.0
            for tr in d.get("transfers") or []:
                from_plant = (tr.get("from_plant") or "").strip()
                from_warehouse = (tr.get("from_warehouse") or "").strip()
                qty = float(tr.get("transfer_qty") or 0)
                if qty <= 0:
                    continue
                if not from_plant or not from_warehouse:
                    frappe.throw(
                        _("Transfer decision for item {0} requires from_plant and from_warehouse.").format(code),
                        frappe.ValidationError,
                    )
                if not frappe.db.exists("Consumables Plant", from_plant):
                    frappe.throw(
                        _("Transfer source plant {0} is invalid for item {1}.").format(from_plant, code),
                        frappe.ValidationError,
                    )
                if from_plant == req_plant:
                    frappe.throw(
                        _("Transfer source plant must be different from requesting plant for item {0}.").format(code),
                        frappe.ValidationError,
                    )
                transfer_qty += qty
                key = (from_plant, from_warehouse)
                ctr_groups.setdefault(key, []).append(
                    {
                        "item_code": code,
                        "item_name": item.item_name,
                        "quantity": qty,
                        "uom": item.uom or "",
                    }
                )
            po_qty = float(d.get("po_qty") or 0)
            allocated = transfer_qty + po_qty
            if allocated > 0:
                any_alloc = True
            if requested > 0 and allocated < requested - 0.0001:
                frappe.throw(
                    _("Total assigned qty must be at least the requested qty for item {0}.").format(code),
                    frappe.ValidationError,
                )
            if po_qty > 0:
                cpr_rows.append(
                    {
                        "item_code": code,
                        "item_name": item.item_name,
                        "qty": po_qty,
                        "uom": item.uom or None,
                    }
                )
            item.quantity_to_transfer = transfer_qty
            item.quantity_to_order = po_qty
            item.fulfillment_status = "Fulfilled" if requested > 0 and allocated >= requested else ("Partially Fulfilled" if allocated > 0 else "Pending")

        if not any_alloc:
            frappe.throw(_("No fulfillment quantities were provided."), frappe.ValidationError)

        ctr_names = []
        if ctr_groups:
            to_warehouse = (
                frappe.db.get_value(
                    "Consumables Plant Warehouse",
                    {"parent": req_plant, "is_active": 1},
                    "warehouse_code",
                )
                or req_plant
            )
            for (from_plant, from_warehouse), rows in ctr_groups.items():
                ctr = frappe.new_doc("Consumables Transfer Request")
                ctr.from_plant = from_plant
                ctr.from_warehouse = from_warehouse
                ctr.to_plant = req_plant or from_plant
                ctr.to_warehouse = to_warehouse
                ctr.cmr_reference = doc.name
                ctr.requested_by = (getattr(doc, "requested_by", None) or doc.owner or "").strip()
                ctr.requested_on = now_datetime()
                ctr.status = "Submitted"
                ctr.remarks = f"Source Material Request: {doc.name}"
                for row in rows:
                    ctr.append("line_items", row)
                ctr.insert(ignore_permissions=True)
                ctr_names.append(ctr.name)
                if hasattr(doc, "transfer_links"):
                    doc.append(
                        "transfer_links",
                        {
                            "transfer_request": ctr.name,
                            "from_plant": from_plant,
                            "from_warehouse": from_warehouse,
                            "quantity": sum(float(r["quantity"] or 0) for r in rows),
                            "status": ctr.status or "Submitted",
                        },
                    )

        cpr_name = ""
        if cpr_rows:
            cpr = frappe.new_doc("Consumables Purchase Request")
            cpr.naming_series = "CPR-.YYYY.-.#####"
            cpr.cmr_reference = doc.name
            cpr.requesting_plant = doc.requesting_plant
            cpr.status = "Submitted"
            cpr.requested_by = (getattr(doc, "requested_by", None) or doc.owner or "").strip()
            cpr.requested_on = now_datetime()
            for row in cpr_rows:
                cpr.append(
                    "line_items",
                    {
                        "item_code": row["item_code"],
                        "item_name": row.get("item_name") or row["item_code"],
                        "quantity": row["qty"],
                        "uom": row.get("uom") or "",
                    },
                )
            cpr.insert(ignore_permissions=True)
            cpr_name = cpr.name
            if hasattr(doc, "purchase_links"):
                doc.append(
                    "purchase_links",
                    {
                        "purchase_request": cpr.name,
                        "quantity": sum(float(r["qty"] or 0) for r in cpr_rows),
                        "status": "Submitted",
                    },
                )
            try:
                from khanal_tech_integrations.consumables.api.notifications import notify_cpr_created
                frappe.enqueue(notify_cpr_created, queue="short", cpr_name=cpr.name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Email notify: CPR created {cpr.name}")

        doc.status = "Fulfilling"
        doc.reviewed_by = frappe.session.user
        doc.reviewed_on = now_datetime()
        doc.save(ignore_permissions=True)
        doc.add_comment("Comment", text=f"Fulfillment decision confirmed by {frappe.session.user}")
        _notify_dc_str_mahadevpura_store_managers(
            doc,
            new_status="Fulfilling",
            message=f"Material request {doc.name} moved to fulfilling.",
            level="info",
        )
        return {
            "name": doc.name,
            "status": "Fulfilling",
            "linked_ctr": ", ".join(ctr_names),
            "linked_cpr": cpr_name or "",
        }

    if _derive_status(doc) == "Draft":
        frappe.throw(_("Send request and start review before deciding fulfillment."), frappe.ValidationError)
    if _derive_status(doc) == "Submitted":
        frappe.throw(_("Start review before deciding fulfillment."), frappe.ValidationError)
    if _derive_status(doc) == "Rejected":
        frappe.throw(_("Rejected request cannot be fulfilled."), frappe.ValidationError)

    parsed = _parse_json(decisions) or []
    by_item = {d.get("item_code"): d for d in parsed if d.get("item_code")}

    ctr_rows = []
    cpr_rows = []
    plant_code = _extract_plant_from_title(doc.title) or ((doc.set_warehouse or "").split("-")[0] if doc.set_warehouse else "")

    for item in doc.items or []:
        item_code = (item.item_code or "").strip()
        if not item_code:
            continue
        d = by_item.get(item_code, {})
        transfer_qty = float(d.get("transfer_qty") or 0)
        po_qty = float(d.get("po_qty") or 0)

        if transfer_qty > 0:
            from_plant = (d.get("from_plant") or "").strip()
            from_warehouse = (d.get("from_warehouse") or "").strip()
            if not from_plant or not from_warehouse:
                frappe.throw(
                    _("Transfer decision for item {0} requires from_plant and from_warehouse.").format(item_code),
                    frappe.ValidationError,
                )
            ctr_rows.append(
                {
                    "item_code": item_code,
                    "item_name": item.item_name,
                    "quantity": transfer_qty,
                    "uom": item.uom or "",
                    "from_plant": from_plant,
                    "from_warehouse": from_warehouse,
                }
            )

        if po_qty > 0:
            cpr_rows.append(
                {
                    "item_code": item_code,
                    "item_name": item.item_name,
                    "qty": po_qty,
                    "uom": item.uom or None,
                }
            )

    if not ctr_rows and not cpr_rows:
        frappe.throw(_("No fulfillment quantities were provided."), frappe.ValidationError)

    ctr_name = ""
    cpr_name = ""

    if ctr_rows:
        first = ctr_rows[0]
        ctr = frappe.new_doc("Consumables Transfer Request")
        ctr.from_plant = first["from_plant"]
        ctr.from_warehouse = first["from_warehouse"]
        ctr.to_plant = plant_code or first["from_plant"]
        ctr.to_warehouse = doc.set_warehouse or plant_code or first["from_warehouse"]
        ctr.requested_by = (getattr(doc, "requested_by", None) or doc.owner or "").strip()
        ctr.requested_on = now_datetime()
        ctr.status = "Submitted"
        ctr.remarks = f"Source Material Request: {doc.name}"
        for row in ctr_rows:
            ctr.append(
                "line_items",
                {
                    "item_code": row["item_code"],
                    "item_name": row["item_name"],
                    "quantity": row["quantity"],
                    "uom": row["uom"],
                },
            )
        ctr.insert(ignore_permissions=True)
        ctr_name = ctr.name

    if cpr_rows:
        cpr = frappe.new_doc("Material Request")
        cpr.material_request_type = "Purchase"
        cpr.transaction_date = nowdate()
        cpr.schedule_date = add_days(nowdate(), 1)
        cpr.title = f"[CPR] for {doc.name}"
        for row in cpr_rows:
            cpr.append(
                "items",
                {
                    "item_code": row["item_code"],
                    "qty": row["qty"],
                    "uom": row["uom"],
                    "schedule_date": cpr.schedule_date,
                },
            )
        cpr.insert(ignore_permissions=True)
        cpr_name = cpr.name

    doc.db_set("custom_sap_doc_entry", ctr_name or "")
    doc.db_set("custom_sap_doc_num", cpr_name or "")
    _set_state_in_title(doc, "Fulfilling")
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", text=f"Fulfillment decided. CTR: {ctr_name or '-'}, CPR: {cpr_name or '-'}")

    return {"name": doc.name, "status": "Fulfilling", "linked_ctr": ctr_name, "linked_cpr": cpr_name}


def _sync_cmr_fulfillment_from_bg(cmr_name):
    """Called from background jobs (no role check) — syncs CMR fulfillment after CTR/GRN completes."""
    if not cmr_name or not frappe.db.exists("Consumables Material Request", cmr_name):
        return

    cmr = frappe.get_doc("Consumables Material Request", cmr_name)
    by_item = {(row.item_code or "").strip(): 0.0 for row in (cmr.line_items or [])}

    for link in (cmr.transfer_links or []):
        ctr_name = (link.transfer_request or "").strip()
        if not ctr_name or not frappe.db.exists("Consumables Transfer Request", ctr_name):
            continue
        ctr = frappe.get_doc("Consumables Transfer Request", ctr_name)
        if ctr.status in ("Completed", "Received"):
            for li in (ctr.line_items or []):
                code = (li.item_code or "").strip()
                if code:
                    by_item[code] = by_item.get(code, 0.0) + float(li.quantity or 0)
        elif ctr.status == "Partially Received":
            for li in (ctr.line_items or []):
                code = (li.item_code or "").strip()
                if code:
                    received = float(getattr(li, "quantity_received", None) or 0)
                    by_item[code] = by_item.get(code, 0.0) + received

    for link in (cmr.purchase_links or []):
        cpr_name = (link.purchase_request or "").strip()
        if not cpr_name or not frappe.db.exists("Consumables Purchase Request", cpr_name):
            continue
        pr = frappe.get_doc("Consumables Purchase Request", cpr_name)
        cpr_status = (pr.status or "").strip()
        if cpr_status == "Cancelled":
            link.status = "Cancelled"
            continue
        # Only count CPR quantity_received when goods were delivered directly to the
        # requesting plant (no inter-plant transfer needed). When receiving_plant differs
        # from requesting_plant, an auto-CTR is created after GRN and those pcs are
        # already counted through transfer_links above — counting here too would
        # double-count the same pcs, masking partial-receipt shortfalls.
        pr_recv_plant = (getattr(pr, "receiving_plant", None) or "").strip()
        pr_req_plant = (pr.requesting_plant or "").strip()
        cpr_is_direct = not pr_recv_plant or pr_recv_plant == pr_req_plant
        if cpr_is_direct:
            for li in (pr.line_items or []):
                code = (li.item_code or "").strip()
                recv = float(getattr(li, "quantity_received", 0) or 0)
                if code and recv > 0:
                    by_item[code] = by_item.get(code, 0.0) + recv
        if cpr_status == "GRN Done":
            link.status = "GRN Done"
        elif cpr_status == "PO Raised":
            link.status = "PO Raised"
        else:
            link.status = cpr_status or "Submitted"

    total_req = 0.0
    total_recv = 0.0
    any_recv = False
    for row in (cmr.line_items or []):
        code = (row.item_code or "").strip()
        req = float(row.quantity_requested or 0)
        raw_recv = float(by_item.get(code, 0.0))
        recv = min(raw_recv, req) if req > 0 else raw_recv
        by_item[code] = recv
        row.quantity_received = recv
        row.fulfillment_status = (
            "Fulfilled" if req > 0 and recv >= req
            else ("Partially Fulfilled" if recv > 0 else "Pending")
        )
        total_req += req
        total_recv += recv
        if recv > 0:
            any_recv = True

    if total_req > 0 and total_recv >= total_req:
        cmr.status = "Fully Fulfilled"
        cmr.save(ignore_permissions=True)
        _notify_dc_str_mahadevpura_store_managers(
            cmr,
            new_status="Fully Fulfilled",
            message=f"Material request {cmr_name} is fully fulfilled.",
            level="success",
        )
    elif any_recv and (cmr.status or "").strip() in ("Fulfilling", "Under Review", "Submitted", "Partially Fulfilled"):
        cmr.status = "Partially Fulfilled"
        cmr.save(ignore_permissions=True)
        _notify_dc_str_mahadevpura_store_managers(
            cmr,
            new_status="Partially Fulfilled",
            message=f"Material request {cmr_name} is partially fulfilled.",
            level="info",
        )
    else:
        cmr.save(ignore_permissions=True)


@frappe.whitelist()
def sync_fulfillment_status(name):
    require_consumables_role()
    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        assert_plant_access(doc.requesting_plant)
        by_item = {(row.item_code or "").strip(): 0.0 for row in (doc.line_items or [])}

        # Sync transfer link status and received quantities from completed CTR.
        for row in (doc.transfer_links or []):
            link_name = (row.transfer_request or "").strip()
            if not link_name or not frappe.db.exists("Consumables Transfer Request", link_name):
                continue
            ctr = frappe.get_doc("Consumables Transfer Request", link_name)
            row.status = ctr.status or row.status
            if ctr.status in ("Completed", "Received"):
                for li in (ctr.line_items or []):
                    code = (li.item_code or "").strip()
                    if code:
                        by_item[code] = by_item.get(code, 0.0) + float(li.quantity or 0)
            elif ctr.status == "Partially Received":
                for li in (ctr.line_items or []):
                    code = (li.item_code or "").strip()
                    if code:
                        received = float(getattr(li, "quantity_received", None) or 0)
                        by_item[code] = by_item.get(code, 0.0) + received

        _ensure_purchase_request_for_rejected_transfers(doc)

        # Sync purchase link status from linked CPR docs.
        for row in (doc.purchase_links or []):
            link_name = (row.purchase_request or "").strip()
            if not link_name or not frappe.db.exists("Consumables Purchase Request", link_name):
                continue
            pr = frappe.get_doc("Consumables Purchase Request", link_name)
            cpr_status = (pr.status or "").strip()
            if cpr_status == "Cancelled":
                row.status = "Cancelled"
                continue
            # Same double-count guard as in _sync_cmr_fulfillment_from_bg:
            # skip CPR quantity_received when an auto-CTR covers the delivery leg.
            pr_recv_plant = (getattr(pr, "receiving_plant", None) or "").strip()
            pr_req_plant = (pr.requesting_plant or "").strip()
            cpr_is_direct = not pr_recv_plant or pr_recv_plant == pr_req_plant
            if cpr_is_direct:
                for li in (pr.line_items or []):
                    code = (li.item_code or "").strip()
                    recv = float(getattr(li, "quantity_received", 0) or 0)
                    if code and recv > 0:
                        by_item[code] = by_item.get(code, 0.0) + recv
            if cpr_status == "GRN Done":
                row.status = "GRN Done"
            elif cpr_status == "PO Raised":
                row.status = "PO Raised"
            else:
                row.status = cpr_status or "Submitted"

        total_req = 0.0
        total_recv = 0.0
        any_recv = False
        for row in (doc.line_items or []):
            code = (row.item_code or "").strip()
            req = float(row.quantity_requested or 0)
            raw_recv = float(by_item.get(code, 0.0))
            recv = min(raw_recv, req) if req > 0 else raw_recv
            by_item[code] = recv
            row.quantity_received = recv
            row.fulfillment_status = "Fulfilled" if req > 0 and recv >= req else ("Partially Fulfilled" if recv > 0 else "Pending")
            total_req += req
            total_recv += recv
            if recv > 0:
                any_recv = True

        if total_req > 0 and total_recv >= total_req:
            doc.status = "Fully Fulfilled"
            doc.save(ignore_permissions=True)
            _notify_dc_str_mahadevpura_store_managers(
                doc,
                new_status="Fully Fulfilled",
                message=f"Material request {doc.name} is fully fulfilled.",
                level="success",
            )
        elif any_recv and (doc.status or "").strip() in ("Fulfilling", "Under Review", "Submitted"):
            doc.status = "Partially Fulfilled"
            doc.save(ignore_permissions=True)
            _notify_dc_str_mahadevpura_store_managers(
                doc,
                new_status="Partially Fulfilled",
                message=f"Material request {doc.name} is partially fulfilled.",
                level="info",
            )
        return {
            "name": doc.name,
            "status": doc.status or "Under Review",
            "ctr_status": None,
            "cpr_status": None,
            "fulfilled_qty_by_item": by_item,
        }
    sync = _sync_snapshot(doc)
    total_requested = sum(float(row.qty or 0) for row in (doc.items or []))
    total_fulfilled = sum(float(v or 0) for v in (sync["fulfilled_qty_by_item"] or {}).values())
    if total_requested > 0 and total_fulfilled >= total_requested:
        _set_state_in_title(doc, "Fully Fulfilled")
        doc.save(ignore_permissions=True)
        sync["status"] = "Fully Fulfilled"
    elif total_fulfilled > 0:
        _set_state_in_title(doc, "Partially Fulfilled")
        doc.save(ignore_permissions=True)
        sync["status"] = "Partially Fulfilled"
    elif sync["status"] in ("Fulfilling", "Completed"):
        _set_state_in_title(doc, "Fulfilling")
        doc.save(ignore_permissions=True)
    return {
        "name": doc.name,
        "status": sync["status"],
        "ctr_status": sync["ctr_status"],
        "cpr_status": sync["cpr_status"],
        "fulfilled_qty_by_item": sync["fulfilled_qty_by_item"],
    }


@frappe.whitelist()
def confirm_cmr_physical_receipt(name):
    """Destination plant user confirms receipt for all In Transit CTRs linked to this MR."""
    require_consumables_role()
    kind, doc = _get_request_doc(name)
    if kind != "CMR":
        frappe.throw(_("Not a consumables material request."), frappe.ValidationError)
    assert_plant_access(doc.requesting_plant)

    from khanal_tech_integrations.consumables.api.transfers import receive_transfer_request

    req_plant = (doc.requesting_plant or "").strip()
    received = []
    errors = []

    for row in doc.transfer_links or []:
        ctr_name = (row.transfer_request or "").strip()
        if not ctr_name or not frappe.db.exists("Consumables Transfer Request", ctr_name):
            continue
        ctr = frappe.get_doc("Consumables Transfer Request", ctr_name)
        if (ctr.to_plant or "").strip() != req_plant:
            continue
        if (ctr.status or "").strip() != "In Transit":
            continue
        try:
            receive_transfer_request(ctr_name)
            received.append(ctr_name)
        except Exception as e:
            errors.append({"name": ctr_name, "error": str(e)})

    if not received and not errors:
        frappe.throw(
            _(
                "Nothing to receive yet. The transfer must be dispatched (In Transit) before you can confirm receipt here."
            ),
            frappe.ValidationError,
        )

    if errors and not received:
        frappe.throw(_("{0}").format(errors[0].get("error") or "Receipt failed"), frappe.ValidationError)

    cmr = frappe.get_doc("Consumables Material Request", name)
    _notify_managers_super_admins_physical_receipt(cmr, frappe.session.user)
    cmr.add_comment(
        "Comment",
        text=_("Physical receipt confirmed by {0}. Completed transfers: {1}").format(
            frappe.session.user,
            ", ".join(received),
        ),
    )

    out = sync_fulfillment_status(name)
    if isinstance(out, dict):
        out["received_transfers"] = received
        if errors:
            out["receipt_errors"] = errors
    return out


@frappe.whitelist()
def get_destination_plants(from_plant=None):
    require_consumables_role()
    rows = frappe.get_all(
        "Consumables Plant",
        filters={"is_active": 1},
        fields=["name", "plant_code", "plant_name"],
        order_by="plant_code asc",
    )
    source = (from_plant or "").strip()
    return [
        {
            "plant_code": (r.get("plant_code") or r.get("name") or "").strip(),
            "plant_name": (r.get("plant_name") or r.get("plant_code") or r.get("name") or "").strip(),
        }
        for r in rows
        if (r.get("plant_code") or r.get("name") or "").strip()
        and (not source or (r.get("plant_code") or r.get("name") or "").strip() != source)
    ]


@frappe.whitelist()
def approve_material_request(name):
    return start_review(name)


@frappe.whitelist()
def retry_sap_posting(name):
    require_manager_or_admin()
    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        _assert_cmr_reviewer_can_act(doc)
        from khanal_tech_integrations.consumables.api.transfers import retry_sap_posting as retry_transfer_sap_posting

        retried = []
        retry_errors = []
        for row in (doc.transfer_links or []):
            ctr_name = (row.transfer_request or "").strip()
            if not ctr_name or not frappe.db.exists("Consumables Transfer Request", ctr_name):
                continue
            ctr_status = frappe.db.get_value("Consumables Transfer Request", ctr_name, "status")
            if ctr_status != "Failed":
                continue
            try:
                retry_transfer_sap_posting(ctr_name)
                retried.append(ctr_name)
            except Exception as e:
                retry_errors.append({"name": ctr_name, "error": str(e)})

        out = sync_fulfillment_status(name)
        out["retried_ctr"] = retried
        out["retry_errors"] = retry_errors
        return out
    return sync_fulfillment_status(name)


@frappe.whitelist()
def delete_material_request(name):
    require_consumables_role()
    kind, doc = _get_request_doc(name)
    if kind == "CMR":
        if (doc.status or "").strip().lower() != "draft":
            frappe.throw(_("Only Draft request can be deleted."), frappe.ValidationError)
        owner = (doc.requested_by or doc.owner or "").strip()
        if owner and owner != frappe.session.user:
            frappe.throw(_("Only creator can delete draft request."), frappe.PermissionError)
        doc.delete(ignore_permissions=True)
        return {"name": name, "deleted": True}

    if _derive_status(doc).lower() != "draft":
        frappe.throw(_("Only Draft request can be deleted."), frappe.ValidationError)
    owner = (doc.owner or "").strip()
    if owner and owner != frappe.session.user:
        frappe.throw(_("Only creator can delete draft request."), frappe.PermissionError)
    doc.delete(ignore_permissions=True)
    return {"name": name, "deleted": True}


@frappe.whitelist()
def raise_po_from_request(plant_code=None, line_items=None, remarks=""):
    """Create a CPR directly from the New Material Request page and notify Procurement Manager users."""
    require_consumables_role()
    plant_code = _default_requesting_plant(plant_code)
    assert_plant_access(plant_code)

    rows = _parse_line_items(line_items)
    if not rows:
        frappe.throw(_("Add at least one line item."), frappe.ValidationError)

    cpr = frappe.new_doc("Consumables Purchase Request")
    cpr.naming_series = "CPR-.YYYY.-.#####"
    cpr.requesting_plant = plant_code
    cpr.status = "Submitted"
    cpr.requested_by = frappe.session.user
    cpr.requested_on = now_datetime()
    if remarks:
        cpr.remarks = remarks

    for row in rows:
        qty = float(row.get("quantity") or 0)
        if qty <= 0:
            frappe.throw(_("Quantity must be greater than zero for all items."), frappe.ValidationError)
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            frappe.throw(_("Item code is required for all line items."), frappe.ValidationError)
        cpr.append("line_items", {
            "item_code": item_code,
            "item_name": row.get("item_name") or item_code,
            "quantity": qty,
            "uom": row.get("uom") or "",
        })

    cpr.insert(ignore_permissions=True)
    _notify_procurement_managers_po_raised(cpr)
    return {"name": cpr.name, "status": cpr.status}


def _notify_procurement_managers_po_raised(cpr):
    managers = frappe.db.sql(
        """
        SELECT DISTINCT u.name, u.email
        FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
        WHERE u.enabled = 1 AND r.role = 'Consumables Procurement User'
        """,
        as_dict=True,
    )
    plant = cpr.requesting_plant or ""
    requester = frappe.db.get_value("User", cpr.requested_by, "full_name") or cpr.requested_by
    msg = f"New PO request {cpr.name} raised by {requester} for plant {plant}."
    for row in managers:
        user = (row.get("name") or "").strip()
        if not user:
            continue
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Purchase Request",
                "doc_name": cpr.name,
                "new_status": "Submitted",
                "message": msg,
                "level": "info",
            },
            user=user,
        )
        try:
            email = (row.get("email") or "").strip() or user
            item_rows = "".join(
                f"<tr><td style='padding:4px 8px;border-bottom:1px solid #e5e7eb'>{li.item_code}</td>"
                f"<td style='padding:4px 8px;border-bottom:1px solid #e5e7eb'>{li.item_name or ''}</td>"
                f"<td style='padding:4px 8px;border-bottom:1px solid #e5e7eb;text-align:right'>{li.quantity} {li.uom or ''}</td></tr>"
                for li in cpr.line_items
            )
            frappe.sendmail(
                recipients=[email],
                subject=f"[StoreOps] New PO Request — {cpr.name} ({plant})",
                message=(
                    f"<p>A new Purchase Order request has been raised.</p>"
                    f"<ul><li><b>CPR:</b> {cpr.name}</li>"
                    f"<li><b>Plant:</b> {plant}</li>"
                    f"<li><b>Raised by:</b> {requester}</li></ul>"
                    f"<table style='border-collapse:collapse;width:100%'>"
                    f"<thead><tr>"
                    f"<th style='text-align:left;padding:4px 8px;background:#f3f4f6'>Item Code</th>"
                    f"<th style='text-align:left;padding:4px 8px;background:#f3f4f6'>Item Name</th>"
                    f"<th style='text-align:right;padding:4px 8px;background:#f3f4f6'>Qty</th>"
                    f"</tr></thead><tbody>{item_rows}</tbody></table>"
                    f"<p>Please log in to StoreOps to select a vendor and raise the PO in SAP.</p>"
                ),
            )
        except Exception:
            pass
