/**
 * Authentication Service for Plant-Specific Kiosk
 * Handles Frappe backend integration with plant-specific access control
 */

import axios from 'axios'
import { useSessionStore } from '../stores/session.js'
import { APP_CONFIG } from '../../config/constants.js'
class AuthService {
  constructor() {
    this.baseURL = APP_CONFIG.FRAPPE_API_URL
    this.apiClient = axios.create({
      baseURL: this.baseURL,
      timeout: APP_CONFIG.API_TIMEOUT,
      withCredentials: true,
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    this.setupInterceptors()
  }
  async resetPasswordWithToken(token, newPassword) {
    try {
      const res = await this.apiClient.post(
        APP_CONFIG.API_ENDPOINTS.RESET_PASSWORD_WITH_TOKEN,
        { token, new_password: newPassword }
      )
      return res.data?.message || { success: true }
    } catch (error) {
      const message = error?.response?.data?.message || 'Failed to reset password'
      throw new Error(message)
    }
  }

  setupInterceptors() {
    // Request interceptor
    this.apiClient.interceptors.request.use(
      (config) => {
        const token = this.getStoredToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor
    this.apiClient.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.logout()
        }
        return Promise.reject(error)
      }
    )
  }

  /**
   * Authenticate user with plant-specific access control
   * @param {string} email - User email
   * @param {string} password - User password
   * @param {string} plantId - Selected plant ID
   * @returns {Promise<Object>} Authentication result
   */
  async authenticate(email, password, plantId) {
    try {
      const sessionStore = useSessionStore()

      // Step 1: Authenticate with Frappe
      const authResponse = await this.apiClient.post(APP_CONFIG.API_ENDPOINTS.LOGIN, {
        usr: email,
        pwd: password
      })

      if (!authResponse.data.message) {
        throw new Error('Authentication failed')
      }

      // Step 2: Verify plant access
      const plantAccessResponse = await this.apiClient.get(APP_CONFIG.API_ENDPOINTS.VERIFY_PLANT_ACCESS, {
        params: {
          user: email,
          plant_id: plantId
        }
      })

      if (!plantAccessResponse.data.message?.has_access) {
        throw new Error(`Access denied for plant: ${plantId}`)
      }

      // Step 3: Get user permissions for the plant
      const permissionsResponse = await this.apiClient.get(APP_CONFIG.API_ENDPOINTS.GET_USER_PERMISSIONS, {
        params: {
          user: email,
          plant_id: plantId
        }
      })

      // Step 4: Generate JWT token with plant info
      const tokenResponse = await this.apiClient.post(APP_CONFIG.API_ENDPOINTS.GENERATE_PLANT_TOKEN, {
        user: email,
        plant_id: plantId,
        permissions: permissionsResponse.data.message
      })

      const token = tokenResponse.data.message.token
      const userData = tokenResponse.data.message.user_data

      // Step 5: Store session data
      sessionStore.setSession({
        token,
        user: userData,
        plant: {
          id: plantId,
          name: plantAccessResponse.data.message.plant_name,
          permissions: permissionsResponse.data.message
        },
        expiresAt: tokenResponse.data.message.expires_at
      })


      return {
        success: true,
        user: userData,
        plant: {
          id: plantId,
          name: plantAccessResponse.data.message.plant_name
        },
        permissions: permissionsResponse.data.message
      }

    } catch (error) {
      console.error('Authentication error:', error)

      throw new Error(error.response?.data?.message || error.message || 'Authentication failed')
    }
  }

  /**
   * Logout user and clear session
   */
  async logout() {
    try {
      const sessionStore = useSessionStore()
      const session = sessionStore.getSession()

      if (session) {
        // Call logout API
        await this.apiClient.post(APP_CONFIG.API_ENDPOINTS.LOGOUT)
      }

      // Clear session
      sessionStore.clearSession()
      
      // Redirect to login
      window.location.href = APP_CONFIG.ROUTES.LOGIN

    } catch (error) {
      console.error('Logout error:', error)
      // Clear session even if API call fails
      const sessionStore = useSessionStore()
      sessionStore.clearSession()
      window.location.href = APP_CONFIG.ROUTES.LOGIN
    }
  }

  /**
   * Refresh authentication token
   */
  async refreshToken() {
    try {
      const sessionStore = useSessionStore()
      const session = sessionStore.getSession()

      if (!session) {
        throw new Error('No active session')
      }

      const response = await this.apiClient.post(APP_CONFIG.API_ENDPOINTS.REFRESH_TOKEN, {
        token: session.token,
        user: session.user.email,
        plant_id: session.plant.id
      })

      const newToken = response.data.message.token
      sessionStore.updateToken(newToken)

      return newToken

    } catch (error) {
      console.error('Token refresh error:', error)
      this.logout()
      throw error
    }
  }

  /**
   * Verify current session validity
   */
  async verifySession() {
    try {
      const sessionStore = useSessionStore()
      const session = sessionStore.getSession()

      if (!session) {
        return false
      }

      // Check if token is expired
      if (session.expiresAt && Date.now() > session.expiresAt) {
        await this.refreshToken()
        return true
      }

      // Verify with backend
      const response = await this.apiClient.get(APP_CONFIG.API_ENDPOINTS.VERIFY_SESSION, {
        params: {
          user: session.user.email,
          plant_id: session.plant.id
        }
      })

      return response.data.message.valid

    } catch (error) {
      console.error('Session verification error:', error)
      return false
    }
  }

  /**
   * Get stored authentication token
   */
  getStoredToken() {
    const sessionStore = useSessionStore()
    const session = sessionStore.getSession()
    return session?.token
  }

  /**
   * Get current user session
   */
  getCurrentSession() {
    const sessionStore = useSessionStore()
    return sessionStore.getSession()
  }

  /**
   * Check if user has specific permission
   */
  hasPermission(permission) {
    const session = this.getCurrentSession()
    return session?.plant?.permissions?.includes(permission) || false
  }

  /**
   * Check if user has access to specific plant
   */
  async hasPlantAccess(plantId) {
    try {
      const session = this.getCurrentSession()
      if (!session) return false

      const response = await this.apiClient.get(APP_CONFIG.API_ENDPOINTS.VERIFY_PLANT_ACCESS, {
        params: {
          user: session.user.email,
          plant_id: plantId
        }
      })

      return response.data.message?.has_access || false

    } catch (error) {
      console.error('Plant access check error:', error)
      return false
    }
  }

  /**
   * Switch active plant without re-entering password (admin or multi-plant users)
   */
  async switchPlant(plantId) {
    try {
      const session = this.getCurrentSession()
      if (!session) throw new Error('No active session')

      // Verify access
      const hasAccess = await this.hasPlantAccess(plantId)
      if (!hasAccess) throw new Error(`Access denied for plant: ${plantId}`)

      // Get permissions for new plant
      const permissionsResponse = await this.apiClient.get(APP_CONFIG.API_ENDPOINTS.GET_USER_PERMISSIONS, {
        params: {
          user: session.user.email,
          plant_id: plantId
        }
      })

      // Generate new token
      const tokenResponse = await this.apiClient.post(APP_CONFIG.API_ENDPOINTS.GENERATE_PLANT_TOKEN, {
        user: session.user.email,
        plant_id: plantId,
        permissions: permissionsResponse.data.message
      })

      const sessionStore = useSessionStore()
      sessionStore.setSession({
        token: tokenResponse.data.message.token,
        user: session.user,
        plant: {
          id: plantId,
          name: tokenResponse.data.message.user_data?.plant_name || plantId,
          permissions: permissionsResponse.data.message
        },
        expiresAt: tokenResponse.data.message.expires_at
      })

      return true
    } catch (error) {
      console.error('Switch plant error:', error)
      throw error
    }
  }

  /**
   * Get client IP address (for logging)
   */
  async getClientIP() {
    try {
      const response = await fetch('https://api.ipify.org?format=json')
      const data = await response.json()
      return data.ip
    } catch (error) {
      return 'unknown'
    }
  }

  /**
   * Reset password request
   */
  async requestPasswordReset(email, plantId) {
    try {
      const response = await this.apiClient.post('/method/khanal_tech_integrations.api.auth.request_password_reset', {
        email,
        plant_id: plantId
      })

      return response.data.message

    } catch (error) {
      throw new Error(error.response?.data?.message || 'Password reset request failed')
    }
  }

  /**
   * Change password
   */
  async changePassword(currentPassword, newPassword) {
    try {
      const session = this.getCurrentSession()
      if (!session) {
        throw new Error('No active session')
      }

      const response = await this.apiClient.post('/method/khanal_tech_integrations.api.auth.change_password', {
        user: session.user.email,
        current_password: currentPassword,
        new_password: newPassword,
        plant_id: session.plant.id
      })

      return response.data.message

    } catch (error) {
      throw new Error(error.response?.data?.message || 'Password change failed')
    }
  }
}

// Export singleton instance
export const authService = new AuthService()
export default authService
