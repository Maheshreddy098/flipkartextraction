/**
 * NandiHills Plant Disassembly Service
 * Fetches Goods Issue and Goods Receipt details for Production Orders
 * Also handles SAP B1 Production operations
 */

import { BaseAPIService } from '../../common/baseService'
import { APP_CONFIG } from '@/config/constants.js'

export class NandiHillsDisassemblyService extends BaseAPIService {
  constructor() {
    super('NandiHillsDisassemblyService')
    this.plantId = 'nandi_hills'
  }

  /**
   * Get disassembly details (Goods Issue & Goods Receipt) for a Production Order
   * @param {string|number} docNum - Production Order Document Number (e.g., 37491)
   * @returns {Promise<Object>} Response with status and data
   */
  async getDisassemblyDetails(docNum) {
    this.logAPICall('getDisassemblyDetails', { docNum })
    this.validateParams({ docNum }, ['docNum'])
    
    // Use endpoint from constants.js
    const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS.NANDI_HILLS.DISASSEMBLY.GET_DISASSEMBLY_DETAILS
    return await this.postToEndpoint(endpoint, {
      doc_num: docNum
    })
  }

  /**
   * Create Goods Issue in SAP B1
   * @param {Object} data - Goods Issue data
   * @returns {Promise<Object>} Response with status and data
   */
  async createGoodsIssue(data) {
    this.logAPICall('createGoodsIssue', data)
    // Use endpoint from constants.js
    const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS.NANDI_HILLS.DISASSEMBLY.CREATE_GOODS_ISSUE
    return await this.postToEndpoint(endpoint, data)
  }

  /**
   * Create Goods Receipt in SAP B1
   * @param {Object} data - Goods Receipt data
   * @returns {Promise<Object>} Response with status and data
   */
  async createGoodsReceipt(data) {
    this.logAPICall('createGoodsReceipt', data)
    // Use endpoint from constants.js
    const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS.NANDI_HILLS.DISASSEMBLY.CREATE_GOODS_RECEIPT
    return await this.postToEndpoint(endpoint, data)
  }

  /**
   * Get completed disassemblies list
   * @param {Object} filters - Optional filters
   * @returns {Promise<Object>} Response with status and data
   */
  async getCompletedDisassemblies(filters = {}) {
    this.logAPICall('getCompletedDisassemblies', filters)
    // Use endpoint from constants.js
    const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS.NANDI_HILLS.DISASSEMBLY.GET_COMPLETED_DISASSEMBLIES
    return await this.postToEndpoint(endpoint, {
      filters: filters
    })
  }

  // Note: backfillProductionOrderDocEntry method removed - backend function doesn't exist
  // If needed in the future, implement backfill_production_order_docentry in disassembly.py first
}

// Export singleton instance
export const nandi_hillsDisassemblyService = new NandiHillsDisassemblyService()

export default nandi_hillsDisassemblyService

