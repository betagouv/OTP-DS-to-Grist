<script setup>
import { ref, onMounted } from 'vue'

const context = ref(null)
const error = ref(null)

onMounted(async () => {
  try {
    context.value = await getGristContext()
  } catch (e) {
    error.value = e
  }
})

</script>

<template>
  <div>
    <p v-if="grist">Module grist chargé</p>
    <p v-if="context">Context : {{context}}</p>
    <p v-if="error">/!\ {{error}}</p>
  </div>
</template>

<style scoped>
</style>
