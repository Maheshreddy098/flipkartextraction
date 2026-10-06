import { frappeRequest } from 'frappe-ui'

const BASE = 'khanal_tech_integrations.consumables.api.inventory'

function normalizeResponse(response) {
  return response?.message ?? response
}

export function fetchWarehouses(plant_code) {
  return frappeRequest({ url: `${BASE}.get_warehouses`, params: { plant_code } }).then(normalizeResponse)
}

export function fetchInventory(plant_code, warehouse_code, opts = {}) {
  return frappeRequest({
    url: `${BASE}.get_inventory`,
    params: { plant_code, warehouse_code, ...opts },
  }).then(normalizeResponse)
}

export function fetchBatchDetail(plant_code, warehouse_code, item_code) {
  return frappeRequest({
    url: `${BASE}.get_batch_detail`,
    params: { plant_code, warehouse_code, item_code },
  }).then(normalizeResponse)
}

export function searchItemsForRequest(search) {
  return frappeRequest({
    url: `${BASE}.search_items_for_request`,
    params: { search },
  }).then(normalizeResponse)
}
