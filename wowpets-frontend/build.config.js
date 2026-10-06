import settings from './src/config/settings.js'

export function getBuildBasePath(command) {
	const { FRAPPE_APP_NAME, FOLDER_NAME, BASE_PATH } = settings
	if (command === 'build') {
		return `/assets/${FRAPPE_APP_NAME}/${FOLDER_NAME}/`
	}
	return BASE_PATH.endsWith('/') ? BASE_PATH : `${BASE_PATH}/`
}

export function getBuildOutDir() {
	const { FRAPPE_APP_NAME, FOLDER_NAME } = settings
	return `../${FRAPPE_APP_NAME}/public/${FOLDER_NAME}`
}

export function getDevServerConfig() {
	return settings.DEV_SERVER
}

export function getSettings() {
	return settings
}
