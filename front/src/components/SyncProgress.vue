<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

import { DsfrBadge } from '@gouvminint/vue-dsfr'

import { useSyncTask } from '../composables/useSyncTask'

const {
  currentTaskId,
  demarcheNumber,
  demarcheIndex,
  totalDemarches,
  finishCurrentTask,
  recordTaskUpdate,
  restoreTasks
} = useSyncTask()
const emit = defineEmits(['sync-running-changed'])
const task = ref(null)
const socket = ref(null)
const syncCardEl = ref(null)

// « Progression de la démarche n°X — i/n » : position affichée en synchro groupée
const progressTitle = computed(() => {
  if (!demarcheNumber.value) return 'Progression'

  const position = totalDemarches.value > 1 ? ` — ${demarcheIndex.value}/${totalDemarches.value}` : ''

  return `Progression de la démarche n°${demarcheNumber.value}${position}`
})

watch(() => task.value?.status, (status) => {
  if (status === 'running') {
    nextTick(() => syncCardEl.value?.scrollIntoView({ behavior: 'smooth' }))
  }
})

// Page ouverte pendant une synchro : reprend son état complet sur le serveur.
// Demandé une fois le socket connecté, pour ne manquer aucun envoi ; sans
// contexte Grist, rien à reprendre (l'erreur est affichée par le formulaire).
const resumeSync = async () => {
  let context
  try {
    context = await getGristContext()
  } catch {
    return
  }

  socket.value?.emit(
    'sync_state',
    { grist_user_id: context.userId, grist_doc_id: context.docId },
    (syncs) => {
      if (!syncs?.length) return

      restoreTasks(syncs)
      const current = syncs.find(sync => sync.task_id === currentTaskId.value)
      if (!current) return

      task.value = current.task
      emit('sync-running-changed', true)
    }
  )
}

onMounted(() => {
  socket.value = io()
  socket.value.on('connect', resumeSync)
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
    v-if="task"
    ref="syncCardEl"
    class="fr-card fr-card--light-grey fr-card--no-border fr-mb-4w"
  >
    <div class="fr-card__body">
      <div class="fr-card__content fr-mb-3w">
        <p class="fr-text--sm fr-mb-1w">
          {{ progressTitle }}
        </p>
        <div class="progress-wrapper">
          <div class="progress-track">
            <div
              class="progress-bar"
              :style="{ width: Math.round(task.progress) + '%' }"
            />
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
