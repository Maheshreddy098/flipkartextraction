import frappe
from frappe import _
from frappe.utils import now_datetime, cint

from khanal_tech_integrations.consumables.services.role_guard import (
    assert_plant_access,
    get_accessible_plants,
    require_consumables_role,
    require_manager_or_admin,
    require_transfer_module_access,
    require_transfer_approval_access,
    require_transfer_approver,
)


def _attach_item_counts(rows):
    """Add items_count to transfer list rows for list/table display."""
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
        FROM `tabConsumables Transfer Request Item`
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


def _resolve_destination_warehouse(to_plant: str, from_warehouse: str, explicit_to_warehouse: str | None):
    """Pick destination warehouse from destination plant when UI doesn't send one.

    Priority:
    1) explicit value from payload
    2) active Receipt warehouse on destination plant
    3) first active warehouse on destination plant
    """
    if explicit_to_warehouse:
        return explicit_to_warehouse

    plant_doc = frappe.get_doc("Consumables Plant", to_plant)
    rows = list(plant_doc.get("warehouses") or [])
    active = [w for w in rows if cint(getattr(w, "is_active", 1)) == 1]
    if not active:
        frappe.throw(_("No active destination warehouse configured for plant {0}.").format(to_plant), frappe.ValidationError)

    receipt = next((w for w in active if (getattr(w, "warehouse_type", "") or "").strip() == "Receipt"), None)
    chosen = receipt or active[0]
    to_wh = (getattr(chosen, "warehouse_code", "") or "").strip()
    if not to_wh:
        frappe.throw(_("Destination warehouse code is missing for plant {0}.").format(to_plant), frappe.ValidationError)

    if from_warehouse and to_wh == from_warehouse:
        frappe.throw(
            _("Destination warehouse cannot be the same as source warehouse."),
            frappe.ValidationError,
        )
    return to_wh


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_transfer_request(
    from_warehouse=None,
    to_warehouse=None,
    from_plant=None,
    to_plant=None,
    line_items=None,
    remarks="",
):
    require_transfer_module_access()
    if not from_warehouse or not from_plant or not to_plant:
        frappe.throw(_("From warehouse, from plant and to plant are required."), frappe.ValidationError)

    to_warehouse = _resolve_destination_warehouse(to_plant, from_warehouse, to_warehouse)

    assert_plant_access(from_plant)

    if line_items is None:
        line_items = []
    if isinstance(line_items, str):
        import json
        line_items = json.loads(line_items)
    if not line_items:
        frappe.throw(_("Add at least one line item."), frappe.ValidationError)

    doc = frappe.new_doc("Consumables Transfer Request")
    doc.from_plant = from_plant
    doc.from_warehouse = from_warehouse
    doc.to_plant = to_plant
    doc.to_warehouse = to_warehouse
    doc.requested_by = frappe.session.user
    doc.requested_on = now_datetime()
    doc.status = "Draft"
    doc.remarks = remarks

    for item in line_items:
        doc.append("line_items", {
            "item_code": item["item_code"],
            "item_name": item.get("item_name", ""),
            "batch_number": item.get("batch_number", ""),
            "quantity": float(item["quantity"]),
            "uom": item.get("uom", ""),
            "available_quantity": float(item.get("available_quantity", 0)),
        })

    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}

@frappe.whitelist()
def get_destination_plants(from_plant=None):
    """List active destination plants for transfer creation."""
    require_transfer_module_access()

    rows = frappe.get_all(
        "Consumables Plant",
        filters={"is_active": 1},
        fields=["name", "plant_code", "plant_name"],
        order_by="plant_code asc",
    )

    source = (from_plant or "").strip()
    out = []
    for r in rows:
        code = (r.get("plant_code") or r.get("name") or "").strip()
        if not code:
            continue
        if source and code == source:
            continue
        out.append({
            "plant_code": code,
            "plant_name": (r.get("plant_name") or code).strip(),
        })

    return out


@frappe.whitelist()
def get_transfer_request(name):
    require_transfer_module_access()
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)
    return _transfer_to_dict(doc)


