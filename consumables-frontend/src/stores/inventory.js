// consumables-frontend/src/stores/inventory.js
import { defineStore } from 'pinia'
import { frappeRequest } from 'frappe-ui'
import { parseApiError } from '../utils/error.js'

const CACHE_TTL = 5 * 60 * 1000 // 5 minutes
const DEFAULT_PAGE_SIZE = 20

const cache = Object.create(null)

function isFresh(key) {
  return cache[key] && Date.now() - cache[key].ts < CACHE_TTL
}

function getFromCache(key) {
  return isFresh(key) ? cache[key].data : null
}

function setCache(key, data) {
  cache[key] = { ts: Date.now(), data }
}

function warehousesCacheKey(plantCode) {
  return `warehouses:${plantCode}`
}

function inventoryStateKey(plantCode, warehouseCode) {
  return `${plantCode}:${warehouseCode}`
}

function inventoryCacheKey(plantCode, warehouseCode, params = {}) {
  const itemGroup = params.item_group || ''
  const search = params.search || ''
  const page = params.page || 1
  const pageSize = params.page_size || DEFAULT_PAGE_SIZE
  const paginateByItem = params.paginate_by_item === false ? '0' : '1'
  return `inventory:${plantCode}:${warehouseCode}:${itemGroup}:${search}:${page}:${pageSize}:${paginateByItem}`
}

function batchCacheKey(plantCode, warehouseCode, itemCode) {
  return `batch:${plantCode}:${warehouseCode}:${itemCode}`
}

function normalizeResponse(response) {
  return response?.message ?? response
}

function callMethod(method, args = {}) {
  return frappeRequest({ url: method, params: args })
}

function getErrorMessage(err, fallback) {
  if (typeof err === 'string') return err
  return parseApiError(err, fallback)
}

function normalizeWarehouses(payload) {
  if (Array.isArray(payload)) return payload
  return payload?.warehouses || []
}

export const useInventoryStore = defineStore('inventory', {
  state: () => ({
    warehouses: {}, // keyed by plant_code
    inventory: {}, // keyed by `${plant_code}:${warehouse_code}`
    warehousesLoading: false,
    inventoryLoading: false,
    error: null
  }),

  actions: {
    async fetchWarehouses(plant_code, { force = false } = {}) {
      const key = warehousesCacheKey(plant_code)

      this.error = null
      this.warehousesLoading = true

      try {
        if (!force) {
          const cached = getFromCache(key)
          if (cached) {
            this.warehouses[plant_code] = cached
            return cached
          }
        }

        const res = await callMethod(
          'khanal_tech_integrations.consumables.api.inventory.get_warehouses',
          { plant_code }
        )

        const payload = normalizeResponse(res)
        const data = normalizeWarehouses(payload)
        this.warehouses[plant_code] = data
        setCache(key, data)
        return data
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch warehouses')
        throw err
      } finally {
        this.warehousesLoading = false
      }
    },

    async fetchInventory(
      plant_code,
      warehouse_code,
      {
        item_group = '',
        search = '',
        page = 1,
        page_size = DEFAULT_PAGE_SIZE,
        paginate_by_item = true,
        force = false
      } = {}
    ) {
      const stateKey = inventoryStateKey(plant_code, warehouse_code)
      const key = inventoryCacheKey(plant_code, warehouse_code, {
        item_group,
        search,
        page,
        page_size,
        paginate_by_item
      })

      this.error = null
      this.inventoryLoading = true

      try {
        if (!force) {
          const cached = getFromCache(key)
          if (cached) {
            this.inventory[stateKey] = cached
            return cached
          }
        }

        const res = await callMethod(
          'khanal_tech_integrations.consumables.api.inventory.get_inventory',
          {
            plant_code,
            warehouse_code,
            item_group,
            search,
            page,
            page_size,
            paginate_by_item: paginate_by_item ? 1 : 0
          }
        )

        const data = normalizeResponse(res)
        this.inventory[stateKey] = data
        setCache(key, data)
        return data
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch inventory')
        throw err
      } finally {
        this.inventoryLoading = false
      }
    },

    async fetchBatchDetail(plant_code, warehouse_code, item_code, { force = false } = {}) {
      const key = batchCacheKey(plant_code, warehouse_code, item_code)

      this.error = null

      try {
        if (!force) {
          const cached = getFromCache(key)
          if (cached) return cached
        }

        const res = await callMethod(
          'khanal_tech_integrations.consumables.api.inventory.get_batch_detail',
          { plant_code, warehouse_code, item_code }
        )

        const data = normalizeResponse(res)
        setCache(key, data)
        return data
      } catch (err) {
        this.error = getErrorMessage(err, 'Failed to fetch batch detail')
        throw err
      }
    },

    invalidateCache(plant_code) {
      const warehouseKey = warehousesCacheKey(plant_code)
      delete cache[warehouseKey]

      for (const key of Object.keys(cache)) {
        if (key.startsWith(`inventory:${plant_code}:`) || key.startsWith(`batch:${plant_code}:`)) {
          delete cache[key]
        }
      }

      delete this.warehouses[plant_code]

      for (const key of Object.keys(this.inventory)) {
        if (key.startsWith(`${plant_code}:`)) {
          delete this.inventory[key]
        }
      }
    }
  }
})
