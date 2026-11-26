import { loadGristPluginApi } from './gristPluginApi'

const TOKEN_ACQUISITION_TIMEOUT_MS = 2000
const TOKEN_EXPIRY_MARGIN_MS = 60 * 1000

let tokenState = null
let readyRequested = false

export const decodeWidgetTokenIdentity = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return null
  }
}

const resolveTokenExpiresAt = (tokenInfo, identity) => {
  if (identity && typeof identity.exp === 'number')
    return identity.exp * 1000

  if (typeof tokenInfo.ttlMsecs === 'number')
    return Date.now() + tokenInfo.ttlMsecs

  return Date.now() + TOKEN_EXPIRY_MARGIN_MS
}

const isCurrentTokenUsable = () =>
  tokenState !== null && Date.now() < tokenState.expiresAt - TOKEN_EXPIRY_MARGIN_MS

export const clearWidgetToken = () => {
  tokenState = null
}

const withAcquisitionTimeout = (promise) => new Promise((resolve) => {
  const timer = setTimeout(() => resolve(null), TOKEN_ACQUISITION_TIMEOUT_MS)
  promise.then(
    (value) => {
      clearTimeout(timer)
      resolve(value)
    },
    () => {
      clearTimeout(timer)
      resolve(null)
    }
  )
})

const requestGristReady = (grist) => {
  if (readyRequested) return

  readyRequested = true
  if (typeof grist.ready === 'function')
    grist.ready({ requiredAccess: 'full' })
}

export const getWidgetToken = async () => {
  if (isCurrentTokenUsable()) return tokenState

  const grist = await loadGristPluginApi()
  if (!grist || typeof grist.docApi === 'undefined')
    return null

  try {
    requestGristReady(grist)
    const tokenInfo = await withAcquisitionTimeout(grist.docApi.getAccessToken({ readOnly: false }))
    if (!tokenInfo || !tokenInfo.token) return null

    const identity = decodeWidgetTokenIdentity(tokenInfo.token)

    tokenState = {
      token: tokenInfo.token,
      baseUrl: tokenInfo.baseUrl,
      expiresAt: resolveTokenExpiresAt(tokenInfo, identity),
      readOnly: identity !== null && identity.readOnly === true
    }

    return tokenState
  } catch (error) {
    console.warn('Jeton widget Grist indisponible :', error)

    return null
  }
}

export const isWidgetReadOnly = async () => {
  const tokenInfo = await getWidgetToken()
  if (!tokenInfo) return false

  return tokenInfo.readOnly === true
}

export const getGristContext = async () => {
  if (!(await loadGristPluginApi()))
    throw new Error('grist not available')

  try {
    const tokenInfo = await getWidgetToken()
    if (!tokenInfo)
      throw new Error('Impossible de récupérer le jeton d’accès Grist')

    const {docId, userId} = decodeWidgetTokenIdentity(tokenInfo.token) || {}
    const baseUrl = getApiBaseUrlFromDocBaseUrl(tokenInfo.baseUrl)

    if (!userId || !docId)
      throw new Error('Impossible de récupérer le user id ou le doc id')

    const params = `?grist_base_url=${encodeURIComponent(baseUrl)}`

    return { params, userId, docId, baseUrl }
  } catch (error) {
    console.warn('Contexte Grist non disponible ou erreur :', error)
    throw new Error('Veuillez donner au widget l’accès complet au document', { cause: error })
  }
}

export const getApiBaseUrlFromDocBaseUrl = (docBaseUrl) => docBaseUrl.match(/^(.+?\/api)/)?.[1]
