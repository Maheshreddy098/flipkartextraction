import STOREOPS_SETTINGS from './storeops.settings.js'

const SITE_ORIGIN = (typeof window !== 'undefined' && window.location?.origin)
  ? window.location.origin
  : (STOREOPS_SETTINGS.EXPLICIT_SITE_URL || 'http://localhost:8000')

const FRAPPE_API_URL = (function computeApiUrl() {
  if (STOREOPS_SETTINGS.EXPLICIT_API_URL) return STOREOPS_SETTINGS.EXPLICIT_API_URL.replace(/\/$/, '')
  if (typeof window !== 'undefined') {
    const onDevPort = String(window.location.port || '') === String(STOREOPS_SETTINGS.DEV_SERVER.PORT)
    if (onDevPort && STOREOPS_SETTINGS.DEV_BACKEND_URL) {
      return STOREOPS_SETTINGS.DEV_BACKEND_URL.replace(/\/$/, '') + '/api'
    }
  }
  return '/api'
})()

const WS_URL = (function computeWsUrl() {
  if (STOREOPS_SETTINGS.EXPLICIT_WS_URL) return STOREOPS_SETTINGS.EXPLICIT_WS_URL
  try {
    const site = STOREOPS_SETTINGS.EXPLICIT_SITE_URL || SITE_ORIGIN
    const url = new URL(site)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return url.origin
  } catch {
    if (typeof window !== 'undefined' && window.location) {
      return (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host
    }
    return 'ws://localhost:8000'
  }
})()

export const APP_CONFIG = {
  APP_NAME: 'KFL StoreOps',
  APP_VERSION: '1.0.0',

  IS_DEVELOPMENT: typeof window !== 'undefined'
    ? !window.location.pathname.startsWith(STOREOPS_SETTINGS.BASE_PATH)
    : false,
  IS_PRODUCTION: typeof window !== 'undefined'
    ? window.location.pathname.startsWith(STOREOPS_SETTINGS.BASE_PATH)
    : true,

  BASE_PATH: STOREOPS_SETTINGS.BASE_PATH.replace(/\/$/, ''),
  FRAPPE_API_URL,
  FRAPPE_SITE_URL: STOREOPS_SETTINGS.EXPLICIT_SITE_URL || SITE_ORIGIN,
  WS_URL,

  USE_REAL_AUTH: true,

  SESSION_TIMEOUT: 30 * 60 * 1000,
  TOKEN_REFRESH_INTERVAL: 5 * 60 * 1000,
  MAX_SESSION_DURATION: 8 * 60 * 60 * 1000,

  API_TIMEOUT: 10000,
  API_RETRY_ATTEMPTS: 3,
  API_RETRY_DELAY: 1000,

  FEATURES: {
    REAL_TIME_LOGGING: false,
    OFFLINE_SUPPORT: true,
    PUSH_NOTIFICATIONS: false,
    ADVANCED_ANALYTICS: true,
    DEBUG_MODE: import.meta.env.DEV,
    CONSOLE_LOGGING: import.meta.env.DEV,
  },

  ERROR_MESSAGES: {
    NETWORK_ERROR: 'Network error. Please check your connection.',
    AUTHENTICATION_FAILED: 'Authentication failed. Please check your credentials.',
    PLANT_ACCESS_DENIED: 'Access denied for this plant.',
    SESSION_EXPIRED: 'Your session has expired. Please login again.',
    INVALID_CREDENTIALS: 'Invalid email or password.',
    PERMISSION_DENIED: 'You do not have permission to access this resource.',
    SERVER_ERROR: 'Server error. Please try again later.',
    VALIDATION_ERROR: 'Please check your input and try again.',
  },

  SUCCESS_MESSAGES: {
    LOGIN_SUCCESS: 'Login successful!',
    LOGOUT_SUCCESS: 'Logged out successfully!',
    DATA_SAVED: 'Data saved successfully!',
    OPERATION_COMPLETED: 'Operation completed successfully!',
  },

  VALIDATION: {
    EMAIL_REGEX: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    PASSWORD_MIN_LENGTH: 8,
    PASSWORD_MAX_LENGTH: 128,
    PLANT_ID_REGEX: /^[a-z0-9-_]+$/,
    USERNAME_REGEX: /^[a-zA-Z0-9._-]+$/,
  },

  ROUTES: {
    LOGIN: `${STOREOPS_SETTINGS.BASE_PATH.replace(/\/$/, '')}/login`,
    DASHBOARD: `${STOREOPS_SETTINGS.BASE_PATH.replace(/\/$/, '')}/dashboard`,
    NOT_FOUND: `${STOREOPS_SETTINGS.BASE_PATH.replace(/\/$/, '')}/404`,
    UNAUTHORIZED: `${STOREOPS_SETTINGS.BASE_PATH.replace(/\/$/, '')}/unauthorized`,
  },
}

export default APP_CONFIG
