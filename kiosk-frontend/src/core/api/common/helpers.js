/**
 * Common Helper Utilities
 * Shared helper functions for all plants
 */

/**
 * Format date to YYYY-MM-DD
 * @param {Date|string} date - Date to format
 * @returns {string} Formatted date string
 */
export function formatDate(date) {
  if (!date) return ''
  
  const d = date instanceof Date ? date : new Date(date)
  if (isNaN(d.getTime())) return ''
  
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  
  return `${year}-${month}-${day}`
}

/**
 * Format number with commas
 * @param {number} number - Number to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted number string
 */
export function formatNumber(number, decimals = 0) {
  if (typeof number !== 'number') return '0'
  
  return number.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

/**
 * Generate batch number based on format
 * @param {Object} params - Parameters for batch generation
 * @param {string} params.vendorCode - Vendor code
 * @param {string} params.itemCode - Item code
 * @param {Date|string} params.date - Date for batch
 * @returns {string} Generated batch number
 */
export function generateBatchNumber({ vendorCode, itemCode, date }) {
  const dateStr = formatDate(date).replace(/-/g, '')
  return `${vendorCode}-${itemCode}-${dateStr}`
}

/**
 * Deep clone object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
export function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj
  return JSON.parse(JSON.stringify(obj))
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, wait = 300) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

/**
 * Throttle function
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in milliseconds
 * @returns {Function} Throttled function
 */
export function throttle(func, limit = 300) {
  let inThrottle
  return function executedFunction(...args) {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => (inThrottle = false), limit)
    }
  }
}

/**
 * Extract error message from various error formats
 * @param {Error|Object|string} error - Error object
 * @returns {string} Error message
 */
export function extractErrorMessage(error) {
  if (typeof error === 'string') return error
  
  if (error?.message) return error.message
  if (error?.error) return error.error
  if (error?.response?.data?.message) return error.response.data.message
  if (error?.response?.data?.error) return error.response.data.error
  
  return 'An unknown error occurred'
}

/**
 * Retry async function with exponential backoff
 * @param {Function} fn - Async function to retry
 * @param {number} maxRetries - Maximum number of retries
 * @param {number} delay - Initial delay in milliseconds
 * @returns {Promise} Promise that resolves with function result
 */
export async function retryWithBackoff(fn, maxRetries = 3, delay = 1000) {
  let lastError
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      if (i < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
      }
    }
  }
  
  throw lastError
}

/**
 * Group array by key
 * @param {Array} array - Array to group
 * @param {string|Function} key - Key or function to group by
 * @returns {Object} Grouped object
 */
export function groupBy(array, key) {
  return array.reduce((result, item) => {
    const groupKey = typeof key === 'function' ? key(item) : item[key]
    if (!result[groupKey]) {
      result[groupKey] = []
    }
    result[groupKey].push(item)
    return result
  }, {})
}

/**
 * Check if value is empty
 * @param {*} value - Value to check
 * @returns {boolean}
 */
export function isEmpty(value) {
  if (value == null) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}

/**
 * Convert snake_case to camelCase
 * @param {string} str - String to convert
 * @returns {string} camelCase string
 */
export function snakeToCamel(str) {
  return str.replace(/_([a-z])/g, (match, letter) => letter.toUpperCase())
}

/**
 * Convert camelCase to snake_case
 * @param {string} str - String to convert
 * @returns {string} snake_case string
 */
export function camelToSnake(str) {
  return str.replace(/([A-Z])/g, '_$1').toLowerCase()
}

export default {
  formatDate,
  formatNumber,
  generateBatchNumber,
  deepClone,
  debounce,
  throttle,
  extractErrorMessage,
  retryWithBackoff,
  groupBy,
  isEmpty,
  snakeToCamel,
  camelToSnake
}