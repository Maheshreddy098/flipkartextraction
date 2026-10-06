import frappe
from frappe.utils import add_to_date, now_datetime, today
import json

from .client import SAPClient, UCClient
from .mappers import ar_invoice_payload
from .workers.fetch import _extract_channel, _extract_order_date, _extract_uc_order_id


@frappe.whitelist()
def check_connections():
    """
    Run login-only connectivity checks for SAP and Unicommerce.
    No posting/fetching business documents is performed.
    """
    results = {
        "sap_login": {"ok": False, "message": ""},
        "uc_login": {"ok": False, "message": ""},
    }

    try:
        sap = SAPClient()
        sap.login()
        results["sap_login"] = {
            "ok": True,
            "message": "Connected and authenticated successfully",
        }
        try:
            sap.logout()
        except Exception:
            pass
    except Exception as e:
        results["sap_login"] = {"ok": False, "message": str(e)}

    try:
        uc = UCClient()
        uc._ensure_token()
        source_map = {
            "stored_token": "stored token",
            "refresh_token": "refresh token",
            "password_grant": "password grant",
        }
        source = source_map.get(getattr(uc, "token_source", ""), "fresh login")
        results["uc_login"] = {
            "ok": bool(uc.token),
            "message": f"Connected using {source}" if uc.token else "No token returned",
        }
    except Exception as e:
        results["uc_login"] = {"ok": False, "message": str(e)}

    return results


@frappe.whitelist()
def fetch_unicommerce_orders_window(window: str = "this_month", channel: str | None = None):
    """
    Fetch real Unicommerce orders for a date window (read-only diagnostic).
    window: this_month | last_month
    """
    now_dt = now_datetime()

    if window == "last_month":
        first_day_this_month = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        from_dt = add_to_date(first_day_this_month, months=-1)
        to_dt = add_to_date(first_day_this_month, seconds=-1)
    else:
        from_dt = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        to_dt = now_dt

    uc = UCClient()
    uc.login()
    orders = uc.get_orders_between(
        from_date=str(from_dt),
        to_date=str(to_dt),
        channel=channel,
    )

    sample_codes = []
    for order in orders[:10]:
        code = order.get("code") or order.get("saleOrderCode") or order.get("displayOrderCode")
        if code:
            sample_codes.append(code)

    return {
        "window": window,
        "channel": channel,
        "from": str(from_dt),
        "to": str(to_dt),
        "count": len(orders),
        "sample_order_codes": sample_codes,
    }


@frappe.whitelist()
def inspect_sample_ar_invoice_payloads(limit: int = 5):
    """
    Build and inspect AR invoice payloads for a sample of staged orders.
    Returns both successes and actionable errors.
    """
    rows = frappe.get_all(
        "Unicommerce Orders",
        filters={"pipeline_status": "fetched"},
        fields=["name", "channel_name as channel", "order_date"],
        order_by="creation desc",
        limit=limit,
    )

    results = []
    for row in rows:
        try:
            doc = frappe.get_doc("Unicommerce Orders", row.name)
            payload = ar_invoice_payload(doc)
            results.append(
                {
                    "uc_order_id": row.name,
                    "channel": row.channel,
                    "ok": True,
                    "payload": payload,
                    "line_count": len(payload.get("DocumentLines", [])),
                    "card_code": payload.get("CardCode"),
                    "series": payload.get("Series"),
                    "first_line_preview": payload.get("DocumentLines", [])[:1],
                }
            )
        except Exception as e:
            results.append(
                {
                    "uc_order_id": row.name,
                    "channel": row.channel,
                    "ok": False,
                    "error": str(e),
                }
            )

    return {"checked": len(rows), "results": results}


@frappe.whitelist()
def summarize_staged_order_dimensions(limit: int = 500):
    """
    Summarize channels, warehouse codes, and tax percents from staged order raw JSON.
    Useful for preparing Unicommerce Settings mappings.
    """
    rows = frappe.get_all(
        "Unicommerce Orders",
        fields=["name", "channel_name as channel", "order_json"],
        order_by="creation desc",
        limit=limit,
    )
    channels = {}
    wh_codes = {}
    tax_percents = {}

    for row in rows:
        ch = row.channel or ""
        channels[ch] = channels.get(ch, 0) + 1
        try:
            raw = json.loads(row.order_json or "{}")
        except Exception:
            continue
        for item in raw.get("items", []):
            wh = str(item.get("warehouseCode") or "").strip()
            if wh:
                wh_codes[wh] = wh_codes.get(wh, 0) + 1
            tx = item.get("taxPercent", 0)
            try:
                tx_key = str(int(float(tx)))
            except Exception:
                tx_key = str(tx)
            tax_percents[tx_key] = tax_percents.get(tx_key, 0) + 1

    return {
        "rows_scanned": len(rows),
        "channels": channels,
        "warehouse_codes": wh_codes,
        "tax_percents": tax_percents,
    }


@frappe.whitelist()
def backfill_orders_in_batches(
    from_date: str,
    to_date: str | None = None,
    batch_size: int = 500,
):
    """
    Refetch and stage full order details in controlled batches.
    This does not depend on poller cursor movement.
    """
    uc = UCClient()
    uc.login()

    to_dt = to_date or str(now_datetime())
    summaries = uc.get_orders_between(from_date=from_date, to_date=to_dt)

    total = len(summaries)
    new_count = 0
    updated_count = 0
    skipped_posted = 0
    detail_failed = 0
    batches = 0

    for i in range(0, total, int(batch_size)):
        chunk = summaries[i : i + int(batch_size)]
        batches += 1
        for summary in chunk:
            uc_order_id = _extract_uc_order_id(summary)
            if not uc_order_id:
                continue
            try:
                order = uc.get_order_detail(uc_order_id)
                if not order:
                    detail_failed += 1
                    continue
            except Exception:
                detail_failed += 1
                continue

            existing_name = frappe.db.exists("Unicommerce Orders", uc_order_id)
            if existing_name:
                current_status = frappe.db.get_value("Unicommerce Orders", existing_name, "pipeline_status")
                if current_status == "posted":
                    skipped_posted += 1
                    continue
                frappe.db.set_value(
                    "Unicommerce Orders",
                    existing_name,
                    {
                        "order_json": json.dumps(order),
                        "channel_name": _extract_channel(order),
                        "order_date": _extract_order_date(order),
                        "pipeline_status": "fetched",
                    },
                )
                updated_count += 1
            else:
                doc = frappe.get_doc(
                    {
                        "doctype": "Unicommerce Orders",
                        "uniware_id": uc_order_id,
                        "channel_name": _extract_channel(order),
                        "order_date": _extract_order_date(order),
                        "pipeline_status": "fetched",
                        "order_json": json.dumps(order),
                        "attempt_count": 0,
                    }
                )
                try:
                    doc.insert(ignore_permissions=True)
                    new_count += 1
                except Exception:
                    existing_name = frappe.db.exists("Unicommerce Orders", uc_order_id)
                    if existing_name:
                        frappe.db.set_value(
                            "Unicommerce Orders",
                            existing_name,
                            {
                                "order_json": json.dumps(order),
                                "channel_name": _extract_channel(order),
                                "order_date": _extract_order_date(order),
                                "pipeline_status": "fetched",
                            },
                        )
                        updated_count += 1

        frappe.db.commit()

    return {
        "from_date": from_date,
        "to_date": to_dt,
        "fetched_summaries": total,
        "batches": batches,
        "new": new_count,
        "updated": updated_count,
        "skipped_posted": skipped_posted,
        "detail_failed": detail_failed,
    }
