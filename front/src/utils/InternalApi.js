const ROUTES = {
  CONFIG: '/api/config',
  GROUPS: '/api/groups',
  SCHEDULE: '/api/schedule',
  START_SYNC: '/api/start-sync',
  START_SYNC_ALL: '/api/start-sync-all',
  SYNC_LOG_LATEST: '/api/sync-log/latest',
  SYNC_LOG_LATEST_BY_DEMARCHE: '/api/sync-log/latest-by-demarche',
  TEST_CONNECTION: '/api/test-connection'
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

// Message d'erreur renvoyé par le serveur ({ message }), s'il y en a un lisible
const readServerMessage = async (response) => {
  try {
    const body = await response.json()
    return typeof body?.message === 'string' ? body.message : null
  } catch {
    return null
  }
}

const request = async (url, options) => {
  const doFetch = typeof apiFetch !== 'undefined' ? apiFetch : fetch
  const response = options === undefined ? await doFetch(url) : await doFetch(url, options)
  if (!response.ok) {
    throw Object.assign(new Error(`Erreur HTTP ${response.status}`), {
      serverMessage: await readServerMessage(response)
    })
  }

  return response.json()
}

class InternalApi {
  getConfig(params) {
    return request(`${ROUTES.CONFIG}${params}`)
  }

  saveConfig(config) {
    return request(ROUTES.CONFIG, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(config)
    })
  }

  deleteConfig(otpConfigId) {
    return request(`${ROUTES.CONFIG}/${otpConfigId}`, {
      method: 'DELETE'
    })
  }

  startSync(otpConfigId) {
    return request(ROUTES.START_SYNC, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ otp_config_id: otpConfigId })
    })
  }

  startSyncAll() {
    return request(ROUTES.START_SYNC_ALL, { method: 'POST' })
  }

  testConnection(body) {
    return request(ROUTES.TEST_CONNECTION, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body)
    })
  }

  getSyncLogLatest(otpConfigId) {
    return request(`${ROUTES.SYNC_LOG_LATEST}?otp_config_id=${otpConfigId}`)
  }

  getLatestSyncsByDemarche() {
    return request(ROUTES.SYNC_LOG_LATEST_BY_DEMARCHE)
  }

  getSyncLogLatestByBaseUrl(gristBaseUrl) {
    return request(`${ROUTES.SYNC_LOG_LATEST}?grist_base_url=${encodeURIComponent(gristBaseUrl)}`)
  }

  async getGroups(otpConfigId) {
    const groups = await request(`${ROUTES.GROUPS}?otp_config_id=${otpConfigId}`)

    return groups.map(([number, label]) => ({ number, label }))
  }

  getSchedule(otpConfigId) {
    return request(`${ROUTES.SCHEDULE}?otp_config_id=${otpConfigId}`)
  }

  enableSchedule(otpConfigId) {
    return request(ROUTES.SCHEDULE, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ otp_config_id: otpConfigId })
    })
  }

  disableSchedule(otpConfigId) {
    return request(ROUTES.SCHEDULE, {
      method: 'DELETE',
      headers: JSON_HEADERS,
      body: JSON.stringify({ otp_config_id: otpConfigId })
    })
  }
}

export const api = new InternalApi()
