import { ref } from 'vue'
import { api } from '../utils/InternalApi'

export const useAutoSync = () => {
  const scheduleEnabled = ref(false)
  const scheduleLoading = ref(false)
  const nextRun = ref(null)

  const fetchSchedule = async (otpConfigId) => {
    scheduleLoading.value = true

    try {
      const result = await api.getSchedule(otpConfigId)
      scheduleEnabled.value = result.enabled || false
      nextRun.value = result.next_run || null
    } catch {
      scheduleEnabled.value = false
      nextRun.value = null
    } finally {
      scheduleLoading.value = false
    }
  }

  const setScheduleEnabled = (value) => {
    scheduleEnabled.value = value
    if (!value) nextRun.value = null
  }

  return { scheduleEnabled, scheduleLoading, nextRun, fetchSchedule, setScheduleEnabled }
}
