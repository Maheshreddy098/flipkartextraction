import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { setConfig, frappeRequest } from 'frappe-ui'
import router from './router.js'
import App from './App.vue'
import './index.css'

const app = createApp(App)
app.use(createPinia())

setConfig('resourceFetcher', frappeRequest)

app.use(router)
app.mount('#app')
