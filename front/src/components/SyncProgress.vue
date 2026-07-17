<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

import { DsfrBadge } from '@gouvminint/vue-dsfr'

import { useDemarcheContext } from '../composables/useDemarcheContext'
import { useNotification } from '../composables/useNotification'

const { totalDemarches, demarcheIndex } = useDemarcheContext()
const emit = defineEmits(['sync-running-changed', 'sync-started', 'sync-finished'])
const { notify } = useNotification()
const task = ref(null)
const socket = ref(null)
const syncCardEl = ref(null)

watch(() => task.value?.status, (status) => {
  if (status === 'running') {
    nextTick(() => syncCardEl.value?.scrollIntoView({ behavior: 'smooth' }))
  }
})

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
      emit('sync-started')
      emit('sync-running-changed', true)
    } else if (data.task.status === 'completed' || data.task.status === 'error') {
      emit('sync-running-changed', false)
      emit('sync-finished', {
        status: data.task.status,
        success_count: data.task.result?.success_count ?? counts.value?.success ?? 0,
        error_count: data.task.result?.error_count ?? counts.value?.error ?? 0,
        timestamp: data.task.end_time
          ? new Date(data.task.end_time * 1000).toISOString()
          : new Date().toISOString(),
        sync_reason: data.task.sync_reason,
        message: data.task.message
      })

      if (data.task.status === 'error') {
        const errorCount = counts.value?.error || 0
        const msg = errorCount > 0
          ? `Échec de la synchronisation (${errorCount} erreur(s))`
          : 'Échec de la synchronisation'
        notify(msg, 'error')
      } else {
        const successCount = counts.value?.success || 0
        notify(`Synchronisation terminée : ${successCount} dossier(s) synchronisé(s)`, 'success')
      }
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
