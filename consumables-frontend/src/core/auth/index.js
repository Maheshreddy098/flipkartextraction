import { frappeRequest } from 'frappe-ui'

export function getCurrentUserContext() {
  return frappeRequest({
    url: 'khanal_tech_integrations.consumables.api.auth.get_current_user_context',
  })
}

export async function login(usr, pwd) {
  const res = await fetch('/api/method/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Frappe-CSRF-Token': window.csrf_token || '' },
    body: new URLSearchParams({ usr, pwd }),
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.message || 'Login failed')
  }
  return res.json()
}

export async function logout() {
  await fetch('/api/method/logout', {
    method: 'GET',
    credentials: 'include',
  })
}
