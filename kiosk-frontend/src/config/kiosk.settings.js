// Editable kiosk settings per machine/team.
// Change these values and rebuild; do not commit secrets.
export default {
  // ========================================
  // BUILD CONFIGURATION
  // ========================================
  // The Frappe app name (must match your app's directory name)
  FRAPPE_APP_NAME: 'khanal_tech_integrations',
  
  // Kiosk folder name within the app's public directory
  KIOSK_FOLDER_NAME: 'kiosk',
  
  // Dev server settings
  DEV_SERVER: { 
    HOST: 'dev.localhost', 
    PORT: 3000
  },

  // ========================================
  // RUNTIME CONFIGURATION
  // ========================================
  // Base path where kiosk is served from your Frappe site (no trailing slash)
  // This is used by Vue Router at runtime
  BASE_PATH: '/kiosk',

  // If running Vite dev server locally, set your dev backend (Frappe site) URL
  // Example: 'http://dev.localhost:8001'
  DEV_BACKEND_URL: 'http://kfltest.localhost:8003',

  // Optional explicit overrides (leave blank to auto-detect)
  // If set, takes precedence over auto detection
  EXPLICIT_API_URL: '',        // e.g. 'http://my-site.local:8000/api'
  EXPLICIT_SITE_URL: '',       // e.g. 'http://my-site.local:8000'
  EXPLICIT_WS_URL: ''          // e.g. 'ws://my-site.local:8000'
}
