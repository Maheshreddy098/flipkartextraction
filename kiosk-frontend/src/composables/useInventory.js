/**
 * Universal Inventory Transfer Composable - frappe-ui based
 * Works for ALL plants
 * Replaces all plant-specific inventory services
 */

/**
 * FUTURE USE: Inventory Management Composable
 * 
 * This composable is ready for inventory feature implementation.
 * Currently, only GRN features are active in the kiosk system.
 * 
 * When implementing inventory features:
 * 1. Import this composable in inventory pages: `import { useInventory } from '@/composables/useInventory'`
 * 2. Initialize with plant ID: `const { inventoryTransfers, createInventoryTransfer, ... } = useInventory('plantId')`
 * 3. Use reactive resources: `inventoryTransfers.fetch()`, `createInventoryTransfer.submit(data)`
 * 4. Replace existing axios-based `inventoryService` calls with these frappe-ui resources
 * 
 * Status: Ready for implementation (not currently in use)
 * Last Updated: October 2025
 */

import { createResource } from 'frappe-ui'

export function useInventory(plantId) {
  const baseUrl = `khanal_tech_integrations.api.plants.${plantId}.inventory`

  // Get Inventory Transfer List
  const inventoryTransferList = createResource({
    url: `${baseUrl}.get_inventory_transfers`,
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
      console.error(`[${plantId}/Inventory] List Error:`, error)
    }
  })

  // Get Inventory Transfer Details
  const inventoryTransferDetails = createResource({
    url: `${baseUrl}.get_transfer_details`,
    method: 'GET',
    auto: false,
    makeParams(transferId) {
      return { transfer_id: transferId }
    },
    onError(error) {
      console.error(`[${plantId}/Inventory] Details Error:`, error)
    }
  })

  // Create Inventory Transfer
  const createTransfer = createResource({
    url: `${baseUrl}.create_inventory_transfer`,
    method: 'POST',
    auto: false,
    makeParams(transferData) {
      return transferData
    },
    onSuccess(data) {
      inventoryTransferList.reload()
      return data
    },
    onError(error) {
      console.error(`[${plantId}/Inventory] Create Transfer Error:`, error)
    }
  })

  // Get Available Stock
  const availableStock = createResource({
    url: `${baseUrl}.get_available_stock`,
    method: 'GET',
    auto: false,
    makeParams({ warehouseCode, itemCode = null }) {
      return { warehouse_code: warehouseCode, item_code: itemCode }
    },
    onError(error) {
      console.error(`[${plantId}/Inventory] Available Stock Error:`, error)
    }
  })

  return {
    // Raw resources
    inventoryTransferList,
    inventoryTransferDetails,
    createTransfer,
    availableStock,

    // Helper methods
    loadInventoryTransfers: async (filters = {}, page = 1, pageSize = 20) => {
      await inventoryTransferList.fetch({
        filters,
        page,
        page_size: pageSize
      })
      return inventoryTransferList.data
    },

    loadTransferDetails: async (transferId) => {
      await inventoryTransferDetails.fetch({ transfer_id: transferId })
      return inventoryTransferDetails.data
    },

    createInventoryTransfer: async (transferData) => {
      await createTransfer.submit(transferData)
      return createTransfer.data
    },

    getAvailableStock: async (warehouseCode, itemCode = null) => {
      await availableStock.fetch({ warehouseCode, itemCode })
      return availableStock.data
    }
  }
}

