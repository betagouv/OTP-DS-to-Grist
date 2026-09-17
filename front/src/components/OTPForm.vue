<script setup>
import { ref, computed, onMounted, watch } from 'vue'

import { DsfrButton, DsfrAccordionsGroup } from '@gouvminint/vue-dsfr'

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'
import OtpAlert from './OtpAlert.vue'

import { useDemarcheContext } from '../composables/useDemarcheContext'
import { api } from '../utils/InternalApi'
import { useNotification } from '../composables/useNotification'
import { sortConfigs, canDeleteConfig, canSyncConfig } from '../utils/configUtils'

const props = defineProps({
  syncRunning: { type: Boolean, default: false }
})

const emit = defineEmits(['config-loaded'])

const { setDemarcheCount, setDemarcheIndex } = useDemarcheContext()
const { notify } = useNotification()
const gristError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)
const configError = ref(null)
const actionErrors = ref([])

// Indices des sections dont une sauvegarde est en vol : leurs boutons
// d'action (synchronisation/suppression) sont désactivés le temps de la
// requête, comme sur le front legacy.
const savingIndices = ref(new Set())

const serverConfigs = ref([])
const activeDnAccordion = ref(-1)

// Chargement initial : tout doit rester fermé. `loaded` devient vrai à la 1re
// requête ; l'ouverture d'une section sauvegardée est gérée dans handleSave.
let loaded = false

// Après une sauvegarde, la section à rouvrir est cherchée par otp_config_id
// dans la liste rechargée : son index peut changer après le tri décroissant.
let pendingOpenId = null

const canDelete = (config) => canDeleteConfig(config)

const canSync = (config) => canSyncConfig(config, props.syncRunning)

const loadConfig = async () => {
  try {
    const context = await getGristContext()
    const data = await api.getConfig(context.params)
    serverConfigs.value = data.configs || []
    loaded = true
    emit('config-loaded', { configs: serverConfigs.value, docId: context.docId })
  } catch (e) {
    configError.value = 'Erreur lors du chargement de la configuration'
  }
}

const configs = computed(() => {
  if (serverConfigs.value.length === 0) return [null]
  return sortConfigs(serverConfigs.value)
})

const hasUnsavedSection = computed(() => configs.value.some(config => !config || !config.otp_config_id))

// Clé de remontage du DsfrAccordionsGroup : il indexe ses enfants par un
// compteur interne monotone qui se désynchronise des index du v-for après
// ajout/suppression/sauvegarde. Changer cette clé force le groupe à se
// démonter/remonter et à réaligner son compteur sur les index.
const accordionGroupKey = computed(() =>
  configs.value.map(config => config?.otp_config_id ?? 'empty').join('|')
)

watch(serverConfigs, (val) => {
  setDemarcheCount(val.length)
}, { immediate: true })

watch(configs, (sections) => {
  if (pendingOpenId !== null) {
    const target = sections.findIndex(config => config?.otp_config_id === pendingOpenId)
    activeDnAccordion.value = target >= 0 ? target : -1
    pendingOpenId = null
    return
  }
  const emptyIndex = sections.findIndex(config => !config || !config.otp_config_id)
  activeDnAccordion.value = loaded ? emptyIndex : -1
}, { immediate: true })

onMounted(loadConfig)

const handleSave = async (index) => {
  actionErrors.value[index] = null
  savingIndices.value.add(index)

  try {
    const dnData = dnSectionRefs.value[index].getData()
    const gristData = gristSectionRef.value.getData()
    const payload = {
      ds_api_token: dnData.token,
      demarche_number: dnData.demarche_number,
      grist_base_url: gristData.baseUrl,
      grist_doc_id: gristData.docId,
      grist_user_id: gristData.userId,
      grist_api_key: gristData.token,
      filter_date_start: dnData.filter_date_start,
      filter_date_end: dnData.filter_date_end,
      filter_statuses: dnData.filter_statuses,
      filter_groups: dnData.filter_groups
    }

    if (configs.value[index]?.otp_config_id)
      payload.otp_config_id = configs.value[index].otp_config_id

    const result = await api.saveConfig(payload)

    if (result.success) {
      const savedId = result.otp_config_id
      const effectiveId = savedId || configs.value[index]?.otp_config_id

      if (effectiveId) {
        const scheduleCall = dnData.auto_sync_enabled
          ? api.enableSchedule(effectiveId)
          : api.disableSchedule(effectiveId)

        try {
          const scheduleResult = await scheduleCall
          if (!scheduleResult.success) {
            actionErrors.value[index] =
              "Configuration sauvegardée, mais la synchronisation automatique n'a pas pu être enregistrée"
          }
        } catch {
          actionErrors.value[index] =
            "Configuration sauvegardée, mais la synchronisation automatique n'a pas pu être enregistrée"
        }
      }

      pendingOpenId = effectiveId || null
      await loadConfig()
      pendingOpenId = null
      if (!actionErrors.value[index]) notify('Configuration sauvegardée', 'success')
    } else {
      actionErrors.value[index] = result.message || 'Erreur lors de la sauvegarde'
    }
  } catch (e) {
    actionErrors.value[index] = 'Erreur lors de la sauvegarde'
  } finally {
    savingIndices.value.delete(index)
  }
}

const handleDelete = async (index) => {
  const otpConfigIdToDelete = configs.value[index]?.otp_config_id
  if (!otpConfigIdToDelete) return

  const confirmed = window.confirm(
    'Êtes-vous sûr de vouloir supprimer cette configuration ? Cette action est irréversible.'
  )
  if (!confirmed) return

  actionErrors.value[index] = null

  try {
    const result = await api.deleteConfig(otpConfigIdToDelete)

    if (!result.success)
      throw Error(result.message)

    await loadConfig()
    notify('Configuration supprimée', 'success')
  } catch (e) {
    actionErrors.value[index] = 'Erreur lors de la suppression'
  }
}

const handleSync = async (index) => {
  if (props.syncRunning) return
  const otpConfigIdToSync = configs.value[index]?.otp_config_id
  if (!otpConfigIdToSync) return
  actionErrors.value[index] = null
  try {
    setDemarcheIndex(index + 1)
    await api.startSync(otpConfigIdToSync)
    activeDnAccordion.value = -1
  } catch (e) {
    actionErrors.value[index] = 'Erreur lors de la synchronisation'
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

    <!-- Bloc Grist unique et partagé par toutes les sections DN :
         on l'initialise volontairement avec la première configuration renvoyée
         par le serveur (serverConfigs[0]), pas avec la liste triée `configs`. -->
    <GristFormSection
      @error-update="gristError = $event"
      :existing-config="serverConfigs[0] || null"
      ref="gristSectionRef"
    />

    <div class="fr-grid-row fr-grid-row--gutters fr-mt-4w fr-mb-1w">
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

    <DsfrAccordionsGroup v-model="activeDnAccordion" :key="accordionGroupKey">
      <DNFormSection 
        :index="index"
        @save="handleSave"
        @delete="handleDelete"
        @sync="handleSync"
        :grist-error="gristError"
        :can-delete="canDelete(config)"
        :can-sync="canSync(config)"
        :in-flight="savingIndices.has(index)"
        :existing-config="config"
        :error="actionErrors[index] || null"
        @clear-error="actionErrors[index] = null"
        v-for="(config, index) in configs"
        :key="config?.otp_config_id || 'new'"
        :ref="(dnComponent) => dnComponent && (dnSectionRefs[index] = dnComponent)"
      />
    </DsfrAccordionsGroup>
</template>
