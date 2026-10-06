import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchSAPItems(params = {}) {
  return callApi(EP.SAP_ITEMS, params)
}

export function searchSAPItems(query) {
  return callApi(EP.SAP_SEARCH, { query })
}

export function searchSAPVendors(query) {
  return callApi(EP.SAP_VENDORS, { query })
}

export function fetchBOM(item_code) {
  return callApi(EP.SAP_BOM, { item_code })
}

/**
 * Fetch available batches for an item (and warehouse) from SAP for WO component selection.
 * @param {string} item_code
 * @param {string} [warehouse_code] - defaults to Real Aquatics warehouse
 * @returns {Promise<{ data: Array<{ batch_number: string, quantity: number }>, error?: string }>}
 */
export function getBatchesForItem(item_code, warehouse_code, all_warehouses = false) {
  return callApi(EP.SAP_BATCHES_FOR_ITEM, { item_code, warehouse_code, all_warehouses })
}

/**
 * Fetch warehouses from SAP for dropdowns (code + name).
 * @returns {Promise<{ data: Array<{ warehouse_code: string, warehouse_name: string }>, error?: string }>}
 */
export function getWarehouses() {
  return callApi(EP.SAP_WAREHOUSES)
}

/**
 * Lightweight health check for SAP B1 connection.
 * Returns { ok, status, message? } where status is one of: connected, disconnected, error.
 */
export function getSapHealth() {
  return callApi(EP.SAP_HEALTH)
}

/**
 * Force a new SAP B1 Service Layer login using INC SAP Settings.
 * Returns { ok, error? }.
 */
export function initiateSapSession() {
  return callApi(EP.SAP_INIT_SESSION, {}, 'POST')
}
