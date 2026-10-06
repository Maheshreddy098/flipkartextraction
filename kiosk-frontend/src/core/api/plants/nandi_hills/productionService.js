/**
 * NandiHills Plant Production Service
 * Plant-specific Production operations for NandiHills
 */

import { BaseAPIService } from '../../common/baseService'

export class NandiHillsProductionService extends BaseAPIService {
  constructor() {
    super('NandiHillsProductionService')
    this.plantId = 'nandi_hills'
  }

  /**
   * Search BOM by Name or Code (Header Level - OITT)
   * @param {string} searchQuery - Search term (minimum 2 characters)
   * @returns {Promise<Object>}
   */
  async searchBOM(searchQuery) {
    this.logAPICall('searchBOM', { searchQuery })
    
    if (!searchQuery || searchQuery.length < 2) {
      return {
        success: false,
        message: 'Search query must be at least 2 characters',
        data: []
      }
    }
    
    return await this.postPlantAPI(this.plantId, 'production', 'search_bom', {
      search_query: searchQuery,
      plant_id: this.plantId
    })
  }

  /**
   * Get ITT1 components for a BOM
   * @param {string} bomCode - BOM code from OITT
   * @returns {Promise<Object>}
   */
  async getITT1Components(bomCode) {
    this.logAPICall('getITT1Components', { bomCode })
    this.validateParams({ bomCode }, ['bomCode'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_itt1_components', {
      bom_code: bomCode,
      plant_id: this.plantId
    })
  }

  /**
   * Get OITT header for a BOM
   * @param {string} bomCode - BOM code
   * @returns {Promise<Object>}
   */
  async getOITTHeader(bomCode) {
    this.logAPICall('getOITTHeader', { bomCode })
    this.validateParams({ bomCode }, ['bomCode'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_oitt_header', {
      bom_code: bomCode,
      plant_id: this.plantId
    })
  }

  /**
   * Get batch numbers for an item
   * @param {string} itemCode - Item code
   * @param {string} warehouse - Warehouse code (optional)
   * @param {string} dateFrom - From date (optional)
   * @param {string} dateTo - To date (optional)
   * @returns {Promise<Object>}
   */
  async getBatchNumbers(itemCode, warehouse = null, dateFrom = null, dateTo = null) {
    this.logAPICall('getBatchNumbers', { itemCode, warehouse, dateFrom, dateTo })
    this.validateParams({ itemCode }, ['itemCode'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_batch_numbers', {
      item_code: itemCode,
      warehouse: warehouse,
      date_from: dateFrom,
      date_to: dateTo,
      plant_id: this.plantId
    })
  }

  /**
   * Get batch numbers from Batch Date Item doctype
   * @param {string} itemCode - Item code
   * @param {string} dateFrom - Optional from date in YYYY-MM-DD format. If not provided, returns latest
   * @param {string} dateTo - Optional to date in YYYY-MM-DD format. Defaults to current date if dateFrom is provided
   * @returns {Promise<Object>}
   */
  async getBatchNumbersFromBatchDateItem(itemCode, dateFrom = null, dateTo = null) {
    this.logAPICall('getBatchNumbersFromBatchDateItem', { itemCode, dateFrom, dateTo })
    this.validateParams({ itemCode }, ['itemCode'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_batch_numbers_from_batch_date_item', {
      item_code: itemCode,
      date_from: dateFrom,
      date_to: dateTo,
      plant_id: this.plantId
    })
  }
}

// Export singleton instance
export const nandi_hillsProductionService = new NandiHillsProductionService()

export default nandi_hillsProductionService