@frappe.whitelist()
def get_transfer_requests(status=None, plant_code=None, from_date=None,
                          to_date=None, page=1, page_size=20):
    require_transfer_module_access()

    accessible = get_accessible_plants()
    if not accessible:
        return {"transfers": [], "total": 0}

    plant_filter = "(from_plant IN %(plants)s OR to_plant IN %(plants)s)"
    filters_dict = {"plants": accessible}

    if plant_code:
        assert_plant_access(plant_code)
        plant_filter = "(from_plant = %(plant_code)s OR to_plant = %(plant_code)s)"
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
    
    # Procurement users should only see requests they created.
    if "Consumables Procurement User" in frappe.get_roles():
        plant_filter += " AND requested_by = %(requested_by)s"
        filters_dict["requested_by"] = frappe.session.user

    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    offset = (page - 1) * page_size

    base_query = f"""
        SELECT name, status, from_plant, from_warehouse, to_plant, to_warehouse,
               requested_by, requested_on, submitted_on, approved_on,
               dispatched_on, received_on, remarks
        FROM `tabConsumables Transfer Request`
        WHERE {plant_filter}
        ORDER BY requested_on DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """
    filters_dict["limit"] = page_size
    filters_dict["offset"] = offset

    count_query = f"""
        SELECT COUNT(*) FROM `tabConsumables Transfer Request`
        WHERE {plant_filter}
    """

    rows = frappe.db.sql(base_query, filters_dict, as_dict=True)
    rows = _attach_item_counts(rows)
    total = frappe.db.sql(count_query, filters_dict)[0][0]

    return {"transfers": rows, "total": total, "page": page, "page_size": page_size}


@frappe.whitelist()
def get_pending_receipts():
    """Returns all In Transit transfers where current user's plant is to_plant."""
    require_transfer_module_access()
    accessible = get_accessible_plants()
    if not accessible:
        return {"transfers": []}

    rows = frappe.get_all(
        "Consumables Transfer Request",
        filters={"status": "In Transit", "to_plant": ["in", accessible]},
        fields=["name", "from_plant", "from_warehouse", "to_plant", "to_warehouse",
                "requested_by", "dispatched_on"],
        order_by="dispatched_on asc",
    )
    rows = _attach_item_counts(rows)
    return {"transfers": rows}


# ---------------------------------------------------------------------------
# Lifecycle actions
# ---------------------------------------------------------------------------

@frappe.whitelist()
def submit_transfer_request(name):
    require_transfer_module_access()
    doc = frappe.get_doc("Consumables Transfer Request", name)

    if doc.status != "Draft":
        frappe.throw(_("Only Draft transfers can be submitted."))

    _assert_can_edit(doc)

    doc.status = "Submitted"
    doc.submitted_by = frappe.session.user
    doc.submitted_on = now_datetime()
    doc.save(ignore_permissions=True)

    _notify_managers(doc, "submitted")
    return {"status": doc.status}


@frappe.whitelist()
def approve_transfer_request(name):
    require_transfer_approval_access()
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)

    if doc.status != "Submitted":
        frappe.throw(_("Only Submitted transfers can be approved."))

    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approved_on = now_datetime()
    doc.sap_last_error = None
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    frappe.publish_realtime(
        "storeops_update",
        {
            "doc_type": "Consumables Transfer Request",
            "doc_name": doc.name,
            "new_status": doc.status,
            "message": "Transfer approved. Ready to dispatch.",
            "level": "success",
        },
    )
    return {"status": doc.status}


