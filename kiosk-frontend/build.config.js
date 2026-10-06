/**
 * Build Configuration Helper
 * This file reads kiosk.settings.js and provides build-time configuration
 */
import kioskSettings from './src/config/kiosk.settings.js'

/**
 * Get the base path for the build
 * @param {string} command - 'build' or 'serve'
 * @returns {string} Base path for assets
 */
export function getBuildBasePath(command) {
  const { FRAPPE_APP_NAME, KIOSK_FOLDER_NAME, BASE_PATH } = kioskSettings
  
  if (command === 'build') {
    // Production: Assets are served from Frappe's public directory
    return `/assets/${FRAPPE_APP_NAME}/${KIOSK_FOLDER_NAME}/`
  } else {
    // Development: Assets are served from Vite dev server
    return BASE_PATH.endsWith('/') ? BASE_PATH : `${BASE_PATH}/`
  }
}

/**
 * Get the output directory for the build
 * @returns {string} Absolute path to output directory
 */
export function getBuildOutDir() {
  const { FRAPPE_APP_NAME, KIOSK_FOLDER_NAME } = kioskSettings
  return `../${FRAPPE_APP_NAME}/public/${KIOSK_FOLDER_NAME}`
}

/**
 * Get the dev server configuration
 * @returns {object} Dev server config
 */
export function getDevServerConfig() {
  return kioskSettings.DEV_SERVER
}

/**
 * Get all kiosk settings
 * @returns {object} All settings
 */
export function getKioskSettings() {
  return kioskSettings
}

