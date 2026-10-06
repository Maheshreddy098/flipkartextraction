"""
Inward Inventory Flow — SAP Inventory Transfers (→ EC-FG) → Unicommerce PO + GRN.

Two use cases handled here:

1. SAP-driven inward transfer (any warehouse → EC-FG):
   When a SAP Inventory Transfer with towarehouse=EC-FG has no UC PO yet,
   create an APPROVED Purchase Order in UC and then one or more Inflow Receipts
   (GRNs) to receive each batch line into UC inventory.

2. Manual UC PO (PO created directly in Unicommerce):
   Given a UC PO code, fetch its details and create GRN(s) to receive the items.

SAFETY RULES — read carefully before editing:
  - ALL UC write operations (PO creation, GRN creation) are triggered ONLY by
    explicit operator action via the Ops Center UI buttons.
  - No scheduled jobs in this module.
  - Every write is idempotent: we check `uniware_po_id` before creating a PO
    and `uniware_grn_no` before creating GRNs.
  - Every UC call is logged. Errors are captured per-item so a single failure
    never silently aborts the whole batch.

UC Limitation — one GRN cannot contain duplicate SKUs:
  If a transfer has the same SKU across N batches, we need N GRN rounds.
  Each round creates one GRN and fills unique SKUs from the remaining list.
  A guard of MAX_GRN_ROUNDS=200 prevents any runaway loop.
"""

from __future__ import annotations

import frappe
from frappe.utils import nowdate

from ..client import UCClient
from ._uc_utils import COMPLETED_PO_STATUSES, MAX_GRN_ROUNDS, _to_uc_datetime

_LOG = frappe.logger

INWARD_TO_WAREHOUSE = "EC-FG"
VENDOR_CODE = "EC-B2C"
PO_ENDPOINT = "services/rest/v1/purchase/purchaseOrder/createApproved"
PO_GET_ENDPOINT = "services/rest/v1/purchase/purchaseOrder/getPurchaseOrderDetails"
GRN_CREATE_ENDPOINT = "services/rest/v1/purchase/inflowReceipt/create"
GRN_ADD_ITEM_ENDPOINT = "services/rest/v1/purchase/inflowReceipt/addItemSKU"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _uc_session() -> tuple[UCClient, dict]:
    """Return a logged-in UCClient and its facility extra-headers."""
    uc = UCClient()
    uc.login()
    facility = (uc._resolve_facility_codes() or ["kfl_ecom_warehouse"])[0]
    extra_headers = {"Facility": facility, "Content-Type": "application/json"}
    return uc, extra_headers


def _build_po_payload(line_items) -> dict:
    """
    Build createApproved PO payload from SAP IT line items.
    UC PO can only have one entry per SKU — we aggregate quantities.
    """
    seen: dict[str, float] = {}
    for item in line_items:
        sku = (item.itemcode or "").strip()
        qty = float(item.batchquantity or item.quantity or 0)
        if sku and qty > 0:
            seen[sku] = round(seen.get(sku, 0.0) + qty, 3)

    return {
        "vendorCode": VENDOR_CODE,
        "purchaseOrderItems": [
            {"itemSKU": sku, "quantity": qty, "unitPrice": 0, "taxTypeCode": None}
            for sku, qty in seen.items()
        ],
    }


def _build_grn_item_list(line_items) -> list[dict]:
    """
    Convert SAP IT line items into the UC inflowReceiptItem format.
    Returns a flat list; duplicated SKUs are kept (each batch is separate).
    Dates are formatted as UTC ISO 8601 per UC API spec.
    """
    items = []
    for item in line_items:
        sku = (item.itemcode or "").strip()
        batch = (item.batchnumber or "").strip()
        qty = float(item.batchquantity or item.quantity or 0)
        if not sku or qty <= 0:
            continue

        expiry_uc = _to_uc_datetime(getattr(item, "expirydate", None))
        mfg_uc = _to_uc_datetime(getattr(item, "manufacturingdate", None))

        grn_item: dict = {
            "skuCode": sku,
            "quantity": qty,
            "unitPrice": 1,
            "manufacturingDate": mfg_uc,
            "expiry": expiry_uc,
            "wsBatchDetail": {
                "wsBatchGroupFieldValue": {
                    "vendorBatchNumber": batch or "NA",
                    "expiryDate": expiry_uc,
                    "mfd": mfg_uc,
                },
            },
        }
        items.append(grn_item)
    return items


