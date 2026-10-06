import { onUnmounted } from 'vue'
import { io } from 'socket.io-client'

function resolveName(refOrFn) {
  if (typeof refOrFn === 'function') return refOrFn()
  return refOrFn?.value ?? ''
}

/**
 * Frappe realtime: namespace /{sitename} on socket port (default 9000).
 */
export function useStoreopsSocket(nameRefOrFn, onMatch) {
  let socket = null

  function resolveSocketPort() {
    // Env override — highest priority (useful for Vite dev server)
    if (import.meta.env.VITE_SOCKETIO_PORT) return import.meta.env.VITE_SOCKETIO_PORT
    // Production: if the page is on standard HTTPS/HTTP, nginx proxies /socket.io
    // on the same port — never use window.socketio_port (that's the internal port).
    const webPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80')
    const webPortNum = parseInt(webPort)
    if (webPortNum === 80 || webPortNum === 443) return webPort
    // Dev: use the explicit socketio_port injected by storeops.py boot
    if (window.socketio_port) return String(window.socketio_port)
    // Dev fallback: Frappe convention is web_port + 1000 (8000→9000, 8001→9001)
    if (webPortNum >= 8000 && webPortNum < 9000) return String(webPortNum + 1000)
    return webPort
  }

  function connect() {
    try {
      const port = resolveSocketPort()
      const hostname = window.location.hostname
      const protocol = window.location.protocol
      const site =
        window.frappe?.boot?.sitename ||
        import.meta.env.VITE_FRAPPE_SITE ||
        hostname
      const url = `${protocol}//${hostname}:${port}/${site}`
      socket = io(url, {
        path: '/socket.io',
        withCredentials: true,
        transports: ['websocket', 'polling'],
      })
      socket.on('storeops_update', payload => {
        const name = resolveName(nameRefOrFn)
        if (!name || !payload) return
        // backend sends doc_name; tolerate name/docname variants too
        const n = payload.doc_name || payload.name || payload.docname
        if (n && n === name) onMatch(payload)
      })
    } catch {
      /* optional */
    }
  }

  connect()

  onUnmounted(() => {
    try {
      socket?.off('storeops_update')
      socket?.disconnect()
    } catch {
      /* ignore */
    }
    socket = null
  })
}
