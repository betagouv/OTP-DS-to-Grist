const TOKEN_ACQUISITION_TIMEOUT_MS = 2000
const TOKEN_EXPIRY_MARGIN_MS = 60 * 1000

let tokenState = null
let readyRequested = false

const decodeWidgetTokenClaims = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return null
  }
}

const resolveTokenExpiresAt = (tokenInfo) => {
  const claims = decodeWidgetTokenClaims(tokenInfo.token)
  if (claims && typeof claims.exp === 'number')
    return claims.exp * 1000

  if (typeof tokenInfo.ttlMsecs === 'number')
    return Date.now() + tokenInfo.ttlMsecs

  return Date.now() + TOKEN_EXPIRY_MARGIN_MS
}

const isCurrentTokenUsable = () =>
  tokenState !== null && Date.now() < tokenState.expiresAt - TOKEN_EXPIRY_MARGIN_MS

const clearWidgetToken = () => {
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

const requestGristReady = () => {
  if (readyRequested) return

  readyRequested = true
  if (typeof grist !== 'undefined' && typeof grist.ready === 'function')
    grist.ready({ requiredAccess: 'full' })
}

const getWidgetToken = async () => {
  if (isCurrentTokenUsable()) return tokenState

  if (typeof grist === 'undefined' || typeof grist.docApi === 'undefined')
    return null

  try {
    requestGristReady()
    const tokenInfo = await withAcquisitionTimeout(grist.docApi.getAccessToken({ readOnly: false }))
    if (!tokenInfo || !tokenInfo.token) return null

    tokenState = {
      token: tokenInfo.token,
      baseUrl: tokenInfo.baseUrl,
      expiresAt: resolveTokenExpiresAt(tokenInfo)
    }

    return tokenState
  } catch (error) {
    console.warn('Jeton widget Grist indisponible :', error)
    return null
  }
}

const getGristContext = async () => {
  if (typeof grist === 'undefined')
    throw new Error('grist not available')

  try {
    const tokenInfo = await getWidgetToken()
    if (!tokenInfo)
      throw new Error('Impossible de récupérer le jeton d’accès Grist')

    const {docId, userId} = decodeWidgetTokenClaims(tokenInfo.token) || {}
    const baseUrl = getApiBaseUrlFromDocBaseUrl(tokenInfo.baseUrl)

    if (!userId || !docId)
      throw new Error('Impossible de récupérer le user id ou le doc id')

    const params = `?grist_user_id=${
                      encodeURIComponent(userId)
                    }&grist_doc_id=${
                      encodeURIComponent(docId)
                    }`

    return { params, userId, docId, baseUrl }
  } catch (error) {
    console.warn('Contexte Grist non disponible ou erreur :', error)
    throw new Error('Veuillez donner au widget l’accès complet au document')
  }
}

const getApiBaseUrlFromDocBaseUrl = (docBaseUrl) => docBaseUrl.match(/^(.+?\/api)/)?.[1]

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    getGristContext,
    getApiBaseUrlFromDocBaseUrl,
    getWidgetToken,
    clearWidgetToken,
    decodeWidgetTokenClaims
  }
}
