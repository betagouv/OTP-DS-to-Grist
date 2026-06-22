<script setup>
import { ref, computed } from 'vue'

import { DsfrButton, DsfrButtonGroup } from '@gouvminint/vue-dsfr';

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'

const gristError = ref(null)
const dnError = ref(null)

const canSave = computed(() => gristError.value === '' && dnError.value === '')
</script>

<template>
    <GristFormSection @error-update="gristError = $event"/>
    <DNFormSection @error-update="dnError = $event"/>
    <DsfrButtonGroup>
      <DsfrButton
        label="Sauvegarder"
        data-test-id="submit-form-button"
        primary
        :disabled="!canSave"
      />
    </ DsfrButtonGroup>
</template>
