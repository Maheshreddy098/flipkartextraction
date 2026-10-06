import axios from 'axios'
import { APP_CONFIG } from '@/config/settings.js'

const apiClient = axios.create({
  baseURL: APP_CONFIG.FRAPPE_API_URL,
  timeout: APP_CONFIG.API_TIMEOUT,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const csrfToken = window.csrf_token
  if (csrfToken) {
    config.headers['X-Frappe-CSRF-Token'] = csrfToken
  }
  return config
})

function extractFrappeErrorMessage(data) {
  if (!data) return ''
  if (typeof data.message === 'string' && data.message.trim()) {
    return data.message
  }
  // Frappe often sends _server_messages as a JSON-encoded list of JSON strings
  if (data._server_messages) {
    try {
      const raw = JSON.parse(data._server_messages)
      const parts = []
      for (const entry of raw) {
        try {
          const obj = typeof entry === 'string' ? JSON.parse(entry) : entry
          if (obj.message) parts.push(obj.message)
        } catch {
          // ignore parse errors for individual entries
        }
      }
      if (parts.length) return parts.join('\n')
    } catch {
      // ignore parse error for _server_messages
    }
  }
  return ''
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      window.location.href = APP_CONFIG.BASE_PATH + '/login'
    }
    // Normalize Frappe validation errors so consumers can use e.response.data.message
    const data = error.response?.data
    const msg = extractFrappeErrorMessage(data)
    if (msg) {
      if (!data.message) data.message = msg
    }
    return Promise.reject(error)
  }
)

export function callApi(endpoint, params = {}, method = 'GET') {
  if (method === 'GET') {
    return apiClient.get(endpoint, { params }).then((r) => r.data.message)
  }
  return apiClient.post(endpoint, params).then((r) => r.data.message)
}

export default apiClient