@frappe.whitelist()
def get_transfer_dispatch_batches(name):
    """Return available batches from the source warehouse for each line item on the CTR."""
    require_manager_or_admin()
    if not frappe.db.exists("Consumables Transfer Request", name):
        frappe.throw(_("Transfer request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)
    warehouse = (doc.from_warehouse or "").strip()
    if not warehouse:
        frappe.throw(_("Source warehouse is not set on this transfer request."), frappe.ValidationError)

    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    from khanal_tech_integrations.consumables.hana.inventory_queries import get_item_batch_detail

    result = []
    try:
        with ConsumablesHANAClient() as client:
            for li in doc.line_items:
                item_code = (li.item_code or "").strip()
                if not item_code:
                    continue
                batches = get_item_batch_detail(client, warehouse, item_code)
                result.append({
                    "item_code": item_code,
                    "item_name": li.item_name or "",
                    "quantity": float(li.quantity or 0),
                    "uom": li.uom or "",
                    "stored_batch": li.batch_number or "",
                    "available_batches": [
                        {
                            "batch_number": b["batch_number"],
                            "quantity": float(b["quantity"] or 0),
                            "expiry_date": str(b["expiry_date"] or "") if b.get("expiry_date") else "",
                        }
                        for b in batches
                    ],
                })
    except Exception as e:
        frappe.log_error(str(e), "get_transfer_dispatch_batches")
        frappe.throw(_("Could not fetch batches from SAP: {0}").format(str(e)[:200]))

    return result


@frappe.whitelist()
def dispatch_transfer_request(name, batch_items=None):
    require_manager_or_admin()
    import json as _json
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)

    if doc.status != "Approved":
        frappe.throw(_("Only Approved transfers can be dispatched."))

    if isinstance(batch_items, str):
        try:
            batch_items = _json.loads(batch_items)
        except Exception:
            batch_items = []
    batch_items = batch_items or []

    # Build per-item splits: {item_code: [{batch_number, quantity}]}
    splits_map = {}
    for b in batch_items:
        code = (b.get("item_code") or "").strip()
        batch = (b.get("batch_number") or "").strip()
        qty = float(b.get("quantity") or 0)
        if code and batch:
            splits_map.setdefault(code, []).append({"batch_number": batch, "quantity": qty})

    missing = []
    extra_rows = []
    for li in doc.line_items:
        code = (li.item_code or "").strip()
        splits = splits_map.get(code)
        if not splits:
            missing.append(code)
        else:
            li.batch_number = splits[0]["batch_number"]
            li.quantity = float(splits[0]["quantity"])
            for sp in splits[1:]:
                extra_rows.append({
                    "item_code": li.item_code,
                    "item_name": li.item_name or "",
                    "batch_number": sp["batch_number"],
                    "quantity": float(sp["quantity"]),
                    "uom": li.uom or "",
                    "available_quantity": float(li.available_quantity or 0),
                })

    if missing:
        frappe.throw(
            _("Batch number is required for all items before dispatch. Missing: {0}").format(", ".join(missing)),
            frappe.ValidationError,
        )

    for row in extra_rows:
        doc.append("line_items", row)

    doc.status = "In Transit"
    doc.dispatched_by = frappe.session.user
    doc.dispatched_on = now_datetime()

    # Post SAP StockTransfer: source warehouse → in-transit (or direct to destination for ATP-HO)
    try:
        from khanal_tech_integrations.consumables.services.sap_transfer import post_stock_transfer_to_intransit
        st_doc_entry, st_doc_num, _used_wh = post_stock_transfer_to_intransit(doc, splits_map)
        doc.sap_transfer_doc_entry = str(st_doc_entry)
        doc.sap_transfer_doc_num = str(st_doc_num)
        doc.sap_last_error = None
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        doc.status = "Failed"
        doc.sap_last_error = str(e)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Transfer Request",
                "doc_name": doc.name,
                "new_status": doc.status,
                "message": f"SAP stock transfer posting failed at dispatch: {str(e)[:300]}",
                "level": "error",
            },
        )
        frappe.throw(_("SAP stock transfer posting failed: {0}").format(str(e)[:300]))

    _notify_destination_plant(doc)
    try:
        from khanal_tech_integrations.consumables.api.notifications import notify_ctr_dispatched
        frappe.enqueue(notify_ctr_dispatched, queue="short", ctr_name=doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Email notify: CTR dispatched {doc.name}")
    frappe.publish_realtime(
        "storeops_update",
        {
            "doc_type": "Consumables Transfer Request",
            "doc_name": doc.name,
            "new_status": doc.status,
            "message": "Transfer dispatched to destination warehouse for receipt confirmation.",
            "level": "success",
        },
    )
    # Also notify the linked CMR page so it refreshes and shows the Confirm Receipt button
    cmr_ref = (getattr(doc, "cmr_reference", None) or "").strip()
    if cmr_ref:
        frappe.publish_realtime(
            "storeops_update",
            {"doc_type": "Consumables Material Request", "doc_name": cmr_ref, "new_status": "In Transit"},
        )
    return {"status": doc.status}


@frappe.whitelist()
def receive_transfer_request(name, received_items=None, receipt_notes="", reject_delivery=0):
    import json as _json
    require_transfer_module_access()
    doc = frappe.get_doc("Consumables Transfer Request", name)

    if doc.status != "In Transit":
        frappe.throw(_("Only In Transit transfers can be confirmed received."))

    accessible = get_accessible_plants()
    if doc.to_plant not in accessible:
        frappe.throw(_("Only the destination plant can confirm receipt."), frappe.PermissionError)

    # Parse received quantities {row_index: qty}
    qty_map = {}
    if received_items:
        if isinstance(received_items, str):
            try:
                received_items = _json.loads(received_items)
            except Exception:
                received_items = []
        for r in (received_items or []):
            idx = r.get("row_index")
            qty = float(r.get("quantity_received") or 0)
            if idx is not None:
                qty_map[int(idx)] = qty

    notes = (receipt_notes or "").strip()
    reject_delivery = str(reject_delivery).lower() in ("1", "true", "yes", "on")

    # Receipt confirmation is exact-match only. Short or excess delivery must be rejected.
    line_receipts = []
    mismatched_items = []
    total_dispatched = 0.0
    total_received = 0.0
    for idx, li in enumerate(doc.line_items):
        dispatched = float(li.quantity or 0)
        received = float(qty_map.get(idx, dispatched))
        if received < -0.0001:
            frappe.throw(_("Received quantity cannot be negative."))
        total_dispatched += dispatched
        total_received += received
        line_receipts.append((idx, li, dispatched, received))
        if abs(received - dispatched) > 0.0001:
            mismatched_items.append({
                "item_code": (li.item_code or "").strip(),
                "dispatched": dispatched,
                "received": received,
            })
    is_full_rejection = total_received <= 0
    if reject_delivery and not notes:
        frappe.throw(_("Rejection reason is required."))
    if mismatched_items and not is_full_rejection and not reject_delivery:
        details = ", ".join(
            f"{row['item_code']}: received {row['received']} of {row['dispatched']}"
            for row in mismatched_items[:5]
        )
        frappe.throw(
            _("Received quantity must exactly match dispatched quantity. Reject the delivery if quantities differ. {0}")
            .format(details),
            frappe.ValidationError,
        )
    # --- Rejection at receipt (quantity mismatch or nothing received) ---
    if reject_delivery or is_full_rejection:
        rejection_text = notes or "Delivery rejected at receipt — nothing physically received."
        for idx, li, dispatched, received in line_receipts:
            li.quantity_dispatched = dispatched
            li.quantity_received = received if reject_delivery else 0.0
        doc.status = "Rejected"
        doc.rejection_reason = rejection_text
        doc.receipt_notes = rejection_text
        doc.received_by = frappe.session.user
        doc.received_on = now_datetime()
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        _notify_source_manager_on_receipt(doc, rejected=True)
        try:
            from khanal_tech_integrations.consumables.api.notifications import notify_ctr_received
            frappe.enqueue(notify_ctr_received, queue="short", ctr_name=doc.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Email notify: CTR rejected at receipt {doc.name}")
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Transfer Request",
                "doc_name": doc.name,
                "new_status": doc.status,
                "message": f"Transfer {doc.name} rejected at receipt by {doc.to_plant}. Reason: {rejection_text[:200]}",
                "level": "warning",
            },
        )
        cmr_ref = (getattr(doc, "cmr_reference", None) or "").strip()
        if cmr_ref:
            try:
                from khanal_tech_integrations.consumables.api.material_requests import _sync_cmr_fulfillment_from_bg
                _sync_cmr_fulfillment_from_bg(cmr_name=cmr_ref)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Auto-sync CMR {cmr_ref} after CTR rejection at receipt")
        return {
            "status": doc.status,
            "received": total_received if reject_delivery else 0,
            "dispatched": total_dispatched,
        }

    # --- Partial or full receipt: post second SAP StockTransfer (in-transit → destination) ---
    from khanal_tech_integrations.consumables.services.sap_transfer import post_intransit_to_final_transfer

    try:
        final_doc_entry, final_doc_num = post_intransit_to_final_transfer(doc)
        if final_doc_entry:
            # Store second transfer doc entry in sap_transfer_request_doc_entry (repurposed)
            doc.sap_transfer_request_doc_entry = str(final_doc_entry)
            doc.sap_transfer_request_doc_num = str(final_doc_num)
        doc.sap_last_error = None

        shortfall_items = []
        for idx, li, dispatched, received in line_receipts:
            li.quantity_dispatched = dispatched
            li.quantity_received = received
            shortfall = dispatched - received
            if shortfall > 0.0001:
                shortfall_items.append({
                    "item_code": (li.item_code or "").strip(),
                    "item_name": li.item_name or "",
                    "qty": shortfall,
                    "uom": li.uom or "",
                })

        doc.receipt_notes = notes
        doc.received_by = frappe.session.user
        doc.received_on = now_datetime()
        doc.status = "Completed"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        doc.status = "Failed"
        doc.sap_last_error = str(e)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.throw(_("SAP stock transfer posting failed during receipt: {0}").format(str(e)[:300]))

    # Auto-create CPR for shortfall items
    cmr_ref = (getattr(doc, "cmr_reference", None) or "").strip()
    if shortfall_items and cmr_ref:
        try:
            _create_shortfall_cpr(cmr_ref, shortfall_items, doc.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Create shortfall CPR for {doc.name}")

    _notify_source_manager_on_receipt(doc, partial=False)
    try:
        from khanal_tech_integrations.consumables.api.notifications import notify_ctr_received
        frappe.enqueue(notify_ctr_received, queue="short", ctr_name=doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Email notify: CTR received {doc.name}")
    frappe.publish_realtime(
        "storeops_update",
        {
            "doc_type": "Consumables Transfer Request",
            "doc_name": doc.name,
            "new_status": doc.status,
            "message": "Transfer received and SAP stock transfer completed.",
            "level": "success",
        },
    )

    if cmr_ref:
        try:
            from khanal_tech_integrations.consumables.api.material_requests import _sync_cmr_fulfillment_from_bg
            _sync_cmr_fulfillment_from_bg(cmr_name=cmr_ref)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Auto-sync CMR {cmr_ref} after CTR receipt failed")

    try:
        from khanal_tech_integrations.consumables.api.procurement import on_ctr_completed_for_cpr
        on_ctr_completed_for_cpr(doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"on_ctr_completed_for_cpr failed for {doc.name}")

    return {
        "status": doc.status,
        "received": total_received,
        "dispatched": total_dispatched,
        "shortfall_items": [i["item_code"] for i in shortfall_items],
    }


def _create_shortfall_cpr(cmr_name, shortfall_items, ctr_name):
    """Create a purchase request on the CMR for items short-received from a CTR."""
    if not frappe.db.exists("Consumables Material Request", cmr_name):
        return
    cmr = frappe.get_doc("Consumables Material Request", cmr_name)
    cpr = frappe.new_doc("Consumables Purchase Request")
    cpr.naming_series = "CPR-.YYYY.-.#####"
    cpr.cmr_reference = cmr_name
    cpr.requesting_plant = cmr.requesting_plant
    cpr.status = "Submitted"
    cpr.requested_by = (getattr(cmr, "requested_by", None) or cmr.owner or "").strip()
    cpr.requested_on = now_datetime()
    for row in shortfall_items:
        cpr.append("line_items", {
            "item_code": row["item_code"],
            "item_name": row.get("item_name") or row["item_code"],
            "quantity": row["qty"],
            "uom": row.get("uom") or "",
        })
    cpr.insert(ignore_permissions=True)
    if hasattr(cmr, "purchase_links"):
        cmr.append("purchase_links", {
            "purchase_request": cpr.name,
            "quantity": sum(float(r["qty"] or 0) for r in shortfall_items),
            "status": "Submitted",
        })
    cmr.save(ignore_permissions=True)
    cmr.add_comment("Comment", text=f"Shortfall CPR {cpr.name} raised after partial receipt of CTR {ctr_name}.")
    try:
        from khanal_tech_integrations.consumables.api.notifications import notify_cpr_created
        frappe.enqueue(notify_cpr_created, queue="short", cpr_name=cpr.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Email notify: shortfall CPR created {cpr.name}")


@frappe.whitelist()
def reject_transfer_request(name, rejection_reason=""):
    require_transfer_approval_access()
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)

    if doc.status not in ("Submitted", "Approved"):
        frappe.throw(_("Only Submitted or Approved transfers can be rejected."))

    if not rejection_reason:
        frappe.throw(_("Rejection reason is required."))

    doc.status = "Rejected"
    doc.rejection_reason = rejection_reason
    doc.save(ignore_permissions=True)

    _notify_requester(doc, "rejected", rejection_reason)
    return {"status": doc.status}


@frappe.whitelist()
def retry_sap_posting(name):
    """Re-enqueue the SAP background job for a Failed transfer."""
    require_manager_or_admin()
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)

    if doc.status != "Failed":
        frappe.throw(_("Only Failed transfers can be retried."))

    doc.sap_last_error = None
    doc.sap_retry_count = (doc.sap_retry_count or 0) + 1
    doc.status = "In Transit" if doc.sap_transfer_doc_entry else "Approved"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": doc.status, "message": "Retry initiated — re-dispatch or re-approve to repost to SAP."}


@frappe.whitelist()
def download_delivery_challan(name, doc_number):
    """Fetch delivery challan PDF (base64) from SAP Crystal Reports for a CTR.

    doc_number: the SAP DocEntry of the dispatch stock transfer (sap_transfer_doc_entry).
    Returns base64-encoded PDF — frontend converts to Blob and triggers browser download.
    """
    from khanal_tech_integrations.consumables.services.role_guard import (
        require_consumables_role,
        assert_plant_access,
    )
    from khanal_tech_integrations.consumables.services.crystal_reports import get_delivery_challan_base64

    require_consumables_role()
    doc = frappe.get_doc("Consumables Transfer Request", name)
    _assert_transfer_visible(doc)

    doc_number = (str(doc_number) or "").strip()
    if not doc_number:
        frappe.throw(_("Doc number is required to export delivery challan."), frappe.ValidationError)

    base64_pdf = get_delivery_challan_base64(doc_number)
    return {"base64": base64_pdf, "filename": f"DeliveryChallan_{name}.pdf"}




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_transfer_visible(doc):
    accessible = get_accessible_plants()
    if "Consumables Procurement User" in frappe.get_roles() and doc.requested_by != frappe.session.user:
        frappe.throw(_("You do not have access to this transfer request."), frappe.PermissionError)
    if doc.from_plant not in accessible and doc.to_plant not in accessible:
        frappe.throw(_("You do not have access to this transfer request."), frappe.PermissionError)


def _assert_can_edit(doc):
    roles = frappe.get_roles()
    is_manager = any(r in roles for r in ("Consumables Store Manager", "Consumables Super Admin"))
    if not is_manager and doc.requested_by != frappe.session.user:
        frappe.throw(_("You can only submit your own transfer requests."), frappe.PermissionError)


def _transfer_to_dict(doc):
    return {
        "name": doc.name,
        "status": doc.status,
        "from_plant": doc.from_plant,
        "from_warehouse": doc.from_warehouse,
        "to_plant": doc.to_plant,
        "to_warehouse": doc.to_warehouse,
        "requested_by": doc.requested_by,
        "requested_on": str(doc.requested_on or ""),
        "submitted_by": doc.submitted_by,
        "submitted_on": str(doc.submitted_on or ""),
        "approved_by": doc.approved_by,
        "approved_on": str(doc.approved_on or ""),
        "dispatched_by": doc.dispatched_by,
        "dispatched_on": str(doc.dispatched_on or ""),
        "received_by": doc.received_by,
        "received_on": str(doc.received_on or ""),
        "remarks": doc.remarks,
        "rejection_reason": doc.rejection_reason,
        "receipt_notes": getattr(doc, "receipt_notes", "") or "",
        "sap_transfer_request_doc_entry": doc.sap_transfer_request_doc_entry,
        "sap_transfer_request_doc_num": doc.sap_transfer_request_doc_num,
        "sap_transfer_doc_entry": doc.sap_transfer_doc_entry,
        "sap_transfer_doc_num": doc.sap_transfer_doc_num,
        "sap_last_error": doc.sap_last_error,
        "sap_retry_count": doc.sap_retry_count or 0,
        "line_items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "batch_number": item.batch_number,
                "quantity": item.quantity,
                "quantity_dispatched": float(getattr(item, "quantity_dispatched", None) or item.quantity or 0),
                "quantity_received": float(getattr(item, "quantity_received", None) or 0),
                "uom": item.uom,
                "available_quantity": item.available_quantity,
            }
            for item in doc.line_items
        ],
    }


