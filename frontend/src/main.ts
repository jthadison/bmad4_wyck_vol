import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import App from './App.vue'
import router from './router'

// Import PrimeVue styles
import 'primevue/resources/themes/lara-dark-blue/theme.css'
import 'primeicons/primeicons.css'

// Import Tailwind CSS
import './style.css'

// Validate required environment variables
// VITE_WS_BASE_URL is intentionally optional (empty = auto-detect from page protocol/host)
const requiredEnvVars = ['VITE_API_BASE_URL', 'VITE_APP_VERSION']
const missingVars = requiredEnvVars.filter(
  (varName) => !import.meta.env[varName]
)

if (missingVars.length > 0) {
  console.error(
    `Missing required environment variables: ${missingVars.join(', ')}`
  )
  console.error(
    'Please configure .env.production file with all required variables'
  )
}

// Log app configuration in development
if (import.meta.env.DEV) {
  console.log('App Configuration:', {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    wsBaseUrl: import.meta.env.VITE_WS_BASE_URL,
    version: import.meta.env.VITE_APP_VERSION,
    mode: import.meta.env.MODE,
  })
}

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(PrimeVue, { ripple: true })
app.use(ToastService)
app.use(ConfirmationService)

app.mount('#app')
