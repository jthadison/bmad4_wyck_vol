import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import App from './App.vue'
import router from './router'

// Import PrimeVue styles
import 'primevue/resources/themes/lara-dark-blue/theme.css'
import 'primeicons/primeicons.css'

// Import Tailwind CSS
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(PrimeVue, { ripple: true })

app.mount('#app')