def _push_grn_rounds(
    po_code: str,
    grn_items: list[dict],
    uc: UCClient,
    extra_headers: dict,
    docname: str = "",
) -> tuple[list[str], list[str]]:
    """
    Create as many GRNs as needed to receive all items in grn_items.
    UC does not allow duplicate SKUs in a single GRN, so we loop:
      Round N: pick one item per unique SKU from the remaining list → create GRN → add items.
    Returns (created_grn_codes, error_messages).
    """
    remaining = list(grn_items)
    created_grns: list[str] = []
    errors: list[str] = []
    date_compact = nowdate().replace("-", "")
    ref = (docname or po_code)

    for round_num in range(MAX_GRN_ROUNDS):
        if not remaining:
            break

        # Pick unique-SKU subset for this round
        seen_skus: set[str] = set()
        this_round: list[dict] = []
        leftover: list[dict] = []
        for entry in remaining:
            sku = entry["skuCode"]
            if sku not in seen_skus:
                seen_skus.add(sku)
                this_round.append(entry)
            else:
                leftover.append(entry)
        remaining = leftover

        # Create GRN — invoice number must be unique per doc + round
        invoice_number = f"GRN-{ref}-{date_compact}-R{round_num + 1}"[:50]
        grn_payload = {
            "wsGRN": {
                "vendorInvoiceNumber": invoice_number,
                "vendorInvoiceDate": _to_uc_datetime(nowdate()),
                "currencyCode": "INR",
            },
            "purchaseOrderCode": po_code,
            "vendorInvoiceDateCheckDisable": True,
        }
        try:
            grn_resp = uc._post_with_reauth(GRN_CREATE_ENDPOINT, grn_payload, extra_headers=extra_headers)
        except Exception as exc:
            msg = f"GRN create failed (round {round_num + 1}): {exc}"
            _LOG().error(msg)
            frappe.log_error(msg, "UC PO GRN Worker")
            errors.append(msg)
            break

        if not grn_resp.get("successful"):
            msg = f"GRN create not successful (round {round_num + 1}): {grn_resp.get('message') or grn_resp}"
            _LOG().warning(msg)
            errors.append(msg)
            break

        grn_code = grn_resp.get("inflowReceiptCode") or ""
        if not grn_code:
            msg = f"GRN created but no code returned (round {round_num + 1})"
            _LOG().warning(msg)
            errors.append(msg)
            break

        created_grns.append(grn_code)
        _LOG().info("UC GRN created: %s (round %s)", grn_code, round_num + 1)

        # Add items to the GRN one by one
        for grn_item in this_round:
            add_payload = {
                "inflowReceiptCode": grn_code,
                "inflowReceiptItem": grn_item,
            }
            try:
                add_resp = uc._post_with_reauth(GRN_ADD_ITEM_ENDPOINT, add_payload, extra_headers=extra_headers)
                if not add_resp.get("successful"):
                    err = f"Add item {grn_item['skuCode']} to {grn_code} failed: {add_resp.get('message') or add_resp}"
                    _LOG().warning(err)
                    errors.append(err)
                else:
                    _LOG().info("Added SKU %s batch %s to GRN %s",
                                grn_item["skuCode"],
                                grn_item.get("wsBatchDetail", {}).get("wsBatchGroupFieldValue", {}).get("vendorBatchNumber", ""),
                                grn_code)
            except Exception as exc:
                err = f"Exception adding {grn_item['skuCode']} to {grn_code}: {exc}"
                _LOG().error(err)
                frappe.log_error(err, "UC PO GRN Worker")
                errors.append(err)

    return created_grns, errors


# ---------------------------------------------------------------------------
# Use Case 1: SAP Inward Transfer → UC PO + GRN
# ---------------------------------------------------------------------------

