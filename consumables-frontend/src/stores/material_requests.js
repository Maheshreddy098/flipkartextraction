import { defineStore } from 'pinia'
import * as materialRequestsApi from '../core/api/material_requests.js'
import { parseApiError } from '../utils/error.js'

function normalizeResponse(response) {
  return response?.message ?? response
}

function getErrorMessage(err, fallback) {
  if (typeof err === 'string') return err
  return parseApiError(err, fallback)
}

function normalizeList(payload) {
  if (Array.isArray(payload)) {
    return { list: payload, total: payload.length }
  }
  const raw = payload?.data ?? payload?.material_requests ?? payload?.items ?? payload?.results
  const list = Array.isArray(raw) ? raw : []
  const total = payload?.total_count ?? payload?.total ?? list.length
  return { list, total }
}

export const useMaterialRequestsStore = defineStore('materialRequests', {
  state: () => ({
    list: [],
    current: null,
    loading: false,
    error: null,
    totalCount: 0,
  }),

  actions: {
    async fetchList(params = {}) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.get_material_requests(params)
        const payload = normalizeResponse(res)
        const { list, total } = normalizeList(payload)
        this.list = list
        this.totalCount = total
        return payload
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch material requests')
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchOne(name, { silent = false } = {}) {
      this.error = null
      if (!silent) this.loading = true
      try {
        const res = await materialRequestsApi.get_material_request(name)
        const payload = normalizeResponse(res)
        this.current = payload
        return payload
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch material request')
        throw err
      } finally {
        if (!silent) this.loading = false
      }
    },

    async create(payload = {}) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.create_material_request(payload)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to create material request')
        throw err
      } finally {
        this.loading = false
      }
    },

    async submit(name) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.submit_material_request(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to submit material request')
        throw err
      } finally {
        this.loading = false
      }
    },

    async approve(name) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.approve_material_request(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to approve material request')
        throw err
      } finally {
        this.loading = false
      }
    },

    async decide(name, decisions = []) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.decide_fulfillment(name, decisions)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to confirm fulfillment decision')
        throw err
      } finally {
        this.loading = false
      }
    },

    async reject(name, rejection_reason) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.reject_material_request(name, rejection_reason)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to reject material request')
        throw err
      } finally {
        this.loading = false
      }
    },

    async retrySapPosting(name) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.retry_sap_posting(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to retry SAP posting')
        throw err
      } finally {
        this.loading = false
      }
    },

    async syncFulfillmentStatus(name) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.sync_fulfillment_status(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to sync material request status')
        throw err
      } finally {
        this.loading = false
      }
    },

    async confirmPhysicalReceipt(name) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.confirm_cmr_physical_receipt(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to confirm receipt')
        throw err
      } finally {
        this.loading = false
      }
    },

    async remove(name) {
      this.error = null
      this.loading = true
      try {
        const res = await materialRequestsApi.delete_material_request(name)
        return normalizeResponse(res)
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to delete material request')
        throw err
      } finally {
        this.loading = false
      }
    },
  },
})
