"""
Inventory Sync — SAP Inventory Transfers → Unicommerce inventory adjustment.

Watches SAP Inventory Transfers (fromwarehouse=EC-FG, towarehouse=EC-B2C) and
removes the transferred batch quantities from Unicommerce inventory using the
bulk adjust API.

Enhanced from unicommerce.py::Batchwise_Inventory_Remove_uniware.

Status field on SAP Inventory Transfers (unicommerce_sync_status):
    Pending   — not yet synced
    Synced    — all items successfully removed from UC inventory
    Failed    — one or more items failed; see comments field for errors
    Partial   — some items synced, some failed
"""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime, nowdate

from ..client import UCClient

# Warehouse filter — only outward transfers trigger UC inventory removal
FROM_WAREHOUSE = "EC-FG"
TO_WAREHOUSE = "EC-B2C"


def _uc_session() -> UCClient:
    uc = UCClient()
    uc.login()
    return uc


def _uc_shelf_stock(uc: UCClient, sku_code: str) -> list[dict]:
    """
    Fetch shelf-wise inventory for a single SKU from Unicommerce.
    Returns list of inventoryDTO dicts.
    """
    facility = uc.facility_code or ""
    extra_headers = {}
    if facility:
        extra_headers["Facility"] = facility.split(",")[0].strip()

    resp = uc._post_with_reauth(
        "services/rest/v1/product/itemTypeInventory/get",
        body={"skuCode": sku_code},
        extra_headers=extra_headers,
    )
    return resp.get("inventoryDTOs") or []


def _build_adjustments(
    inv_transfer_docname: str,
    uc: UCClient,
) -> tuple[list[dict], list[str]]:
    """
    For each line item in the SAP Inventory Transfer, match the vendor batch
    number in Unicommerce and build a REMOVE adjustment payload.

    Returns:
        adjustments — list of adjustment dicts ready for bulk API
        errors      — list of human-readable error strings for items not matched
    """
    inv_doc = frappe.get_doc("SAP Inventory Transfers", inv_transfer_docname)
    facility = (uc.facility_code or "").split(",")[0].strip()
    remark = f"Outward stock transfer - DocNum {inv_doc.docnum}"

    adjustments: list[dict] = []
    errors: list[str] = []

    for item in inv_doc.line_items:
        sku = item.itemcode
        batch = item.batchnumber
        qty = item.batchquantity

        shelf_inventory = _uc_shelf_stock(uc, sku)
        matched = [
            shelf for shelf in shelf_inventory
            if shelf.get("vendorBatchNumber") == batch
        ]

        if not matched:
            errors.append(f"Batch {batch} not found in UC for SKU {sku}")
            continue

        shelf = matched[0]
        adjustments.append({
            "itemSKU": sku,
            "quantity": qty,
            "shelfCode": shelf.get("shelf", "DEFAULT"),
            "inventoryType": shelf.get("type", "GOOD_INVENTORY"),
            "adjustmentType": "REMOVE",
            "facilityCode": facility,
            "remarks": remark,
        })

    return adjustments, errors


