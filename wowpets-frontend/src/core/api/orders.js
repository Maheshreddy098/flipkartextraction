import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchOrders(params = {}) {
  return callApi(EP.ORDER_LIST, params)
}

export function fetchOrder(name) {
  return callApi(EP.ORDER_DETAIL, { name })
}

export function createOrder(data) {
  return callApi(EP.ORDER_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function updateOrder(name, data) {
  return callApi(EP.ORDER_UPDATE, { name, data: JSON.stringify(data) }, 'POST')
}

export function submitOrder(name) {
  return callApi(EP.ORDER_SUBMIT, { name }, 'POST')
}

export function approveOrder(name) {
  return callApi(EP.ORDER_APPROVE, { name }, 'POST')
}

export function rejectOrder(name, reason = '') {
  return callApi(EP.ORDER_REJECT, { name, reason }, 'POST')
}

export function acceptOrder(name) {
  return callApi(EP.ORDER_ACCEPT, { name }, 'POST')
}

export function startPackagingOrder(name) {
  return callApi(EP.ORDER_START_PACKAGING, { name }, 'POST')
}

export function completeOrder(name, data = null) {
  const payload = { name }
  if (data != null) payload.data = typeof data === 'string' ? data : JSON.stringify(data)
  return callApi(EP.ORDER_COMPLETE, payload, 'POST')
}

export function previewOrderSap(name) {
  return callApi(EP.ORDER_PREVIEW_SAP, { name })
}

export function sendOrderToSap(name) {
  return callApi(EP.ORDER_SEND_TO_SAP, { name }, 'POST')
}

export function retryOrderSap(name) {
  return callApi(EP.ORDER_RETRY_SAP, { name }, 'POST')
}

export function retryOrderSapRequest(name) {
  return callApi(EP.ORDER_RETRY_SAP_REQUEST, { name }, 'POST')
}

export function warehouseRequestKfAssistanceOrder(name) {
  return callApi(EP.ORDER_WAREHOUSE_REQUEST_KF, { name }, 'POST')
}

export function kfUpdateForWarehouseResumeOrder(name, data) {
  return callApi(EP.ORDER_KF_UPDATE_RESUME, { name, data: JSON.stringify(data) }, 'POST')
}

export function kfReleaseWarehouseHoldOrder(name) {
  return callApi(EP.ORDER_KF_RELEASE_HOLD, { name }, 'POST')
}

export function revertOrderToDraft(name) {
  return callApi(EP.ORDER_REVERT, { name }, 'POST')
}

export function deleteOrder(name) {
  return callApi(EP.ORDER_DELETE, { name }, 'POST')
}
