<script setup>
import { ref, onMounted, watch } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrInputGroup,
  DsfrInput
} from '@gouvminint/vue-dsfr'

import DsfrInfoIcon from './icons/DsfrInfoIcon.vue'
import { api } from '../utils/InternalApi'
import { useNotification } from '../composables/useNotification'

const props = defineProps({
  existingConfig: { type: Object, default: null }
})

const HELP_LINKS = window.HELP_LINKS
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
const { notify } = useNotification()

const handleGristInputChange = async () => {
  gristTokenErrorMessage.value = null

  try {
    const result = await api.testConnection({
      type: 'grist',
      base_url: baseUrl.value,
      api_key: inputGristToken.value,
      doc_id: docId.value
    })

    gristTokenErrorMessage.value = result.success ? '' : result.message
    emit('error-update', gristTokenErrorMessage.value)
  } catch (e) {
    notify('Erreur lors du test de connexion Grist', 'error')
  }
}

onMounted(async () => {
  try {
    context.value = await getGristContext()

    userId.value = context.value.userId
    docId.value = context.value.docId
    baseUrl.value = context.value.baseUrl
  } catch (e) {
    notify(e.message, 'error')
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
              :href="HELP_LINKS.grist_api_key"
              target="_blank"
              rel="noopener noreferrer"
              class="fr-link fr-text--xs">Où trouver votre clé API Grist ?</a>
          </p>
        </DsfrInputGroup>
      </DsfrAccordion>
    </DsfrAccordionsGroup>
  </div>
</template>
