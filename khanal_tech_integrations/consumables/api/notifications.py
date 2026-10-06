import uuid

import frappe
from frappe.utils import get_url


def _emails_with_role(role):
    """Return email addresses of all enabled users holding the given role (single query)."""
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.email
        FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
        WHERE u.enabled = 1 AND r.role = %s AND u.email != ''
        """,
        role,
        as_dict=True,
    )
    return [(row.email or "").strip() for row in rows if (row.email or "").strip()]


def _get_inventory_managers():
    """Enabled users with the Inventory Manager role."""
    return _emails_with_role("Consumables Inventory Manager")


def _get_plant_store_managers(plant_code):
    """Store Managers assigned to a specific plant via Consumables User Plant."""
    if not plant_code:
        return []
    plant_users = frappe.get_all(
        "Consumables User Plant",
        filters={"plant": plant_code, "is_active": 1},
        fields=["user"],
    )
    if not plant_users:
        return []
    user_names = [(row.get("user") or "").strip() for row in plant_users if (row.get("user") or "").strip()]
    if not user_names:
        return []
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.email
        FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
        WHERE u.enabled = 1 AND r.role = 'Consumables Store Manager'
          AND u.name IN ({placeholders}) AND u.email != ''
        """.format(placeholders=", ".join(["%s"] * len(user_names))),
        user_names,
        as_dict=True,
    )
    return [(row.email or "").strip() for row in rows if (row.email or "").strip()]


def _get_procurement_users():
    """Users with the Consumables Procurement User role."""
    return _emails_with_role("Consumables Procurement User")


def _user_email(user):
    if not user:
        return ""
    return (frappe.db.get_value("User", user, "email") or "").strip()


def _user_full_name(user):
    if not user:
        return ""
    return (frappe.db.get_value("User", user, "full_name") or user).strip()


def _get_or_create_thread_id(cmr_name):
    """
    Get the Message-ID stored on the CMR, or create and persist one.
    All emails for this CMR use the same thread_id so email clients group them.
    """
    thread_id = frappe.db.get_value(
        "Consumables Material Request", cmr_name, "notification_thread_id"
    )
    if not thread_id:
        thread_id = f"<{cmr_name}.{uuid.uuid4().hex[:10]}@storeops.kfl>"
        frappe.db.set_value(
            "Consumables Material Request",
            cmr_name,
            "notification_thread_id",
            thread_id,
            update_modified=False,
        )
    return thread_id


def _cmr_url(cmr_name):
    return f"{get_url()}/storeops/material-requests/{cmr_name}"


def _items_table_html(line_items):
    rows_html = ""
    for li in line_items or []:
        if isinstance(li, dict):
            code = li.get("item_code") or ""
            name = li.get("item_name") or ""
            qty = li.get("quantity") or li.get("qty") or ""
            uom = li.get("uom") or ""
        else:
            code = getattr(li, "item_code", "") or ""
            name = getattr(li, "item_name", "") or ""
            qty = getattr(li, "quantity_requested", None) or getattr(li, "quantity", None) or ""
            uom = getattr(li, "uom", "") or ""
        rows_html += (
            f"<tr>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{code}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #e5e7eb;color:#374151;'>{name}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #e5e7eb;text-align:right;color:#111827;'>{qty} {uom}</td>"
            f"</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:13px;margin:12px 0;'>"
        "<thead><tr style='background:#f3f4f6;'>"
        "<th style='padding:8px 12px;text-align:left;color:#374151;font-weight:600;'>Item Code</th>"
        "<th style='padding:8px 12px;text-align:left;color:#374151;font-weight:600;'>Item Name</th>"
        "<th style='padding:8px 12px;text-align:right;color:#374151;font-weight:600;'>Qty</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
    )


def _wrap_email(heading, body_html, cmr_name):
    view_url = _cmr_url(cmr_name)
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;"
        "background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;'>"
        "<div style='background:#0d9488;padding:18px 24px;'>"
        "<span style='color:#ffffff;font-size:18px;font-weight:700;'>KFL StoreOps</span>"
        "</div>"
        "<div style='padding:24px;'>"
        f"<h2 style='color:#111827;font-size:15px;font-weight:600;margin:0 0 6px;'>{heading}</h2>"
        f"<p style='color:#6b7280;font-size:12px;margin:0 0 18px;'>Reference: <strong>{cmr_name}</strong></p>"
        f"{body_html}"
        "<div style='margin-top:24px;'>"
        f"<a href='{view_url}' style='display:inline-block;background:#0d9488;color:#ffffff;"
        "text-decoration:none;padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;'>"
        "View in StoreOps</a>"
        "</div>"
        "</div>"
        "<div style='background:#f9fafb;border-top:1px solid #e5e7eb;padding:10px 24px;"
        "font-size:11px;color:#9ca3af;'>"
        "Automated notification from KFL StoreOps — do not reply to this email."
        "</div>"
        "</div>"
    )


