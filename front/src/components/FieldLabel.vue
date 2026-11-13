<script setup>
import { DsfrBadge } from '@gouvminint/vue-dsfr'

// Libellé de champ, suivi d'un badge « Vérifié » quand la valeur saisie a été
// confirmée par un test de connexion
defineProps({
  label: { type: String, required: true },
  verified: { type: Boolean, default: false }
})
</script>

<template>
  <p class="fr-mb-0 otp-field-label">
    {{ label }}
    <DsfrBadge
      v-if="verified"
      label="Vérifié"
      type="success"
      small
      data-test-id="verified-badge"
    />
  </p>
</template>

<style scoped>
.otp-field-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
