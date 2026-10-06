"""SP-API FBA Inventory client: GET /fba/inventory/v1/summaries."""
from khanal_tech_integrations.amazon_us.client.sp_api import _get

_INVENTORY_PATH = "/fba/inventory/v1/summaries"


def get_inventory_summaries(marketplace_id):
    """
    Pull every FBA inventory summary for marketplace_id (paginated via
    nextToken). Unlike the Orders API's NextToken-only-on-subsequent-pages
    convention used elsewhere in sp_api.py, the Inventory API requires
    marketplaceIds (and the other base params) on EVERY page, including
    paginated ones -- dropping them gets a 400 "Invalid query parameter
    [marketplaceIds] value entered" on page 2+ (confirmed live: page 1
    alone always succeeds, it's only pagination that broke without this).

    Returns {seller_sku: summary_dict}, where each summary_dict has
    totalQuantity and inventoryDetails (fulfillableQuantity,
    unfulfillableQuantity.totalUnfulfillableQuantity,
    reservedQuantity.totalReservedQuantity, inboundWorkingQuantity,
    inboundShippedQuantity, inboundReceivingQuantity).
    """
    base_params = {
        "granularityType": "Marketplace",
        "granularityId": marketplace_id,
        "marketplaceIds": marketplace_id,
        "details": "true",
    }

    summaries = {}
    next_token = None
    while True:
        params = {**base_params, "nextToken": next_token} if next_token else base_params
        resp = _get(_INVENTORY_PATH, params=params)
        if resp.status_code != 200:
            raise Exception(f"get_inventory_summaries failed: {resp.status_code} {resp.text[:300]}")

        body = resp.json()
        for row in body.get("payload", {}).get("inventorySummaries", []):
            sku = row.get("sellerSku")
            if sku:
                summaries[sku] = row

        next_token = body.get("pagination", {}).get("nextToken")
        if not next_token:
            break

    return summaries
