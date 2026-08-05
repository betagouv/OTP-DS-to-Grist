<script setup>
import { ref, computed, watch } from 'vue'

import { DsfrInput, DsfrInputGroup } from '@gouvminint/vue-dsfr'

const props = defineProps({
  existingConfig: { type: Object, default: null }
})

const emit = defineEmits(['change', 'error-update'])

const dateDebut = ref('')
const dateFin = ref('')

const dateError = computed(() => {
  if (dateDebut.value && dateFin.value && dateFin.value < dateDebut.value)
    return 'La date de fin doit être postérieure ou égale à la date de début'
  return ''
})

const handleDateChange = () => {
  emit('change')
}

watch([dateDebut, dateFin], () => {
  emit('error-update', dateError.value)
})

watch(() => props.existingConfig, (config) => {
  dateDebut.value = config?.filter_date_start || ''
  dateFin.value = config?.filter_date_end || ''
  emit('error-update', dateError.value)
}, { immediate: true })

defineExpose({
  getData: () => ({
    filter_date_start: dateDebut.value,
    filter_date_end: dateFin.value
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
</template>
