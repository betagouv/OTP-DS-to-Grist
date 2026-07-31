<script setup>
import { ref, watch, computed } from 'vue'

import {
  DsfrAccordion,
  DsfrButton,
  DsfrButtonGroup,
  DsfrInputGroup,
  DsfrInput
} from '@gouvminint/vue-dsfr'

import DsfrInfoIcon from './icons/DsfrInfoIcon.vue'
import { api } from '../utils/InternalApi'
import OtpAlert from './OtpAlert.vue'
import { debounce } from '../utils/debounce'

const props = defineProps({
  existingConfig: { type: Object, default: null },
  gristError: { type: String, default: null },
  canDelete: { type: Boolean, default: false },
  canSync: { type: Boolean, default: false },
  error: { type: String, default: null },
  index: { type: Number, required: true }
})

const HELP_LINKS = window.HELP_LINKS
const DEFAULT_DN_TITLE = 'Configurer votre démarche'
const ERROR_DN_TITLE = 'Échec'

const formatTitle = (number, title) => (number ? `N°${number} — ${title}` : title)

const validateDSConnection = async () => {
  if (!inputDNNumber.value) return
  if (!inputDNToken.value && !props.existingConfig?.otp_config_id) return

  const body = {
    type: 'demarches',
    api_url: dnApiUrl,
    demarche_number: inputDNNumber.value,
    ...(inputDNToken.value
      ? { api_token: inputDNToken.value }
      : { otp_config_id: props.existingConfig.otp_config_id })
  }

  accordionTitleDN.value = '...'

  try {
    const result = await api.testConnection(body)
    dnErrorMessage.value = result.success ? '' : result.message
    accordionTitleDN.value = result.success
      ? formatTitle(inputDNNumber.value, result.title || DEFAULT_DN_TITLE)
      : ERROR_DN_TITLE
  } catch (e) {
    dnErrorMessage.value = 'Erreur lors du test de connexion'
    accordionTitleDN.value = ERROR_DN_TITLE
  }

  emit('error-update', dnErrorMessage.value === '' ? '' : dnErrorMessage.value)
}

const emit = defineEmits(['error-update', 'save', 'delete', 'sync', 'clear-error'])

const accordionTitleDN = ref(DEFAULT_DN_TITLE)
const inputDNToken = ref('')
const inputDNNumber = ref('')
const dnErrorMessage = ref(null)
const DEFAULT_DN_PLACEHOLDER = 'Saisissez votre clé Démarche Numérique'
const dnTokenPlaceholder = ref(DEFAULT_DN_PLACEHOLDER)
const dnApiUrl = 'https://www.demarches-simplifiees.fr/api/v2/graphql'

const sectionEmpty = computed(() => {
  const isUnsaved = props.existingConfig === null
    || props.existingConfig?.otp_config_id === null
  return isUnsaved && inputDNToken.value === '' && inputDNNumber.value === ''
})

const configValid = computed(() => props.gristError === '' && dnErrorMessage.value === '')

const debouncedValidate = debounce(validateDSConnection)

const handleDNInputsChange = () => {
  dnErrorMessage.value = null
  emit('error-update', null)
  debouncedValidate()
}

defineExpose({
  getData: () => ({
    token: inputDNToken.value,
    demarche_number: inputDNNumber.value,
  })
})

const applyExistingConfig = async (config) => {
  if (config.demarche_number)
    inputDNNumber.value = config.demarche_number

  if (config.has_ds_token)
    dnTokenPlaceholder.value = '****************************************'

  if (config.otp_config_id && config.demarche_number) {
    await validateDSConnection()
  } else {
    emit('error-update', null)
  }
}

const resetConfig = () => {
  inputDNNumber.value = ''
  inputDNToken.value = ''
  dnTokenPlaceholder.value = DEFAULT_DN_PLACEHOLDER
  accordionTitleDN.value = DEFAULT_DN_TITLE
  emit('error-update', null)
}

watch(() => props.existingConfig, (config) => {
  dnErrorMessage.value = null
  config ? applyExistingConfig(config) : resetConfig()
}, {immediate: true})
</script>

<template>
  <div>
    <OtpAlert
      v-if="error"
      type="error"
      :title="error"
      closeable
      @close="$emit('clear-error')"
      class="fr-mb-3w"
    />

    <DsfrAccordion>
      <template #title>
        <span
          class="otp-accordion-title"
          :title="accordionTitleDN"
        >{{ accordionTitleDN }}</span>
      </template>
        <DsfrInputGroup
            :error-message="dnErrorMessage"
        >
          <h5 class="fr-mt-3w fr-mb-0">Renseignez les informations de votre démarche numérique</h5>
          <p class="fr-mb-0">Jeton d'API *</p>
          <DsfrInput
            :error-message="dnErrorMessage"
            data-test-id="dn-token"
            v-model="inputDNToken"
            @input="handleDNInputsChange"
            label="DN token"
            :placeholder="dnTokenPlaceholder"
            type="password"
            required
          />
          <p class="fr-mt-2w">
            <DsfrInfoIcon class="fr-mr-1v"/>
            <a
              :href="HELP_LINKS.token_api"
              target="_blank"
              rel="noopener noreferrer"
              class="fr-link fr-text--xs">Où trouver votre jeton API ?</a>
          </p>

          <p class="fr-mb-0">Numéro de démarche *</p>
          <DsfrInput
            data-test-id="dn-number"
            v-model="inputDNNumber"
            @input="handleDNInputsChange"
            label="DN number"
            placeholder="Saisissez votre numéro DN"
            required
          />
        </DsfrInputGroup>

        <DsfrButtonGroup inline-layout-when="always" size="large">
          <DsfrButton
            label="Lancer la synchronisation"
            data-test-id="sync-button"
            primary
            :disabled="!canSync || sectionEmpty"
            @click="$emit('sync', index)"
          />
          <DsfrButton
            label="Sauvegarder"
            data-test-id="submit-form-button"
            secondary
            :disabled="!configValid || sectionEmpty"
            @click="$emit('save', index)"
          />
          <DsfrButton
            label="Supprimer"
            data-test-id="delete-config-button"
            secondary
            :disabled="!canDelete || sectionEmpty"
            @click="$emit('delete', index)"
          />
        </DsfrButtonGroup>
      </DsfrAccordion>
  </div>
</template>

<style scoped>
.otp-accordion-title {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
</style>
