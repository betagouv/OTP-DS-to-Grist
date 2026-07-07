<script setup>
import { ref } from 'vue'
import OTPForm from './components/OTPForm.vue'
import SyncProgress from './components/SyncProgress.vue'

const syncRunning = ref(false)
</script>

<template>
  <header>
    <div class="wrapper">
      <SyncProgress @sync-running-changed="syncRunning = $event" />
      <OTPForm :sync-running="syncRunning" />
    </div>
  </header>
</template>

<style scoped>
</style>
