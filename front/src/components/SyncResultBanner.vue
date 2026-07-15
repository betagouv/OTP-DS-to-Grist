<script setup>
import { computed } from 'vue'
import { DsfrAlert } from '@gouvminint/vue-dsfr'

const props = defineProps({
  status: { type: String, required: true },
  successCount: { type: Number, required: true },
  errorCount: { type: Number, required: true },
  timestamp: { type: String, default: null },
  syncType: { type: String, required: true }
})

const alertType = computed(() => {
  if (props.status === 'success') return 'success'
  if (props.status === 'warning') return 'info'
  return 'error'
})

const title = computed(() => {
  const message = props.status === 'success'
    ? 'Synchronisation terminée avec succès'
    : 'Synchronisation terminée avec erreur(s)'
  const typeLabel = props.syncType === 'auto' ? '(automatique)' : '(déclenchée manuellement)'
  return `${message} ${typeLabel}`
})

const count = computed(() =>
  `${props.successCount} dossiers traités avec succès, ${props.errorCount} en échec`
)

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
    <p>{{ count }}</p>
    <p class="fr-text--sm">{{ date }}</p>
  </DsfrAlert>
</template>
