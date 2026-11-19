<script setup>
import { ref } from 'vue'
import OTPForm from './components/OTPForm.vue'
import SyncProgress from './components/SyncProgress.vue'
import SyncSeriesTable from './components/SyncSeriesTable.vue'
import { useSyncHistory } from './composables/useSyncHistory'
import NotificationToast from './components/NotificationToast.vue'

const syncRunning = ref(false)
const syncHistory = ref([])
// Noms des démarches par numéro, reçus du test de connexion de chaque volet
const demarcheTitles = ref({})

const { fetchHistory } = useSyncHistory()

const handleConfigLoaded = () => {
  // Sans historique lisible, le tableau ne s'affiche simplement pas
  fetchHistory()
    .then(rows => { syncHistory.value = rows })
    .catch(() => {})
}

const handleTitleLoaded = (demarcheNumber, title) => {
  demarcheTitles.value = { ...demarcheTitles.value, [demarcheNumber]: title }
}
</script>

<template>
  <NotificationToast />
  <header>
    <div class="wrapper">
      <!-- Tableau et barre accolés : la marge basse est portée par le groupe -->
      <div class="sync-status">
        <SyncSeriesTable
          :history="syncHistory"
          :titles="demarcheTitles"
        />
        <SyncProgress @sync-running-changed="syncRunning = $event" />
      </div>

      <OTPForm
        :sync-running="syncRunning"
        @config-loaded="handleConfigLoaded"
        @title-loaded="handleTitleLoaded"
      />
    </div>
  </header>
</template>

<style>
/* Les v-if non rendus ne laissent que des commentaires, ignorés par :empty */
.sync-status:not(:empty) {
  margin-bottom: 2rem;
}

/* Le menu des DsfrMultiselect est positionné en absolu dans le contenu des
   accordéons DSFR. Or .fr-collapse--expanded a overflow-y:auto qui le rogne.
   On ne cible que le panneau d'accordéon (.fr-accordion > .fr-collapse), pas
   les menus, et uniquement à l'état stable (hors .fr-collapsing) pour ne pas
   dégrader l'animation d'ouverture/fermeture. */
#app .fr-accordion > .fr-collapse--expanded:not(.fr-collapsing) {
  overflow: visible;
}
</style>
