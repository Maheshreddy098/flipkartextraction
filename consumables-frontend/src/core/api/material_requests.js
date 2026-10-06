import { frappeRequest } from 'frappe-ui'

const BASE = 'khanal_tech_integrations.consumables.api.material_requests'

export function get_material_requests(params = {}) {
  return frappeRequest({ url: `${BASE}.get_material_requests`, params })
}

export function get_material_request(name) {
  return frappeRequest({ url: `${BASE}.get_material_request`, params: { name } })
}

export function get_destination_plants(from_plant = '') {
  const params = from_plant ? { from_plant } : {}
  return frappeRequest({ url: `${BASE}.get_destination_plants`, params })
}

export function create_material_request(payload = {}) {
  return frappeRequest({ url: `${BASE}.create_material_request`, params: payload })
}

export function submit_material_request(name) {
  return frappeRequest({ url: `${BASE}.submit_material_request`, params: { name } })
}

export function approve_material_request(name) {
  return frappeRequest({ url: `${BASE}.approve_material_request`, params: { name } })
}

export function decide_fulfillment(name, decisions = []) {
  return frappeRequest({ url: `${BASE}.decide_fulfillment`, params: { name, decisions } })
}

export function reject_material_request(name, rejection_reason) {
  return frappeRequest({
    url: `${BASE}.reject_material_request`,
    params: { name, rejection_reason },
  })
}

export function retry_sap_posting(name) {
  return frappeRequest({ url: `${BASE}.retry_sap_posting`, params: { name } })
}

export function sync_fulfillment_status(name) {
  return frappeRequest({ url: `${BASE}.sync_fulfillment_status`, params: { name } })
}

export function confirm_cmr_physical_receipt(name) {
  return frappeRequest({ url: `${BASE}.confirm_cmr_physical_receipt`, params: { name } })
}

export function delete_material_request(name) {
  return frappeRequest({ url: `${BASE}.delete_material_request`, params: { name } })
}

export function raise_po_from_request(payload = {}) {
  return frappeRequest({ url: `${BASE}.raise_po_from_request`, params: payload })
}
