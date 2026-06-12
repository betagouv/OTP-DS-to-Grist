import { createApp } from 'vue'
import '@gouvfr/dsfr/dist/dsfr.min.css'
import '@gouvminint/vue-dsfr/styles'
import VueDsfr from '@gouvminint/vue-dsfr'
import App from './App.vue'

createApp(App)
  .use(VueDsfr)
  .mount('#app')
