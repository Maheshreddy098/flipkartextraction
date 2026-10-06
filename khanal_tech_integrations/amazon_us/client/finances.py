"""
SP-API Finances API client: list refund events.

Finances API reports refunds as MONEY (ChargeType Principal/Tax amounts
per SKU) -- it does not report a returned quantity. The credit-note
builder infers quantity from the refunded Principal amount divided by
the original per-unit invoice price; see workers/credit_note.py.
"""
from datetime import datetime, timedelta, timezone

import frappe

from khanal_tech_integrations.amazon_us.client.sp_api import _get

_FINANCES_PATH = "/finances/v0/financialEvents"


def _clamp_posted_before(posted_before):
    """Amazon 400s when PostedBefore is less than 2 minutes in the past, which
    happens whenever the caller passes today's Pacific date (its end-of-day is
    still in the future). Pull it back to now-5min in that case."""
    limit = datetime.now(timezone.utc) - timedelta(minutes=5)
    try:
        requested = datetime.fromisoformat(posted_before.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return posted_before
    if requested > limit:
        return limit.strftime("%Y-%m-%dT%H:%M:%SZ")
    return posted_before


def fetch_refund_events(posted_after, posted_before=None):
    """
    posted_after/posted_before: UTC ISO 8601 strings.
    Returns a list of dicts shaped like the CSV-parsed events in
    workers/credit_note.py, so both sources feed the same posting loop:
      {refund_id, amazon_order_id, posted_date, item_adjustments: [
          {seller_sku, principal_amount, tax_amount,
           shipping_amount, shipping_tax_amount}, ...
      ]}
    One event per (AmazonOrderId, PostedDate) -- matches how Amazon
    batches a single refund transaction's line items in the response.
    """
    if posted_before:
        posted_before = _clamp_posted_before(posted_before)

    events = []
    next_token = None

    while True:
        if next_token:
            params = {"NextToken": next_token}
        else:
            params = {"PostedAfter": posted_after, "MaxResultsPerPage": 100}
            if posted_before:
                params["PostedBefore"] = posted_before

        resp = _get(_FINANCES_PATH, params=params)
        if resp.status_code != 200:
            frappe.log_error(
                f"SP-API Finances fetch failed: {resp.status_code} {resp.text[:500]}",
                "Amazon US SP-API",
            )
            raise Exception(f"SP-API Finances fetch failed: {resp.status_code}")

        payload = resp.json().get("payload", {})
        financial_events = payload.get("FinancialEvents", {})

        for raw in financial_events.get("RefundEventList") or []:
            event = _parse_refund_event(raw)
            if event:
                events.append(event)

        next_token = payload.get("NextToken")
        if not next_token:
            return events


def _parse_refund_event(raw):
    order_id = raw.get("AmazonOrderId", "")
    posted_date_raw = raw.get("PostedDate", "")
    if not order_id or not posted_date_raw:
        return None

    adjustments = []
    for item in raw.get("ShipmentItemAdjustmentList") or []:
        sku = (item.get("SellerSKU") or "").strip()
        if not sku:
            continue

        principal = tax = shipping = shipping_tax = 0.0
        for charge in item.get("ItemChargeAdjustmentList") or []:
            amount = float((charge.get("ChargeAmount") or {}).get("CurrencyAmount") or 0)
            charge_type = charge.get("ChargeType", "")
            if charge_type == "Principal":
                principal += amount
            elif charge_type == "Tax":
                tax += amount
            elif charge_type == "ShippingCharge":
                shipping += amount
            elif charge_type == "ShippingTax":
                shipping_tax += amount

        if principal == 0 and tax == 0 and shipping == 0 and shipping_tax == 0:
            continue
        adjustments.append({
            "seller_sku": sku,
            "principal_amount": principal,
            "tax_amount": tax,
            "shipping_amount": shipping,
            "shipping_tax_amount": shipping_tax,
        })

    if not adjustments:
        return None

    return {
        "refund_id": f"{order_id}-{posted_date_raw}",
        "amazon_order_id": order_id,
        "posted_date": posted_date_raw[:10],
        "item_adjustments": adjustments,
    }
