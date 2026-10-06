"""
Amazon FBA inventory vs SAP B1 inventory reconciliation.

Compares every SAP<->Amazon mapped SKU (mappers.payload.get_item_mapping,
the same hybrid SAP U_Amz_SKU + Amazon US Item Mapping source used for
invoice posting) against live Amazon FBA inventory, on the AMZ-FBA
warehouse only. On-demand only -- no scheduler entry, no persistence;
every run is a fresh live comparison.

Flags (definitions confirmed with the business before building this):
  MISSING    SAP has the SKU mapped, but Amazon's inventory feed doesn't
             return it at all -- a stale mapping or a delisted item SAP
             still thinks is live.
  MISMATCH   SAP OnHand != Amazon totalQuantity. Exact match, no tolerance.
  INACTIVE   SAP item is inactive/frozen but Amazon still shows nonzero
             quantity for it -- overselling risk, not the orphaned-stock
             direction.
  BLOCKED    unfulfillable + reserved + inbound(working/shipped/receiving)
             > _BLOCKED_THRESHOLD units. Reserved/inbound alone is normal
             ongoing FBA activity, not a problem by itself.
"""
import frappe

from khanal_tech_integrations.amazon_us.client.fba_inventory import get_inventory_summaries
from khanal_tech_integrations.amazon_us.client.hana import HanaUnavailableError, _close, _connect, _get_schema
from khanal_tech_integrations.amazon_us.mappers.payload import get_item_mapping

_SETTINGS_DOCTYPE = "Amazon US Settings"
_BLOCKED_THRESHOLD = 20  # units; tune here, same as the health check's own thresholds


def _cache_key(job_id):
    return f"amz_us_inventory_recon_{job_id}"


def _emit(job_id, msg, level="info"):
    if not job_id:
        frappe.logger().info(f"[amz_inventory_recon] {msg}")
        return
    import json
    raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    log = data.get("log", [])
    log.append({"msg": msg, "level": level, "at": str(frappe.utils.now_datetime())})
    data["log"] = log[-100:]
    frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


def _set(job_id, updates):
    if not job_id:
        return
    import json
    raw = frappe.cache().get_value(_cache_key(job_id)) or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    data.update(updates)
    frappe.cache().set_value(_cache_key(job_id), json.dumps(data), expires_in_sec=3600)


def _fetch_sap_inventory(item_codes, warehouse):
    """
    Bulk {item_code: {"on_hand": float, "active": bool}} for item_codes on
    warehouse, via one batched HANA query.

    NOTE: OITM."validFor" ('Y'/'N') is the standard SAP B1 item-active flag
    -- verify this against the real INC HANA schema before relying on the
    INACTIVE flag in production; every other HANA query in this module
    (hana.py) was verified against a live connection when written, this one
    could not be (no live HANA reachable from this dev environment).
    Raises HanaUnavailableError if HANA is unreachable.
    """
    if not item_codes:
        return {}

    schema = _get_schema()
    if not schema:
        raise HanaUnavailableError("HANA schema not configured in INC SAP Settings")

    conn, cursor = _connect()
    if not conn:
        raise HanaUnavailableError("HANA connection failed — check INC SAP Settings and error log")

    try:
        placeholders = ",".join(["?"] * len(item_codes))
        query = f"""
            SELECT T0."ItemCode" AS "ItemCode", T0."OnHand" AS "OnHand", T1."validFor" AS "ValidFor"
            FROM "{schema}"."OITW" T0
            JOIN "{schema}"."OITM" T1 ON T1."ItemCode" = T0."ItemCode"
            WHERE T0."WhsCode" = ? AND T0."ItemCode" IN ({placeholders})
        """
        cursor.execute(query, [warehouse, *item_codes])
        rows = cursor.fetchall() or []
    except Exception as e:
        raise HanaUnavailableError(f"SAP inventory query failed: {e}")
    finally:
        _close(conn, cursor)

    return {
        str(r[0]).strip(): {"on_hand": float(r[1] or 0), "active": str(r[2]).strip().upper() != "N"}
        for r in rows
    }


def _blocked_qty(amazon_row):
    details = amazon_row.get("inventoryDetails") or {}
    unfulfillable = (details.get("unfulfillableQuantity") or {}).get("totalUnfulfillableQuantity", 0)
    reserved = (details.get("reservedQuantity") or {}).get("totalReservedQuantity", 0)
    inbound = (
        (details.get("inboundWorkingQuantity") or 0)
        + (details.get("inboundShippedQuantity") or 0)
        + (details.get("inboundReceivingQuantity") or 0)
    )
    return float(unfulfillable or 0) + float(reserved or 0) + float(inbound or 0)


