import apiClient from '../api/apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'
import { useSessionStore } from '../stores/session.js'

export async function login(email, password) {
  const sessionStore = useSessionStore()

  await apiClient.post(APP_CONFIG.API_ENDPOINTS.LOGIN, {
    usr: email,
    pwd: password,
  })

  const { data } = await apiClient.get(APP_CONFIG.API_ENDPOINTS.VERIFY_ACCESS, {
    params: { user: email },
  })

  const accessInfo = data.message
  if (!accessInfo?.has_access) {
    throw new Error('No Real Aquatics access assigned to this user')
  }

  sessionStore.setSession(accessInfo)
  return accessInfo
}

export async function logout() {
  const sessionStore = useSessionStore()
  try {
    await apiClient.post(APP_CONFIG.API_ENDPOINTS.LOGOUT)
  } catch { /* ignore */ }
  sessionStore.clearSession()
  window.location.href = APP_CONFIG.BASE_PATH + '/login'
}

export async function checkSession() {
  const sessionStore = useSessionStore()

  if (!sessionStore.isAuthenticated) {
    const restored = sessionStore.initFromStorage()
    if (!restored) return false
  }

  try {
    const { data } = await apiClient.get(APP_CONFIG.API_ENDPOINTS.USER_INFO)
    if (data.message?.user && data.message.user !== 'Guest') {
      sessionStore.setSession(data.message)
      return true
    }
  } catch { /* session invalid */ }

  sessionStore.clearSession()
  return false
}
