<script setup>
import { ref, computed } from 'vue'

import { DsfrButton, DsfrButtonGroup } from '@gouvminint/vue-dsfr';

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'

const gristError = ref(null)
const dnError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)

const canSave = computed(() => gristError.value === '' && dnError.value === '')
const nbDemarches = [{}]

const handleSaveButtonClick = async () => {
  if (!canSave.value) return

  const config = {
    ds_api_token: dnSectionRefs.value[0].getData().token,
    demarche_number: dnSectionRefs.value[0].getData().demarche_number,
    grist_base_url: gristSectionRef.value.getData().baseUrl,
    grist_doc_id: gristSectionRef.value.getData().docId,
    grist_user_id: gristSectionRef.value.getData().userId,
  }

  const response = await fetch('/api/config', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config)
  })

  const result = await response.json()
  console.log(result)
}

</script>

<template>
    <GristFormSection
      @error-update="gristError = $event"
      ref="gristSectionRef"
    />

    <DNFormSection 
      @error-update="dnError = $event"
      v-for="(_, index) in nbDemarches"
      :key="index"
      :ref="(dnComponent) => dnComponent && (dnSectionRefs[index] = dnComponent)"
    />

    <DsfrButtonGroup>
      <DsfrButton
        label="Sauvegarder"
        data-test-id="submit-form-button"
        primary
        :disabled="!canSave"
        @click="handleSaveButtonClick"
      />
    </ DsfrButtonGroup>
</template>
