import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchReturns(params = {}) {
  return callApi(EP.RETURN_LIST, params)
}

export function fetchReturn(name) {
  return callApi(EP.RETURN_DETAIL, { name })
}

export function createReturn(data) {
  return callApi(EP.RETURN_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function submitReturn(name) {
  return callApi(EP.RETURN_SUBMIT, { name }, 'POST')
}

export function approveReturn(name) {
  return callApi(EP.RETURN_APPROVE, { name }, 'POST')
}

export function processReturn(name) {
  return callApi(EP.RETURN_PROCESS, { name }, 'POST')
}
