<script setup>
import { ref, computed, onMounted, watch } from 'vue'

import { DsfrButton, DsfrAccordionsGroup } from '@gouvminint/vue-dsfr'

import GristFormSection from './GristFormSection.vue'
import DNFormSection from './DNFormSection.vue'
import OtpAlert from './OtpAlert.vue'

import { useSyncTask } from '../composables/useSyncTask'
import { api } from '../utils/InternalApi'
import { useNotification } from '../composables/useNotification'
import { sortConfigs, canDeleteConfig, canSyncConfig } from '../utils/configUtils'

const props = defineProps({
  syncRunning: { type: Boolean, default: false }
})

const emit = defineEmits(['config-loaded', 'title-loaded'])

const { setCurrentTaskId, setTasks } = useSyncTask()
const { notify } = useNotification()
const gristError = ref(null)
const dnSectionRefs = ref([])
const gristSectionRef = ref(null)
const configError = ref(null)
const actionErrors = ref([])
const syncAllError = ref(null)
// Requête « Tout synchroniser » en vol : évite un second envoi avant le
// démarrage effectif (syncRunning ne passe à vrai qu'au premier événement)
const syncAllPending = ref(false)

// Indices des sections dont une sauvegarde est en vol : leurs boutons
// d'action (synchronisation/suppression) sont désactivés le temps de la requête
const savingIndices = ref(new Set())

const serverConfigs = ref([])
const activeDnAccordion = ref(-1)

// Niveaux d'accès de la clé Grist qui ne permettent pas d'écrire dans le
// document : une synchro échouerait, il faut prévenir l'utilisateur.
const GRIST_KEY_INSUFFICIENT_ACCESS = ['viewers', 'editors', 'no-access']
const gristKeyWarningDismissed = ref(false)

const gristKeyAccessWarning = computed(() =>
  serverConfigs.value.some(config =>
    config && GRIST_KEY_INSUFFICIENT_ACCESS.includes(config.grist_key_access)
  )
)

// Chargement initial : tout doit rester fermé. `loaded` devient vrai à la fin de
// la 1re requête, même en échec ; l'ouverture d'une section sauvegardée est
// gérée dans handleSave. Le bloc Grist n'est monté qu'ensuite.
const loaded = ref(false)

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
    emit('config-loaded')
  } catch {
    configError.value = 'Erreur lors du chargement de la configuration'
  } finally {
    loaded.value = true
  }
}

const configs = computed(() => {
  if (serverConfigs.value.length === 0) return [null]

  return sortConfigs(serverConfigs.value)
})

const hasUnsavedSection = computed(() => configs.value.some(config => !config || !config.otp_config_id))

const hasSavedConfig = computed(() => configs.value.some(config => config?.otp_config_id))

// Clé de remontage du DsfrAccordionsGroup : il indexe ses enfants par un
// compteur interne monotone qui se désynchronise des index du v-for après
// ajout/suppression/sauvegarde. Changer cette clé force le groupe à se
// démonter/remonter et à réaligner son compteur sur les index.
const accordionGroupKey = computed(() =>
  configs.value.map(config => config?.otp_config_id ?? 'empty').join('|')
)

watch(configs, (sections) => {
  if (pendingOpenId !== null) {
    const target = sections.findIndex(config => config?.otp_config_id === pendingOpenId)
    activeDnAccordion.value = target >= 0 ? target : -1
    pendingOpenId = null

    return
  }
  const emptyIndex = sections.findIndex(config => !config || !config.otp_config_id)
  activeDnAccordion.value = loaded.value ? emptyIndex : -1
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
  } catch {
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
  } catch {
    actionErrors.value[index] = 'Erreur lors de la suppression'
  }
}

const handleSync = async (index) => {
  if (props.syncRunning) return
  const otpConfigIdToSync = configs.value[index]?.otp_config_id
  if (!otpConfigIdToSync) return
  actionErrors.value[index] = null
  try {
    const result = await api.startSync(otpConfigIdToSync)
    setCurrentTaskId(result.task_id, configs.value[index].demarche_number)
    activeDnAccordion.value = -1
  } catch {
    actionErrors.value[index] = 'Erreur lors de la synchronisation'
  }
}

const handleSyncAll = async () => {
  if (props.syncRunning || syncAllPending.value) return
  syncAllError.value = null
  syncAllPending.value = true
  try {
    const result = await api.startSyncAll()
    setTasks(result.syncs.map(sync => ({
      taskId: sync.task_id,
      demarcheNumber: sync.demarche_number
    })))
    activeDnAccordion.value = -1
  } catch (e) {
    syncAllError.value = e.serverMessage ?? 'Erreur lors de la synchronisation de toutes les démarches'
  } finally {
    syncAllPending.value = false
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
    class="fr-mb-4w"
    @close="configError = null"
  />

  <OtpAlert
    v-if="gristKeyAccessWarning && !gristKeyWarningDismissed"
    type="warning"
    title="Clé API Grist insuffisante"
    closeable
    class="fr-mb-4w"
    @close="gristKeyWarningDismissed = true"
  >
    La clé API Grist enregistrée n'a pas les droits de propriétaire sur ce document.
  </OtpAlert>

  <p class="fr-mb-4w">Les champs suivis d'un astérisque (*) sont obligatoires.</p>

  <h6 class="fr-mb-3w">1. Grist</h6>

  <!-- Bloc Grist unique et partagé par toutes les sections DN :
       on l'initialise volontairement avec la première configuration renvoyée
       par le serveur (serverConfigs[0]), pas avec la liste triée `configs`. -->
  <GristFormSection
    v-if="loaded"
    ref="gristSectionRef"
    :existing-config="serverConfigs[0] || null"
    @error-update="gristError = $event"
  />

  <div class="fr-grid-row fr-grid-row--gutters fr-mt-4w fr-mb-1w">
    <div class="fr-col-6">
      <h6 class="fr-mb-3w">2. Démarche numérique</h6>
    </div>

    <div
      class="fr-col-6"
      style="text-align: right"
    >
      <DsfrButton
        label="Ajouter une démarche numérique"
        icon="fr-icon-add-circle-line"
        data-test-id="add-dn-section-button"
        secondary
        :disabled="hasUnsavedSection"
        @click="handleAddDemarche"
      />
    </div>
  </div>

  <DsfrAccordionsGroup
    :key="accordionGroupKey"
    v-model="activeDnAccordion"
  >
    <DNFormSection
      v-for="(config, index) in configs"
      :key="config?.otp_config_id || 'new'"
      :ref="(dnComponent) => dnComponent && (dnSectionRefs[index] = dnComponent)"
      :index="index"
      :grist-error="gristError"
      :can-delete="canDelete(config)"
      :can-sync="canSync(config)"
      :in-flight="savingIndices.has(index)"
      :existing-config="config"
      :error="actionErrors[index] || null"
      @save="handleSave"
      @delete="handleDelete"
      @sync="handleSync"
      @title-loaded="(demarcheNumber, title) => emit('title-loaded', demarcheNumber, title)"
      @clear-error="actionErrors[index] = null"
    />
  </DsfrAccordionsGroup>

  <OtpAlert
    v-if="syncAllError"
    type="error"
    :title="syncAllError"
    closeable
    class="fr-mt-4w"
    @close="syncAllError = null"
  />

  <div
    class="fr-mt-4w"
    style="text-align: right"
  >
    <DsfrButton
      label="Tout synchroniser"
      icon="fr-icon-refresh-line"
      data-test-id="sync-all-button"
      :disabled="syncRunning || syncAllPending || !hasSavedConfig"
      @click="handleSyncAll"
    />
  </div>
</template>
