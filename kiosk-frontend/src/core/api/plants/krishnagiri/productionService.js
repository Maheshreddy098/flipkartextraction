/**
 * Krishnagiri Plant Production Service
 * Plant-specific Production operations for Krishnagiri
 */

import { BaseAPIService } from '../../common/baseService'
import { validateProductionData } from '../../common/validators'
import config from './config'

export class KrishnagiriProductionService extends BaseAPIService {
  constructor() {
    super('KrishnagiriProductionService')
    this.plantId = 'krishnagiri'
    this.config = config
  }

  /**
   * Get crate assignments
   * @param {string} itemCode - Filter by item code
   * @returns {Promise<Object>}
   */
  async getCrateAssignments(itemCode = null) {
    this.logAPICall('getCrateAssignments', { itemCode })
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_crate_assignments', {
      plant_id: this.plantId,
      item_code: itemCode
    })
  }

  /**
   * Get production items
   * @returns {Promise<Object>}
   */
  async getProductionItems() {
    this.logAPICall('getProductionItems')
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_production_items', {
      plant_id: this.plantId
    })
  }

  /**
   * Get process types
   * @returns {Promise<Object>}
   */
  async getProcessTypes() {
    this.logAPICall('getProcessTypes')
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_process_types', {
      plant_id: this.plantId
    })
  }

  /**
   * Create pre-production order with Krishnagiri-specific validation
   * @param {Object} crateDetails - Crate consumption details
   * @param {string} processType - Process type
   * @param {number} employeeCount - Number of employees
   * @param {string} userEmail - User email
   * @returns {Promise<Object>}
   */
  async createPreProduction(crateDetails, processType, employeeCount, userEmail) {
    this.logAPICall('createPreProduction', { crateDetails, processType, employeeCount, userEmail })
    this.validateParams(
      { crateDetails, processType, employeeCount, userEmail },
      ['crateDetails', 'processType', 'employeeCount', 'userEmail']
    )
    
    // Krishnagiri-specific validation
    validateProductionData({ process_type: processType, employee_count: employeeCount, user_email: userEmail }, this.config)
    
    return await this.postPlantAPI(this.plantId, 'production', 'create_pre_production', {
      crate_details: JSON.stringify(crateDetails),
      process_type: JSON.stringify(processType),
      employee_count: employeeCount,
      user_email: userEmail,
      plant_id: this.plantId
    })
  }

  /**
   * Get production orders
   * @param {Object} filters - Filter criteria
   * @param {number} page - Page number
   * @param {number} pageSize - Records per page
   * @returns {Promise<Object>}
   */
  async getProductionOrders(filters = {}, page = 1, pageSize = null) {
    pageSize = pageSize || this.config.settings.defaultPageSize
    this.logAPICall('getProductionOrders', { filters, page, pageSize })
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_production_orders', {
      filters: JSON.stringify(filters),
      page: page,
      page_size: pageSize,
      plant_id: this.plantId
    })
  }

  /**
   * Get production order details
   * @param {string} productionId - Production order document name
   * @returns {Promise<Object>}
   */
  async getProductionOrderDetails(productionId) {
    this.logAPICall('getProductionOrderDetails', { productionId })
    this.validateParams({ productionId }, ['productionId'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_production_order_details', {
      production_id: productionId
    })
  }

  /**
   * Submit production output
   * @param {string} productionId - Production order document name
   * @param {Array} outputData - Output details
   * @returns {Promise<Object>}
   */
  async submitProductionOutput(productionId, outputData) {
    this.logAPICall('submitProductionOutput', { productionId, outputData })
    this.validateParams({ productionId, outputData }, ['productionId', 'outputData'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'submit_production_output', {
      production_id: productionId,
      output_data: JSON.stringify(outputData)
    })
  }

  /**
   * Approve production order
   * @param {string} productionId - Production order document name
   * @returns {Promise<Object>}
   */
  async approveProductionOrder(productionId) {
    this.logAPICall('approveProductionOrder', { productionId })
    this.validateParams({ productionId }, ['productionId'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'approve_production_order', {
      production_id: productionId
    })
  }

  /**
   * Reject production order
   * @param {string} productionId - Production order document name
   * @param {string} rejectionReason - Reason for rejection
   * @returns {Promise<Object>}
   */
  async rejectProductionOrder(productionId, rejectionReason) {
    this.logAPICall('rejectProductionOrder', { productionId, rejectionReason })
    this.validateParams({ productionId, rejectionReason }, ['productionId', 'rejectionReason'])
    
    return await this.postPlantAPI(this.plantId, 'production', 'reject_production_order', {
      production_id: productionId,
      rejection_reason: rejectionReason
    })
  }

  /**
   * Get production statistics
   * @param {Object} dateRange - Date range filter
   * @returns {Promise<Object>}
   */
  async getProductionStatistics(dateRange = null) {
    this.logAPICall('getProductionStatistics', { dateRange })
    
    return await this.postPlantAPI(this.plantId, 'production', 'get_production_statistics', {
      plant_id: this.plantId,
      date_range: dateRange ? JSON.stringify(dateRange) : null
    })
  }
}

// Export singleton instance
export const krishnagiriProductionService = new KrishnagiriProductionService()

export default krishnagiriProductionService

