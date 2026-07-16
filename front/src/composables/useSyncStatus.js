import { ref } from 'vue'
import { api } from '../utils/InternalApi'

export const useSyncStatus = () => {
  const lastAutoSync = ref(null)
  const lastManualSync = ref(null)


  const fetchLatestSync = async (otpConfigId) => {
    const data = await api.getSyncLogLatest(otpConfigId)
    if (data.success) {
      lastAutoSync.value = data.auto || null
      lastManualSync.value = data.manual || null
    }
  }

  const fetchAllLatestSyncs = async (configs) => {
    const validConfigs = configs.filter(c => c?.otp_config_id)
    if (validConfigs.length === 0) return

    const results = await Promise.all(
      validConfigs.map(c => api.getSyncLogLatest(c.otp_config_id))
    )

    const autos = []
    const manuals = []

    for (const data of results) {
      if (!data.success) continue
      if (data.auto) autos.push(data.auto)
      if (data.manual) manuals.push(data.manual)
    }

    lastAutoSync.value = mergeSyncs(autos)
    lastManualSync.value = mergeSyncs(manuals)
  }

  const mergeSyncs = (syncs) => {
    if (syncs.length === 0) return null
    if (syncs.length === 1) return syncs[0]
    return syncs.reduce((latest, current) =>
      new Date(current.timestamp) > new Date(latest.timestamp) ? current : latest
    )
  }

  return { lastAutoSync, lastManualSync, fetchLatestSync, fetchAllLatestSyncs }
}
