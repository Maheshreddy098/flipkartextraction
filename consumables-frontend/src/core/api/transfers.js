import { frappeRequest } from 'frappe-ui'

const BASE = 'khanal_tech_integrations.consumables.api.transfers'

export function get_transfer_requests(params = {}) {
  return frappeRequest({ url: `${BASE}.get_transfer_requests`, params })
}

export function get_transfer_request(name) {
  return frappeRequest({ url: `${BASE}.get_transfer_request`, params: { name } })
}

export function get_pending_receipts() {
  return frappeRequest({ url: `${BASE}.get_pending_receipts` })
}

export function get_destination_plants(from_plant = '') {
  const params = from_plant ? { from_plant } : {}
  return frappeRequest({ url: `${BASE}.get_destination_plants`, params })
}

export function create_transfer_request(payload = {}) {
  return frappeRequest({ url: `${BASE}.create_transfer_request`, params: payload })
}

export function submit_transfer_request(name) {
  return frappeRequest({ url: `${BASE}.submit_transfer_request`, params: { name } })
}

export function approve_transfer_request(name) {
  return frappeRequest({ url: `${BASE}.approve_transfer_request`, params: { name } })
}

export function get_transfer_dispatch_batches(name) {
  return frappeRequest({ url: `${BASE}.get_transfer_dispatch_batches`, params: { name } })
}

export function dispatch_transfer_request(name, batch_items) {
  return frappeRequest({ url: `${BASE}.dispatch_transfer_request`, params: { name, batch_items } })
}

export function receive_transfer_request(name, received_items, receipt_notes = '', reject_delivery = 0) {
  return frappeRequest({ url: `${BASE}.receive_transfer_request`, params: { name, received_items, receipt_notes, reject_delivery } })
}

export function reject_transfer_request(name, rejection_reason) {
  return frappeRequest({
    url: `${BASE}.reject_transfer_request`,
    params: { name, rejection_reason },
  })
}

export function retry_sap_posting(name) {
  return frappeRequest({ url: `${BASE}.retry_sap_posting`, params: { name } })
}

export function download_delivery_challan(name, doc_number) {
  return frappeRequest({ url: `${BASE}.download_delivery_challan`, params: { name, doc_number } })
}
