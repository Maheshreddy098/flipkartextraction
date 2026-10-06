import { frappeRequest } from 'frappe-ui'

const BASE = 'khanal_tech_integrations.consumables.api.procurement'

export function get_purchase_requests(params = {}) {
  return frappeRequest({ url: `${BASE}.get_purchase_requests`, params })
}

export function get_purchase_request(name) {
  return frappeRequest({ url: `${BASE}.get_purchase_request`, params: { name } })
}

export function get_split_family(name) {
  return frappeRequest({ url: `${BASE}.get_split_family`, params: { name } })
}

export function raise_purchase_order(name, vendor_code, item_prices, po_options, line_extras, extra_items) {
  return frappeRequest({
    url: `${BASE}.raise_purchase_order`,
    params: { name, vendor_code, item_prices, po_options, line_extras, extra_items },
  })
}

export function split_purchase_request(name, row_names) {
  return frappeRequest({ url: `${BASE}.split_purchase_request`, params: { name, row_names } })
}

export function remove_split_item(name, row_names) {
  return frappeRequest({ url: `${BASE}.remove_split_item`, params: { name, row_names } })
}

export function submit_grn(name, grn_items) {
  return frappeRequest({ url: `${BASE}.submit_grn`, params: { name, grn_items } })
}

export function approve_warehouse_decision(name, decision, notes = '') {
  return frappeRequest({ url: `${BASE}.approve_warehouse_decision`, params: { name, decision, notes } })
}

export function retry_sap_posting(name) {
  return frappeRequest({ url: `${BASE}.retry_sap_posting`, params: { name } })
}

export function search_vendors(query) {
  return frappeRequest({ url: `${BASE}.search_vendors`, params: { query } })
}

export function list_vendor_po_addresses(card_code, addr_type) {
  return frappeRequest({ url: `${BASE}.list_vendor_po_addresses`, params: { card_code, addr_type } })
}

export function list_plant_ship_addresses(plant_code) {
  return frappeRequest({ url: `${BASE}.list_plant_ship_addresses`, params: { plant_code } })
}

export function get_items_tax_info(item_codes) {
  return frappeRequest({ url: `${BASE}.get_items_tax_info`, params: { item_codes } })
}

export function get_cpr_grn_info(cpr_names) {
  return frappeRequest({ url: `${BASE}.get_cpr_grn_info`, params: { cpr_names } })
}
export function approve_purchase_order(name) {
  return frappeRequest({ url: `${BASE}.approve_purchase_order`, params: { name } })
}

export function reject_purchase_order(name) {
  return frappeRequest({ url: `${BASE}.reject_purchase_order`, params: { name } })
}

export function get_purchase_order_pdf_url(name) {
  return `/api/method/${BASE}.download_purchase_order_pdf?name=${encodeURIComponent(name)}`
}
