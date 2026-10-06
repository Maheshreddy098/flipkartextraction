import { defineStore } from 'pinia'
import * as transfersApi from '../core/api/transfers.js'
import { parseApiError } from '../utils/error.js'

function normalizeResponse(response) {
  return response?.message ?? response
}

function getErrorMessage(err, fallback) {
  if (typeof err === 'string') return err
  return parseApiError(err, fallback)
}

function normalizeListResult(payload) {
  if (Array.isArray(payload)) {
    return { list: payload, total: payload.length }
  }
  const raw = payload?.data ?? payload?.transfers ?? payload?.items ?? payload?.results
  const list = Array.isArray(raw) ? raw : []
  const total = payload?.total_count ?? payload?.total ?? list.length
  return { list, total }
}

function normalizePendingReceipts(payload) {
  if (Array.isArray(payload)) return payload
  return payload?.data ?? payload?.transfers ?? payload?.pending_receipts ?? []
}

function compactFilters(filters) {
  const out = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') out[key] = value
  }
  return out
}

export const useTransfersStore = defineStore('transfers', {
  state: () => ({
    transfers: [],
    currentTransfer: null,
    pendingReceipts: [],
    totalCount: 0,
    loading: false,
    error: null,
    filters: {
      status: null,
      plant_code: null,
      from_date: null,
      to_date: null,
      page: 1,
      page_size: 20,
    },
  }),

  getters: {
    pendingReceiptsCount: (state) => state.pendingReceipts.length,
    transfersByStatus: (state) => {
      return (status) => state.transfers.filter((t) => t.status === status)
    },
  },

  actions: {
    async fetchTransfers(overrides = {}) {
      this.error = null
      this.loading = true
      try {
        this.filters = { ...this.filters, ...overrides }
        const params = compactFilters(this.filters)
        const res = await transfersApi.get_transfer_requests(params)
        const payload = normalizeResponse(res)
        const { list, total } = normalizeListResult(payload)
        this.transfers = list
        this.totalCount = total
        return payload
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch transfers')
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchTransfer(name, { silent = false } = {}) {
      this.error = null
      if (!silent) this.loading = true
      try {
        const res = await transfersApi.get_transfer_request(name)
        const data = normalizeResponse(res)
        this.currentTransfer = data
        return data
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch transfer')
        throw err
      } finally {
        if (!silent) this.loading = false
      }
    },

    async fetchPendingReceipts() {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.get_pending_receipts()
        const payload = normalizeResponse(res)
        this.pendingReceipts = normalizePendingReceipts(payload)
        return this.pendingReceipts
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch pending receipts')
        throw err
      } finally {
        this.loading = false
      }
    },

    async createTransfer(payload) {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.create_transfer_request(payload)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to create transfer')
        throw err
      } finally {
        this.loading = false
      }
    },

    async submitTransfer(name) {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.submit_transfer_request(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to submit transfer')
        throw err
      } finally {
        this.loading = false
      }
    },

    async approveTransfer(name) {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.approve_transfer_request(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to approve transfer')
        throw err
      } finally {
        this.loading = false
      }
    },

    async dispatchTransfer(name, batchItems = []) {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.dispatch_transfer_request(name, JSON.stringify(batchItems))
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to dispatch transfer')
        throw err
      } finally {
        this.loading = false
      }
    },

    async receiveTransfer(name, received_items = [], receipt_notes = '') {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.receive_transfer_request(name, JSON.stringify(received_items), receipt_notes)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to receive transfer')
        throw err
      } finally {
        this.loading = false
      }
    },

    async rejectTransfer(name, rejection_reason) {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.reject_transfer_request(name, rejection_reason)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to reject transfer')
        throw err
      } finally {
        this.loading = false
      }
    },

    async retrySapPosting(name) {
      this.error = null
      this.loading = true
      try {
        const res = await transfersApi.retry_sap_posting(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to retry SAP posting')
        throw err
      } finally {
        this.loading = false
      }
    },
  },
})
