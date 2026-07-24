<script setup>
import { ref, watch, nextTick } from 'vue'
import { DsfrAlert } from '@gouvminint/vue-dsfr'

const props = defineProps({
  type: { type: String, default: 'info' },
  title: { type: String, required: true },
  closeable: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])

const alertRef = ref(null)

watch(() => props.title, async (title) => {
  if (title) {
    await nextTick()
    alertRef.value?.$el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
})
</script>

<template>
  <DsfrAlert
    ref="alertRef"
    :type="type"
    :title="title"
    :closeable="closeable"
    @close="emit('close')"
  />
</template>
