// StoreOps build & runtime settings.
// Change these values and rebuild; do not commit secrets.
export default {
  // ========================================
  // BUILD CONFIGURATION
  // ========================================
  FRAPPE_APP_NAME: 'khanal_tech_integrations',
  FOLDER_NAME: 'storeops',

  // Dev server settings
  DEV_SERVER: {
    HOST: 'dev.localhost',
    PORT: 3001,
  },

  // ========================================
  // RUNTIME CONFIGURATION
  // ========================================
  BASE_PATH: '/storeops',
  DEV_BACKEND_URL: 'http://dev.localhost:8000',

  // Optional explicit overrides (leave blank to auto-detect)
  EXPLICIT_API_URL: '',
  EXPLICIT_SITE_URL: '',
  EXPLICIT_WS_URL: '',
}
