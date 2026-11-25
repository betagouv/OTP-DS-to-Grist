import { clearWidgetToken, getApiBaseUrlFromDocBaseUrl, getWidgetToken } from './gristContext'

export const WIDGET_TOKEN_HEADER = 'X-Grist-Widget-Token'
const GRIST_BASE_URL_HEADER = 'X-Grist-Base-Url'

const deriveBaseUrl = (docBaseUrl) => {
  if (!docBaseUrl) return null

  return getApiBaseUrlFromDocBaseUrl(docBaseUrl) || null
}

const buildRequestWithToken = (input, init, token, baseUrl) => {
  const headers = new Headers(input instanceof Request ? input.headers : undefined)
  if (init && init.headers)
    new Headers(init.headers).forEach((value, key) => headers.set(key, value))
  headers.set(WIDGET_TOKEN_HEADER, token)
  if (baseUrl)
    headers.set(GRIST_BASE_URL_HEADER, baseUrl)

  if (input instanceof Request) {
    const extraInit = { ...init }
    delete extraInit.headers

    return { input: new Request(input, { headers }), init: Object.keys(extraInit).length ? extraInit : undefined }
  }

  return { input, init: { ...init, headers } }
}

const buildReadOnlyResponse = () => new Response(
  JSON.stringify({ success: false, message: 'Accès éditeur requis' }),
  { status: 403, headers: { 'Content-Type': 'application/json' } }
)

export const apiFetch = async (input, init) => {
  const tokenInfo = await getWidgetToken()
  if (!tokenInfo)
    return fetch(input, init)

  if (tokenInfo.readOnly === true)
    return buildReadOnlyResponse()

  const baseUrl = deriveBaseUrl(tokenInfo.baseUrl)
  const firstAttempt = buildRequestWithToken(input, init, tokenInfo.token, baseUrl)
  let response = await fetch(firstAttempt.input, firstAttempt.init)

  if (response.status === 401) {
    clearWidgetToken()
    const refreshedToken = await getWidgetToken()
    if (refreshedToken) {
      const secondAttempt = buildRequestWithToken(
        input, init, refreshedToken.token, deriveBaseUrl(refreshedToken.baseUrl)
      )
      response = await fetch(secondAttempt.input, secondAttempt.init)
    }
  }

  return response
}
