import { frappeRequest } from 'frappe-ui'

const BASE = 'khanal_tech_integrations.consumables.api.delivery_notes'

export function get_delivery_notes(params = {}) {
  return frappeRequest({ url: `${BASE}.get_delivery_notes`, params })
}

export function get_delivery_note(name) {
  return frappeRequest({ url: `${BASE}.get_delivery_note`, params: { name } })
}

export function create_delivery_note(payload = {}) {
  return frappeRequest({ url: `${BASE}.create_delivery_note`, params: payload })
}

export function post_delivery_note(payload = {}) {
  return frappeRequest({ url: `${BASE}.post_delivery_note`, params: payload })
}

export function submit_delivery_note(name) {
  return frappeRequest({ url: `${BASE}.submit_delivery_note`, params: { name } })
}

export function approve_delivery_note(name) {
  return frappeRequest({ url: `${BASE}.approve_delivery_note`, params: { name } })
}

export function reject_delivery_note(name, rejection_reason) {
  return frappeRequest({
    url: `${BASE}.reject_delivery_note`,
    params: { name, rejection_reason },
  })
}

export function retry_sap_posting(name) {
  return frappeRequest({ url: `${BASE}.retry_sap_posting`, params: { name } })
}

export function cancel_delivery_note(name) {
  return frappeRequest({ url: `${BASE}.cancel_delivery_note`, params: { name } })
}

export function repost_cancelled_delivery_note(name) {
  return frappeRequest({ url: `${BASE}.repost_cancelled_delivery_note`, params: { name } })
}
