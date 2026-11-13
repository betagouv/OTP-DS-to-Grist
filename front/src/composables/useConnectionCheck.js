import { ref, computed } from 'vue'
import { api } from '../utils/InternalApi'

export const CONNECTION_STATUS = Object.freeze({
  UNTESTED: 'untested',
  PENDING: 'pending',
  VERIFIED: 'verified',
  FAILED: 'failed'
})

/**
 * État d'un test de connexion (Grist ou Démarche numérique).
 *
 * `networkErrorMessage` est le message retenu quand la requête elle-même
 * échoue (réseau, serveur) ; l'erreur est ensuite relancée pour que
 * l'appelant la présente.
 */
export const useConnectionCheck = ({ networkErrorMessage = null } = {}) => {
  const status = ref(CONNECTION_STATUS.UNTESTED)
  const message = ref(null)

  // Format attendu par les parents (événement error-update) : null tant que
  // rien n'est vérifié, '' une fois vérifié, le message en cas d'échec
  const errorMessage = computed(() => {
    if (status.value === CONNECTION_STATUS.VERIFIED) return ''
    if (status.value === CONNECTION_STATUS.FAILED) return message.value

    return null
  })

  const check = async (body) => {
    status.value = CONNECTION_STATUS.PENDING
    message.value = null

    let result
    try {
      result = await api.testConnection(body)
    } catch (error) {
      status.value = CONNECTION_STATUS.FAILED
      message.value = networkErrorMessage
      throw error
    }

    status.value = result.success ? CONNECTION_STATUS.VERIFIED : CONNECTION_STATUS.FAILED
    message.value = result.success ? null : result.message

    return result
  }

  const reset = () => {
    status.value = CONNECTION_STATUS.UNTESTED
    message.value = null
  }

  return { status, errorMessage, check, reset }
}