def _send(recipients, subject, html, cmr_name):
    """Send email and link it to the CMR document for conversation tracking."""
    if not recipients:
        return
    recipients = list(dict.fromkeys(r for r in recipients if r))
    if not recipients:
        return
    _get_or_create_thread_id(cmr_name)
    try:
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=html,
            reference_doctype="Consumables Material Request",
            reference_name=cmr_name,
            now=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"StoreOps email: {cmr_name}")


# ---------------------------------------------------------------------------
# Public notification functions
# All accept a document *name* (string) so they are safe for frappe.enqueue.
# ---------------------------------------------------------------------------


def notify_cmr_submitted(cmr_name):
    """CMR submitted → email all Inventory Managers to take action."""
    if not frappe.db.exists("Consumables Material Request", cmr_name):
        return
    cmr = frappe.get_doc("Consumables Material Request", cmr_name)
    recipients = _get_inventory_managers()
    if not recipients:
        return
    requester = _user_full_name(cmr.requested_by)
    plant = cmr.requesting_plant or ""
    urgency = cmr.urgency or "Normal"
    body = (
        "<p style='color:#374151;font-size:14px;'>A new material request has been submitted and requires your review.</p>"
        "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Plant</td><td style='color:#111827;font-weight:500;'>{plant}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Urgency</td><td style='color:#111827;font-weight:500;'>{urgency}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Requested By</td><td style='color:#111827;font-weight:500;'>{requester}</td></tr>"
        "</table>"
        "<p style='color:#374151;font-size:13px;font-weight:600;margin-bottom:4px;'>Items Requested:</p>"
        f"{_items_table_html(cmr.line_items)}"
    )
    subject = f"[StoreOps] New Material Request {cmr_name} — Review Required"
    html = _wrap_email(f"New Material Request: {cmr_name}", body, cmr_name)
    _send(recipients, subject, html, cmr_name)


def notify_cmr_rejected(cmr_name):
    """CMR rejected → email the requester with the rejection reason."""
    if not frappe.db.exists("Consumables Material Request", cmr_name):
        return
    cmr = frappe.get_doc("Consumables Material Request", cmr_name)
    email = _user_email(cmr.requested_by)
    if not email:
        return
    reason = (cmr.rejection_reason or "").strip() or "No reason provided."
    body = (
        "<p style='color:#374151;font-size:14px;'>Your material request has been reviewed and "
        "<strong style='color:#ef4444;'>rejected</strong>.</p>"
        "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Plant</td><td style='color:#111827;font-weight:500;'>{cmr.requesting_plant or ''}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Reason</td><td style='color:#ef4444;font-weight:500;'>{reason}</td></tr>"
        "</table>"
        "<p style='color:#374151;font-size:13px;'>If you have questions, please contact your Inventory Manager.</p>"
    )
    subject = f"[StoreOps] Material Request {cmr_name} — Rejected"
    html = _wrap_email(f"Material Request Rejected: {cmr_name}", body, cmr_name)
    _send([email], subject, html, cmr_name)


def notify_ctr_dispatched(ctr_name):
    """CTR dispatched (In Transit) → email destination plant Store Managers."""
    if not frappe.db.exists("Consumables Transfer Request", ctr_name):
        return
    ctr = frappe.get_doc("Consumables Transfer Request", ctr_name)
    cmr_ref = (ctr.cmr_reference or "").strip()
    if not cmr_ref:
        return
    to_plant = (ctr.to_plant or "").strip()
    recipients = _get_plant_store_managers(to_plant)
    if not recipients:
        return
    dispatcher = _user_full_name(getattr(ctr, "dispatched_by", None))
    body = (
        "<p style='color:#374151;font-size:14px;'>A stock transfer has been dispatched and is en route to your plant.</p>"
        "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Transfer Ref</td><td style='color:#111827;font-weight:500;'>{ctr_name}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>From Plant</td><td style='color:#111827;font-weight:500;'>{ctr.from_plant or ''}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>To Plant</td><td style='color:#111827;font-weight:500;'>{to_plant}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Dispatched By</td><td style='color:#111827;font-weight:500;'>{dispatcher}</td></tr>"
        "</table>"
        "<p style='color:#374151;font-size:13px;font-weight:600;margin-bottom:4px;'>Items in Transfer:</p>"
        f"{_items_table_html(ctr.line_items)}"
        "<p style='color:#374151;font-size:13px;'>Please confirm receipt once goods arrive at your warehouse.</p>"
    )
    subject = f"[StoreOps] Transfer {ctr_name} Dispatched — Confirm Receipt ({cmr_ref})"
    html = _wrap_email(f"Transfer Dispatched: {ctr_name}", body, cmr_ref)
    _send(recipients, subject, html, cmr_ref)


