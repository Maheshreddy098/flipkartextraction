/**
 * Session Store - Manages user session and plant-specific data
 * Uses Pinia for state management with persistence
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { logger } from '@/core/utils/logger'
import { secureStorage } from '@/core/utils/security'
import { APP_CONFIG } from '@/config/constants.js'

export const useSessionStore = defineStore('session', () => {
  // State
  const token = ref(null)
  const user = ref(null)
  const plant = ref(null)
  const permissions = ref([])
  const loginTime = ref(null)
  const expiresAt = ref(null)
  const isAuthenticated = ref(false)

  // Computed properties
  const currentUser = computed(() => user.value)
  const currentPlant = computed(() => plant.value)
  const userPermissions = computed(() => permissions.value)
  const sessionDuration = computed(() => {
    if (!loginTime.value) return 0
    return Date.now() - loginTime.value
  })
  const isSessionValid = computed(() => {
    if (!isAuthenticated.value || !expiresAt.value) return false
    // Convert expiresAt to timestamp if it's a string
    const expiryTime = typeof expiresAt.value === 'string' 
      ? new Date(expiresAt.value).getTime() 
      : expiresAt.value
    return Date.now() < expiryTime
  })

  // Actions
  function setSession(sessionData) {
    token.value = sessionData.token
    user.value = sessionData.user
    plant.value = sessionData.plant
    permissions.value = sessionData.plant?.permissions || []
    loginTime.value = Date.now()
    expiresAt.value = sessionData.expiresAt
    isAuthenticated.value = true

    // Store in encrypted localStorage for security
    secureStorage.setItem('kiosk-session', {
      token: token.value,
      user: user.value,
      plant: plant.value,
      permissions: permissions.value,
      loginTime: loginTime.value,
      expiresAt: expiresAt.value
    })

    logger.info('Session established', { 
      user: user.value?.email, 
      plant: plant.value?.id 
    }, 'SessionStore')
  }

  function updateToken(newToken) {
    token.value = newToken
    
    // Update encrypted storage
    const stored = secureStorage.getItem('kiosk-session')
    if (stored) {
      stored.token = newToken
      secureStorage.setItem('kiosk-session', stored)
      logger.debug('Token updated', null, 'SessionStore')
    }
  }

  function clearSession() {
    token.value = null
    user.value = null
    plant.value = null
    permissions.value = []
    loginTime.value = null
    expiresAt.value = null
    isAuthenticated.value = false

    // Clear secure storage
    secureStorage.removeItem('kiosk-session')
    sessionStorage.clear()
    
    logger.info('Session cleared', null, 'SessionStore')
  }

  function getSession() {
    if (isAuthenticated.value) {
      return {
        token: token.value,
        user: user.value,
        plant: plant.value,
        permissions: permissions.value,
        loginTime: loginTime.value,
        expiresAt: expiresAt.value
      }
    }
    return null
  }

  function hasPermission(permission) {
    return permissions.value.includes(permission)
  }

  function hasAnyPermission(permissionList) {
    return permissionList.some(permission => permissions.value.includes(permission))
  }

  function hasAllPermissions(permissionList) {
    return permissionList.every(permission => permissions.value.includes(permission))
  }

  function updateUserData(userData) {
    user.value = { ...user.value, ...userData }
    
    // Update encrypted storage
    const stored = secureStorage.getItem('kiosk-session')
    if (stored) {
      stored.user = user.value
      secureStorage.setItem('kiosk-session', stored)
    }
  }

  function updatePlantData(plantData) {
    plant.value = { ...plant.value, ...plantData }
    
    // Update encrypted storage
    const stored = secureStorage.getItem('kiosk-session')
    if (stored) {
      stored.plant = plant.value
      secureStorage.setItem('kiosk-session', stored)
    }
  }

  function initializeFromStorage() {
    try {
      const sessionData = secureStorage.getItem('kiosk-session')
      if (sessionData) {
        // Check if session is still valid
        const expiryTime = typeof sessionData.expiresAt === 'string' 
          ? new Date(sessionData.expiresAt).getTime() 
          : sessionData.expiresAt
        if (sessionData.expiresAt && Date.now() < expiryTime) {
          token.value = sessionData.token
          user.value = sessionData.user
          plant.value = sessionData.plant
          permissions.value = sessionData.permissions || []
          loginTime.value = sessionData.loginTime
          expiresAt.value = sessionData.expiresAt
          isAuthenticated.value = true
          logger.debug('Session restored from storage', { user: user.value?.email }, 'SessionStore')
          return true
        } else {
          // Session expired, clear it
          logger.warn('Session expired', { expiresAt: sessionData.expiresAt }, 'SessionStore')
          clearSession()
        }
      }
    } catch (error) {
      logger.error('Error initializing session from storage', error, 'SessionStore')
      clearSession()
    }
    return false
  }

  function extendSession(newExpiresAt) {
    expiresAt.value = newExpiresAt
    
    // Update encrypted storage
    const stored = secureStorage.getItem('kiosk-session')
    if (stored) {
      stored.expiresAt = newExpiresAt
      secureStorage.setItem('kiosk-session', stored)
      logger.debug('Session extended', { expiresAt: newExpiresAt }, 'SessionStore')
    }
  }

  // Session activity tracking
  const lastActivity = ref(Date.now())
  const activityTimeout = ref(null)

  function updateActivity() {
    lastActivity.value = Date.now()
    
    // Clear existing timeout
    if (activityTimeout.value) {
      clearTimeout(activityTimeout.value)
    }
    
    // Set new timeout for session expiry
    const timeoutDuration = 30 * 60 * 1000 // 30 minutes
    activityTimeout.value = setTimeout(() => {
      if (isAuthenticated.value) {
        logger.warn('Session timeout due to inactivity', { duration: timeoutDuration }, 'SessionStore')
        clearSession()
        window.location.href = APP_CONFIG.ROUTES.LOGIN
      }
    }, timeoutDuration)
  }

  function getSessionInfo() {
    return {
      isAuthenticated: isAuthenticated.value,
      user: user.value,
      plant: plant.value,
      permissions: permissions.value,
      sessionDuration: sessionDuration.value,
      lastActivity: lastActivity.value,
      isSessionValid: isSessionValid.value
    }
  }

  return {
    // State
    token,
    user,
    plant,
    permissions,
    loginTime,
    expiresAt,
    isAuthenticated,
    lastActivity,

    // Computed
    currentUser,
    currentPlant,
    userPermissions,
    sessionDuration,
    isSessionValid,

    // Actions
    setSession,
    updateToken,
    clearSession,
    getSession,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    updateUserData,
    updatePlantData,
    initializeFromStorage,
    extendSession,
    updateActivity,
    getSessionInfo
  }
})
