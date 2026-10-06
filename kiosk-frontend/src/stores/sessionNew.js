/**
 * Session Store - Following /frontend pattern
 * Uses cookie-based authentication (standard Frappe)
 * NO JWT, NO CSRF logic needed!
 */

import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { ref, computed } from 'vue'

export const useSessionStore = defineStore('kiosk-session', () => {
  // Get user from cookie (standard Frappe approach)
  function sessionUser() {
    let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
    let _sessionUser = cookies.get('user_id')
    if (_sessionUser === 'Guest') {
      _sessionUser = null
    }
    return _sessionUser
  }

  // Get current plant from cookie
  function currentPlant() {
    let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
    return cookies.get('current_plant') || null
  }

  // Reactive state
  const user = ref(sessionUser())
  const plant = ref(currentPlant())
  const isAuthenticated = computed(() => !!user.value)

  // Login resource (standard Frappe login)
  const login = createResource({
    url: 'khanal_tech_integrations.api.auth.plant_login',
    makeParams({ email, password, plantId }) {
      return {
        usr: email,
        pwd: password,
        plant_id: plantId
      }
    },
    onError(error) {
      console.error('[Login] Error:', error)
      throw new Error(error?.messages?.[0] || 'Login failed')
    },
    onSuccess(data) {
      user.value = sessionUser()
      plant.value = data.plant_id || plantId
      
      // Store plant in cookie for persistence
      document.cookie = `current_plant=${plant.value}; path=/`
      
      login.reset()
      
      // Redirect to dashboard
      window.location.href = `/kiosk/plant/${plant.value}/dashboard`
    }
  })

  // Logout resource
  const logout = createResource({
    url: 'logout',
    onSuccess() {
      user.value = null
      plant.value = null
      
      // Clear plant cookie
      document.cookie = 'current_plant=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT'
      
      // Redirect to login
      window.location.href = '/kiosk/login'
    },
    onError(error) {
      console.error('[Logout] Error:', error)
      // Force logout even if API fails
      user.value = null
      plant.value = null
      window.location.href = '/kiosk/login'
    }
  })

  // Verify session (check if still logged in)
  const verifySession = createResource({
    url: 'frappe.auth.get_logged_user',
    auto: false,
    onSuccess(data) {
      if (data?.message) {
        user.value = sessionUser()
      } else {
        user.value = null
        window.location.href = '/kiosk/login'
      }
    },
    onError() {
      user.value = null
      window.location.href = '/kiosk/login'
    }
  })

  // Switch plant
  async function switchPlant(newPlantId) {
    plant.value = newPlantId
    document.cookie = `current_plant=${newPlantId}; path=/`
    window.location.href = `/kiosk/plant/${newPlantId}/dashboard`
  }

  return {
    // State
    user,
    plant,
    isAuthenticated,
    
    // Resources
    login,
    logout,
    verifySession,
    
    // Methods
    switchPlant,
    sessionUser,
    currentPlant
  }
})

