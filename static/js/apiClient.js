const WIDGET_TOKEN_HEADER = 'X-Grist-Widget-Token'

const gristContext = (typeof module !== 'undefined' && module.exports)
  ? require('./gristContext.js')
  : null

const getToken = () => (gristContext ? gristContext.getWidgetToken() : getWidgetToken())

const clearToken = () => (gristContext ? gristContext.clearWidgetToken() : clearWidgetToken())

const buildRequestWithToken = (input, init, token) => {
  const headers = new Headers(input instanceof Request ? input.headers : undefined)
  if (init && init.headers)
    new Headers(init.headers).forEach((value, key) => headers.set(key, value))
  headers.set(WIDGET_TOKEN_HEADER, token)

  if (input instanceof Request) {
    const extraInit = { ...init }
    delete extraInit.headers

    return { input: new Request(input, { headers }), init: Object.keys(extraInit).length ? extraInit : undefined }
  }

  return { input, init: { ...init, headers } }
}

const apiFetch = async (input, init) => {
  const tokenInfo = await getToken()
  if (!tokenInfo)
    return fetch(input, init)

  const firstAttempt = buildRequestWithToken(input, init, tokenInfo.token)
  let response = await fetch(firstAttempt.input, firstAttempt.init)

  if (response.status === 401) {
    clearToken()
    const refreshedToken = await getToken()
    if (refreshedToken) {
      const secondAttempt = buildRequestWithToken(input, init, refreshedToken.token)
      response = await fetch(secondAttempt.input, secondAttempt.init)
    }
  }

  return response
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    apiFetch,
    WIDGET_TOKEN_HEADER
  }
}