def notify_ctr_received(ctr_name):
    """
    CTR receipt outcome — two distinct recipient groups:
    - Rejected at receipt  → Inventory Managers (they dispatched it; they must act)
    - Completed / Partial  → CMR requester (their goods have arrived)
    """
    if not frappe.db.exists("Consumables Transfer Request", ctr_name):
        return
    ctr = frappe.get_doc("Consumables Transfer Request", ctr_name)
    cmr_ref = (ctr.cmr_reference or "").strip()
    if not cmr_ref or not frappe.db.exists("Consumables Material Request", cmr_ref):
        return

    status = (ctr.status or "")
    is_rejected = status == "Rejected"
    is_partial = status == "Partially Received"

    if is_rejected:
        # Goods rejected at destination — Inventory Managers need to take corrective action
        recipients = _get_inventory_managers()
        if not recipients:
            return
        reason = (ctr.rejection_reason or getattr(ctr, "receipt_notes", None) or "No reason provided.").strip()
        rejected_by = _user_full_name(getattr(ctr, "received_by", None))
        body = (
            "<p style='color:#374151;font-size:14px;'>Goods dispatched from your plant were "
            "<strong style='color:#ef4444;'>rejected at delivery</strong> by the destination plant. "
            "Corrective action is required.</p>"
            "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Transfer Ref</td><td style='color:#111827;font-weight:500;'>{ctr_name}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Material Request</td><td style='color:#111827;font-weight:500;'>{cmr_ref}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>From Plant</td><td style='color:#111827;font-weight:500;'>{ctr.from_plant or ''}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>To Plant</td><td style='color:#111827;font-weight:500;'>{ctr.to_plant or ''}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Rejected By</td><td style='color:#111827;font-weight:500;'>{rejected_by}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Reason</td><td style='color:#ef4444;font-weight:500;'>{reason}</td></tr>"
            "</table>"
            f"{_items_table_html(ctr.line_items)}"
            "<p style='color:#374151;font-size:13px;margin-top:12px;'>Please arrange a re-dispatch or raise a Purchase Request for the affected items.</p>"
        )
        subject = f"[StoreOps] Transfer {ctr_name} Rejected at Delivery — Action Required ({cmr_ref})"
        html = _wrap_email(f"Delivery Rejected — Action Required: {ctr_name}", body, cmr_ref)
        _send(recipients, subject, html, cmr_ref)

    else:
        # Goods received (fully or partially) — inform the CMR requester
        requester = frappe.db.get_value("Consumables Material Request", cmr_ref, "requested_by")
        email = _user_email(requester)
        if not email:
            return
        status_label = "Partially Received" if is_partial else "Received"
        status_color = "#f59e0b" if is_partial else "#10b981"
        body = (
            "<p style='color:#374151;font-size:14px;'>Goods from your material request have been received at your plant.</p>"
            "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Transfer Ref</td><td style='color:#111827;font-weight:500;'>{ctr_name}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Status</td><td style='color:{status_color};font-weight:600;'>{status_label}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Received At</td><td style='color:#111827;font-weight:500;'>{ctr.to_plant or ''}</td></tr>"
            "</table>"
            f"{_items_table_html(ctr.line_items)}"
        )
        if is_partial:
            body += (
                "<p style='color:#f59e0b;font-size:13px;margin-top:12px;'>"
                "&#9888; Some items were partially received. Your Inventory Manager will arrange the shortfall."
                "</p>"
            )
        subject = f"[StoreOps] Your Request {cmr_ref} — Items {status_label}"
        html = _wrap_email(f"Items {status_label}: {cmr_ref}", body, cmr_ref)
        _send([email], subject, html, cmr_ref)


