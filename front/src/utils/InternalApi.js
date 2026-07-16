const ROUTES = {
  CONFIG: '/api/config',
  START_SYNC: '/api/start-sync',
  SYNC_LOG_LATEST: '/api/sync-log/latest',
  TEST_CONNECTION: '/api/test-connection'
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

class InternalApi {
  async getConfig(params) {
    const response = await fetch(`${ROUTES.CONFIG}${params}`)
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)
    return response.json()
  }

  async saveConfig(config) {
    const response = await fetch(ROUTES.CONFIG, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(config)
    })
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)
    return response.json()
  }

  async deleteConfig(otpConfigId) {
    const response = await fetch(`${ROUTES.CONFIG}/${otpConfigId}`, {
      method: 'DELETE'
    })
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)
    return response.json()
  }

  async startSync(otpConfigId) {
    const response = await fetch(ROUTES.START_SYNC, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ otp_config_id: otpConfigId })
    })
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)
    return response.json()
  }

  async testConnection(body) {
    const response = await fetch(ROUTES.TEST_CONNECTION, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body)
    })
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)
    return response.json()
  }

  async getSyncLogLatest(otpConfigId) {
    const response = await fetch(`${ROUTES.SYNC_LOG_LATEST}?otp_config_id=${otpConfigId}`)
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`)
    return response.json()
  }
}

export const api = new InternalApi()
