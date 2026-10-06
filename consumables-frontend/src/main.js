import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { setConfig, frappeRequest } from 'frappe-ui'
import router from './router.js'
import App from './App.vue'
import './index.css'

function getCookieValue(name) {
  const cookies = document.cookie?.split('; ') || []
  for (const cookie of cookies) {
    const [key, ...value] = cookie.split('=')
    if (decodeURIComponent(key) === name) {
      return decodeURIComponent(value.join('='))
    }
  }
  return ''
}

if (!window.csrf_token) {
  window.csrf_token = getCookieValue('csrf_token') || getCookieValue('csrftoken') || ''
}

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
setConfig('resourceFetcher', frappeRequest)
app.use(router)
app.mount('#app')
