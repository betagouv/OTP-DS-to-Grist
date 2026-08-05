<script setup>
import { ref, computed, watch } from 'vue'

import { DsfrInput, DsfrInputGroup, DsfrCheckboxSet, DsfrMultiselect } from '@gouvminint/vue-dsfr'

import OtpAlert from './OtpAlert.vue'
import { api } from '../utils/InternalApi'

const props = defineProps({
  existingConfig: { type: Object, default: null }
})

const emit = defineEmits(['change', 'error-update'])

const STATUS_OPTIONS = [
  { name: 'statuts', label: 'En construction', value: 'en_construction' },
  { name: 'statuts', label: 'En instruction', value: 'en_instruction' },
  { name: 'statuts', label: 'Accepté', value: 'accepte' },
  { name: 'statuts', label: 'Refusé', value: 'refuse' },
  { name: 'statuts', label: 'Sans suite', value: 'sans_suite' }
]

const dateDebut = ref('')
const dateFin = ref('')
const selectedStatuses = ref([])
const groups = ref([])
const selectedGroups = ref([])
const loadingGroups = ref(false)
const groupsError = ref('')

const hasConfig = computed(() => !!props.existingConfig?.otp_config_id)

const showGroupsSection = computed(() =>
  hasConfig.value && (loadingGroups.value || groupsError.value || groups.value.length > 0)
)

const dateError = computed(() => {
  if (dateDebut.value && dateFin.value && dateFin.value < dateDebut.value)
    return 'La date de fin doit être postérieure ou égale à la date de début'
  return ''
})

const handleDateChange = () => {
  emit('change')
}

const handleStatusChange = () => {
  emit('change')
}

const handleGroupsChange = () => {
  emit('change')
}

watch([dateDebut, dateFin], () => {
  emit('error-update', dateError.value)
})

watch(() => props.existingConfig, async (config) => {
  dateDebut.value = config?.filter_date_start || ''
  dateFin.value = config?.filter_date_end || ''
  selectedStatuses.value = config?.filter_statuses ? config.filter_statuses.split(',') : []
  emit('error-update', dateError.value)

  const id = config?.otp_config_id

  if (!id) {
    groups.value = []
    selectedGroups.value = []
    groupsError.value = ''
    loadingGroups.value = false

    return
  }

  selectedGroups.value = config.filter_groups ? config.filter_groups.split(',').map(Number) : []
  groupsError.value = ''
  loadingGroups.value = true

  try {
    groups.value = await api.getGroups(id)
  } catch {
    groupsError.value = 'Erreur lors du chargement des groupes instructeurs'
  } finally {
    loadingGroups.value = false
  }
}, { immediate: true })

defineExpose({
  getData: () => ({
    filter_date_start: dateDebut.value,
    filter_date_end: dateFin.value,
    filter_statuses: selectedStatuses.value.join(','),
    filter_groups: selectedGroups.value.join(',')
  })
})
</script>

<template>
  <fieldset class="fr-fieldset">
    <legend class="fr-fieldset__legend">
      Filtrer par dates
    </legend>

    <div class="fr-fieldset__content">
      <div class="fr-grid-row fr-grid-row--gutters">
        <div class="fr-col-12 fr-col-md-6">
          <DsfrInputGroup>
            <DsfrInput
              v-model="dateDebut"
              label="Date de début"
              type="date"
              data-test-id="filter-date-start"
              @input="handleDateChange"
            />
          </DsfrInputGroup>
        </div>

        <div class="fr-col-12 fr-col-md-6">
          <DsfrInputGroup :error-message="dateError">
            <DsfrInput
              v-model="dateFin"
              label="Date de fin"
              :is-invalid="!!dateError"
              type="date"
              data-test-id="filter-date-end"
              @input="handleDateChange"
            />
          </DsfrInputGroup>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset class="fr-fieldset fr-mt-3w">
    <legend class="fr-fieldset__legend">
      Filtrer par statut
    </legend>

    <div class="fr-fieldset__content">
      <DsfrCheckboxSet
        v-model="selectedStatuses"
        :options="STATUS_OPTIONS"
        inline
        @update:model-value="handleStatusChange"
      />
    </div>
  </fieldset>

  <fieldset v-if="showGroupsSection" class="fr-fieldset fr-mt-3w">
    <legend class="fr-fieldset__legend">
      Filtrer par groupe instructeur
    </legend>

    <div class="fr-fieldset__content">
      <OtpAlert
        v-if="groupsError"
        type="error"
        :title="groupsError"
        class="fr-mb-3w"
      />
      <p v-else-if="loadingGroups">...</p>
      <DsfrMultiselect
        v-else
        v-model="selectedGroups"
        :options="groups"
        label="Groupes instructeurs"
        button-label="Vous pouvez sélectionner un ou plusieurs choix"
        id-key="number"
        label-key="label"
        search
        @update:model-value="handleGroupsChange"
      />
    </div>
  </fieldset>
</template>
