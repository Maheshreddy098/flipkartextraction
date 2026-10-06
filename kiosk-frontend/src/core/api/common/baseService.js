/**
 * Base API Service
 * Common functionality for all API services
 */

import axios from 'axios'
import { authService } from '../../auth/authService'
import { APP_CONFIG } from '@/config/constants.js'

const BASE_URL = window.location.origin

/**
 * Base class for all API services
 * Provides common functionality like interceptors, error handling, etc.
 */
export class BaseAPIService {
  constructor(serviceName = 'API') {
    this.serviceName = serviceName
    this.baseURL = BASE_URL
    this.setupInterceptors()
  }

  /**
   * Ensure CSRF token is available and get it
   * Tries window.csrf_token first, then falls back to window.boot.csrf_token
   * @returns {string|null} CSRF token or null if not available
   */
  ensureCSRFToken() {
    // Try boot object as fallback if csrf_token not set
    if (!window.csrf_token || window.csrf_token === '{{ csrf_token }}') {
      if (window.boot && window.boot.csrf_token) {
        window.csrf_token = window.boot.csrf_token
      }
    }
    
    const csrfToken = window.csrf_token
    return (csrfToken && csrfToken !== '{{ csrf_token }}') ? csrfToken : null
  }

  /**
   * Setup axios interceptors for authentication and error handling
   * CSRF token is read from window.csrf_token (injected by kiosk.py)
   */
  setupInterceptors() {
    // Request interceptor - Add authentication and CSRF token
    axios.interceptors.request.use(
      (config) => {
        const token = authService.getStoredToken()
        
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        
        // Add CSRF token (uses helper method to avoid duplication)
        const csrfToken = this.ensureCSRFToken()
        if (csrfToken) {
          config.headers['X-Frappe-CSRF-Token'] = csrfToken
        }
        
        // Enable credentials for session-based auth
        config.withCredentials = true
        
        return config
      },
      (error) => {
        console.error(`[${this.serviceName}] Request error:`, error)
        return Promise.reject(error)
      }
    )

    // Response interceptor - Handle errors
    axios.interceptors.response.use(
      (response) => response,
      (error) => {
        const status = error.response?.status
        
        if (status === 401) {
          alert('⚠️ Your session has expired. You will be redirected to login.')
          authService.logout()
        } else if (status === 403) {
          console.error('🚫 Access Denied')
          alert('⚠️ You don\'t have permission to access this resource.')
        }
        
        return Promise.reject(error)
      }
    )
  }

  /**
   * Build API endpoint URL for plant-specific APIs
   * First tries to get endpoint from constants.js, falls back to dynamic building
   * @param {string} plantId - Plant identifier (malur, krishnagiri, etc.)
   * @param {string} module - Module name (grn, production, etc.)
   * @param {string} method - Method name (get_purchase_orders, etc.)
   * @returns {string} Complete API endpoint URL
   */
  buildPlantAPIEndpoint(plantId, module, method) {
    // Try to get endpoint from constants.js first
    try {
      const plantKey = this.getPlantKeyFromId(plantId)
      const moduleKey = this.getModuleKeyFromName(module)
      const methodKey = this.getMethodKeyFromName(method)
      
      // Check if constants exist for this plant/module/method
      if (APP_CONFIG?.PLANT_API_ENDPOINTS?.[plantKey]?.[moduleKey]?.[methodKey]) {
        // Use constant from constants.js
        // Constants have /method/... but we need /api/method/...
        const endpoint = APP_CONFIG.PLANT_API_ENDPOINTS[plantKey][moduleKey][methodKey]
        const normalizedEndpoint = endpoint.startsWith('/method') 
          ? `/api${endpoint}` 
          : endpoint
        return `${this.baseURL}${normalizedEndpoint}`
      }
    } catch (error) {
      // Fall back to dynamic building if constants not available
      console.warn(`[${this.serviceName}] Could not use constants for ${plantId}.${module}.${method}, using dynamic URL`)
    }
    
    // Fallback: Build URL dynamically (original behavior)
    return `${this.baseURL}/api/method/khanal_tech_integrations.api.plants.${plantId}.${module}.${method}`
  }

  /**
   * Convert plant ID to constants key (e.g., 'nandi_hills' -> 'NANDI_HILLS')
   * @param {string} plantId - Plant identifier
   * @returns {string} Constants key
   */
  getPlantKeyFromId(plantId) {
    // Convert snake_case to UPPER_SNAKE_CASE
    return plantId.toUpperCase().replace(/-/g, '_')
  }

  /**
   * Convert module name to constants key (e.g., 'disassembly' -> 'DISASSEMBLY')
   * @param {string} module - Module name
   * @returns {string} Constants key
   */
  getModuleKeyFromName(module) {
    return module.toUpperCase()
  }

  /**
   * Convert method name to constants key (e.g., 'get_disassembly_details' -> 'GET_DISASSEMBLY_DETAILS')
   * @param {string} method - Method name
   * @returns {string} Constants key
   */
  getMethodKeyFromName(method) {
    return method.toUpperCase()
  }

  /**
   * Build API endpoint URL for common APIs
   * @param {string} module - Module name
   * @param {string} method - Method name
   * @returns {string} Complete API endpoint URL
   */
  buildCommonAPIEndpoint(module, method) {
    return `${this.baseURL}/api/method/khanal_tech_integrations.api.${module}.${method}`
  }

