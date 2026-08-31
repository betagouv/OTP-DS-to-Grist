const ROUTES = {
  CONFIG: '/api/config',
  GROUPS: '/api/groups',
  SCHEDULE: '/api/schedule',
  START_SYNC: '/api/start-sync',
  SYNC_LOG_LATEST: '/api/sync-log/latest',
  TEST_CONNECTION: '/api/test-connection'
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

const request = async (url, options) => {
  const response = options === undefined ? await fetch(url) : await fetch(url, options)
  if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)

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

  getSyncLogLatestByDocId(docId) {
    return request(`${ROUTES.SYNC_LOG_LATEST}?grist_doc_id=${docId}`)
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
