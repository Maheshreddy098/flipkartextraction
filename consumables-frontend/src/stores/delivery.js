import { defineStore } from 'pinia'
import * as deliveryApi from '../core/api/delivery.js'
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

  const raw =
    payload?.delivery_notes ?? payload?.data ?? payload?.items ?? payload?.results
  const list = Array.isArray(raw) ? raw : []
  const total = payload?.total_count ?? payload?.total ?? list.length
  return { list, total }
}

function compactFilters(filters) {
  const out = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') out[key] = value
  }
  return out
}

export const useDeliveryStore = defineStore('delivery', {
  state: () => ({
    deliveryNotes: [],
    currentDeliveryNote: null,
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
    pendingApprovalCount: (state) =>
      state.deliveryNotes.filter((note) => note.status === 'Submitted').length,
  },

  actions: {
    async fetchDeliveryNotes(overrides = {}) {
      this.error = null
      this.loading = true
      try {
        this.filters = { ...this.filters, ...overrides }
        const params = compactFilters(this.filters)
        const res = await deliveryApi.get_delivery_notes(params)
        const payload = normalizeResponse(res)
        const { list, total } = normalizeListResult(payload)
        this.deliveryNotes = list
        this.totalCount = total
        return payload
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch delivery notes')
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchDeliveryNote(name, { silent = false } = {}) {
      this.error = null
      if (!silent) this.loading = true
      try {
        const res = await deliveryApi.get_delivery_note(name)
        const data = normalizeResponse(res)
        this.currentDeliveryNote = data
        return data
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch delivery note')
        throw err
      } finally {
        if (!silent) this.loading = false
      }
    },

    async createDeliveryNote(payload) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.create_delivery_note(payload)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to create delivery note')
        throw err
      } finally {
        this.loading = false
      }
    },

    async postDeliveryNote(payload) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.post_delivery_note(payload)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to post delivery note to SAP')
        throw err
      } finally {
        this.loading = false
      }
    },

    async submitDeliveryNote(name) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.submit_delivery_note(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to submit delivery note')
        throw err
      } finally {
        this.loading = false
      }
    },

    async cancelDeliveryNote(name) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.cancel_delivery_note(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to cancel delivery note')
        throw err
      } finally {
        this.loading = false
      }
    },

    async repostCancelledDeliveryNote(name) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.repost_cancelled_delivery_note(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to repost delivery note')
        throw err
      } finally {
        this.loading = false
      }
    },

    async approveDeliveryNote(name) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.approve_delivery_note(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to approve delivery note')
        throw err
      } finally {
        this.loading = false
      }
    },

    async rejectDeliveryNote(name, rejection_reason) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.reject_delivery_note(name, rejection_reason)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to reject delivery note')
        throw err
      } finally {
        this.loading = false
      }
    },

    async retrySapPosting(name) {
      this.error = null
      this.loading = true
      try {
        const res = await deliveryApi.retry_sap_posting(name)
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
