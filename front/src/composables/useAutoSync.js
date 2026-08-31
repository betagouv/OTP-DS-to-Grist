import { ref } from 'vue'
import { api } from '../utils/InternalApi'
import { useNotification } from './useNotification'

export const useAutoSync = () => {
  const scheduleEnabled = ref(false)
  const scheduleLoading = ref(false)
  const { notify } = useNotification()

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

  const toggleSchedule = async (otpConfigId, enabled, hasGristKey) => {
    if (!hasGristKey) {
      notify("Clé API Grist requise pour activer la synchronisation automatique", 'error')
      scheduleEnabled.value = !enabled

      return false
    }

    try {
      const result = enabled
        ? await api.enableSchedule(otpConfigId)
        : await api.disableSchedule(otpConfigId)

      if (result.success) {
        scheduleEnabled.value = enabled
        const status = enabled ? 'activée' : 'désactivée'
        notify(`Synchronisation automatique ${status}`, 'success')

        return true
      }

      notify(result.message || 'Erreur lors de la modification', 'error')
      scheduleEnabled.value = !enabled

      return false

    } catch {
      notify('Erreur lors de la modification de la synchronisation automatique', 'error')
      scheduleEnabled.value = !enabled

      return false
    }
  }

  return { scheduleEnabled, scheduleLoading, fetchSchedule, toggleSchedule }
}
