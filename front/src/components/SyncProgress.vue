<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

import { DsfrBadge } from '@gouvminint/vue-dsfr'

import { useSyncTask } from '../composables/useSyncTask'

const {
  currentTaskId,
  demarcheNumber,
  demarcheIndex,
  totalDemarches,
  finishCurrentTask,
  recordTaskUpdate
} = useSyncTask()
const emit = defineEmits(['sync-running-changed'])
const task = ref(null)
const socket = ref(null)
const syncCardEl = ref(null)

watch(() => task.value?.status, (status) => {
  if (status === 'running') {
    nextTick(() => syncCardEl.value?.scrollIntoView({ behavior: 'smooth' }))
  }
})

onMounted(() => {
  socket.value = io()
  socket.value.on('task_update', (data) => {
    // Toutes les démarches de la série alimentent le tableau ; la barre ne suit que la courante
    recordTaskUpdate(data.task_id, data.task)
    if (data.task_id !== currentTaskId.value) return
    task.value = data.task
    if (data.task.status === 'running') {
      emit('sync-running-changed', true)
    } else if (data.task.status === 'completed' || data.task.status === 'error') {
      // Série : la démarche suivante prend le relais, rien n'est terminé
      if (finishCurrentTask()) return

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
    ref="syncCardEl"
    v-if="task"
    class="fr-card fr-card--light-grey fr-card--no-border fr-mb-4w"
  >
    <div class="fr-card__body">
      <div class="fr-card__content fr-mb-3w">
        <h2 class="fr-card__title">Synchronisation des données</h2>
        <p v-if="demarcheNumber" class="fr-text--bold fr-mb-2w">
          Démarche n°{{ demarcheNumber }}<template v-if="totalDemarches > 1"> — {{ demarcheIndex }}/{{ totalDemarches }}</template>
        </p>
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
