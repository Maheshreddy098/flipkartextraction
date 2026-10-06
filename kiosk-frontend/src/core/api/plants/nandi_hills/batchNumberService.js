/**
 * NandiHills Plant Batch Number Service
 * Handles batch number generation and retrieval for Nandi Hills plant
 */

import { BaseAPIService } from '../../common/baseService'
import { APP_CONFIG } from '@/config/constants.js'

export class NandiHillsBatchNumberService extends BaseAPIService {
  constructor() {
    super('NandiHillsBatchNumberService')
    this.plantId = 'nandi_hills'
  }

  /**
   * Get batch numbers for configured items
   * @param {string} date - Date in YYYY-MM-DD format (optional, defaults to today)
   * @param {number} days - Number of days to look back (optional, defaults to 1)
   * @returns {Promise<Object>}
   */
  async getBatches(date = null, days = 1) {
    this.logAPICall('getBatches', { date, days })
    
    const params = {}
    if (date) params.date = date
    if (days) params.days = days
    
    // Use endpoint from constants
    const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS.NANDI_HILLS.BATCH_NUMBER_GENERATOR.GET_BATCHES
    return await this.postToEndpoint(endpoint, params)
  }

  /**
   * Generate batch numbers for the given date
   * @param {string} date - Date in YYYY-MM-DD format (optional, defaults to today)
   * @returns {Promise<Object>}
   */
  async generateBatches(date = null) {
    this.logAPICall('generateBatches', { date })
    
    // Verify CSRF token is available
    if (!window.csrf_token || window.csrf_token === '{{ csrf_token }}') {
      console.warn('⚠️ CSRF token not available. Make sure you are logged in.')
    }
    
    const data = {}
    if (date) data.date = date
    
    // Use endpoint from constants
    const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS.NANDI_HILLS.BATCH_NUMBER_GENERATOR.GENERATE_BATCHES
    return await this.postToEndpoint(endpoint, data)
  }
}

// Export singleton instance
export const nandiHillsBatchNumberService = new NandiHillsBatchNumberService()

export default nandiHillsBatchNumberService

