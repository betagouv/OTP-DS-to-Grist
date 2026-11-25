<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

import { DsfrBadge } from '@gouvminint/vue-dsfr'

import { useSyncTask } from '../composables/useSyncTask'

const {
  currentTaskId,
  finishCurrentTask,
  recordTaskUpdate,
  restoreTasks
} = useSyncTask()
const emit = defineEmits(['sync-running-changed'])
const task = ref(null)
const socket = ref(null)
const percent = computed(() => Math.round(task.value?.progress ?? 0))

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
  <!-- Barre seule, collée sous le tableau des synchros : ni carte ni titre -->
  <div
    v-if="task"
    class="sync-progress"
  >
    <div class="progress-track">
      <div
        class="progress-bar"
        :style="{ width: `${percent}%` }"
      />
    </div>
    <!-- Décalé d'autant que la progression : reste dans la largeur de la barre à 0 % comme à 100 % -->
    <DsfrBadge
      :label="`${percent}%`"
      type="info"
      class="progress-badge"
      :style="{
        left: `${percent}%`,
        transform: `translateX(-${percent}%)`
      }"
      no-icon
    />
  </div>
</template>

<style scoped>
.sync-progress {
  position: relative;
  /* Place du badge, positionné en absolu sous la barre (top + hauteur du badge - barre) */
  padding-bottom: 1.875rem;
}

.progress-track {
  height: 4px;
  background: var(--border-default-grey);
  /* Coins du haut droits : la barre prolonge le bas du tableau */
  border-radius: 0 0 2px 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--background-action-high-blue-france);
  transition: width 0.3s ease;
}

.progress-badge {
  position: absolute;
  top: 10px;
  transition: left 0.3s ease, transform 0.3s ease;
}
</style>
