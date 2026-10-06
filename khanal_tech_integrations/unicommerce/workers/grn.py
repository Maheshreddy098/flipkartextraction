"""
GRN Processor — SAP Inventory Transfers → Unicommerce Purchase Orders + GRNs.

Migrated from unicommerce_clean.py (PO_GRN_Completion, Check_Uniware_PO_Exists,
create_Approved_PO, Create_GRNs_fill_Items, Update_Uniware_PO_Status).
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import add_to_date, nowdate

from ..client import UCClient
from ._uc_utils import COMPLETED_PO_STATUSES, MAX_GRN_ROUNDS, _to_uc_datetime
from .po_grn import _build_grn_item_list, _push_grn_rounds


def _uc_session() -> UCClient:
    uc = UCClient()
    uc.login()
    return uc


def _save_transfer_state(
    docname: str,
    *,
    sync_status: str | None = None,
    po_status: str | None = None,
    comments: str | None = None,
    po_id: str | None = None,
    grn_no: str | None = None,
) -> None:
    update = {}
    if sync_status is not None:
        update["unicommerce_sync_status"] = sync_status
    if po_status is not None:
        update["uniware_po_status"] = po_status
    if comments is not None:
        # SAP Inventory Transfers.comments is a plain Data field (Frappe
        # default max length 140, same as uniware_grn_no right below) --
        # not 500. A too-long comments string here crashes MariaDB with
        # "Data too long for column 'comments'" instead of saving, which is
        # exactly what happened in production on 2026-07-23.
        update["comments"] = comments[:140]
    if po_id is not None:
        update["uniware_po_id"] = po_id
    if grn_no is not None:
        update["uniware_grn_no"] = grn_no[:140]
    if update:
        frappe.db.set_value("SAP Inventory Transfers", docname, update)
        frappe.db.commit()


def _claim_po_creation(inv_transfer_docname: str) -> bool:
    """Atomically claim "no PO created yet" for this transfer before calling UC create.

    Without this, a manual push_po retry racing the scheduled sync (or two
    overlapping scheduler ticks) can both read an empty uniware_po_id and both
    call UC purchaseOrder/create, producing two separate Unicommerce POs for
    the same inventory transfer. uniware_po_status is a free-text Data field
    (not a constrained Select), so "CREATING" is a safe sentinel value here.

    Returns True if this call owns the claim (uniware_po_id was empty AND
    uniware_po_status was not already "CREATING"); False if another process
    already claimed it.
    """
    frappe.db.sql(
        """
        UPDATE `tabSAP Inventory Transfers`
           SET uniware_po_status = 'CREATING'
         WHERE name = %s
           AND (uniware_po_id IS NULL OR uniware_po_id = '')
           AND (uniware_po_status IS NULL OR uniware_po_status = '')
        """,
        inv_transfer_docname,
    )
    affected = 0
    try:
        affected = frappe.db._cursor.rowcount
    except Exception:
        state = frappe.db.get_value("SAP Inventory Transfers", inv_transfer_docname, "uniware_po_status")
        affected = 1 if state == "CREATING" else 0
    frappe.db.commit()
    return affected == 1


@frappe.whitelist()
def push_po(inv_transfer_docname: str) -> dict:
    """
    Create and approve a Purchase Order in Unicommerce for the given SAP Inventory Transfer.
    Uses two-step flow: create → approve.
    Returns a result dict with keys: success, purchaseOrderCode, message.
    """
    uc = _uc_session()
    settings = frappe.get_single("Unicommerce Settings")
    vendor_code = getattr(settings, "vendor_code", None) or "EC-DIS"
    facility = uc.facility_code or "kfl_ecom_warehouse"

    inv_doc = frappe.get_doc("SAP Inventory Transfers", inv_transfer_docname)

    _APPROVED_OR_BEYOND = {"APPROVED"} | COMPLETED_PO_STATUSES
    if inv_doc.uniware_po_id:
        po_code = inv_doc.uniware_po_id
        if str(inv_doc.uniware_po_status or "").upper() in _APPROVED_OR_BEYOND:
            return {"success": True, "purchaseOrderCode": po_code, "message": "PO already approved"}
        # PO created but approval failed on a prior attempt — skip step 1, re-attempt step 2
        approve_response = uc._post_with_reauth(
            "services/rest/v1/purchase/purchaseOrder/approve",
            body={"purchaseOrderCode": po_code},
            extra_headers={"Facility": facility},
        )
        if not approve_response.get("successful"):
            err_msg = f"PO approve (retry) failed for {inv_transfer_docname} (PO {po_code}): {approve_response}"
            _save_transfer_state(inv_transfer_docname, sync_status="Failed", comments=err_msg)
            try:
                from ..api.ops import send_failure_alert
                send_failure_alert("grn_failed", "SAP Inventory Transfers", inv_transfer_docname, err_msg)
            except Exception:
                pass
            return {"success": False, "purchaseOrderCode": po_code, "message": err_msg}
        _save_transfer_state(inv_transfer_docname, po_status="APPROVED", sync_status="Pending", comments="")
        return {"success": True, "purchaseOrderCode": po_code}

    # Sum batchquantity per SKU across all batch rows
    sku_qty: dict[str, float] = defaultdict(float)
    for item in inv_doc.line_items:
        sku = (item.itemcode or "").strip()
        if not sku:
            continue
        sku_qty[sku] += float(item.batchquantity or item.quantity or 0)

    po_items = [
        {"itemSKU": sku, "quantity": qty, "unitPrice": 0, "taxTypeCode": None}
        for sku, qty in sku_qty.items()
        if qty > 0
    ]

    if not po_items:
        err_msg = f"No valid SKU/quantity found in line items for {inv_transfer_docname}"
        _save_transfer_state(inv_transfer_docname, sync_status="Failed", comments=err_msg)
        return {"success": False, "message": err_msg}

    if not _claim_po_creation(inv_transfer_docname):
        # Another process already created (or is creating) this transfer's PO —
        # don't call UC create a second time. Caller can re-check shortly.
        return {
            "success": False,
            "message": f"PO creation already in progress or completed for {inv_transfer_docname} by another process",
        }

    # Step 1: Create PO
    try:
        create_response = uc._post_with_reauth(
            "services/rest/v1/purchase/purchaseOrder/create",
            body={"vendorCode": vendor_code, "purchaseOrderItems": po_items},
            extra_headers={"Facility": facility},
        )
    except Exception as e:
        # The claim above set uniware_po_status='CREATING' with no po_id yet.
        # If the UC call itself raises (network error, auth failure, non-2xx
        # via raise_for_status) rather than returning a response with a
        # missing purchaseOrderCode, this transfer would otherwise be stuck
        # in "CREATING" forever — _claim_po_creation refuses to claim again
        # while that sentinel is set, and po_id is still empty so the
        # "already created" branch at the top of this function never
        # triggers either. Release the claim here the same way the
        # explicit "no po_code" branch below does.
        err_msg = f"PO create raised for {inv_transfer_docname}: {e}"
        # _save_transfer_state truncates comments to the field's real 140-char
        # limit itself -- no need (and it'd be misleading) to pre-slice here.
        _save_transfer_state(inv_transfer_docname, po_status="", sync_status="Failed", comments=err_msg)
        try:
            from ..api.ops import send_failure_alert
            send_failure_alert("grn_failed", "SAP Inventory Transfers", inv_transfer_docname, err_msg)
        except Exception:
            pass
        return {"success": False, "message": err_msg}

    po_code = create_response.get("purchaseOrderCode")
    if not po_code:
        err_msg = f"PO create failed for {inv_transfer_docname}: {create_response}"
        # Release the claim so a retry isn't permanently blocked by "CREATING".
        _save_transfer_state(inv_transfer_docname, po_status="", sync_status="Failed", comments=err_msg)
        try:
            from ..api.ops import send_failure_alert
            send_failure_alert("grn_failed", "SAP Inventory Transfers", inv_transfer_docname, err_msg)
        except Exception:
            pass
        return {"success": False, "message": err_msg}

    # Persist po_code immediately so retries are idempotent even if approve raises
    _save_transfer_state(inv_transfer_docname, po_id=po_code)

    # Step 2: Approve PO
    approve_response = uc._post_with_reauth(
        "services/rest/v1/purchase/purchaseOrder/approve",
        body={"purchaseOrderCode": po_code},
        extra_headers={"Facility": facility},
    )

    if not approve_response.get("successful"):
        err_msg = f"PO approve failed for {inv_transfer_docname} (PO {po_code}): {approve_response}"
        _save_transfer_state(
            inv_transfer_docname,
            po_id=po_code,
            sync_status="Failed",
            comments=err_msg,
        )
        try:
            from ..api.ops import send_failure_alert
            send_failure_alert("grn_failed", "SAP Inventory Transfers", inv_transfer_docname, err_msg)
        except Exception:
            pass
        return {"success": False, "purchaseOrderCode": po_code, "message": err_msg}

    _save_transfer_state(
        inv_transfer_docname,
        po_id=po_code,
        po_status="APPROVED",
        sync_status="Pending",
        comments="",
    )
    return {"success": True, "purchaseOrderCode": po_code}


@frappe.whitelist()
def fill_grn_items(inv_transfer_docname: str) -> dict:
    """
    Create one or more GRNs in Unicommerce for the inventory transfer and
    add all batch-level line items into each GRN.
    """
    uc = _uc_session()
    facility = uc.facility_code or "kfl_ecom_warehouse"
    inv_doc = frappe.get_doc("SAP Inventory Transfers", inv_transfer_docname)
    if not inv_doc.uniware_po_id:
        err_msg = f"PO missing for {inv_transfer_docname}"
        _save_transfer_state(inv_transfer_docname, sync_status="Failed", comments=err_msg)
        return {"success": False, "status": "Failed", "synced": 0, "failed": 1, "errors": [err_msg]}

    existing_grn = (inv_doc.uniware_grn_no or "").strip()
    if existing_grn:
        return {"success": True, "status": "Synced", "synced": 0, "failed": 0, "errors": [],
                "grn_codes": [g.strip() for g in existing_grn.split(",") if g.strip()],
                "message": f"GRNs already created: {existing_grn}"}

    try:
        grn_items = _build_grn_item_list(inv_doc.line_items)
        if not grn_items:
            err_msg = f"No valid batch items to add to GRN for {inv_transfer_docname}"
            _save_transfer_state(inv_transfer_docname, sync_status="Failed", comments=err_msg)
            return {"success": False, "status": "Failed", "synced": 0, "failed": 1, "errors": [err_msg]}

        extra_headers = {"Facility": facility, "Content-Type": "application/json"}
        grn_codes, post_errors = _push_grn_rounds(
            inv_doc.uniware_po_id, grn_items, uc, extra_headers, docname=inv_transfer_docname
        )

        if post_errors and not grn_codes:
            final_status = "Failed"
        elif post_errors:
            final_status = "Partial"
        else:
            final_status = "Synced"

        _save_transfer_state(
            inv_transfer_docname,
            sync_status=final_status,
            po_status="GRN_COMPLETED" if final_status == "Synced" else inv_doc.uniware_po_status,
            comments="; ".join(post_errors) if post_errors else "",
            grn_no=", ".join(grn_codes) if grn_codes else None,
        )

        if post_errors:
            try:
                from ..api.ops import send_failure_alert
                send_failure_alert(
                    "grn_failed",
                    "SAP Inventory Transfers",
                    inv_transfer_docname,
                    "; ".join(post_errors),
                )
            except Exception:
                pass

        return {
            "success": final_status in ("Synced", "Partial"),
            "status": final_status,
            "synced": len(grn_items) if final_status == "Synced" else 0,
            "failed": len(post_errors),
            "errors": post_errors,
            "grn_codes": grn_codes,
        }

    except Exception as e:
        err_msg = f"Error in fill_grn_items for {inv_transfer_docname}: {e}"
        _save_transfer_state(inv_transfer_docname, sync_status="Failed", comments=err_msg)
        frappe.log_error(err_msg, "GRN Processor")
        return {"success": False, "status": "Failed", "synced": 0, "failed": 1, "errors": [str(e)]}


def sync_pos(days: int | None = None) -> dict:
    """
    Scan recent SAP Inventory Transfers (towarehouse=EC-FG) that have no
    Unicommerce PO yet and create one.
    """
    start = add_to_date(nowdate(), days=-(days or 12))
    transfers = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={"towarehouse": "EC-FG", "docdate": [">", start]},
        fields=["name", "docentry", "uniware_po_id"],
    )

    created = failed = 0

    for row in transfers:
        if not row.get("uniware_po_id"):
            try:
                resp = push_po(row["name"])
                if resp.get("success"):
                    created += 1
                else:
                    failed += 1
                    frappe.log_error(
                        f"PO creation failed for {row['name']}: {resp}",
                        "GRN Processor",
                    )
            except Exception as e:
                failed += 1
                _save_transfer_state(row["name"], sync_status="Failed", comments=str(e))
                frappe.log_error(
                    f"PO creation exception for {row['name']}: {e}",
                    "GRN Processor",
                )
    return {"total": len(transfers), "po_created": created, "po_failed": failed}


@frappe.whitelist()
def refresh_po_status(days: int | None = None) -> None:
    """Refresh PO status from Unicommerce for APPROVED/GRN_COMPLETED transfers."""
    uc = _uc_session()
    facility = uc.facility_code or "kfl_ecom_warehouse"
    start = add_to_date(nowdate(), days=-(days or 4))

    transfers = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={
            "towarehouse": "EC-FG",
            "uniware_po_status": ("in", ["APPROVED", "GRN_COMPLETED"]),
            "docdate": [">", start],
        },
        fields=["name", "uniware_po_id"],
    )

    for row in transfers:
        if not row.get("uniware_po_id"):
            continue
        try:
            resp = uc._post_with_reauth(
                "services/rest/v1/purchase/purchaseOrder/getPurchaseOrderDetails",
                body={"purchaseOrderCode": row["uniware_po_id"]},
                extra_headers={"Facility": facility},
            )
            if resp.get("successful") and resp.get("statusCode"):
                po_status = resp["statusCode"]
                _save_transfer_state(
                    row["name"],
                    po_status=po_status,
                    sync_status="Synced" if str(po_status).upper() in COMPLETED_PO_STATUSES else None,
                )
        except Exception as e:
            frappe.log_error(
                f"PO status update failed for {row['name']}: {e}",
                "GRN Processor",
            )


def sync_grns(days: int | None = None) -> dict:
    """
    Scheduled entry point — creates missing POs, completes pending GRNs,
    and refreshes PO statuses.
    """
    po_stats = sync_pos(days)

    start = add_to_date(nowdate(), days=-(days or 2))
    pending_grns = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={
            "towarehouse": "EC-FG",
            "uniware_po_id": ["!=", ""],
            "unicommerce_sync_status": ("in", ["", "Pending", "Failed", "Partial"]),
            "docdate": [">", start],
        },
        fields=["name", "uniware_po_status"],
    )
    synced = partial = failed = 0
    _APPROVED_OR_BEYOND = {"APPROVED"} | COMPLETED_PO_STATUSES
    for row in pending_grns:
        po_status = str(row.get("uniware_po_status") or "").upper()
        # Skip docs that are fully completed or whose PO hasn't been approved yet
        if po_status in COMPLETED_PO_STATUSES or po_status not in _APPROVED_OR_BEYOND:
            continue
        result = fill_grn_items(row["name"])
        status = result.get("status")
        if status == "Synced":
            synced += 1
        elif status == "Partial":
            partial += 1
        else:
            failed += 1

    refresh_po_status(days)
    return {
        "po_total": po_stats.get("total", 0),
        "po_created": po_stats.get("po_created", 0),
        "po_failed": po_stats.get("po_failed", 0),
        "grn_checked": len(pending_grns),
        "grn_synced": synced,
        "grn_partial": partial,
        "grn_failed": failed,
    }
