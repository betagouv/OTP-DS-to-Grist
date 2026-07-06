<script setup>
import { ref, watch } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrButton,
  DsfrButtonGroup,
  DsfrInputGroup,
  DsfrInput
} from '@gouvminint/vue-dsfr'

import DsfrInfoIcon from './icons/DsfrInfoIcon.vue'

const props = defineProps({
  existingConfig: { type: Object, default: null },
  canSave: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canSync: { type: Boolean, default: false }
})

const USE_OTP_URL = window.USE_OTP_URL
const emit = defineEmits(['error-update', 'save', 'delete', 'sync'])

// TODO le mettre dans le parent
const activeAccordion = ref(0) // Premier accordéon ouvert par défaut
const accordionTitleDN = ref('Configurer votre démarche')

const inputDNToken = ref('')
const inputDNNumber = ref('')
const dnErrorMessage = ref(null)
const DEFAULT_DN_PLACEHOLDER = 'Saisissez votre clé Démarche Numérique'
const dnTokenPlaceholder = ref(DEFAULT_DN_PLACEHOLDER)
const dnApiUrl = 'https://www.demarches-simplifiees.fr/api/v2/graphql'

const handleDNInputsChange = async () => {
  dnErrorMessage.value = null

  // Only check with both values setted
  if (!inputDNToken.value || !inputDNNumber.value)
    return emit('error-update', null)

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
    <h6 class="fr-mb-3w">2. Démarche numérique</h6>

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
              :href="`${USE_OTP_URL}#help-ds`"
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
            :disabled="!canSync"
            @click="$emit('sync')"
          />
          <DsfrButton
            label="Sauvegarder"
            data-test-id="submit-form-button"
            secondary
            :disabled="!canSave"
            @click="$emit('save')"
          />
          <DsfrButton
            label="Supprimer"
            data-test-id="delete-config-button"
            secondary
            :disabled="!canDelete"
            @click="$emit('delete')"
          />
        </DsfrButtonGroup>
      </DsfrAccordion>
    </DsfrAccordionsGroup>
  </div>
</template>
