<script setup>
import { ref, computed, onMounted, watch } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrInputGroup,
  DsfrInput
} from '@gouvminint/vue-dsfr'

import DsfrInfoIcon from './icons/DsfrInfoIcon.vue'
import FieldLabel from './FieldLabel.vue'
import { useConnectionCheck, CONNECTION_STATUS } from '../composables/useConnectionCheck'
import OtpAlert from './OtpAlert.vue'
import { debounce } from '../utils/debounce'

const props = defineProps({
  existingConfig: { type: Object, default: null }
})

const {HELP_LINKS} = window
const emit = defineEmits(['error-update'])
const context = ref(null)
// Vrai une fois le contexte Grist résolu (ou en échec) : la config n'est
// appliquée qu'ensuite, pour que son baseUrl ne soit pas écrasé par celui du contexte
const contextReady = ref(false)

const userId = ref('')
const docId = ref('')
const baseUrl = ref('')
const inputGristToken = ref('')

const accordionTitleGrist = ref('Configurer Grist')
const activeAccordion = ref(-1)

const DEFAULT_GRIST_PLACEHOLDER = 'Saisissez votre clé grist'
const GRIST_NETWORK_ERROR = 'Erreur lors du test de connexion Grist'
const gristTokenPlaceholder = ref(DEFAULT_GRIST_PLACEHOLDER)
const gristFetchError = ref(null)

const buildGristTestBody = () => ({
  type: 'grist',
  base_url: baseUrl.value,
  api_key: inputGristToken.value,
  doc_id: docId.value,
  ...(!inputGristToken.value && props.existingConfig?.otp_config_id
    ? { otp_config_id: props.existingConfig.otp_config_id }
    : {})
})

const gristConnection = useConnectionCheck()
const gristTokenErrorMessage = gristConnection.errorMessage
const gristVerified = computed(() => gristConnection.status.value === CONNECTION_STATUS.VERIFIED)

const validateGristConnection = async () => {
  try {
    await gristConnection.check(buildGristTestBody())
  } catch {
    // Message affiché dans l'alerte, et remonté pour bloquer l'auto-save
    gristFetchError.value = GRIST_NETWORK_ERROR
    emit('error-update', GRIST_NETWORK_ERROR)

    return
  }
  emit('error-update', gristTokenErrorMessage.value)
}

const debouncedValidate = debounce(validateGristConnection)

const handleGristInputChange = () => {
  gristConnection.reset()
  gristFetchError.value = null
  debouncedValidate()
}

onMounted(async () => {
  try {
    context.value = await getGristContext()

    userId.value = context.value.userId
    docId.value = context.value.docId
    baseUrl.value = context.value.baseUrl
  } catch (e) {
    gristFetchError.value = e.message
  } finally {
    contextReady.value = true
  }
})

const applyExistingConfig = async (config) => {
  if (config.otp_config_id && config.grist_base_url)
    baseUrl.value = config.grist_base_url

  if (config.has_grist_key) {
    gristTokenPlaceholder.value = '****************************************'
  }

  if (config.otp_config_id) {
    await validateGristConnection()
  } else {
    emit('error-update', null)
  }
}

const resetConfig = () => {
  inputGristToken.value = ''
  gristTokenPlaceholder.value = DEFAULT_GRIST_PLACEHOLDER
  baseUrl.value = context.value?.baseUrl || ''
  gristConnection.reset()
  emit('error-update', null)
}

// Sans configuration, OTPForm transmet null (le backend renvoie une liste vide) ;
// une config non enregistrée (otp_config_id falsy) est traitée de même : l'accordéon
// s'ouvre pour guider l'utilisateur. OTPForm ne monte ce bloc qu'une fois la config
// chargée : la première valeur reçue est donc la bonne, sans null provisoire.
watch([() => props.existingConfig, contextReady], ([config, ready]) => {
  if (!ready) return

  if (config?.otp_config_id) {
    applyExistingConfig(config)
    activeAccordion.value = -1

    return
  }
  resetConfig()
  activeAccordion.value = 0
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
    <OtpAlert
      v-if="gristFetchError"
      type="error"
      :title="gristFetchError"
      closeable
      class="fr-mb-3w"
      @close="gristFetchError = null"
    />

    <DsfrAccordionsGroup v-model="activeAccordion">
      <DsfrAccordion
        id="accordion-grist"
        :title="accordionTitleGrist"
      >
        <DsfrInputGroup
          :error-message="gristTokenErrorMessage"
        >
          <h5 class="fr-mt-3w fr-mb-0">
            Renseignez votre clé API Grist
          </h5>
          <DsfrInput
            v-model="inputGristToken"
            :error-message="gristTokenErrorMessage"
            data-test-id="grist-token"
            label-visible
            :placeholder="gristTokenPlaceholder"
            type="password"
            required
            @input="handleGristInputChange"
          >
            <template #label>
              <FieldLabel
                label="Clé API Grist *"
                :verified="gristVerified"
              />
            </template>
          </DsfrInput>
          <p class="fr-mt-2w">
            <DsfrInfoIcon class="fr-mr-1v" />
            <a
              :href="HELP_LINKS.grist_api_key"
              target="_blank"
              rel="noopener noreferrer"
              class="fr-link fr-text--xs"
            >Où trouver votre clé API Grist ?</a>
          </p>
        </DsfrInputGroup>
      </DsfrAccordion>
    </DsfrAccordionsGroup>
  </div>
</template>
