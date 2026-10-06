from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import frappe

from .client import SAPClient


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def load_parent_order(order_ref: str | None):
    order_ref = normalize_text(order_ref)
    if not order_ref:
        return None

    if frappe.db.exists("Unicommerce Orders", order_ref):
        return frappe.get_doc("Unicommerce Orders", order_ref)

    by_uniware = frappe.db.get_value("Unicommerce Orders", {"uniware_id": order_ref}, "name")
    if by_uniware:
        return frappe.get_doc("Unicommerce Orders", by_uniware)

    return None


def resolve_actual_uc_order_id(order_ref: str | None) -> str:
    parent = load_parent_order(order_ref)
    if parent:
        return str(parent.name)
    return normalize_text(order_ref)


def _safe_json_loads(raw_value: Any) -> dict:
    if isinstance(raw_value, dict):
        return raw_value
    if not raw_value:
        return {}
    try:
        return json.loads(raw_value)
    except Exception:
        return {}


def _invoice_line_maps(invoice_doc: dict) -> dict[str, Any]:
    by_uc_item_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_item_code: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for idx, line in enumerate(invoice_doc.get("DocumentLines") or []):
        item_code = normalize_text(line.get("ItemCode"))
        sale_order_item_code = normalize_text(
            line.get("U_UCOrderItemID") or line.get("U_Sale_order_itemcode")
        )
        warehouse_code = normalize_text(line.get("WarehouseCode"))
        base_line = line.get("LineNum", idx)
        try:
            base_line = int(base_line)
        except Exception:
            base_line = idx

        line_ref = {
            "base_line": base_line,
            "item_code": item_code,
            "warehouse_code": warehouse_code,
            "account_code": normalize_text(line.get("AccountCode")),
            "batch_numbers": [
                {
                    "BatchNumber": normalize_text((bn or {}).get("BatchNumber")),
                    "Quantity": float((bn or {}).get("Quantity") or 0),
                }
                for bn in (line.get("BatchNumbers") or [])
                if normalize_text((bn or {}).get("BatchNumber"))
            ],
        }
        if sale_order_item_code:
            by_uc_item_id[sale_order_item_code].append(line_ref)
        if item_code:
            by_item_code[item_code].append(line_ref)

    return {"by_uc_item_id": by_uc_item_id, "by_item_code": by_item_code}


def _pick_line(
    item: dict,
    line_maps: dict[str, Any],
    used_keys: set[tuple[str, int]],
) -> dict[str, Any] | None:
    sale_order_item_code = normalize_text(item.get("saleOrderItemCode"))
    item_code = normalize_text(item.get("itemSku"))

    if sale_order_item_code:
        for line in line_maps["by_uc_item_id"].get(sale_order_item_code, []):
            key = (line["item_code"], line["base_line"])
            if key not in used_keys:
                used_keys.add(key)
                return line

    unused_candidates = []
    for line in line_maps["by_item_code"].get(item_code, []):
        key = (line["item_code"], line["base_line"])
        if key not in used_keys:
            unused_candidates.append((key, line))

    if unused_candidates:
        # Pick first unused candidate — handles multi-batch (same SKU, multiple SAP lines)
        # and partial-quantity returns where SAP qty != UC order qty.
        key, line = unused_candidates[0]
        used_keys.add(key)
        return line
    return None


def prepare_credit_note_items(
    parent_order_doc,
    raw_items: list[dict] | None,
    fallback_warehouse: str = "",
    invoice_doc: dict | None = None,
    sap_client: SAPClient | None = None,
) -> dict[str, Any]:
    payload_doc = _safe_json_loads(getattr(parent_order_doc, "payload_json", None))
    payload_maps = _invoice_line_maps(payload_doc)
    used_payload_keys: set[tuple[str, int]] = set()
    normalized_items: list[dict] = []

    for row in raw_items or []:
        normalized = dict(row or {})
        # UC return/get uses skuCode; older fallbacks for any alternate field names
        normalized["itemSku"] = normalize_text(
            row.get("skuCode") or row.get("itemSku") or row.get("itemTypeSkuCode")
        )
        normalized["saleOrderItemCode"] = normalize_text(
            row.get("saleOrderItemCode") or row.get("code") or row.get("channelSaleOrderItemCode")
        )
        normalized["warehouseCode"] = normalize_text(
            row.get("forwardItemFacility") or row.get("warehouseCode") or row.get("returnFacilityCode") or fallback_warehouse
        )
        try:
            normalized["quantity"] = float(
                row.get("quantity") or row.get("returnedQuantity") or row.get("totalQuantity") or 1
            )
        except Exception:
            normalized["quantity"] = 1.0

        line = _pick_line(normalized, payload_maps, used_payload_keys)
        if line:
            normalized["sapBaseLine"] = int(line["base_line"])
            normalized["sapItemCode"] = line["item_code"]
            normalized["itemSku"] = normalized["itemSku"] or line["item_code"]
            normalized["warehouseCode"] = normalized["warehouseCode"] or line["warehouse_code"]
            normalized["sapAccountCode"] = line.get("account_code") or ""
            normalized["sapBatchNumbers"] = line.get("batch_numbers") or []
        normalized_items.append(normalized)

    resolved_items = [row for row in normalized_items if row.get("sapBaseLine") not in (None, "")]
    unresolved_items = [row for row in normalized_items if row.get("sapBaseLine") in (None, "")]
    if unresolved_items and getattr(parent_order_doc, "sap_ar_invoice_docentry", None):
        if invoice_doc:
            sap_maps = _invoice_line_maps(invoice_doc)
        else:
            try:
                client = sap_client or SAPClient()
                sap_doc = client.get_invoice_by_doc_entry(parent_order_doc.sap_ar_invoice_docentry)
                sap_maps = _invoice_line_maps(sap_doc)
            except Exception:
                sap_maps = {"by_uc_item_id": {}, "by_item_code": {}}

        used_sap_keys: set[tuple[str, int]] = set()
        still_unresolved: list[dict] = []
        for row in unresolved_items:
            line = _pick_line(row, sap_maps, used_sap_keys)
            if not line:
                still_unresolved.append(row)
                continue
            row["sapBaseLine"] = int(line["base_line"])
            row["sapItemCode"] = line["item_code"]
            row["itemSku"] = row["itemSku"] or line["item_code"]
            row["warehouseCode"] = row["warehouseCode"] or line["warehouse_code"]
            row["sapAccountCode"] = line.get("account_code") or ""
            row["sapBatchNumbers"] = line.get("batch_numbers") or []
            resolved_items.append(row)
        unresolved_items = still_unresolved

    return {
        "items": resolved_items + unresolved_items,
        "resolved_count": len(resolved_items),
        "unresolved_count": len(unresolved_items),
        "unresolved": unresolved_items,
    }
