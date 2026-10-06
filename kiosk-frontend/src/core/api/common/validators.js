/**
 * Common Validation Utilities
 * Shared validation functions for all plants
 */

/**
 * Validate GRN data structure
 * @param {Object} grnData - GRN data to validate
 * @param {Object} plantConfig - Plant-specific configuration
 * @throws {Error} If validation fails
 */
export function validateGRNData(grnData, plantConfig = {}) {
  const required = ['po_number', 'vendor_code', 'vendor_name', 'invoice_number', 'invoice_date', 'received_date']
  
  for (const field of required) {
    if (!grnData[field]) {
      throw new Error(`Missing required field: ${field}`)
    }
  }
  
  // Validate line items (frontend uses 'lines', backend expects 'line_items')
  const lineItems = grnData.lines || grnData.line_items
  if (!lineItems || !Array.isArray(lineItems) || lineItems.length === 0) {
    throw new Error('GRN must have at least one line item')
  }
  
  // Plant-specific validation
  if (plantConfig.warehousePrefix) {
    for (const item of lineItems) {
      if (item.warehouse && !item.warehouse.startsWith(plantConfig.warehousePrefix)) {
        throw new Error(`Warehouse must start with ${plantConfig.warehousePrefix} for this plant`)
      }
    }
  }
  
  return true
}

/**
 * Validate production data structure
 * @param {Object} productionData - Production order data to validate
 * @param {Object} plantConfig - Plant-specific configuration
 * @throws {Error} If validation fails
 */
export function validateProductionData(productionData, plantConfig = {}) {
  const required = ['process_type', 'employee_count', 'user_email']
  
  for (const field of required) {
    if (!productionData[field]) {
      throw new Error(`Missing required field: ${field}`)
    }
  }
  
  // Validate employee count
  if (productionData.employee_count < 1) {
    throw new Error('Employee count must be at least 1')
  }
  
  // Validate email format
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(productionData.user_email)) {
    throw new Error('Invalid email format')
  }
  
  // Validate process type if plant has specific types
  if (plantConfig.settings?.defaultProcessTypes) {
    if (!plantConfig.settings.defaultProcessTypes.includes(productionData.process_type)) {
      throw new Error(`Invalid process type. Must be one of: ${plantConfig.settings.defaultProcessTypes.join(', ')}`)
    }
  }
  
  return true
}

/**
 * Validate date format (YYYY-MM-DD)
 * @param {string} dateString - Date string to validate
 * @returns {boolean}
 */
export function isValidDate(dateString) {
  if (!dateString) return false
  
  const regex = /^\d{4}-\d{2}-\d{2}$/
  if (!regex.test(dateString)) return false
  
  const date = new Date(dateString)
  return date instanceof Date && !isNaN(date)
}

/**
 * Validate batch number format
 * @param {string} batchNumber - Batch number to validate
 * @param {Object} plantConfig - Plant-specific configuration
 * @returns {boolean}
 */
export function isValidBatchNumber(batchNumber, plantConfig = {}) {
  if (!batchNumber) return false
  
  // Basic validation - alphanumeric with hyphens
  const basicRegex = /^[A-Z0-9-]+$/
  if (!basicRegex.test(batchNumber)) return false
  
  // Plant-specific format validation
  if (plantConfig.settings?.batchNumberFormat) {
    // Check if batch follows expected pattern
    // Format: {vendorCode}-{itemCode}-{date}
    const parts = batchNumber.split('-')
    if (parts.length < 3) return false
  }
  
  return true
}

/**
 * Validate quantity
 * @param {number} quantity - Quantity to validate
 * @param {number} min - Minimum allowed (default: 0)
 * @param {number} max - Maximum allowed (default: Infinity)
 * @returns {boolean}
 */
export function isValidQuantity(quantity, min = 0, max = Infinity) {
  if (typeof quantity !== 'number') return false
  if (quantity < min || quantity > max) return false
  return true
}

/**
 * Sanitize input string
 * @param {string} input - Input string to sanitize
 * @returns {string} Sanitized string
 */
export function sanitizeInput(input) {
  if (typeof input !== 'string') return ''
  
  // Remove potentially dangerous characters
  return input
    .trim()
    .replace(/[<>]/g, '') // Remove angle brackets
    .slice(0, 500) // Limit length
}

export default {
  validateGRNData,
  validateProductionData,
  isValidDate,
  isValidBatchNumber,
  isValidQuantity,
  sanitizeInput
}

