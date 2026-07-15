import { ref } from 'vue'

export const useSyncStatus = () => {
  const lastAutoSync = ref(null)
  const lastManualSync = ref(null)

  const fetchLatestSync = async (otpConfigId) => {
    const url = `/api/sync-log/latest?otp_config_id=${otpConfigId}`
    const response = await fetch(url)
    const data = await response.json()
    if (data.success) {
      lastAutoSync.value = data.auto || null
      lastManualSync.value = data.manual || null
    }
  }

  const fetchAllLatestSyncs = async (configs) => {
    const validConfigs = configs.filter(c => c?.otp_config_id)
    if (validConfigs.length === 0) return

    const results = await Promise.all(
      validConfigs.map(c =>
        fetch(`/api/sync-log/latest?otp_config_id=${c.otp_config_id}`).then(r => r.json())
      )
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
