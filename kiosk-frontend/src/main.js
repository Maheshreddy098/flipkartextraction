/**
 * Main Application Entry Point
 * Sets up Vue app with all necessary plugins and configurations
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router.js'

// Import frappe-ui API utilities (not UI components to avoid build issues)
import { setConfig, frappeRequest } from 'frappe-ui'

// Import main app component
import App from './App.vue'

// Import global styles
import './index.css'

// Create Vue app
const app = createApp(App)

// Create Pinia store
const pinia = createPinia()
app.use(pinia)

// Configure frappe-ui resource fetcher (CRITICAL - this handles all CSRF automatically!)
setConfig('resourceFetcher', frappeRequest)

// Use router
app.use(router)

// Global error handler
app.config.errorHandler = (error, instance, info) => {
  console.error('Global error:', error)
  console.error('Component instance:', instance)
  console.error('Error info:', info)
}

// Mount app
app.mount('#app')

// Export for testing
export { app, router, pinia }