/**
 * Build Configuration Helper for StoreOps
 */
import storeopsSettings from './src/config/storeops.settings.js'

export function getBuildBasePath(command) {
  const { FRAPPE_APP_NAME, FOLDER_NAME, BASE_PATH } = storeopsSettings

  if (command === 'build') {
    return `/assets/${FRAPPE_APP_NAME}/${FOLDER_NAME}/`
  } else {
    return BASE_PATH.endsWith('/') ? BASE_PATH : `${BASE_PATH}/`
  }
}

export function getBuildOutDir() {
  const { FRAPPE_APP_NAME, FOLDER_NAME } = storeopsSettings
  return `../${FRAPPE_APP_NAME}/public/${FOLDER_NAME}`
}

export function getDevServerConfig() {
  return storeopsSettings.DEV_SERVER
}

export function getStoreOpsSettings() {
  return storeopsSettings
}

