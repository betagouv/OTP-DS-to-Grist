<script setup>
import { DsfrBadge } from '@gouvminint/vue-dsfr'

// Contenu du libellé d'un champ (slot `label` de DsfrInput), suivi d'un badge
// « Vérifié » quand la valeur saisie a été confirmée par un test de connexion
defineProps({
  label: { type: String, required: true },
  verified: { type: Boolean, default: false }
})
</script>

<template>
  <span class="otp-field-label">
    {{ label }}
    <DsfrBadge
      v-if="verified"
      label="Vérifié"
      type="success"
      small
      data-test-id="verified-badge"
    />
  </span>
</template>

<style scoped>
.otp-field-label {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
