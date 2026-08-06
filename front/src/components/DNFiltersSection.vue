<script setup>
import { ref, computed, watch } from 'vue'

import { DsfrInput, DsfrInputGroup, DsfrCheckboxSet, DsfrMultiselect, DsfrButton } from '@gouvminint/vue-dsfr'

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
const groupsWarning = ref('')

const hasConfig = computed(() => !!props.existingConfig?.otp_config_id)

const showGroupsSection = computed(() =>
  hasConfig.value && (loadingGroups.value || groupsError.value || groupsWarning.value || groups.value.length > 1)
)

const dateError = computed(() => {
  if (dateDebut.value && dateFin.value && dateFin.value < dateDebut.value)
    return 'La date de fin doit être postérieure ou égale à la date de début'
  return ''
})

const dateTags = computed(() => {
  const tags = []
  if (dateDebut.value) tags.push(`Date de début: ${formatDate(dateDebut.value)}`)
  if (dateFin.value) tags.push(`Date de fin: ${formatDate(dateFin.value)}`)
  return tags
})

const statusTags = computed(() => {
  if (selectedStatuses.value.length === 0) return []
  const labels = selectedStatuses.value.map(
    (value) => STATUS_OPTIONS.find((option) => option.value === value)?.label ?? value
  )
  return [`Statuts: ${labels.join(', ')}`]
})

const groupTags = computed(() => {
  if (groups.value.length <= 1 || selectedGroups.value.length === 0) return []
  const groupMap = new Map(groups.value.map((g) => [g.number, g.label]))
  const labels = selectedGroups.value.map((n) => groupMap.get(n) ?? `Groupe #${n}`)
  return [`Groupes: ${labels.join(', ')}`]
})

const hasActiveFilters = computed(() =>
  dateTags.value.length > 0 || statusTags.value.length > 0 || groupTags.value.length > 0
)

const handleDateChange = () => {
  emit('change')
}

const handleStatusChange = () => {
  emit('change')
}

const handleGroupsChange = () => {
  emit('change')
}

const handleReset = () => {
  dateDebut.value = ''
  dateFin.value = ''
  selectedStatuses.value = []
  selectedGroups.value = []
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
    groupsWarning.value = ''
    loadingGroups.value = false

    return
  }

  selectedGroups.value = config.filter_groups ? config.filter_groups.split(',').map(Number) : []
  groupsError.value = ''
  groupsWarning.value = ''
  loadingGroups.value = true

  try {
    groups.value = await api.getGroups(id)

    const available = new Set(groups.value.map((g) => g.number))
    const missing = selectedGroups.value.filter((n) => !available.has(n))

    if (missing.length > 0) {
      selectedGroups.value = selectedGroups.value.filter((n) => available.has(n))
      groupsWarning.value = 'Certains groupes instructeurs sauvegardés ne sont plus proposés par la démarche. Ils ont été retirés du filtre. Vérifiez la sélection puis enregistrez vos modifications.'
      emit('change')
    }
  } catch {
    groupsError.value = 'Erreur lors du chargement des groupes instructeurs'
    groupsWarning.value = ''
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
        v-else-if="groups.length"
        v-model="selectedGroups"
        :options="groups"
        label="Groupes instructeurs"
        button-label="Vous pouvez sélectionner un ou plusieurs choix"
        id-key="number"
        label-key="label"
        search
        @update:model-value="handleGroupsChange"
      />
      <OtpAlert
        v-if="groupsWarning"
        type="warning"
        :title="groupsWarning"
        class="fr-mt-3w"
      />
    </div>
  </fieldset>

  <div v-if="hasActiveFilters" class="fr-mt-3w">
    <h5 class="fr-mb-1w">Filtres actifs</h5>
    <ul v-if="dateTags.length" class="fr-tags-group">
      <li v-for="tag in dateTags" :key="tag">
        <span class="fr-tag fr-tag--high-blue-france">{{ tag }}</span>
      </li>
    </ul>
    <ul v-if="statusTags.length" class="fr-tags-group fr-mt-1w">
      <li v-for="tag in statusTags" :key="tag">
        <span class="fr-tag fr-tag--high-blue-france">{{ tag }}</span>
      </li>
    </ul>
    <ul v-if="groupTags.length" class="fr-tags-group fr-mt-1w">
      <li v-for="tag in groupTags" :key="tag">
        <span class="fr-tag fr-tag--high-blue-france">{{ tag }}</span>
      </li>
    </ul>
  </div>

  <div class="fr-mt-3w">
    <DsfrButton
      label="Réinitialiser"
      data-test-id="reset-filters-button"
      secondary
      :disabled="!hasActiveFilters"
      @click="handleReset"
    />
  </div>
</template>
