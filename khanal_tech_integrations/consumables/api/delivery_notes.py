import json

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, today

from khanal_tech_integrations.consumables.services.role_guard import (
    assert_plant_access,
    get_accessible_plants,
    require_consumables_role,
    require_manager_or_admin,
    require_super_admin,
)

BACKDATE_MAX_DAYS = 30


def _validate_doc_date(doc_date, remarks):
    resolved = getdate(doc_date)
    todays = getdate(today())

    if resolved > todays:
        frappe.throw(_("Delivery date cannot be in the future."))

    if resolved < getdate(add_days(todays, -BACKDATE_MAX_DAYS)):
        frappe.throw(_(
            "Delivery date cannot be more than {0} days in the past."
        ).format(BACKDATE_MAX_DAYS))

    if resolved != todays and not (remarks or "").strip():
        frappe.throw(_("Remarks are required when backdating a delivery note."))


def _parse_fefo_batches(raw):
    try:
        batches = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        frappe.log_error(f"Malformed fefo_batches value: {raw!r}", "DeliveryNote fefo_batches parse error")
        return []
    return [
        {
            "batch_code": b.get("batch") or b.get("batch_code") or "",
            "batch": b.get("batch") or b.get("batch_code") or "",
            "quantity": b.get("qty") or b.get("quantity") or 0,
            "qty": b.get("qty") or b.get("quantity") or 0,
            "expiry_date": b.get("expiry_date") or b.get("expiry") or "",
        }
        for b in batches
    ]


def _attach_item_counts(rows):
    """Add items_count to delivery list rows for list/table display."""
    if not rows:
        return rows

    names = [r.get("name") for r in rows if r.get("name")]
    if not names:
        for r in rows:
            r["items_count"] = 0
        return rows

    counts = frappe.db.sql(
        """
        SELECT parent, COUNT(*) AS c
        FROM `tabConsumables Delivery Note Item`
        WHERE parent IN %(parents)s
        GROUP BY parent
        """,
        {"parents": tuple(names)},
        as_dict=True,
    )
    by_parent = {c.get("parent"): int(c.get("c") or 0) for c in counts}
    for r in rows:
        r["items_count"] = by_parent.get(r.get("name"), 0)
    return rows


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_delivery_note(
    plant_code,
    warehouse_code,
    line_items,
    purpose,
    remarks="",
    card_name="",
    doc_date=None,
    doc_due_date=None,
    series="",
    ship_to_code="",
    bill_to_code="",
    address="",
    sap_customer_code="",
):
    require_consumables_role()
    assert_plant_access(plant_code)

    if isinstance(line_items, str):
        line_items = json.loads(line_items)

    if not line_items:
        frappe.throw(_("At least one line item is required."))

    customer_code = _resolve_delivery_customer_code(plant_code, sap_customer_code)
    address_code = (ship_to_code or "").strip() or (bill_to_code or "").strip()

    resolved_doc_date = doc_date or today()
    _validate_doc_date(resolved_doc_date, remarks)

    doc = frappe.new_doc("Consumables Delivery Note")
    doc.plant = plant_code
    doc.warehouse = warehouse_code
    doc.purpose = purpose
    doc.remarks = remarks
    doc.requested_by = frappe.session.user
    doc.requested_on = now_datetime()
    doc.status = "Draft"
    doc.sap_customer_code = customer_code
    doc.card_name = card_name or ""
    doc.doc_date = resolved_doc_date
    doc.doc_due_date = doc_due_date or doc.doc_date
    doc.series = series or ""
    doc.ship_to_code = address_code
    doc.bill_to_code = address_code
    doc.address = address or ""

    for item in line_items:
        qty = float(item.get("requested_quantity") or item.get("quantity") or 0)
        if qty <= 0:
            frappe.throw(_("Quantity must be greater than zero for item {0}.").format(item.get("item_code")))
        doc.append("line_items", {
            "item_code": item["item_code"],
            "item_name": item.get("item_name", ""),
            "requested_quantity": qty,
            "uom": item.get("uom", ""),
            "unit_price": float(item.get("unit_price") or 0),
            "tax_code": item.get("tax_code", ""),
            "account_code": item.get("account_code", ""),
            "fefo_batches": "[]",
            "total_allocated_quantity": 0.0,
            "fefo_status": "Pending",
        })

    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def post_delivery_note(
    plant_code,
    warehouse_code,
    line_items,
    purpose,
    remarks="",
    card_name="",
    doc_date=None,
    doc_due_date=None,
    series="",
    ship_to_code="",
    bill_to_code="",
    address="",
    sap_customer_code="",
):
    frappe.logger().info(
        f"post_delivery_note called: plant={plant_code}, warehouse={warehouse_code}, purpose={purpose}, user={frappe.session.user}"
    )
    try:
        created = create_delivery_note(
            plant_code=plant_code,
            warehouse_code=warehouse_code,
            line_items=line_items,
            purpose=purpose,
            remarks=remarks,
            card_name=card_name,
            doc_date=doc_date,
            doc_due_date=doc_due_date,
            series=series,
            ship_to_code=ship_to_code,
            bill_to_code=bill_to_code,
            address=address,
            sap_customer_code=sap_customer_code,
        )
        posted = submit_delivery_note(created["name"])
        if posted.get("status") != "Posted":
            error_message = posted.get("sap_last_error") or posted.get("status") or _(
                "Delivery note was not posted to SAP."
            )
            frappe.logger().error(
                f"post_delivery_note failed: {error_message} for delivery note {created['name']}"
            )
            frappe.throw(
                _(f"Delivery note was not posted to SAP: {error_message}"),
                frappe.ValidationError,
            )
        return {"name": created["name"], **posted}
    except Exception as e:
        frappe.logger().error(
            f"post_delivery_note exception: {str(e)}",
            exc_info=True,
        )
        raise


