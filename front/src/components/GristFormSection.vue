<script setup>
import { ref, onMounted, watch } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrInputGroup,
  DsfrInput
} from '@gouvminint/vue-dsfr'

import DsfrInfoIcon from './icons/DsfrInfoIcon.vue'

const props = defineProps({
  existingConfig: { type: Object, default: null }
})

const USE_OTP_URL = window.USE_OTP_URL
const emit = defineEmits(['error-update'])
const context = ref(null)

const userId = ref('')
const docId = ref('')
const baseUrl = ref('')
const inputGristToken = ref('')

const accordionTitleGrist = ref('Configurer Grist')
const activeAccordion = ref(0) // Premier accordéon ouvert par défaut

const gristTokenErrorMessage = ref(null)
const DEFAULT_GRIST_PLACEHOLDER = 'Saisissez votre clé grist'
const gristTokenPlaceholder = ref(DEFAULT_GRIST_PLACEHOLDER)

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

  gristTokenErrorMessage.value = result.success ? '' : result.message

  emit('error-update', gristTokenErrorMessage.value)
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

watch(() => props.existingConfig, (config) => {
  if (config) {
    if (config.otp_config_id && config.grist_base_url)
      baseUrl.value = config.grist_base_url

    if (config.has_grist_key) {
      gristTokenPlaceholder.value = '****************************************'
      emit('error-update', '')
    }
  } else {
    inputGristToken.value = ''
    gristTokenPlaceholder.value = DEFAULT_GRIST_PLACEHOLDER
    baseUrl.value = context.value?.baseUrl || ''
    emit('error-update', null)
  }
})

defineExpose({
  getData: () => ({
    userId: userId.value,
    docId: docId.value,
    baseUrl: baseUrl.value,
    token: inputGristToken.value
  })
})

</script>

<template>
  <div>
    <DsfrAccordionsGroup v-model="activeAccordion">
      <DsfrAccordion
        id="accordion-grist"
        :title="accordionTitleGrist"
      >
        <DsfrInputGroup
          :error-message="gristTokenErrorMessage"
        >
          <h5 class="fr-mt-3w fr-mb-0">Renseignez votre clé API Grist</h5>
          <p class="fr-mb-0">Clé API Grist *</p>
          <DsfrInput
            :error-message="gristTokenErrorMessage"
            data-test-id="grist-token"
            v-model="inputGristToken"
            @change="handleGristInputChange"
            label="Grist token"
            :placeholder="gristTokenPlaceholder"
            type="password"
            required
          />
          <p class="fr-mt-2w">
            <DsfrInfoIcon class="fr-mr-1v"/>
            <a
              :href="`${USE_OTP_URL}#help-grist`"
              class="fr-link fr-text--xs">Où trouver votre clé API Grist ?</a>
          </p>
        </DsfrInputGroup>
      </DsfrAccordion>
    </DsfrAccordionsGroup>
  </div>
</template>
