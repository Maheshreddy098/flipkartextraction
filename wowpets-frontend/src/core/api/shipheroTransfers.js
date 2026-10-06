import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchShipheroTransfers(params = {}) {
  return callApi(EP.SHIPHERO_LIST, params)
}

export function fetchShipheroTransfer(name) {
  return callApi(EP.SHIPHERO_DETAIL, { name })
}

export function createShipheroTransfer(data) {
  return callApi(EP.SHIPHERO_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function updateShipheroTransfer(name, data) {
  return callApi(EP.SHIPHERO_UPDATE, { name, data: JSON.stringify(data) }, 'POST')
}

export function submitShipheroTransfer(name) {
  return callApi(EP.SHIPHERO_SUBMIT, { name }, 'POST')
}

export function approveShipheroTransfer(name) {
  return callApi(EP.SHIPHERO_APPROVE, { name }, 'POST')
}

export function rejectShipheroTransfer(name, reason = '') {
  return callApi(EP.SHIPHERO_REJECT, { name, reason }, 'POST')
}

export function acceptShipheroTransfer(name, items = null, remarks = null) {
  const payload = { name }
  if (items != null) payload.items = JSON.stringify(items)
  if (remarks != null) payload.remarks = JSON.stringify(remarks)
  return callApi(EP.SHIPHERO_ACCEPT, payload, 'POST')
}

export function updateShipheroAcceptedQuantities(name, items, remarks = null) {
  const payload = { name, items: JSON.stringify(items) }
  if (remarks != null) payload.remarks = JSON.stringify(remarks)
  return callApi(EP.SHIPHERO_UPDATE_ACCEPTED_QTYS, payload, 'POST')
}

export function sendShipheroTransferToSap(name) {
  return callApi(EP.SHIPHERO_SEND_TO_SAP, { name }, 'POST')
}

export function retrySapRequest(name) {
  return callApi(EP.SHIPHERO_RETRY_SAP_REQUEST, { name }, 'POST')
}

export function markReceivedShipheroTransfer(name) {
  return callApi(EP.SHIPHERO_MARK_RECEIVED, { name }, 'POST')
}

export function warehouseRequestKfAssistanceShiphero(name) {
  return callApi(EP.SHIPHERO_WAREHOUSE_REQUEST_KF, { name }, 'POST')
}

export function kfUpdateForWarehouseResumeShiphero(name, data) {
  return callApi(EP.SHIPHERO_KF_UPDATE_RESUME, { name, data: JSON.stringify(data) }, 'POST')
}

export function kfReleaseWarehouseHoldShiphero(name) {
  return callApi(EP.SHIPHERO_KF_RELEASE_HOLD, { name }, 'POST')
}

export function revertShipheroTransferToDraft(name) {
  return callApi(EP.SHIPHERO_REVERT, { name }, 'POST')
}

export function deleteShipheroTransfer(name) {
  return callApi(EP.SHIPHERO_DELETE, { name }, 'POST')
}
