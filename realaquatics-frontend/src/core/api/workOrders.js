import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchProductionOrderSeries() {
  return callApi(EP.SAP_PO_SERIES)
}

export function fetchWorkOrders(params = {}) {
  return callApi(EP.WO_LIST, params)
}

export function fetchWorkOrder(name) {
  return callApi(EP.WO_DETAIL, { name })
}

export function createWorkOrder(data) {
  return callApi(EP.WO_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function updateWorkOrder(name, data) {
  return callApi(EP.WO_UPDATE, { name, data: JSON.stringify(data) }, 'POST')
}

export function submitWOForApproval(name) {
  return callApi(EP.WO_SUBMIT, { name }, 'POST')
}

export function approveWO(name) {
  return callApi(EP.WO_APPROVE, { name }, 'POST')
}

export function rejectWO(name, reason = '') {
  return callApi(EP.WO_REJECT, { name, reason }, 'POST')
}

export function startProcessingWO(name) {
  return callApi(EP.WO_START, { name }, 'POST')
}

export function retryCreateProductionOrderWO(name, series = null) {
  return callApi(EP.WO_RETRY_PO, { name, series: series != null ? series : undefined }, 'POST')
}

export function warehouseMarkConsumedWO(name) {
  return callApi(EP.WO_WAREHOUSE_MARK_CONSUMED, { name }, 'POST')
}

export function warehouseCompleteWO(name) {
  return callApi(EP.WO_WAREHOUSE_COMPLETE, { name }, 'POST')
}

export function consumeAndIssueWO(name) {
  return callApi(EP.WO_CONSUME_AND_ISSUE, { name }, 'POST')
}

export function retryIssueForProductionWO(name) {
  return callApi(EP.WO_RETRY_ISSUE, { name }, 'POST')
}

export function completeWO(name, produced_qty = null, finished_goods_batch = null) {
  return callApi(EP.WO_COMPLETE, { name, produced_qty, finished_goods_batch }, 'POST')
}

export function revertWOToDraft(name) {
  return callApi(EP.WO_REVERT, { name }, 'POST')
}

export function createWOProductionOrderAndIssue(name, series = null) {
  return callApi(EP.WO_CREATE_PRODUCTION_AND_ISSUE, { name, series: series != null ? series : undefined }, 'POST')
}

export function receiptFromProduction(name, finished_goods_batch = null) {
  return callApi(EP.WO_RECEIPT_FROM_PRODUCTION, { name, finished_goods_batch }, 'POST')
}

export function warehouseRequestKfAssistance(name) {
  return callApi(EP.WO_WAREHOUSE_REQUEST_KF, { name }, 'POST')
}

export function kfUpdateForWarehouseResume(name, data) {
  return callApi(EP.WO_KF_UPDATE_RESUME, { name, data: JSON.stringify(data) }, 'POST')
}

export function kfReleaseWarehouseHoldWO(name) {
  return callApi(EP.WO_KF_RELEASE_HOLD, { name }, 'POST')
}

export function deleteWorkOrder(name) {
  return callApi(EP.WO_DELETE, { name }, 'POST')
}
