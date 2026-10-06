/**
 * Universal GRN Composable - frappe-ui based
 * Works for ALL plants (malur, krishnagiri, nandi_hills, mahadevpura, champavath)
 * Replaces all plant-specific grnService files
 */

import { createResource } from 'frappe-ui'

export function useGRN(plantId) {
  // Normalize plant ID for backend (hyphens to underscores)
  // Frontend uses 'nandi-hills' but backend folder is 'nandi_hills'
  const backendPlantId = plantId.replace(/-/g, '_')
  const baseUrl = `khanal_tech_integrations.api.plants.${backendPlantId}.grn`

  // Get GRN List with filters and pagination
  const grnList = createResource({
    url: `${baseUrl}.get_grn_list`,
    method: 'POST',
    params: {
      filters: {},
      page: 1,
      page_size: 20
    },
    auto: false,
    transform(data) {
      return data?.data || data || []
    },
    onError(error) {
      console.error(`[${plantId}/GRN] List Error:`, error)
    }
  })

  // Get single GRN details
  const grnDetails = createResource({
    url: `${baseUrl}.get_grn_details`,
    method: 'POST',  // ✅ FIXED: Changed from GET to POST
    auto: false,
    makeParams(grnId) {
      return { grn_id: grnId }
    },
    transform(data) {
      return data?.message || data
    },
    onError(error) {
      console.error(`[${plantId}/GRN] Details Error:`, error)
    }
  })

  // Get Purchase Orders
  const purchaseOrders = createResource({
    url: `${baseUrl}.get_purchase_orders`,
    method: 'POST',
    auto: false,
    makeParams({ fromDate = '', toDate = '', businessPartner = null, status = 'Open', fetchAll = false }) {
      return {
        plant_id: plantId,
        status: status,
        from_date: fromDate,
        to_date: toDate,
        fetch_all: fetchAll,
        bp_search: businessPartner
      }
    },
    transform(data) {
      // Extract data from Frappe response structure
      return data?.message?.data || data?.data || data || []
    },
    onError(error) {
      console.error(`[${plantId}/GRN] Purchase Orders Error:`, error)
    }
  })

  // Get PO Line Items
  const poLineItems = createResource({
    url: `${baseUrl}.get_po_line_items`,
    method: 'POST',  // ✅ FIXED: Changed from GET to POST
    auto: false,
    makeParams(docEntry) {
      return {
        doc_entry: docEntry,
        plant_id: plantId
      }
    },
    transform(data) {
      // Ensure we return the line items array
      const items = data?.message?.data?.LineItems || data?.data?.LineItems || data?.LineItems || []
      return Array.isArray(items) ? items : []
    },
    onError(error) {
      console.error(`[${plantId}/GRN] PO Line Items Error:`, error)
    }
  })

  // Create GRN Draft
  const createGRN = createResource({
    url: `${baseUrl}.create_grn_draft`,
    method: 'POST',
    auto: false,
    makeParams(grnData) {
      // ✅ Wrap with parameter name to match backend function signature
      return { grn_data: grnData }
    },
    onSuccess(data) {
      // Reload GRN list after successful creation
      grnList.reload()
      return data
    },
    onError(error) {
      console.error(`[${plantId}/GRN] Create Error:`, error)
    }
  })

  // Reject GRN
  const rejectGRN = createResource({
    url: `${baseUrl}.reject_grn`,
    method: 'POST',
    auto: false,
    makeParams({ grnId, reason }) {
      return { grn_id: grnId, reason }
    },
    onSuccess() {
      // Reload GRN list and details after rejection
      grnList.reload()
    },
    onError(error) {
      console.error(`[${plantId}/GRN] Reject Error:`, error)
    }
  })

  // Cancel GRN (Reopen GRN posted to SAP)
  const cancelGRN = createResource({
    url: `${baseUrl}.cancel_grn`,
    method: 'POST',
    auto: false,
    makeParams({ grnId, reason }) {
      return {
        grn_id: grnId,
        reason: reason,
        plant_id: backendPlantId
      }
    },
    onSuccess() {
      // Reload GRN list after cancellation
      grnList.reload()
    },
    onError(error) {
      console.error(`[${plantId}/GRN] Cancel Error:`, error)
    }
  })

  return {
    // Raw resources (for direct access)
    grnList,
    grnDetails,
    purchaseOrders,
    poLineItems,
    createGRN,
    rejectGRN,
    cancelGRN,

    // Helper methods for easier usage
    loadGRNList: async (filters = {}, page = 1, pageSize = 20) => {
      await grnList.fetch({
        filters,
        page,
        page_size: pageSize
      })
      return grnList.data
    },

    loadGRNDetails: async (grnId) => {
      await grnDetails.fetch({ grn_id: grnId })
      return grnDetails.data
    },

    fetchPurchaseOrders: async (fromDate, toDate, businessPartner = null) => {
      await purchaseOrders.fetch({
        fromDate,
        toDate,
        businessPartner
      })
      return purchaseOrders.data
    },

    fetchPOLineItems: async (poNo) => {
      await poLineItems.fetch({ po_no: poNo })
      return poLineItems.data
    },

    submitGRN: async (grnData) => {
      await createGRN.submit(grnData)
      return createGRN.data
    },

    rejectGRNWithReason: async (grnId, reason) => {
      await rejectGRN.submit({ grnId, reason })
      return rejectGRN.data
    },

    cancelGRNWithReason: async (grnId, reason) => {
      await cancelGRN.submit({ grnId, reason })
      return cancelGRN.data
    }
  }
}
