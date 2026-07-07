<script setup>
defineProps({
  count: { type: Number, required: true },
  label: { type: String, required: true },
  color: { type: String, default: 'green' }
})
</script>

<template>
  <div class="fr-card fr-card--grey">
    <div class="fr-card__body">
      <div class="fr-card__content" :class="`border-${color}`">
        <p class="fr-text--bold fr-text--lg fr-text--center fr-mb-2v">
          {{ count }}
        </p>
        <p class="fr-mb-0 fr-text--center fr-text--sm">
          {{ label }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.border-green {
  border-bottom: 4px solid var(--text-default-success);
}
.border-red {
  border-bottom: 4px solid var(--text-default-error);
}
</style>
