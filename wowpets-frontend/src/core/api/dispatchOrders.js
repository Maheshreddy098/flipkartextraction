import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchDispatchOrders(params = {}) {
  return callApi(EP.DISPATCH_LIST, params)
}

export function fetchDispatchOrder(name) {
  return callApi(EP.DISPATCH_DETAIL, { name })
}

export function createDispatchOrder(data) {
  return callApi(EP.DISPATCH_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function updateDispatchOrder(name, data) {
  return callApi(EP.DISPATCH_UPDATE, { name, data: JSON.stringify(data) }, 'POST')
}

export function submitDispatchOrder(name) {
  return callApi(EP.DISPATCH_SUBMIT, { name }, 'POST')
}

export function approveDispatchOrder(name) {
  return callApi(EP.DISPATCH_APPROVE, { name }, 'POST')
}

export function rejectDispatchOrder(name, reason = '') {
  return callApi(EP.DISPATCH_REJECT, { name, reason }, 'POST')
}

export function acceptDispatchOrder(name) {
  return callApi(EP.DISPATCH_ACCEPT, { name }, 'POST')
}

export function startPreparationDispatchOrder(name) {
  return callApi(EP.DISPATCH_START_PREPARATION, { name }, 'POST')
}

export function dispatchDispatchOrder(name) {
  return callApi(EP.DISPATCH_DISPATCH, { name }, 'POST')
}

export function retryDispatchOrderSap(name) {
  return callApi(EP.DISPATCH_RETRY_SAP, { name }, 'POST')
}

export function warehouseRequestKfAssistanceDispatch(name) {
  return callApi(EP.DISPATCH_WAREHOUSE_REQUEST_KF, { name }, 'POST')
}

export function kfUpdateForWarehouseResumeDispatch(name, data) {
  return callApi(EP.DISPATCH_KF_UPDATE_RESUME, { name, data: JSON.stringify(data) }, 'POST')
}

export function kfReleaseWarehouseHoldDispatch(name) {
  return callApi(EP.DISPATCH_KF_RELEASE_HOLD, { name }, 'POST')
}

export function reconcileDispatchStatus(name) {
  return callApi(EP.DISPATCH_RECONCILE, { name }, 'POST')
}

export function revertDispatchOrderToDraft(name) {
  return callApi(EP.DISPATCH_REVERT, { name }, 'POST')
}

export function searchSAPCustomers(query) {
  return callApi(EP.SAP_CUSTOMERS, { query })
}

/** Addresses for a customer (CardCode) from SAP – for Ship-To selection */
export function getCustomerAddresses(cardCode) {
  return callApi(EP.SAP_GET_CUSTOMER_ADDRESSES, { card_code: cardCode })
}

/** Add a new Ship-To or Bill-To address for a customer in SAP. addressType: 'bo_ShipTo' | 'bo_BillTo' (default bo_ShipTo) */
export function addCustomerAddress(cardCode, payload, addressType = 'bo_ShipTo') {
  return callApi(EP.SAP_ADD_CUSTOMER_ADDRESS, {
    card_code: cardCode,
    data: JSON.stringify(payload),
    address_type: addressType,
  }, 'POST')
}

/** Batches from WO -FG for dispatch order lines */
export function getBatchesForDispatchItem(item_code) {
  return callApi(EP.SAP_BATCHES_FOR_DISPATCH, { item_code })
}

export function deleteDispatchOrder(name) {
  return callApi(EP.DISPATCH_DELETE, { name }, 'POST')
}
