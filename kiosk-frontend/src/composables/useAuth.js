/**
 * Authentication composable using frappe-ui
 * Replaces authService.js
 */

import { createResource } from 'frappe-ui'
import { ref, computed } from 'vue'

export function useAuth() {
  // Get current user from cookies
  const getUserFromCookie = () => {
    const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
    let userId = cookies.get('user_id')
    return userId === 'Guest' ? null : userId
  }

  const user = ref(getUserFromCookie())
  const isAuthenticated = computed(() => !!user.value)

  // Login resource
  const login = createResource({
    url: 'login',
    method: 'POST',
    auto: false,
    onSuccess(data) {
      user.value = getUserFromCookie()
      login.reset()
    },
    onError(error) {
      console.error('Login failed:', error)
      throw new Error(error?.messages?.[0] || 'Login failed')
    }
  })

  // Logout resource
  const logout = createResource({
    url: 'logout',
    method: 'POST',
    auto: false,
    onSuccess() {
      user.value = null
      window.location.href = '/kiosk/login'
    },
    onError(error) {
      console.error('Logout failed:', error)
      // Even if API fails, clear session
      user.value = null
      window.location.href = '/kiosk/login'
    }
  })

  // Verify plant access
  const verifyPlantAccess = createResource({
    url: 'khanal_tech_integrations.api.auth.verify_plant_access',
    method: 'GET',
    auto: false,
    makeParams({ plantId }) {
      return {
        user: user.value,
        plant_id: plantId
      }
    }
  })

  return {
    user,
    isAuthenticated,
    login,
    logout,
    verifyPlantAccess,
    getUserFromCookie
  }
}

