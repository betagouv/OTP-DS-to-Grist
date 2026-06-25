<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import { DsfrBadge } from '@gouvminint/vue-dsfr'

const emit = defineEmits(['sync-running-changed'])

const task = ref(null)
const socket = ref(null)

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
        <h2 class="fr-card__title">Synchronisation</h2>
        <p class="fr-text--bold fr-mb-2w">{{ task.message }}</p>
        <div class="fr-grid-row fr-grid-row--middle fr-mb-1w">
          <div class="fr-col">
            <span class="fr-text--bold">Progression</span>
          </div>
          <div class="fr-col-auto">
            <DsfrBadge :label="`${Math.round(task.progress)}%`" type="info" />
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-bar" :style="{ width: Math.round(task.progress) + '%' }" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
</style>
