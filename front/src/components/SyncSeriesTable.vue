<script setup>
import { DsfrBadge, DsfrButton } from '@gouvminint/vue-dsfr'

import { useSyncTask } from '../composables/useSyncTask'
import { useNotification } from '../composables/useNotification'

const { seriesTasks } = useSyncTask()
const { notify } = useNotification()

const formatDemarche = (task) => (task.demarcheTitle
  ? `N°${task.demarcheNumber} — ${task.demarcheTitle}`
  : `N°${task.demarcheNumber}`
)

const formatMessage = (task) => {
  if (task.status !== 'completed') return task.message
  if (task.syncReason === 'already_up_to_date') return 'Grist déjà à jour'

  return `${task.result?.success_count ?? 0} dossiers mis à jour/ajoutés`
}

const statusBadge = (task) => {
  const errorCount = task.result?.error_count ?? 0
  if (errorCount > 0) return { label: `${errorCount} erreur(s)`, type: 'error' }
  if (task.status === 'error') return { label: 'Erreur', type: 'error' }
  if (task.status === 'completed') return { label: 'Terminée', type: 'success' }
  if (task.status === 'running') return { label: 'En cours', type: 'info' }

  // « standard » : badge gris de base (sans type, DsfrBadge retombe sur « info », bleu)
  return { label: 'En attente', type: 'standard' }
}

const copyLogs = (task) => {
  const text = task.logs.map(log => log.message).join('\n')
  navigator.clipboard
    .writeText(text)
    .then(() => notify('Logs copiés dans le presse-papiers', 'success'))
    .catch(() => notify('Erreur lors de la copie des logs', 'error'))
}
</script>

<template>
  <div v-if="seriesTasks.length" class="fr-table fr-mb-4w">
    <table data-test-id="sync-series-table">
      <!-- Largeurs fixes : le contenu, qui change à chaque événement, ne redimensionne plus les colonnes -->
      <colgroup>
        <col class="col-demarche">
        <col>
        <col class="col-status">
        <col class="col-logs">
      </colgroup>
      <thead>
        <tr>
          <th colspan="4">Détails des synchronisations</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in seriesTasks" :key="task.taskId">
          <td class="ellipsis" :title="formatDemarche(task)">{{ formatDemarche(task) }}</td>
          <td class="ellipsis" :title="formatMessage(task)">{{ formatMessage(task) }}</td>
          <td class="nowrap">
            <DsfrBadge
              :label="statusBadge(task).label"
              :type="statusBadge(task).type"
              small
            />
          </td>
          <td class="nowrap">
            <DsfrButton
              label="Copier les logs"
              tertiary
              no-outline
              size="sm"
              :disabled="!task.logs.length"
              @click="copyLogs(task)"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* Le DSFR passe le tableau en display: block, ce qui ignore table-layout */
table {
  display: table;
  table-layout: fixed;
  width: 100%;
}

.col-demarche {
  width: 30%;
}

.col-status {
  width: 9rem;
}

.col-logs {
  width: 11rem;
}

.nowrap {
  white-space: nowrap;
}

.ellipsis {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