def notify_cpr_created(cpr_name):
    """
    CPR created → two emails on the same thread:
    1. Requester: your request has been forwarded to procurement.
    2. Procurement team: please raise a PO for this CPR.
    """
    if not frappe.db.exists("Consumables Purchase Request", cpr_name):
        return
    cpr = frappe.get_doc("Consumables Purchase Request", cpr_name)
    cmr_ref = (cpr.cmr_reference or "").strip()
    if not cmr_ref or not frappe.db.exists("Consumables Material Request", cmr_ref):
        return

    requester = frappe.db.get_value("Consumables Material Request", cmr_ref, "requested_by")
    requester_email = _user_email(requester)
    procurement_emails = _get_procurement_users()

    if requester_email:
        body = (
            "<p style='color:#374151;font-size:14px;'>Some items from your request could not be fulfilled "
            "via internal transfer and have been forwarded to the procurement team to raise a Purchase Order.</p>"
            "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Purchase Request</td><td style='color:#111827;font-weight:500;'>{cpr_name}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Plant</td><td style='color:#111827;font-weight:500;'>{cpr.requesting_plant or ''}</td></tr>"
            "</table>"
            "<p style='color:#374151;font-size:13px;font-weight:600;margin-bottom:4px;'>Items Forwarded:</p>"
            f"{_items_table_html(cpr.line_items)}"
            "<p style='color:#374151;font-size:13px;'>You will be notified when goods are received from the supplier.</p>"
        )
        subject = f"[StoreOps] Your Request {cmr_ref} — Forwarded to Procurement"
        html = _wrap_email(f"Request Forwarded to Procurement: {cmr_ref}", body, cmr_ref)
        _send([requester_email], subject, html, cmr_ref)

    if procurement_emails:
        body = (
            "<p style='color:#374151;font-size:14px;'>A purchase request has been created and requires a Purchase Order to be raised in SAP.</p>"
            "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Purchase Request</td><td style='color:#111827;font-weight:500;'>{cpr_name}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Material Request</td><td style='color:#111827;font-weight:500;'>{cmr_ref}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Plant</td><td style='color:#111827;font-weight:500;'>{cpr.requesting_plant or ''}</td></tr>"
            "</table>"
            "<p style='color:#374151;font-size:13px;font-weight:600;margin-bottom:4px;'>Items Required:</p>"
            f"{_items_table_html(cpr.line_items)}"
            "<p style='color:#374151;font-size:13px;'>Please raise a Purchase Order in SAP for the above items at the earliest.</p>"
        )
        subject = f"[StoreOps] Purchase Request {cpr_name} — Please Raise PO ({cmr_ref})"
        html = _wrap_email(f"Please Raise PO: {cpr_name}", body, cmr_ref)
        _send(procurement_emails, subject, html, cmr_ref)


def notify_cpr_grn_done(cpr_name):
    """CPR GRN done → email the CMR requester that goods arrived from supplier."""
    if not frappe.db.exists("Consumables Purchase Request", cpr_name):
        return
    cpr = frappe.get_doc("Consumables Purchase Request", cpr_name)
    cmr_ref = (cpr.cmr_reference or "").strip()
    if not cmr_ref or not frappe.db.exists("Consumables Material Request", cmr_ref):
        return
    requester = frappe.db.get_value("Consumables Material Request", cmr_ref, "requested_by")
    email = _user_email(requester)
    if not email:
        return
    grpo_num = (getattr(cpr, "sap_grpo_doc_num", None) or "").strip()
    body = (
        "<p style='color:#374151;font-size:14px;'>Goods for your material request have been received from the supplier and posted to SAP.</p>"
        "<table style='font-size:13px;margin:16px 0;border-collapse:collapse;'>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Purchase Request</td><td style='color:#111827;font-weight:500;'>{cpr_name}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>SAP GRPO No.</td><td style='color:#111827;font-weight:500;'>{grpo_num or '—'}</td></tr>"
        f"<tr><td style='color:#6b7280;padding:4px 16px 4px 0;'>Plant</td><td style='color:#111827;font-weight:500;'>{cpr.requesting_plant or ''}</td></tr>"
        "</table>"
        f"{_items_table_html(cpr.line_items)}"
    )
    subject = f"[StoreOps] Your Request {cmr_ref} — Goods Received from Supplier"
    html = _wrap_email(f"Goods Received from Supplier: {cmr_ref}", body, cmr_ref)
    _send([email], subject, html, cmr_ref)