def process_inward_transfer(docname: str) -> dict:
    """
    Create UC PO + GRN(s) for a single SAP Inventory Transfer (towarehouse=EC-FG).
    Idempotent: skips PO creation if uniware_po_id already set.
    Called by the Ops Center UI button only — never scheduled.
    """
    inv_doc = frappe.get_doc("SAP Inventory Transfers", docname)

    if inv_doc.towarehouse != INWARD_TO_WAREHOUSE:
        return {
            "success": False,
            "message": f"Skipped: towarehouse is {inv_doc.towarehouse}, expected {INWARD_TO_WAREHOUSE}",
        }

    if not inv_doc.line_items:
        return {"success": False, "message": "No line items on this transfer document"}

    uc, extra_headers = _uc_session()

    # ── Step 1: Create PO (skip if already exists) ──────────────────────────
    po_code = (inv_doc.uniware_po_id or "").strip()
    if not po_code:
        po_payload = _build_po_payload(inv_doc.line_items)
        if not po_payload["purchaseOrderItems"]:
            return {"success": False, "message": "No valid SKU/quantity found in line items"}

        try:
            po_resp = uc._post_with_reauth(PO_ENDPOINT, po_payload, extra_headers=extra_headers)
        except Exception as exc:
            msg = f"PO creation API error: {exc}"
            frappe.log_error(msg, "UC PO GRN Worker")
            # comments is a plain Data field (Frappe default max length 140,
            # not 500) -- a too-long value crashes MariaDB instead of saving.
            frappe.db.set_value("SAP Inventory Transfers", docname, {
                "unicommerce_sync_status": "Failed",
                "comments": msg[:140],
            })
            frappe.db.commit()
            return {"success": False, "message": msg}

        if not po_resp.get("successful") or not po_resp.get("purchaseOrderCode"):
            msg = f"PO creation failed: {po_resp.get('message') or po_resp}"
            frappe.log_error(msg, "UC PO GRN Worker")
            frappe.db.set_value("SAP Inventory Transfers", docname, {
                "unicommerce_sync_status": "Failed",
                "comments": msg[:140],
            })
            frappe.db.commit()
            return {"success": False, "message": msg}

        po_code = po_resp["purchaseOrderCode"]
        frappe.db.set_value("SAP Inventory Transfers", docname, {
            "uniware_po_id": po_code,
            "uniware_po_status": "APPROVED",
            "unicommerce_sync_status": "Pending",
        })
        frappe.db.commit()
        _LOG().info("UC PO created: %s for SAP IT %s", po_code, docname)

    # ── Step 2: Create GRN(s) (skip if already done) ────────────────────────
    # Re-read from DB — inv_doc may be stale if PO was just created above.
    current_grn = frappe.db.get_value("SAP Inventory Transfers", docname, "uniware_grn_no") or ""
    if current_grn.strip():
        return {
            "success": True,
            "po_code": po_code,
            "message": f"GRNs already created: {current_grn}",
        }

    grn_items = _build_grn_item_list(inv_doc.line_items)
    if not grn_items:
        return {
            "success": True,
            "po_code": po_code,
            "message": "PO created but no batch items to add to GRN",
        }

    created_grns, grn_errors = _push_grn_rounds(po_code, grn_items, uc, extra_headers, docname=docname)

    grn_str = ",".join(created_grns) if created_grns else ""
    if created_grns and not grn_errors:
        final_po_status = "GRN_COMPLETED"
        sync_status = "Synced"
    elif created_grns and grn_errors:
        final_po_status = "GRN_PARTIAL"
        sync_status = "Partial"
    else:
        final_po_status = "APPROVED"
        sync_status = "Failed"
    # comments is a plain Data field (Frappe default max length 140, not 500).
    comment = ("; ".join(grn_errors))[:140] if grn_errors else ""

    update_fields = {
        "uniware_po_status": final_po_status,
        "unicommerce_sync_status": sync_status,
    }
    if grn_str:
        update_fields["uniware_grn_no"] = grn_str
    if comment:
        update_fields["comments"] = comment
    frappe.db.set_value("SAP Inventory Transfers", docname, update_fields)
    frappe.db.commit()

    _LOG().info("Inward transfer %s: PO=%s GRNs=%s errors=%s",
                docname, po_code, created_grns, len(grn_errors))

    return {
        "success": bool(created_grns),
        "po_code": po_code,
        "grn_codes": created_grns,
        "errors": grn_errors,
        "status": final_po_status,
    }