def build_inventory_reconciliation(progress_id=None):
    """
    Compare SAP inventory (AMZ-FBA warehouse) against live Amazon FBA
    inventory for every mapped SKU. Returns a summary dict with per-SKU
    rows and flag counts. Never posts anything -- read-only comparison.
    """
    _set(progress_id, {"status": "running"})
    settings = frappe.get_doc(_SETTINGS_DOCTYPE)
    warehouse = settings.sap_warehouse_code
    marketplace_id = settings.marketplace_id

    _emit(progress_id, "Loading SAP<->Amazon SKU mapping...")
    item_mapping = get_item_mapping()
    item_codes = sorted({m["sap_item_code"] for m in item_mapping.values()})
    _emit(progress_id, f"{len(item_mapping)} mapped SKUs ({len(item_codes)} distinct SAP item codes)")

    try:
        _emit(progress_id, f"Querying SAP inventory on {warehouse}...")
        sap_inventory = _fetch_sap_inventory(item_codes, warehouse)
    except HanaUnavailableError as e:
        msg = f"HANA unavailable: {e}"
        _emit(progress_id, msg, "error")
        result = {"status": "hana_down", "message": msg}
        _set(progress_id, result)
        return result

    _emit(progress_id, "Pulling live Amazon FBA inventory...")
    try:
        amazon_inventory = get_inventory_summaries(marketplace_id)
    except Exception as e:
        msg = f"Amazon Inventory API failed: {e}"
        _emit(progress_id, msg, "error")
        frappe.log_error(msg, "Amazon US Inventory Reconciliation")
        result = {"status": "error", "message": msg}
        _set(progress_id, result)
        return result

    _emit(progress_id, f"Amazon returned {len(amazon_inventory)} SKUs. Comparing...")

    rows = []
    counts = {"missing": 0, "mismatch": 0, "inactive": 0, "blocked": 0}

    for seller_sku, mapping in sorted(item_mapping.items()):
        sap_item_code = mapping["sap_item_code"]
        sap_row = sap_inventory.get(sap_item_code, {"on_hand": 0.0, "active": True})
        sap_qty = sap_row["on_hand"]
        sap_active = sap_row["active"]
        amazon_row = amazon_inventory.get(seller_sku)

        flags = []
        remarks = []

        if amazon_row is None:
            flags.append("MISSING")
            remarks.append("SAP has this SKU mapped, but Amazon's inventory feed doesn't return it.")
            rows.append({
                "seller_sku": seller_sku, "sap_item_code": sap_item_code,
                "sap_qty": sap_qty, "amazon_qty": None, "diff": None, "blocked_qty": None,
                "flags": flags, "remarks": " ".join(remarks),
            })
            counts["missing"] += 1
            continue

        amazon_qty = float(amazon_row.get("totalQuantity") or 0)
        diff = round(sap_qty - amazon_qty, 3)
        blocked_qty = _blocked_qty(amazon_row)

        if diff != 0:
            flags.append("MISMATCH")
            remarks.append(f"SAP OnHand {sap_qty:g} != Amazon total {amazon_qty:g}.")
            counts["mismatch"] += 1

        if not sap_active and amazon_qty > 0:
            flags.append("INACTIVE")
            remarks.append("SAP item is inactive but Amazon still shows stock -- overselling risk.")
            counts["inactive"] += 1

        if blocked_qty > _BLOCKED_THRESHOLD:
            flags.append("BLOCKED")
            remarks.append(f"{blocked_qty:g} units blocked (unfulfillable/reserved/inbound).")
            counts["blocked"] += 1

        rows.append({
            "seller_sku": seller_sku, "sap_item_code": sap_item_code,
            "sap_qty": sap_qty, "amazon_qty": amazon_qty, "diff": diff, "blocked_qty": blocked_qty,
            "flags": flags, "remarks": " ".join(remarks),
        })

    result = {
        "status": "done",
        "total_skus": len(item_mapping),
        "counts": counts,
        "rows": rows,
    }
    _emit(progress_id, f"Done. missing={counts['missing']} mismatch={counts['mismatch']} "
                        f"inactive={counts['inactive']} blocked={counts['blocked']}")
    _set(progress_id, result)
    return result
