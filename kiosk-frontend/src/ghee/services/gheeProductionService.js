/**
 * Ghee Reverse Production Order API service.
 * All calls go to khanal_tech_integrations.api.ghee.production_order.*
 */

import axios from 'axios'

const BASE = `${window.location.origin}/api/method/khanal_tech_integrations.api.ghee.production_order`

function csrfToken() {
  const t = window.csrf_token || (window.boot && window.boot.csrf_token)
  return t && t !== '{{ csrf_token }}' ? t : null
}

async function post(method, data = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = csrfToken()
  if (token) headers['X-Frappe-CSRF-Token'] = token

  const resp = await axios.post(`${BASE}.${method}`, data, {
    headers,
    withCredentials: true,
  })

  // Frappe wraps response in { message: <actual payload> }
  return resp.data?.message ?? resp.data
}

export const gheeProductionService = {
  // --- Ghee Production Order (persistent records) ---

  saveOrder(fields) {
    return post('save_production_order', fields)
  },

  getOrder(name) {
    return post('get_production_order', { name })
  },

  getAllOrders(filters = {}) {
    return post('get_all_production_orders', filters)
  },

  // --- Legacy draft methods (kept for backward compat) ---

  getAllDrafts() {
    return post('get_all_ghee_drafts', {})
  },

  getDraft(name) {
    return post('get_ghee_draft', { name })
  },

  getActiveDraft() {
    return post('get_active_ghee_draft', {})
  },

  saveDraft(fields) {
    return post('save_ghee_draft', fields)
  },

  deleteDraft(name) {
    return post('delete_ghee_draft', { name })
  },

  // --- SAP operations ---

  getItemBatches(itemCode) {
    return post('get_item_batches', { item_code: itemCode })
  },

  getBomLines(newItemCode) {
    return post('get_bom_lines', { new_item_code: newItemCode })
  },

  previewCostSplit(sourceItemCode, batchNo, newItemCode, sourceWarehouse, sourceQty, sourceBatches) {
    return post('preview_cost_split', {
      source_item_code: sourceItemCode,
      batch_no:         batchNo         || undefined,
      new_item_code:    newItemCode,
      source_warehouse: sourceWarehouse || undefined,
      source_qty:       sourceQty       || undefined,
      source_batches:   sourceBatches   || undefined,
    })
  },

  createProductionOrder(payload) {
    return post('create_production_order', payload)
  },

  completeProductionOrder(payload) {
    return post('complete_production_order', payload)
  },
}