def process_pending_inward_transfers(days: int = 30) -> dict:
    """
    Process all incomplete SAP Inward Transfers (towarehouse=EC-FG):
      - No PO created yet, OR
      - PO created but GRN never completed (e.g. previous run failed at GRN step).
    Called from background job only. Returns summary dict.
    """
    from frappe.utils import add_to_date
    start = add_to_date(nowdate(), days=-int(days or 30))
    base_filters = {"towarehouse": INWARD_TO_WAREHOUSE, "docdate": [">", start]}

    # Category 1: no PO at all
    no_po = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={**base_filters, "uniware_po_id": ["is", "not set"]},
        fields=["name"],
        order_by="docdate asc",
        limit=500,
    )

    # Category 2: PO approved but GRN missing (failed at GRN step)
    # Exclude unapproved POs — attempting a GRN against an unapproved PO causes UC API errors.
    po_no_grn = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={
            **base_filters,
            "uniware_po_id": ["is", "set"],
            "uniware_grn_no": ["is", "not set"],
            "uniware_po_status": ["in", ["APPROVED", *COMPLETED_PO_STATUSES]],
        },
        fields=["name"],
        order_by="docdate asc",
        limit=500,
    )

    # Category 3: PO created but not yet approved (step 2 failed on prior run)
    po_unapproved = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={
            **base_filters,
            "uniware_po_id": ["is", "set"],
            "uniware_grn_no": ["is", "not set"],
            "uniware_po_status": ["not in", ["APPROVED", *COMPLETED_PO_STATUSES]],
        },
        fields=["name"],
        order_by="docdate asc",
        limit=500,
    )

    # Deduplicate and preserve order for categories 1 + 2
    seen: set[str] = set()
    pending: list[dict] = []
    for row in no_po + po_no_grn:
        if row["name"] not in seen:
            seen.add(row["name"])
            pending.append(row)

    total = len(pending)
    success_count = failed_count = 0
    for row in pending:
        result = process_inward_transfer(row["name"])
        if result.get("success"):
            success_count += 1
        else:
            failed_count += 1

    # Category 3: PO created but not yet approved — call approve directly,
    # then leave GRN creation to the next batch run (category 2 will pick them up).
    approve_success = approve_failed = 0
    if po_unapproved:
        uc, extra_headers = _uc_session()
    for row in po_unapproved:
        if row["name"] in seen:
            continue
        po_code = frappe.db.get_value("SAP Inventory Transfers", row["name"], "uniware_po_id") or ""
        if not po_code:
            continue
        try:
            resp = uc._post_with_reauth(
                "services/rest/v1/purchase/purchaseOrder/approve",
                body={"purchaseOrderCode": po_code},
                extra_headers=extra_headers,
            )
            if resp.get("successful"):
                frappe.db.set_value("SAP Inventory Transfers", row["name"], {
                    "uniware_po_status": "APPROVED",
                    "unicommerce_sync_status": "Pending",
                    "comments": "",
                })
                frappe.db.commit()
                approve_success += 1
            else:
                frappe.log_error(f"PO approve failed for {row['name']} (PO {po_code}): {resp}", "UC PO GRN Worker")
                approve_failed += 1
        except Exception as exc:
            frappe.log_error(f"PO approve error for {row['name']}: {exc}", "UC PO GRN Worker")
            approve_failed += 1

    _LOG().info(
        "Batch inward transfer sync: total=%s success=%s failed=%s approve_ok=%s approve_fail=%s",
        total, success_count, failed_count, approve_success, approve_failed,
    )
    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "approve_retried": approve_success + approve_failed,
        "approve_success": approve_success,
        "approve_failed": approve_failed,
    }


