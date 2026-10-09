const { apiFetch, WIDGET_TOKEN_HEADER } = require('../../static/js/apiClient.js')
const { clearWidgetToken } = require('../../static/js/gristContext.js')

const originalFetch = global.fetch

const createTokenWithExp = (expInSecondsFromNow, userId = '1', docId = 'd') => {
  const payload = { userId, docId, exp: Math.floor(Date.now() / 1000) + expInSecondsFromNow }
  return `header.${Buffer.from(JSON.stringify(payload)).toString('base64')}.signature`
}

describe('apiFetch', () => {
  beforeEach(() => {
    clearWidgetToken()
    delete global.grist
    global.fetch = jest.fn().mockResolvedValue({ status: 200 })
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('passes through without a widget token', async () => {
    await apiFetch('/api/config')

    expect(global.fetch).toHaveBeenCalledWith('/api/config', undefined)
  })

  it('attaches the widget token header when a token is available', async () => {
    const token = createTokenWithExp(900)
    global.grist = {
      ready: jest.fn(),
      docApi: { getAccessToken: jest.fn().mockResolvedValue({ token, baseUrl: 'http://x/api', ttlMsecs: 900000 }) }
    }

    await apiFetch('/api/config')

    const [, init] = global.fetch.mock.calls[0]
    expect(new Headers(init.headers).get(WIDGET_TOKEN_HEADER)).toBe(token)
  })

  it('retries once with a fresh token after a 401', async () => {
    global.fetch
      .mockResolvedValueOnce({ status: 401 })
      .mockResolvedValueOnce({ status: 200 })
    const getAccessToken = jest.fn().mockResolvedValue({
      token: createTokenWithExp(900),
      baseUrl: 'http://x/api',
      ttlMsecs: 900000
    })
    global.grist = { ready: jest.fn(), docApi: { getAccessToken } }

    const response = await apiFetch('/api/start-sync', { method: 'POST' })

    expect(response.status).toBe(200)
    expect(global.fetch).toHaveBeenCalledTimes(2)
    expect(getAccessToken).toHaveBeenCalledTimes(2)
  })
})
