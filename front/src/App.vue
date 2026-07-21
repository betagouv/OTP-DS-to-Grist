<script setup>
import { ref } from 'vue'
import OTPForm from './components/OTPForm.vue'
import SyncProgress from './components/SyncProgress.vue'
import SyncResultBanner from './components/SyncResultBanner.vue'
import { useSyncStatus } from './composables/useSyncStatus'

const syncRunning = ref(false)
const lastSyncResult = ref(null)

const { lastAutoSync, lastManualSync, fetchAllLatestSyncs } = useSyncStatus()

const handleConfigLoaded = ({ configs, docId }) => {
  fetchAllLatestSyncs(configs, docId).catch(() => {})
}

const handleSyncStarted = () => {
  lastSyncResult.value = null
}

const handleSyncFinished = (result) => {
  lastSyncResult.value = {
    status: result.status === 'completed' ? 'success' : 'error',
    successCount: result.success_count,
    errorCount: result.error_count,
    timestamp: result.timestamp,
    syncType: 'manual',
    syncReason: result.sync_reason || null,
  }
}
</script>

<template>
  <header>
    <div class="wrapper">
      <template v-if="!syncRunning">
        <SyncResultBanner
          v-if="lastSyncResult"
          :status="lastSyncResult.status"
          :success-count="lastSyncResult.successCount"
          :error-count="lastSyncResult.errorCount"
          :timestamp="lastSyncResult.timestamp"
          :sync-type="lastSyncResult.syncType"
          :sync-reason="lastSyncResult.syncReason"
          class="fr-mb-4w"
        />
        <template v-else>
          <SyncResultBanner
            v-if="lastAutoSync"
            :status="lastAutoSync.status"
            :success-count="lastAutoSync.success_count"
            :error-count="lastAutoSync.error_count"
            :timestamp="lastAutoSync.timestamp"
            sync-type="auto"
            class="fr-mb-4w"
          />
          <SyncResultBanner
            v-if="lastManualSync"
            :status="lastManualSync.status"
            :success-count="lastManualSync.success_count"
            :error-count="lastManualSync.error_count"
            :timestamp="lastManualSync.timestamp"
            sync-type="manual"
            class="fr-mb-4w"
          />
        </template>
      </template>
      <SyncProgress
        @sync-running-changed="syncRunning = $event"
        @sync-started="handleSyncStarted"
        @sync-finished="handleSyncFinished"
      />
      <OTPForm
        :sync-running="syncRunning"
        @config-loaded="handleConfigLoaded"
      />
    </div>
  </header>
</template>

<style scoped>
</style>
