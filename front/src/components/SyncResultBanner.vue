<script setup>
import { computed } from 'vue'
import { DsfrAlert } from '@gouvminint/vue-dsfr'

const props = defineProps({
  status: { type: String, required: true },
  successCount: { type: Number, required: true },
  errorCount: { type: Number, required: true },
  timestamp: { type: String, default: null },
  syncType: { type: String, required: true },
  syncReason: { type: String, default: null },
})

const isUpToDate = computed(() =>
  props.syncReason === 'already_up_to_date'
  || (!props.syncReason && props.status === 'success' && props.successCount === 0 && props.errorCount === 0)
)

const alertType = computed(() => {
  if (isUpToDate.value) return 'info'
  if (props.status === 'success') return 'success'
  if (props.status === 'warning') return 'info'
  return 'error'
})

const title = computed(() => {
  if (isUpToDate.value) return 'Grist déjà à jour'
  const message = props.status === 'success'
    ? 'Synchronisation terminée avec succès'
    : 'Synchronisation terminée avec erreur(s)'
  const typeLabel = props.syncType === 'auto' ? '(automatique)' : '(déclenchée manuellement)'
  return `${message} ${typeLabel}`
})

const description = computed(() => {
  if (isUpToDate.value) return 'Aucun dossier nouveau ou modifié depuis la dernière synchronisation.'
  return `${props.successCount} dossiers traités avec succès, ${props.errorCount} en échec`
})

const date = computed(() =>
  props.timestamp
    ? new Date(props.timestamp).toLocaleString('fr-FR')
    : new Date().toLocaleString('fr-FR')
)
</script>

<template>
  <DsfrAlert
    :type="alertType"
    :title="title"
  >
    <p>{{ description }}</p>
    <p class="fr-text--sm">{{ date }}</p>
  </DsfrAlert>
</template>
