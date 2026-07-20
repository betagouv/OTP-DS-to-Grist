<script setup>
import { ref, watch, computed } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrButton,
  DsfrButtonGroup,
  DsfrInputGroup,
  DsfrInput
} from '@gouvminint/vue-dsfr'

import DsfrInfoIcon from './icons/DsfrInfoIcon.vue'
import { api } from '../utils/InternalApi'
import { useNotification } from '../composables/useNotification'
import OtpAlert from './OtpAlert.vue'

const props = defineProps({
  existingConfig: { type: Object, default: null },
  configValid: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canSync: { type: Boolean, default: false },
  error: { type: String, default: null }
})

const HELP_LINKS = window.HELP_LINKS
const emit = defineEmits(['error-update', 'save', 'delete', 'sync', 'clear-error'])

// TODO le mettre dans le parent
const activeAccordion = ref(0) // Premier accordéon ouvert par défaut
const accordionTitleDN = ref('Configurer votre démarche')

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

const handleDNInputsChange = async () => {
  dnErrorMessage.value = null

  if (!inputDNNumber.value)
    return emit('error-update', null)

  const body = {
    type: 'demarches',
    api_url: dnApiUrl,
    demarche_number: inputDNNumber.value
  }

  if (inputDNToken.value) {
    body.api_token = inputDNToken.value
  } else if (props.existingConfig?.otp_config_id) {
    body.otp_config_id = props.existingConfig.otp_config_id
  } else {
    return emit('error-update', null)
  }

  try {
    const result = await api.testConnection(body)
    dnErrorMessage.value = result.success ? '' : result.message
    emit('error-update', dnErrorMessage.value)
  } catch (e) {
    dnErrorMessage.value = 'Erreur lors du test de connexion'
    emit('error-update', dnErrorMessage.value)
  }
}

defineExpose({
  getData: () => ({
    token: inputDNToken.value,
    demarche_number: inputDNNumber.value,
  })
})

watch(() => props.existingConfig, (config) => {
  if (config) {
    if (config.demarche_number)
      inputDNNumber.value = config.demarche_number

    if (config.has_ds_token) {
      dnTokenPlaceholder.value = '****************************************'
      emit('error-update', '')
    }
  } else {
    inputDNNumber.value = ''
    inputDNToken.value = ''
    dnTokenPlaceholder.value = DEFAULT_DN_PLACEHOLDER
    emit('error-update', null)
  }
})
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

    <DsfrAccordionsGroup v-model="activeAccordion">
      <DsfrAccordion
        id="accordion-dn"
        :title="accordionTitleDN"
      >
        <DsfrInputGroup
            :error-message="dnErrorMessage"
        >
          <h5 class="fr-mt-3w fr-mb-0">Renseignez les informations de votre démarche numérique</h5>
          <p class="fr-mb-0">Jeton d'API *</p>
          <DsfrInput
            :error-message="dnErrorMessage"
            data-test-id="dn-token"
            v-model="inputDNToken"
            @change="handleDNInputsChange"
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
            @change="handleDNInputsChange"
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
            @click="$emit('sync')"
          />
          <DsfrButton
            label="Sauvegarder"
            data-test-id="submit-form-button"
            secondary
            :disabled="!configValid || sectionEmpty"
            @click="$emit('save')"
          />
          <DsfrButton
            label="Supprimer"
            data-test-id="delete-config-button"
            secondary
            :disabled="!canDelete || sectionEmpty"
            @click="$emit('delete')"
          />
        </DsfrButtonGroup>
      </DsfrAccordion>
    </DsfrAccordionsGroup>
  </div>
</template>
