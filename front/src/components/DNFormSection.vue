<script setup>
import { ref } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrInputGroup
} from '@gouvminint/vue-dsfr'

const emit = defineEmits(['error-update'])

// TODO le mettre dans le parent
const activeAccordion = ref(0) // Premier accordéon ouvert par défaut
const accordionTitleDN = ref('Configurer votre démarche')

const inputDNToken = ref('')
const inputDNNumber = ref('')
const dnErrorMessage = ref(null)
const dnApiUrl = 'https://www.demarches-simplifiees.fr/api/v2/graphql'

const handleDNInputsChange = async () => {
  dnErrorMessage.value = null

  const response = await fetch('/api/test-connection', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      type: 'demarches',
      api_token: inputDNToken.value,
      api_url: dnApiUrl,
      demarche_number: inputDNNumber.value
    })
  })
  const result = await response.json()

  dnErrorMessage.value = result.success ? '' : result.message

  emit('error-update', dnErrorMessage.value)
}

defineExpose({
  getData: () => ({
    token: inputDNToken.value,
    demarche_number: inputDNNumber.value,
  })
})
</script>

<template>
  <h3 class="fr-mb-3w">2. Démarche numérique</h3>

  <DsfrAccordionsGroup v-model="activeAccordion">
    <DsfrAccordion
      id="accordion-dn"
      :title="accordionTitleDN"
    >
      <DsfrInputGroup
          :error-message="dnErrorMessage"
      >
        <DsfrInput
          :error-message="dnErrorMessage"
          data-test-id="dn-token"
          v-model="inputDNToken"
          @change="handleDNInputsChange"
          label="DN token"
          placeholder="Saisissez votre clé DN"
          required
        />

        <DsfrInput
          data-test-id="dn-number"
          v-model="inputDNNumber"
          @change="handleDNInputsChange"
          label="DN number"
          placeholder="Saisissez votre numéro DN"
          required
        />
      </DsfrInputGroup>
    </DsfrAccordion>
  </DsfrAccordionsGroup>
</template>
