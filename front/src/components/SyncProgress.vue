<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

import { DsfrBadge } from '@gouvminint/vue-dsfr'

import SyncStatsCard from './SyncStatsCard.vue'
import { useDemarcheContext } from '../composables/useDemarcheContext'

const { totalDemarches, demarcheIndex } = useDemarcheContext()
const emit = defineEmits(['sync-running-changed'])
const task = ref(null)
const socket = ref(null)

const counts = computed(() => {
  if (!task.value?.logs) return null

  let syncStatus = { success: 0, error: 0, total: 0 }
  for (const log of task.value.logs) {
    syncStatus = parseLogMessage(log.message, syncStatus)
  }

  return syncStatus
})

onMounted(() => {
  socket.value = io()
  socket.value.on('task_update', (data) => {
    task.value = data.task
    if (data.task.status === 'running') {
      emit('sync-running-changed', true)
    } else if (data.task.status === 'completed' || data.task.status === 'error') {
      emit('sync-running-changed', false)
    }
  })
})

onUnmounted(() => {
  if (socket.value) {
    socket.value.disconnect()
    socket.value = null
  }
})
</script>

<template>
  <div
    v-if="task"
    class="fr-card fr-card--light-grey fr-card--no-border fr-mb-4w"
  >
    <div class="fr-card__body">
      <div class="fr-card__content">
        <h2 class="fr-card__title">Synchronisation des données</h2>
        <p v-if="totalDemarches > 0" class="fr-text--bold fr-mb-2w">{{ demarcheIndex }}/{{ totalDemarches }} démarche(s) synchronisée(s)</p>
        <p class="fr-mb-2w">{{ task.message }}</p>
        <p class="fr-text--bold fr-mb-1w">Progression</p>
        <div class="progress-wrapper">
          <div class="progress-track">
            <div class="progress-bar" :style="{ width: Math.round(task.progress) + '%' }" />
          </div>
          <DsfrBadge
            :label="`${Math.round(task.progress)}%`"
            type="info"
            class="progress-badge"
            :style="{ left: Math.round(task.progress) + '%' }"
            no-icon
          />
        </div>
        <div v-if="counts && (counts.success > 0 || counts.error > 0)" class="fr-grid-row fr-grid-row--gutters fr-mt-2w">
          <div v-if="counts.success > 0" class="fr-col-6">
            <SyncStatsCard :count="counts.success" label="Dossiers synchronisés" color="green" />
          </div>
          <div v-if="counts.error > 0" class="fr-col-6">
            <SyncStatsCard :count="counts.error" label="Échecs" color="red" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-wrapper {
  position: relative;
}

.progress-track {
  height: 8px;
  background: var(--border-default-grey);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--background-action-high-blue-france);
  transition: width 0.3s ease;
}

.progress-badge {
  position: absolute;
  top: 14px;
  transform: translateX(-50%);
  transition: left 0.3s ease;
}
</style>
