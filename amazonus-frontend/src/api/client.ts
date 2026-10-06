import axios from 'axios'
import { toast } from '@/stores/toast'

declare global {
  interface Window { csrf_token?: string; session_user?: string }
}

const API_BASE = '/api/method/khanal_tech_integrations.amazon_us.api.ops.'

const http = axios.create({ withCredentials: true })

http.interceptors.request.use((config) => {
  if (window.csrf_token) config.headers['X-Frappe-CSRF-Token'] = window.csrf_token
  return config
})

/** Call a whitelisted ops endpoint; unwraps Frappe's {message} envelope. */
export async function call<T = any>(method: string, params: Record<string, any> = {}): Promise<T> {
  try {
    const res = await http.post(API_BASE + method, params, {
      headers: { 'Content-Type': 'application/json' },
    })
    return res.data.message as T
  } catch (err: any) {
    const status = err?.response?.status
    if (status === 403) {
      toast('View-only access — posting needs the Amazon US Manager role', 'error')
    } else if (status === 401) {
      window.location.href = `/login?redirect-to=${encodeURIComponent('/amazonus')}`
    } else {
      const server = err?.response?.data
      let msg = server?._server_messages
      try { msg = msg ? JSON.parse(JSON.parse(msg)[0]).message : undefined } catch { /* keep raw */ }
      toast(msg || server?.exception?.split('\n')[0] || err.message || 'Request failed', 'error')
    }
    throw err
  }
}
