import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchPurchaseOrders(params = {}) {
  return callApi(EP.PO_LIST, params)
}

export function fetchPurchaseOrder(name) {
  return callApi(EP.PO_DETAIL, { name })
}

export function createPurchaseOrder(data) {
  return callApi(EP.PO_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function updatePurchaseOrder(name, data) {
  return callApi(EP.PO_UPDATE, { name, data: JSON.stringify(data) }, 'POST')
}

export function submitPOForApproval(name) {
  return callApi(EP.PO_SUBMIT, { name }, 'POST')
}

export function approvePO(name) {
  return callApi(EP.PO_APPROVE, { name }, 'POST')
}

export function rejectPO(name, reason = '') {
  return callApi(EP.PO_REJECT, { name, reason }, 'POST')
}

export function acceptPO(name) {
  return callApi(EP.PO_ACCEPT, { name }, 'POST')
}

export function updateAcceptedQuantities(name, items, remarks = null) {
  const payload = { name, items: JSON.stringify(items) }
  if (remarks != null) payload.remarks = JSON.stringify(remarks)
  return callApi(EP.PO_UPDATE_ACCEPTED_QTYS, payload, 'POST')
}

export function receivePO(name) {
  return callApi(EP.PO_RECEIVE, { name }, 'POST')
}

export function revertPOToDraft(name) {
  return callApi(EP.PO_REVERT, { name }, 'POST')
}

export function retryPOSapSync(name) {
  return callApi(EP.PO_RETRY_SAP, { name }, 'POST')
}

export function createPOGrn(name) {
  return callApi(EP.PO_CREATE_GRN, { name }, 'POST')
}

export function retryPOGrn(name) {
  return callApi(EP.PO_RETRY_GRN, { name }, 'POST')
}

export function revertPOGrn(name) {
  return callApi(EP.PO_REVERT_GRN, { name }, 'POST')
}

export function warehouseRequestKfAssistancePO(name) {
  return callApi(EP.PO_WAREHOUSE_REQUEST_KF, { name }, 'POST')
}

export function kfUpdateForWarehouseResumePO(name, data) {
  return callApi(EP.PO_KF_UPDATE_RESUME, { name, data: JSON.stringify(data) }, 'POST')
}

export function kfUpdateGrnDetails(name, data) {
  return callApi(EP.PO_KF_UPDATE_GRN_DETAILS, { name, data: JSON.stringify(data) }, 'POST')
}

export function kfReleaseWarehouseHoldPO(name) {
  return callApi(EP.PO_KF_RELEASE_HOLD, { name }, 'POST')
}

export function deletePurchaseOrder(name) {
  return callApi(EP.PO_DELETE, { name }, 'POST')
}