  /**
   * Make POST request to plant-specific endpoint
   * @param {string} plantId - Plant identifier
   * @param {string} module - Module name
   * @param {string} method - Method name
   * @param {Object} data - Request payload
   * @returns {Promise<Object>} API response
   */
  async postPlantAPI(plantId, module, method, data = {}) {
    try {
      const url = this.buildPlantAPIEndpoint(plantId, module, method)
      
      const response = await axios.post(url, data, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      })
      return this.extractResponse(response)
    } catch (error) {
      console.error(`[${this.serviceName}] Error calling ${method}:`, error)
      throw this.handleError(error)
    }
  }

  /**
   * Make POST request to a specific endpoint (full path)
   * Useful when using constants directly
   * @param {string} endpoint - Full endpoint path (e.g., '/method/khanal_tech_integrations.api...')
   * @param {Object} data - Request payload
   * @returns {Promise<Object>} API response
   */
  async postToEndpoint(endpoint, data = {}) {
    try {
      // Ensure endpoint starts with /api if it starts with /method
      // Constants have /method/... but we need /api/method/...
      const normalizedEndpoint = endpoint.startsWith('/method') 
        ? `/api${endpoint}` 
        : endpoint
      
      const url = `${this.baseURL}${normalizedEndpoint}`
      
      // Build headers - ensure CSRF token is included
      const headers = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Content-Type': 'application/json'
      }
      
      // Add CSRF token if available (CRITICAL - must be present for POST requests)
      // Uses helper method to avoid code duplication
      const csrfToken = this.ensureCSRFToken()
      if (csrfToken) {
        headers['X-Frappe-CSRF-Token'] = csrfToken
      } else {
        console.error('⚠️ CSRF token missing! Requests will fail with 417 error.')
        console.error('Available:', { 
          'window.csrf_token': window.csrf_token,
          'window.boot': window.boot,
          'window.boot.csrf_token': window.boot?.csrf_token 
        })
      }
      
      const response = await axios.post(url, data, {
        headers,
        withCredentials: true
      })
      return this.extractResponse(response)
    } catch (error) {
      console.error(`[${this.serviceName}] Error calling endpoint ${endpoint}:`, error)
      
      // If 417 error, log CSRF token status for debugging
      if (error.response?.status === 417) {
        console.error('417 Error - CSRF Token Debug:', {
          'window.csrf_token': window.csrf_token,
          'window.boot.csrf_token': window.boot?.csrf_token,
          'Token in headers': error.config?.headers?.['X-Frappe-CSRF-Token']
        })
      }
      
      throw this.handleError(error)
    }
  }

  /**
   * Make POST request to common endpoint
   * @param {string} module - Module name
   * @param {string} method - Method name
   * @param {Object} data - Request payload
   * @returns {Promise<Object>} API response
   */
  async postCommonAPI(module, method, data = {}) {
    try {
      const url = this.buildCommonAPIEndpoint(module, method)
      
      const response = await axios.post(url, data, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      })
      return this.extractResponse(response)
    } catch (error) {
      console.error(`[${this.serviceName}] Error calling ${method}:`, error)
      throw this.handleError(error)
    }
  }

  /**
   * Extract response data from Frappe API response
   * @param {Object} response - Axios response object
   * @returns {Object} Extracted data
   */
  extractResponse(response) {
    // Frappe typically returns data in response.data.message
    return response.data.message || response.data
  }

  /**
   * Handle API errors consistently
   * @param {Error} error - Error object
   * @returns {Object} Formatted error
   */
  handleError(error) {
    if (error.response) {
      // Server responded with error
      const message = error.response.data?.message || 
                     error.response.data?.error || 
                     error.response.data?.exc || 
                     'An error occurred'
      
      return {
        success: false,
        message: this.cleanErrorMessage(message),
        status: error.response.status,
        data: error.response.data
      }
    } else if (error.request) {
      // Request made but no response
      return {
        success: false,
        message: 'No response from server. Please check your connection.',
        status: 0
      }
    } else {
      // Error in request setup
      return {
        success: false,
        message: error.message || 'An unexpected error occurred',
        status: 0
      }
    }
  }

  /**
   * Clean error messages from Frappe exceptions
   * @param {string} message - Raw error message
   * @returns {string} Cleaned message
   */
  cleanErrorMessage(message) {
    if (typeof message !== 'string') return message
    
    // Remove Python traceback
    const lines = message.split('\n')
    const cleanedLines = lines.filter(line => 
      !line.includes('Traceback') && 
      !line.includes('File "') &&
      !line.trim().startsWith('at ')
    )
    
    return cleanedLines.join('\n').trim() || message
  }

  /**
   * Validate required parameters
   * @param {Object} params - Parameters object
   * @param {Array<string>} required - Required parameter names
   * @throws {Error} If required parameters are missing
   */
  validateParams(params, required) {
    const missing = required.filter(key => params[key] === undefined || params[key] === null)
    if (missing.length > 0) {
      throw new Error(`Missing required parameters: ${missing.join(', ')}`)
    }
  }

  /**
   * Log API call for debugging
   * @param {string} method - Method name
   * @param {Object} params - Parameters
   */
  logAPICall(method, params = {}) {
    if (process.env.NODE_ENV === 'development') {
    }
  }
}

export default BaseAPIService