@frappe.whitelist()
def get_delivery_note(name):
    require_consumables_role()
    doc = frappe.get_doc("Consumables Delivery Note", name)
    assert_plant_access(doc.plant)
    return _delivery_to_dict(doc)


@frappe.whitelist()
def get_delivery_notes(status=None, plant_code=None, from_date=None,
                       to_date=None, page=1, page_size=20):
    require_consumables_role()

    accessible = get_accessible_plants()
    if not accessible:
        return {"delivery_notes": [], "total": 0}

    plant_filter = "plant IN %(plants)s"
    filters_dict = {"plants": accessible}

    if plant_code:
        assert_plant_access(plant_code)
        plant_filter = "plant = %(plant_code)s"
        filters_dict["plant_code"] = plant_code

    if status:
        plant_filter += " AND status = %(status)s"
        filters_dict["status"] = status

    if from_date:
        plant_filter += " AND requested_on >= %(from_date)s"
        filters_dict["from_date"] = from_date

    if to_date:
        plant_filter += " AND requested_on <= %(to_date)s"
        filters_dict["to_date"] = to_date

    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    offset = (page - 1) * page_size
    filters_dict["limit"] = page_size
    filters_dict["offset"] = offset

    rows = frappe.db.sql(f"""
        SELECT name, status, plant, warehouse, purpose,
               requested_by, requested_on, approved_by, approved_on,
               sap_doc_num, remarks, doc_date
        FROM `tabConsumables Delivery Note`
        WHERE {plant_filter}
        ORDER BY requested_on DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, filters_dict, as_dict=True)
    rows = _attach_item_counts(rows)

    total = frappe.db.sql(f"""
        SELECT COUNT(*) FROM `tabConsumables Delivery Note`
        WHERE {plant_filter}
    """, filters_dict)[0][0]

    return {"delivery_notes": rows, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Lifecycle actions
# ---------------------------------------------------------------------------

@frappe.whitelist()
def submit_delivery_note(name):
    require_consumables_role()
    doc = frappe.get_doc("Consumables Delivery Note", name)
    assert_plant_access(doc.plant)

    frappe.logger().info(
        f"submit_delivery_note called: name={name}, status={doc.status}, user={frappe.session.user}"
    )

    if doc.status != "Draft":
        frappe.throw(_("Only Draft delivery notes can be submitted."))

    if doc.requested_by != frappe.session.user:
        roles = frappe.get_roles()
        if not any(r in roles for r in ("Consumables Store Manager", "Consumables Super Admin")):
            frappe.throw(_("You can only submit your own delivery notes."), frappe.PermissionError)

    if not doc.sap_customer_code:
        frappe.throw(_(
            "No SAP customer code configured for plant {0}. "
            "Please set the delivery customer code in plant settings."
        ).format(doc.plant))

    from khanal_tech_integrations.consumables.services.fefo import (
        InsufficientStockError,
        run_fefo_for_delivery_note,
    )

    try:
        run_fefo_for_delivery_note(doc)
    except InsufficientStockError as e:
        doc.status = "Failed"
        doc.sap_last_error = f"[FIFO] {str(e)}"
        doc.submitted_by = frappe.session.user
        doc.submitted_on = now_datetime()
        doc.save(ignore_permissions=True)
        frappe.throw(_(str(e)))

    doc.submitted_by = frappe.session.user
    doc.submitted_on = now_datetime()
    doc.sap_posting_date = today()
    doc.save(ignore_permissions=True)

    # Post immediately — deterministic outcome without background worker dependency.
    _post_delivery_note_to_sap(name)
    doc.reload()
    return {
        "status": doc.status,
        "sap_doc_num": doc.sap_doc_num,
        "sap_last_error": doc.sap_last_error,
    }


@frappe.whitelist()
def retry_sap_posting(name):
    """Re-attempt SAP posting for a Failed delivery note (SAP errors only, not stock errors)."""
    require_manager_or_admin()
    doc = frappe.get_doc("Consumables Delivery Note", name)

    if doc.status != "Failed":
        frappe.throw(_("Only Failed delivery notes can be retried."))

    if doc.sap_last_error and doc.sap_last_error.startswith("[FIFO]"):
        frappe.throw(_(
            "This delivery note failed due to insufficient stock, not a SAP error. "
            "Please create a new one with corrected quantities."
        ))

    for item in doc.line_items:
        if item.fefo_status != "Allocated":
            frappe.throw(_(
                "Batch allocation is incomplete for item {0}. Cannot retry SAP posting."
            ).format(item.item_code))

    doc.sap_last_error = None
    doc.save(ignore_permissions=True)

    frappe.enqueue(
        "khanal_tech_integrations.consumables.api.delivery_notes._post_delivery_note_to_sap",
        queue="long",
        job_name=f"sap_delivery_note_retry_{name}",
        doc_name=name,
    )
    return {"status": doc.status}


@frappe.whitelist()
def cancel_delivery_note(name):
    """Cancel an already-Posted delivery note's live SAP document. Super
    Admin only. Deliberately does NOT repost — see
    repost_cancelled_delivery_note() — so cancel and repost are always two
    separate, deliberate clicks rather than one combined action.
    """
    require_super_admin()
    doc = frappe.get_doc("Consumables Delivery Note", name)
    assert_plant_access(doc.plant)

    if doc.status != "Posted":
        frappe.throw(_("Only Posted delivery notes can be cancelled."))
    if not doc.sap_doc_entry:
        frappe.throw(_("This delivery note has no SAP document to cancel."))

    from khanal_tech_integrations.unicommerce.client.sap import SAPClient

    old_doc_entry = doc.sap_doc_entry
    old_doc_num = doc.sap_doc_num

    client = SAPClient()
    client.cancel_delivery_note(old_doc_entry)

    doc.sap_doc_entry = None
    doc.sap_doc_num = None
    doc.sap_last_error = None
    doc.status = "Cancelled"
    note = (
        f"[{now_datetime()}] Cancelled SAP DeliveryNote DocEntry {old_doc_entry} "
        f"(DocNum {old_doc_num}) by {frappe.session.user}. Awaiting manual repost."
    )
    doc.remarks = f"{doc.remarks}\n{note}" if doc.remarks else note
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": doc.status,
        "cancelled_doc_entry": old_doc_entry,
        "cancelled_doc_num": old_doc_num,
    }


@frappe.whitelist()
def repost_cancelled_delivery_note(name):
    """Repost a Cancelled delivery note to SAP as a fresh document. Super
    Admin only. Reuses the SAME line items, quantities and FEFO batch
    allocations already on the doc (no re-run of FEFO), so the only thing
    that changes on repost is whatever server-side logic changed since the
    original posting (e.g. AcctCode).
    """
    require_super_admin()
    doc = frappe.get_doc("Consumables Delivery Note", name)
    assert_plant_access(doc.plant)

    if doc.status != "Cancelled":
        frappe.throw(_("Only Cancelled delivery notes can be reposted."))
    if doc.sap_doc_entry:
        frappe.throw(_("This delivery note already has a SAP document."))

    _post_delivery_note_to_sap(name)
    doc.reload()
    return {
        "status": doc.status,
        "sap_doc_num": doc.sap_doc_num,
        "sap_last_error": doc.sap_last_error,
    }


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------

def _post_delivery_note_to_sap(doc_name):
    from khanal_tech_integrations.consumables.services.sap_delivery import (
        post_delivery_note_to_sap,
    )

    doc = frappe.get_doc("Consumables Delivery Note", doc_name)
    if doc.sap_doc_entry:
        return

    try:
        results, skipped_lines = post_delivery_note_to_sap(doc)
    except Exception as e:
        doc.status = "Failed"
        error_str = str(e)
        doc.sap_last_error = error_str
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Delivery Note",
                "doc_name": doc_name,
                "new_status": "Failed",
                "message": f"SAP posting failed: {error_str[:800]}",
                "level": "error",
            },
            user=doc.requested_by,
        )
        return

    # SAP has already created real documents by this point (or genuinely held
    # some lines back) — anything that goes wrong from here on is OUR OWN
    # bookkeeping, not a SAP failure, and must never be allowed to erase or
    # hide the DocEntries SAP already created. A stale-timestamp save conflict
    # is recovered by reloading and retrying the SAME real results — it is
    # never treated as if the SAP posting itself had failed.
    try:
        doc.status = "Posted"
        doc.sap_doc_entry = ",".join(str(r[0]) for r in results)
        doc.sap_doc_num = ",".join(str(r[1]) for r in results)
        doc.sap_last_error = "\n".join(skipped_lines) if skipped_lines else None
        doc.save(ignore_permissions=True)
    except Exception:
        doc = frappe.get_doc("Consumables Delivery Note", doc_name)
        doc.status = "Posted"
        doc.sap_doc_entry = ",".join(str(r[0]) for r in results)
        doc.sap_doc_num = ",".join(str(r[1]) for r in results)
        doc.sap_last_error = "\n".join(skipped_lines) if skipped_lines else None
        doc.save(ignore_permissions=True)

    frappe.db.commit()

    doc_nums = doc.sap_doc_num
    success_msg = f"Delivery Note {doc_name} posted to SAP successfully. SAP#: {doc_nums}"

    frappe.publish_realtime(
        "storeops_update",
        {
            "doc_type": "Consumables Delivery Note",
            "doc_name": doc_name,
            "new_status": "Posted",
            "message": success_msg,
            "level": "success",
        },
        user=doc.requested_by,
    )




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _delivery_to_dict(doc):
    return {
        "name": doc.name,
        "status": doc.status,
        "plant": doc.plant,
        "warehouse": doc.warehouse,
        "purpose": doc.purpose,
        "requested_by": doc.requested_by,
        "requested_on": str(doc.requested_on or ""),
        "submitted_by": doc.submitted_by,
        "submitted_on": str(doc.submitted_on or ""),
        "approved_by": doc.approved_by,
        "approved_on": str(doc.approved_on or ""),
        "remarks": doc.remarks,
        "rejection_reason": doc.rejection_reason,
        "sap_customer_code": doc.sap_customer_code,
        "card_name": doc.card_name,
        "doc_date": str(doc.doc_date or ""),
        "doc_due_date": str(doc.doc_due_date or ""),
        "series": doc.series,
        "ship_to_code": doc.ship_to_code,
        "bill_to_code": doc.bill_to_code,
        "address": doc.address,
        "sap_doc_entry": doc.sap_doc_entry,
        "sap_doc_num": doc.sap_doc_num,
        "sap_posting_date": str(doc.sap_posting_date or ""),
        "sap_last_error": doc.sap_last_error,
        "line_items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "requested_quantity": item.requested_quantity,
                "uom": item.uom,
                "unit_price": item.unit_price,
                "tax_code": item.tax_code,
                "account_code": item.account_code,
                "fefo_batches": _parse_fefo_batches(item.fefo_batches),
                "total_allocated_quantity": item.total_allocated_quantity,
                "fefo_status": item.fefo_status,
            }
            for item in doc.line_items
        ],
    }



def _resolve_delivery_customer_code(plant_code, explicit_customer_code=""):
    explicit = (explicit_customer_code or "").strip()
    if explicit:
        return explicit

    plant_doc = frappe.get_doc("Consumables Plant", plant_code)
    plant_level = (plant_doc.delivery_customer_code or "").strip()
    if plant_level:
        return plant_level

    settings_default = (
        frappe.db.get_single_value("Consumables Settings", "default_delivery_customer") or ""
    ).strip()
    if settings_default:
        return settings_default

    return _derive_delivery_customer_code_by_plant(plant_doc)


_PLANT_CUSTOMER_CODE = {
    'KG-STR': 'C03604',  # Krishnagiri, Tamil Nadu
}
_DEFAULT_CUSTOMER_CODE = 'C03327'  # Karnataka plants


def _derive_delivery_customer_code_by_plant(plant_doc):
    plant_code = str(getattr(plant_doc, "plant_code", "") or "").strip()
    return _PLANT_CUSTOMER_CODE.get(plant_code, _DEFAULT_CUSTOMER_CODE)
