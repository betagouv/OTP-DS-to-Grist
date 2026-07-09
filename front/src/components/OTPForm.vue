<script setup>
import { ref, computed, onMounted, watch } from 'vue'

import { DsfrButton } from '@gouvminint/vue-dsfr'

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'

import { useDemarcheContext } from '../composables/useDemarcheContext'

const props = defineProps({
  syncRunning: { type: Boolean, default: false }
})

const { setDemarcheCount } = useDemarcheContext()
const gristError = ref(null)
const dnError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)

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
    const response = await fetch(`/api/config${context.params}`)
    const data = await response.json()
    serverConfigs.value = data.configs || []
    otpConfigId.value = serverConfigs.value[0]?.otp_config_id || null
  } catch (e) {
    console.error('Erreur lors du chargement de la configuration :', e)
  }
}

onMounted(loadConfig)

const handleSave = async () => {
  if (!configValid.value) return

  const hadEmpty = serverConfigs.value.includes(null)

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
    if (hadEmpty) serverConfigs.value.push(null)
  } else {
    console.error('Erreur lors de la sauvegarde :', result.message)
  }
}

const handleDelete = async () => {
  if (!otpConfigId.value) return

  const confirmed = window.confirm(
    'Êtes-vous sûr de vouloir supprimer cette configuration ? Cette action est irréversible.'
  )
  if (!confirmed) return

  try {
    const response = await fetch(`/api/config/${otpConfigId.value}`, {
      method: 'DELETE'
    })

    const result = await response.json()

    if (!result.success)
      throw Error(result.message)

    otpConfigId.value = null
    serverConfigs.value = [] // TMP
  } catch (e) {
    console.error('Erreur lors de la suppression :', e.message)
  }
}

const handleSync = async () => {
  if (!otpConfigId.value || props.syncRunning) return
  try {
    await fetch('/api/start-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: otpConfigId.value })
    })
  } catch {}
}

const handleAddDemarche = async () => {
  serverConfigs.value.push(null)
}

</script>

<template>
    <p class="fr-mb-4w">Les champs suivis d’un astérisque (*) sont obligatoires.</p>

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
      v-for="(config, index) in configs"
      :key="index"
      :ref="(dnComponent) => dnComponent && (dnSectionRefs[index] = dnComponent)"
      class="fr-mt-1w"
    />
</template>
