import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function uploadKFAttachment(doctype, docname, fileName, filedata) {
  return callApi(EP.KF_ATTACH_UPLOAD, { doctype, docname, file_name: fileName, filedata }, 'POST')
}

export function listKFAttachments(doctype, docname) {
  return callApi(EP.KF_ATTACH_LIST, { doctype, docname })
}

export function deleteKFAttachment(name) {
  return callApi(EP.KF_ATTACH_DELETE, { name }, 'POST')
}