def _notify_managers(doc, event):
    managers = _get_plant_managers(doc.from_plant)
    for user in managers:
        if user == frappe.session.user:
            continue
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Transfer Request",
                "doc_name": doc.name,
                "new_status": "Submitted",
                "message": f"Transfer request {doc.name} submitted for approval.",
                "level": "info",
            },
            user=user,
        )


def _notify_destination_plant(doc):
    dest_users = _get_plant_users(doc.to_plant)
    for user in dest_users:
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Transfer Request",
                "doc_name": doc.name,
                "new_status": "In Transit",
                "message": (
                    f"Incoming transfer {doc.name} from {doc.from_plant}. "
                    "Please confirm receipt when the stock arrives."
                ),
                "level": "info",
            },
            user=user,
        )


def _notify_source_manager_on_receipt(doc, partial=False, rejected=False):
    managers = _get_plant_managers(doc.from_plant)
    if rejected:
        msg = f"Transfer {doc.name} was REJECTED at receipt by {doc.to_plant}. Reason: {doc.rejection_reason or '—'}"
        level = "error"
    elif partial:
        msg = f"Transfer {doc.name} was PARTIALLY received by {doc.to_plant}. A purchase order has been raised for the shortfall."
        level = "warning"
    else:
        msg = f"Destination plant {doc.to_plant} confirmed full receipt of transfer {doc.name}."
        level = "success"
    for user in managers:
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Transfer Request",
                "doc_name": doc.name,
                "new_status": doc.status,
                "message": msg,
                "level": level,
            },
            user=user,
        )


def _notify_requester(doc, event, reason=""):
    frappe.publish_realtime(
        "storeops_update",
        {
            "doc_type": "Consumables Transfer Request",
            "doc_name": doc.name,
            "new_status": doc.status,
            "message": f"Transfer request {doc.name} was {event}. Reason: {reason}",
            "level": "warning",
        },
        user=doc.requested_by,
    )


def _get_plant_managers(plant_code):
    users = frappe.get_all(
        "Consumables User Plant",
        filters={"plant": plant_code, "is_active": 1},
        fields=["user"],
    )
    managers = []
    for u in users:
        roles = frappe.get_roles(u.user)
        if any(r in roles for r in ("Consumables Store Manager", "Consumables Inventory Manager", "Consumables Super Admin")):
            managers.append(u.user)
    return managers


def _get_plant_users(plant_code):
    users = frappe.get_all(
        "Consumables User Plant",
        filters={"plant": plant_code, "is_active": 1},
        fields=["user"],
    )
    return [u.user for u in users]
