import { ref } from 'vue'
import { api } from '../utils/InternalApi'

export const useAutoSync = () => {
  const scheduleEnabled = ref(false)
  const scheduleLoading = ref(false)

  const fetchSchedule = async (otpConfigId) => {
    scheduleLoading.value = true

    try {
      const result = await api.getSchedule(otpConfigId)
      scheduleEnabled.value = result.enabled || false
    } catch {
      scheduleEnabled.value = false
    } finally {
      scheduleLoading.value = false
    }
  }

  return { scheduleEnabled, scheduleLoading, fetchSchedule }
}