def _sync_one_transfer(inv_transfer_docname: str) -> dict:
    """
    Sync a single SAP Inventory Transfer to Unicommerce.
    Removes transferred batch quantities from UC inventory using bulk adjust.

    Returns a result dict with keys: success, synced, failed, errors.
    """
    # Guard: only process outward transfers
    inv_doc = frappe.get_doc("SAP Inventory Transfers", inv_transfer_docname)
    if inv_doc.fromwarehouse != FROM_WAREHOUSE or inv_doc.towarehouse != TO_WAREHOUSE:
        return {
            "success": False,
            "message": f"Skipped: transfer is {inv_doc.fromwarehouse}→{inv_doc.towarehouse}, expected {FROM_WAREHOUSE}→{TO_WAREHOUSE}",
        }

    # Atomic claim — without this, a manual "push_transfer" retry racing the
    # scheduled sync_inventory tick (or two overlapping scheduler runs) can
    # both pass this point and both submit REMOVE adjustments for the same
    # batch/qty, double-decrementing real Unicommerce inventory.
    # "Syncing" is not in unicommerce_sync_status's declared Select options
    # (Pending/Synced/Failed/Partial), but this whole module already writes
    # to that field via raw frappe.db.set_value/sql, bypassing doctype
    # validation — consistent with the existing pattern, not a new risk.
    # Every exit path below ends in _save_sync_status(), which overwrites
    # this sentinel with a real terminal status.
    frappe.db.sql(
        """
        UPDATE `tabSAP Inventory Transfers`
           SET unicommerce_sync_status = 'Syncing'
         WHERE name = %s
           AND IFNULL(unicommerce_sync_status, '') != 'Syncing'
        """,
        inv_transfer_docname,
    )
    claimed = False
    try:
        claimed = frappe.db._cursor.rowcount == 1
    except Exception:
        state = frappe.db.get_value("SAP Inventory Transfers", inv_transfer_docname, "unicommerce_sync_status")
        claimed = state == "Syncing"
    frappe.db.commit()
    if not claimed:
        return {
            "success": False,
            "message": f"Sync already in progress for {inv_transfer_docname} (another process holds the claim)",
        }

    try:
        uc = _uc_session()
        adjustments, pre_errors = _build_adjustments(inv_transfer_docname, uc)
    except Exception as e:
        # The claim above set unicommerce_sync_status='Syncing'. If UC login
        # or the per-item shelf-stock lookup (_build_adjustments ->
        # _uc_shelf_stock, both real UC API calls) raises, this transfer
        # would otherwise be stuck in "Syncing" forever — only the bulk
        # adjust call further below was covered by a try/except before this.
        err_msg = f"Inventory sync setup failed for {inv_transfer_docname}: {e}"
        _save_sync_status(inv_transfer_docname, "Failed", [err_msg])
        frappe.log_error(err_msg, "Inventory Sync")
        return {"success": False, "synced": 0, "failed": 1, "errors": [err_msg]}

    if not adjustments:
        _save_sync_status(inv_transfer_docname, "Failed", pre_errors)
        return {"success": False, "synced": 0, "failed": len(pre_errors), "errors": pre_errors}

    facility = (uc.facility_code or "").split(",")[0].strip()
    extra_headers = {}
    if facility:
        extra_headers["Facility"] = facility

    synced = 0
    post_errors = list(pre_errors)

    try:
        resp = uc._post_with_reauth(
            "services/rest/v1/inventory/adjust/bulk",
            body={"inventoryAdjustments": adjustments},
            extra_headers=extra_headers,
        )

        item_responses = resp.get("inventoryAdjustmentResponses") or []
        for item_resp in item_responses:
            adj = item_resp.get("facilityInventoryAdjustment") or {}
            sku = adj.get("itemSKU", "?")
            if item_resp.get("successful"):
                synced += 1
            else:
                err_msgs = [e.get("message", "unknown") for e in (item_resp.get("errors") or [])]
                post_errors.append(f"SKU {sku}: {', '.join(err_msgs)}")

        # If bulk endpoint gave no per-item breakdown, count all as synced
        if not item_responses and resp.get("successful"):
            synced = len(adjustments)

    except Exception as e:
        post_errors.append(f"Bulk adjust API error: {e}")
        _save_sync_status(inv_transfer_docname, "Failed", post_errors)
        frappe.log_error(
            f"Inventory sync failed for {inv_transfer_docname}: {e}",
            "Inventory Sync",
        )
        return {"success": False, "synced": 0, "failed": len(post_errors), "errors": post_errors}

    if post_errors and synced == 0:
        final_status = "Failed"
    elif post_errors:
        final_status = "Partial"
    else:
        final_status = "Synced"

    _save_sync_status(inv_transfer_docname, final_status, post_errors)

    frappe.logger().info(
        "Inventory sync for %s: status=%s synced=%s failed=%s",
        inv_transfer_docname,
        final_status,
        synced,
        len(post_errors),
    )

    return {
        "success": final_status in ("Synced", "Partial"),
        "status": final_status,
        "synced": synced,
        "failed": len(post_errors),
        "errors": post_errors,
    }


def _save_sync_status(docname: str, status: str, errors: list[str]) -> None:
    update = {"unicommerce_sync_status": status}
    if errors:
        # SAP Inventory Transfers.comments is a plain Data field (Frappe
        # default max length 140), not 500 -- a too-long value here crashes
        # MariaDB with "Data too long for column 'comments'" instead of
        # saving, which is exactly what happened in production on
        # 2026-07-23 (transfer 24798, "no adjustments" branch).
        update["comments"] = "; ".join(errors)[:140]
    frappe.db.set_value("SAP Inventory Transfers", docname, update)
    frappe.db.commit()
    if status in ("Failed", "Partial") and errors:
        try:
            from ..api.ops import send_failure_alert
            send_failure_alert("inventory_failed", "SAP Inventory Transfers", docname, "; ".join(errors))
        except Exception:
            pass


def sync_inventory(days: int = 7) -> dict:
    """
    Scheduled entry point — finds all unsynced outward inventory transfers
    in the past `days` days and syncs them to Unicommerce.
    """
    start = add_to_date(nowdate(), days=-days)
    transfers = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={
            "fromwarehouse": FROM_WAREHOUSE,
            "towarehouse": TO_WAREHOUSE,
            "unicommerce_sync_status": ("in", ["Pending", "Failed", ""]),
            "docdate": [">", start],
        },
        fields=["name"],
        order_by="docdate asc",
    )

    total = len(transfers)
    synced = failed = partial = 0

    for row in transfers:
        result = _sync_one_transfer(row["name"])
        status = result.get("status", "Failed")
        if status == "Synced":
            synced += 1
        elif status == "Partial":
            partial += 1
        else:
            failed += 1

    frappe.logger().info(
        "Inventory sync batch complete: total=%s synced=%s partial=%s failed=%s",
        total, synced, partial, failed,
    )
    return {"total": total, "synced": synced, "partial": partial, "failed": failed}


@frappe.whitelist()
def push_transfer(inv_transfer_docname: str) -> dict:
    """
    Whitelisted — manually trigger sync for a single SAP Inventory Transfer
    from the Frappe UI or API.
    """
    return _sync_one_transfer(inv_transfer_docname)
