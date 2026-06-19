<script setup>
import { ref, onMounted } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrInputGroup
} from '@gouvminint/vue-dsfr'

const context = ref(null)

const userId = ref('')
const docId = ref('')
const baseUrl = ref('')
const inputGristToken = ref('')

const accordionTitleGrist = ref('Configurer Grist')
const activeAccordion = ref(0) // Premier accordéon ouvert par défaut

const gristTokenErrorMessage = ref(null)

const handleGristInputChange = async () => {
  gristTokenErrorMessage.value = null

  const response = await fetch('/api/test-connection', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      type: 'grist',
      base_url: baseUrl.value,
      api_key: inputGristToken.value,
      doc_id: docId.value
    })
  })
  const result = await response.json()

  if (result.success) {
    gristTokenErrorMessage.value = null
    return
  }

  gristTokenErrorMessage.value = result.message
}

onMounted(async () => {
  try {
    context.value = await getGristContext()

    userId.value = context.value.userId
    docId.value = context.value.docId
    baseUrl.value = context.value.baseUrl
  } catch (e) {
    alert(e.message)
  }
})

</script>

<template>
  <h3 class="fr-mb-3w">1. Grist</h3>

  <DsfrAccordionsGroup v-model="activeAccordion">
    <DsfrAccordion
      id="accordion-grist"
      :title="accordionTitleGrist"
    >
      <DsfrInputGroup
        :error-message="gristTokenErrorMessage"
        data-test-id="grist-token"
        v-model="inputGristToken"
        @change="handleGristInputChange"
        label="Grist token"
        placeholder="Saisissez votre clé grist"
        required
      />
    </DsfrAccordion>
  </DsfrAccordionsGroup>
</template>
