<script setup>
import { ref, computed, onMounted } from 'vue'

import { DsfrButton, DsfrButtonGroup } from '@gouvminint/vue-dsfr';

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'

const gristError = ref(null)
const dnError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)

const canSave = computed(() => gristError.value === '' && dnError.value === '')
const nbDemarches = [{}]

const existingConfig = ref(null)
const otpConfigId = ref(null)

const loadConfig = async () => {
  try {
    const context = await getGristContext()
    const response = await fetch(`/api/config${context.params}`)
    const data = await response.json()
    const config = data.configs?.[0] || null
    existingConfig.value = config
    otpConfigId.value = config?.otp_config_id || null
  } catch (e) {
    console.error('Erreur lors du chargement de la configuration :', e)
  }
}

onMounted(loadConfig)

const handleSaveButtonClick = async () => {
  if (!canSave.value) return

  const config = {
    ds_api_token: dnSectionRefs.value[0].getData().token,
    demarche_number: dnSectionRefs.value[0].getData().demarche_number,
    grist_base_url: gristSectionRef.value.getData().baseUrl,
    grist_doc_id: gristSectionRef.value.getData().docId,
    grist_user_id: gristSectionRef.value.getData().userId,
    grist_api_key: gristSectionRef.value.getData().token // TODO update test
  }

  if (otpConfigId.value) {
    config.otp_config_id = otpConfigId.value
  }

  const response = await fetch('/api/config', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config)
  })

  const result = await response.json()

  if (result.success) {
    await loadConfig()
  } else {
    console.error('Erreur lors de la sauvegarde :', result.message)
  }
}

</script>

<template>
    <GristFormSection
      @error-update="gristError = $event"
      :existing-config="existingConfig"
      ref="gristSectionRef"
    />

    <DNFormSection 
      @error-update="dnError = $event"
      :existing-config="existingConfig"
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