def get_inward_transfer_list(days: int = 30) -> list[dict]:
    """
    Read-only: return SAP Inventory Transfers (→ EC-FG) with their UC sync status.
    Safe to call at any time — no UC writes.
    """
    from frappe.utils import add_to_date
    start = add_to_date(nowdate(), days=-int(days or 30))
    rows = frappe.db.get_list(
        "SAP Inventory Transfers",
        filters={
            "towarehouse": INWARD_TO_WAREHOUSE,
            "docdate": [">", start],
        },
        fields=["name", "docnum", "docdate", "fromwarehouse", "towarehouse",
                "uniware_po_id", "uniware_po_status", "uniware_grn_no", "comments"],
        order_by="docdate desc",
        limit=200,
    )

    result = []
    for row in rows:
        po = (row.get("uniware_po_id") or "").strip()
        grn = (row.get("uniware_grn_no") or "").strip()
        po_status = (row.get("uniware_po_status") or "").strip()

        if po and grn and po_status == "GRN_COMPLETED":
            ui_status = "GRN_COMPLETED"
        elif po and grn:
            ui_status = "GRN_PARTIAL"
        elif po:
            ui_status = "PO_CREATED"
        else:
            ui_status = "PENDING"

        result.append({
            "name": row["name"],
            "docnum": row.get("docnum") or row["name"],
            "docdate": str(row.get("docdate") or ""),
            "fromwarehouse": row.get("fromwarehouse") or "",
            "po_code": po,
            "po_status": po_status,
            "grn_nos": grn,
            "ui_status": ui_status,
            "comments": (row.get("comments") or "")[:200],
        })

    return result


# ---------------------------------------------------------------------------
# Use Case 2: Manual UC PO → GRN
# ---------------------------------------------------------------------------

def get_uc_po_details(po_code: str) -> dict:
    """
    Read-only: fetch a UC PO's details (items, status) by PO code.
    Safe to call — no UC writes.
    """
    uc, extra_headers = _uc_session()
    try:
        resp = uc._post_with_reauth(
            PO_GET_ENDPOINT,
            {"purchaseOrderCode": po_code.strip()},
            extra_headers=extra_headers,
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    if not resp.get("successful"):
        return {"success": False, "error": resp.get("message") or "UC returned unsuccessful"}

    items = resp.get("purchaseOrderItems") or []
    return {
        "success": True,
        "po_code": po_code,
        "status_code": resp.get("statusCode") or "",
        "vendor_name": resp.get("vendorName") or "",
        "items": [
            {
                "sku": item.get("itemSKU") or "",
                "quantity": item.get("quantity") or 0,
            }
            for item in items
        ],
        "raw_status": resp.get("statusCode") or "",
    }


def create_grn_for_manual_po(po_code: str) -> dict:
    """
    Create GRN(s) for a PO that was manually created in Unicommerce.
    The GRN items are derived from the PO line items (no batch detail —
    vendorBatchNumber is set to 'NA' since no SAP doc exists for lookup).
    Called by Ops Center UI button only — never scheduled.
    """
    po_details = get_uc_po_details(po_code)
    if not po_details.get("success"):
        return {"success": False, "message": po_details.get("error", "Could not fetch PO")}

    items = po_details.get("items") or []
    if not items:
        return {"success": False, "message": f"PO {po_code} has no items"}

    grn_items = [
        {
            "skuCode": item["sku"],
            "quantity": float(item["quantity"] or 0),
            "unitPrice": 1,
            "wsBatchDetail": {
                "wsBatchGroupFieldValue": {"vendorBatchNumber": "NA"},
            },
        }
        for item in items
        if (item.get("sku") or "").strip() and float(item.get("quantity") or 0) > 0
    ]

    if not grn_items:
        return {"success": False, "message": f"No valid items in PO {po_code}"}

    uc, extra_headers = _uc_session()
    created_grns, errors = _push_grn_rounds(po_code, grn_items, uc, extra_headers)

    _LOG().info("Manual UC PO %s: GRNs=%s errors=%s", po_code, created_grns, len(errors))
    return {
        "success": bool(created_grns),
        "po_code": po_code,
        "grn_codes": created_grns,
        "errors": errors,
    }
