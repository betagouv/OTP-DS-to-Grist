<script setup>
import { ref, computed, onMounted } from 'vue'

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'

const props = defineProps({
  syncRunning: { type: Boolean, default: false }
})

const gristError = ref(null)
const dnError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)

const serverConfigs = ref([])
const otpConfigId = ref(null)

const canSave = computed(() => gristError.value === '' && dnError.value === '')
const canDelete = computed(() => !!otpConfigId.value)
const canSync = computed(() => !!otpConfigId.value && !props.syncRunning)
const configs = computed(() => {
  if (serverConfigs.value.length === 0) return [null]
  return serverConfigs.value
})

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

const handleSaveButtonClick = async () => {
  if (!canSave.value) return

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
  } else {
    console.error('Erreur lors de la sauvegarde :', result.message)
  }
}

const handleDeleteButtonClick = async () => {
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

</script>

<template>
    <GristFormSection
      @error-update="gristError = $event"
      :existing-config="serverConfigs[0] || null"
      ref="gristSectionRef"
    />

    <DNFormSection 
      @error-update="dnError = $event"
      @save="handleSaveButtonClick"
      @delete="handleDeleteButtonClick"
      @sync="handleSync"
      :can-save="canSave"
      :can-delete="canDelete"
      :can-sync="canSync"
      :existing-config="config"
      v-for="(config, index) in configs"
      :key="index"
      :ref="(dnComponent) => dnComponent && (dnSectionRefs[index] = dnComponent)"
    />
</template>
