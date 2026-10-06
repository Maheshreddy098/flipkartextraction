import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchInventory(params = {}) {
  return callApi(EP.INVENTORY_LIST, params)
}

export function fetchItemStock(item_code, warehouse = 'WowPets Warehouse') {
  return callApi(EP.ITEM_STOCK, { item_code, warehouse })
}

export function fetchShipheroInventory(params = {}) {
  return callApi(EP.SHIPHERO_INVENTORY, params)
}
