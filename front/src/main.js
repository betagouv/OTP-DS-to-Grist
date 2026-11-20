import { createApp } from 'vue'
import '@gouvfr/dsfr/dist/dsfr.min.css'
// Classes utilitaires du DSFR, dont les icônes fr-icon-* (aussi utilisées par base.html)
import '@gouvfr/dsfr/dist/utility/utility.min.css'
import '@gouvminint/vue-dsfr/styles'
import VueDsfr from '@gouvminint/vue-dsfr'
import App from './App.vue'

createApp(App)
  .use(VueDsfr)
  .mount('#app')
