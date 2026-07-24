<script setup>
import { ref, computed, onMounted, watch } from 'vue'

import { DsfrButton } from '@gouvminint/vue-dsfr'

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'
import OtpAlert from './OtpAlert.vue'

import { useDemarcheContext } from '../composables/useDemarcheContext'
import { api } from '../utils/InternalApi'
import { useNotification } from '../composables/useNotification'

const props = defineProps({
  syncRunning: { type: Boolean, default: false }
})

const emit = defineEmits(['config-loaded'])

const { setDemarcheCount } = useDemarcheContext()
const { notify } = useNotification()
const gristError = ref(null)
const dnError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)
const configError = ref(null)
const actionErrors = ref([])

const serverConfigs = ref([])
const otpConfigId = ref(null)

const configValid = computed(() => gristError.value === '' && dnError.value === '')
const canDelete = computed(() => !!otpConfigId.value)
const canSync = computed(() => !!otpConfigId.value && !props.syncRunning && configValid.value)
const configs = computed(() => {
  if (serverConfigs.value.length === 0) return [null]
  return serverConfigs.value
})
const hasUnsavedSection = computed(() => configs.value.some(config => !config || !config.otp_config_id))

watch(serverConfigs, (val) => {
  setDemarcheCount(val.length)
}, { immediate: true })

const loadConfig = async () => {
  try {
    const context = await getGristContext()
    const data = await api.getConfig(context.params)
    serverConfigs.value = data.configs || []
    otpConfigId.value = serverConfigs.value[0]?.otp_config_id || null
    emit('config-loaded', { configs: serverConfigs.value, docId: context.docId })
  } catch (e) {
    configError.value = 'Erreur lors du chargement de la configuration'
  }
}

onMounted(loadConfig)

const handleSave = async () => {
  if (!configValid.value) return

  const hadEmpty = serverConfigs.value.includes(null)

  actionErrors.value[0] = null

  try {
    const config = {
      ds_api_token: dnSectionRefs.value[0].getData().token,
      demarche_number: dnSectionRefs.value[0].getData().demarche_number,
      grist_base_url: gristSectionRef.value.getData().baseUrl,
      grist_doc_id: gristSectionRef.value.getData().docId,
      grist_user_id: gristSectionRef.value.getData().userId,
      grist_api_key: gristSectionRef.value.getData().token
    }

    if (otpConfigId.value) {
      config.otp_config_id = otpConfigId.value
    }

    const result = await api.saveConfig(config)

    if (result.success) {
      await loadConfig()
      if (hadEmpty) serverConfigs.value.push(null)
      notify('Configuration sauvegardée', 'success')
    } else {
      actionErrors.value[0] = result.message || 'Erreur lors de la sauvegarde'
    }
  } catch (e) {
    actionErrors.value[0] = 'Erreur lors de la sauvegarde'
  }
}

const handleDelete = async () => {
  if (!otpConfigId.value) return

  const confirmed = window.confirm(
    'Êtes-vous sûr de vouloir supprimer cette configuration ? Cette action est irréversible.'
  )
  if (!confirmed) return

  actionErrors.value[0] = null

  try {
    const result = await api.deleteConfig(otpConfigId.value)

    if (!result.success)
      throw Error(result.message)

    otpConfigId.value = null
    serverConfigs.value = []
    notify('Configuration supprimée', 'success')
  } catch (e) {
    actionErrors.value[0] = 'Erreur lors de la suppression'
  }
}

const handleSync = async () => {
  if (!otpConfigId.value || props.syncRunning) return
  actionErrors.value[0] = null
  try {
    await api.startSync(otpConfigId.value)
  } catch (e) {
    actionErrors.value[0] = 'Erreur lors de la synchronisation'
  }
}

const handleAddDemarche = async () => {
  serverConfigs.value.push(null)
}

</script>

<template>
    <OtpAlert
      v-if="configError"
      type="error"
      :title="configError"
      closeable
      @close="configError = null"
      class="fr-mb-4w"
    />

    <p class="fr-mb-4w">Les champs suivis d'un astérisque (*) sont obligatoires.</p>

    <h6 class="fr-mb-3w">1. Grist</h6>

    <GristFormSection
      @error-update="gristError = $event"
      :existing-config="serverConfigs[0] || null"
      ref="gristSectionRef"
    />

    <div class="fr-grid-row fr-grid-row--gutters fr-mt-4w">
      <div class="fr-col-6">
        <h6 class="fr-mb-3w">2. Démarche numérique</h6>
      </div>

      <div class="fr-col-6" style="text-align: right">
        <DsfrButton
          label="Ajouter une démarche numérique"
          icon="fr-icon-add-circle-line"
          data-test-id="add-dn-section-button"
          secondary
          @click="handleAddDemarche"
          :disabled="hasUnsavedSection"
        />
      </div>
    </div>

    <DNFormSection 
      @error-update="dnError = $event"
      @save="handleSave"
      @delete="handleDelete"
      @sync="handleSync"
      :config-valid="configValid"
      :can-delete="canDelete"
      :can-sync="canSync"
      :existing-config="config"
      :error="actionErrors[0] || null"
      @clear-error="actionErrors[0] = null"
      v-for="(config, index) in configs"
      :key="index"
      :ref="(dnComponent) => dnComponent && (dnSectionRefs[index] = dnComponent)"
      class="fr-mt-1w"
    />
</template>
