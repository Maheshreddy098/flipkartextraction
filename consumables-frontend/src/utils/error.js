/**
 * Extract a human-readable message from any error thrown by frappeRequest.
 *
 * frappe-ui throws errors with:
 *   e.messages  → string[]  (parsed _server_messages from Frappe)
 *   e.message   → string    (URL + exc_type, or a JS TypeError)
 *   e.exc       → string    (Python traceback)
 *
 * When the backend returns a non-JSON body, frappe-ui itself throws a TypeError
 * with message "Cannot read properties of undefined (reading 'exc')".
 * We hide that and show a generic server error instead.
 */
export function parseApiError(e, fallback = 'Something went wrong. Please try again.') {
  if (!e) return fallback
  // frappe-ui's structured messages array (most specific)
  if (Array.isArray(e.messages) && e.messages.length) {
    const first = e.messages.find(m => m && typeof m === 'string')
    if (first) return first
  }
  // Plain Error message — but NOT the internal frappe-ui JS TypeError
  if (e.message && typeof e.message === 'string') {
    if (e.message.includes('Cannot read properties') || e.message.includes('undefined')) {
      return fallback
    }
    // Strip the URL prefix that frappe-ui prepends
    const parts = e.message.split('\n')
    const clean = parts[parts.length - 1].trim()
    if (clean) return clean
  }
  return fallback
}
