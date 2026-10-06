/**
 * Universal Production Order Composable - frappe-ui based
 * Works for ALL plants
 * Replaces all plant-specific productionService files
 */

/**
 * FUTURE USE: Production Management Composable
 * 
 * This composable is ready for production feature implementation.
 * Currently, only GRN features are active in the kiosk system.
 * 
 * When implementing production features:
 * 1. Import this composable in production pages: `import { useProduction } from '@/composables/useProduction'`
 * 2. Initialize with plant ID: `const { productionOrders, submitProductionOutput, ... } = useProduction('plantId')`
 * 3. Use reactive resources: `productionOrders.fetch()`, `productionOrderDetails.fetch(doc_entry)`
 * 4. Replace existing axios-based `productionService` calls with these frappe-ui resources
 * 
 * Status: Ready for implementation (not currently in use)
 * Last Updated: October 2025
 */

import { createResource } from 'frappe-ui'

export function useProduction(plantId) {
  const baseUrl = `khanal_tech_integrations.api.plants.${plantId}.production`

  // Get Production Order List
  const productionOrderList = createResource({
    url: `${baseUrl}.get_production_orders`,
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
      console.error(`[${plantId}/Production] List Error:`, error)
    }
  })

  // Get Production Order Details
  const productionOrderDetails = createResource({
    url: `${baseUrl}.get_production_order_details`,
    method: 'GET',
    auto: false,
    makeParams(orderId) {
      return { order_id: orderId }
    },
    onError(error) {
      console.error(`[${plantId}/Production] Details Error:`, error)
    }
  })

  // Create Pre-Production
  const createPreProduction = createResource({
    url: `${baseUrl}.create_pre_production`,
    method: 'POST',
    auto: false,
    makeParams(productionData) {
      return productionData
    },
    onSuccess(data) {
      productionOrderList.reload()
      return data
    },
    onError(error) {
      console.error(`[${plantId}/Production] Create Pre-Production Error:`, error)
    }
  })

  // Submit Production Output
  const submitOutput = createResource({
    url: `${baseUrl}.submit_production_output`,
    method: 'POST',
    auto: false,
    makeParams(outputData) {
      return outputData
    },
    onSuccess(data) {
      productionOrderList.reload()
      return data
    },
    onError(error) {
      console.error(`[${plantId}/Production] Submit Output Error:`, error)
    }
  })

  return {
    // Raw resources
    productionOrderList,
    productionOrderDetails,
    createPreProduction,
    submitOutput,

    // Helper methods
    loadProductionOrders: async (filters = {}, page = 1, pageSize = 20) => {
      await productionOrderList.fetch({
        filters,
        page,
        page_size: pageSize
      })
      return productionOrderList.data
    },

    loadProductionOrderDetails: async (orderId) => {
      await productionOrderDetails.fetch({ order_id: orderId })
      return productionOrderDetails.data
    },

    createPreProductionOrder: async (productionData) => {
      await createPreProduction.submit(productionData)
      return createPreProduction.data
    },

    submitProductionOutput: async (outputData) => {
      await submitOutput.submit(outputData)
      return submitOutput.data
    }
  }
}

