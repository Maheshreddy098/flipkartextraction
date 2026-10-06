/**
 * Generic Plant API composable using frappe-ui
 * Provides common API methods for all plants
 */

import { createResource } from 'frappe-ui'

/**
 * Create a plant-specific API composable
 * @param {string} plantId - Plant identifier (malur, krishnagiri, etc.)
 * @param {string} module - Module name (grn, production, inventory)
 */
export function usePlantAPI(plantId, module) {
  const baseUrl = `khanal_tech_integrations.api.plants.${plantId}.${module}`

  /**
   * Create a generic resource for any method
   * @param {string} method - API method name
   * @param {object} options - Additional resource options
   */
  const createMethod = (method, options = {}) => {
    return createResource({
      url: `${baseUrl}.${method}`,
      auto: false,
      ...options
    })
  }

  return {
    createMethod,
    baseUrl
  }
}

/**
 * Create a list resource with pagination
 */
export function useListResource(plantId, module, method, options = {}) {
  return createResource({
    url: `khanal_tech_integrations.api.plants.${plantId}.${module}.${method}`,
    params: {
      page: 1,
      page_size: 20,
      ...options.params
    },
    auto: false,
    transform(data) {
      return data?.data || []
    },
    onError(error) {
      console.error(`[${plantId}/${module}/${method}] Error:`, error)
    },
    ...options
  })
}

/**
 * Create a detail resource
 */
export function useDetailResource(plantId, module, method, options = {}) {
  return createResource({
    url: `khanal_tech_integrations.api.plants.${plantId}.${module}.${method}`,
    auto: false,
    onError(error) {
      console.error(`[${plantId}/${module}/${method}] Error:`, error)
    },
    ...options
  })
}

/**
 * Create a mutation resource (create, update, delete)
 */
export function useMutationResource(plantId, module, method, options = {}) {
  return createResource({
    url: `khanal_tech_integrations.api.plants.${plantId}.${module}.${method}`,
    method: 'POST',
    auto: false,
    onError(error) {
      console.error(`[${plantId}/${module}/${method}] Error:`, error)
    },
    ...options
  })
}

