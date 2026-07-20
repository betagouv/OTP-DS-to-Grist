<script setup>
import { useNotification } from '../composables/useNotification'
import { DsfrAlert } from '@gouvminint/vue-dsfr'

const { notifications, remove } = useNotification()
</script>

<template>
  <div class="notification-container">
    <DsfrAlert
      v-for="notif in notifications"
      :key="notif.id"
      :type="notif.type"
      :description="notif.message"
      closeable
      @close="remove(notif.id)"
      class="notification-toast"
    />
  </div>
</template>

<style scoped>
.notification-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 24rem;
}

.notification-toast {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
