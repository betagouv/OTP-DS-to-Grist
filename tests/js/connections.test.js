/** @jest-environment jsdom */

const {
  testDemarchesConnection,
  testGristConnection,
  testWebSocket,
  testExternalConnections
} = require('../../static/js/connections.js')

jest.mock('../../static/js/notifications.js', () => ({
  showNotification: jest.fn()
}))

describe('testDemarchesConnection', () => {
  beforeEach(() => {
    // Context DOM elements
    document.body.innerHTML = `
      <input id="ds_api_token">
      <input id="demarche_number">

      <div class="hide">
        <div id="ds_test_result"></div>
      </div>
    `

    // Mock fetch
    global.fetch = jest.fn()

    // Mock global variables
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })
    global.console.error = jest.fn()
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it(
    'should test connection successfully with token from input',
    async () => {
      document.getElementById('ds_api_token').value = 'test-token'
      document.getElementById('demarche_number').value = '123'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: true, message: 'Connexion réussie' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testDemarchesConnection()

      const resultDiv = document.getElementById('ds_test_result')

      expect(global.fetch).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          type: 'demarches',
          api_token: 'test-token',
          api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
          demarche_number: '123'
        })
      }))
      expect(resultDiv.innerHTML).toContain('Connexion réussie')
      expect(resultDiv.innerHTML).toContain('fr-alert--success')
      expect(showNotification).toHaveBeenCalledWith('Connexion réussie', 'success')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when connection fails',
    async () => {
      document.getElementById('ds_api_token').value = 'test-token'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: false, message: 'Erreur de connexion' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testDemarchesConnection()

      const resultDiv = document.getElementById('ds_test_result')

      expect(resultDiv.innerHTML).toContain('Erreur de connexion')
      expect(resultDiv.innerHTML).toContain('fr-alert--error')
      expect(showNotification).toHaveBeenCalledWith('Erreur de connexion', 'error')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should reload config when no token in input but config exists',
    async () => {
      global.currentConfig = { ds_api_token_exists: true }

      const mockConfigResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ configs: [{ has_ds_token: true }] })
      }
      global.fetch.mockResolvedValue(mockConfigResponse)

      const result = await testDemarchesConnection()

      expect(global.getGristContext).toHaveBeenCalled()
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).not.toHaveBeenCalledWith('/api/test-connection', expect.any(Object))
      expect(result).toBe(true)
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no token available',
    async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => ({ configs: [{ has_ds_token: false }] })
      })

      await testDemarchesConnection()

      expect(document.getElementById('ds_test_result').innerHTML).toContain('Token API requis')
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).not.toHaveBeenCalledWith('/api/test-connection', expect.any(Object))
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should handle fetch error',
    async () => {
      document.getElementById('ds_api_token').value = 'test-token'
      global.fetch.mockRejectedValue(new Error('Network error'))

      await testDemarchesConnection()

      expect(document.getElementById('ds_test_result').innerHTML).toContain('Erreur de connexion: Network error')
      expect(showNotification).toHaveBeenCalledWith('Erreur lors du test de connexion', 'error')
      expect(global.console.error).toHaveBeenCalledWith('Erreur lors du test DS:', expect.any(Error))
    }
  )
})

describe('testGristConnection', () => {

  beforeEach(() => {
    // Context DOM elements
    document.body.innerHTML = `
      <input id="grist_api_key">
      <input id="grist_base_url">
      <input id="grist_doc_id">

      <div class="hide">
        <div id="grist_test_result"></div>
      </div>
    `

    // Mock fetch
    global.fetch = jest.fn()

    // Mock global variables
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })
    global.console.error = jest.fn()
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it(
    'should test connection successfully with key from input', async () => {
      document.getElementById('grist_api_key').value  = 'test-key'
      document.getElementById('grist_base_url').value = 'https://grist.example.com'
      document.getElementById('grist_doc_id').value   = 'doc123'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: true, message: 'Connexion Grist réussie' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testGristConnection()

      const resultDiv = document.getElementById('grist_test_result')

      expect(global.fetch).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          type: 'grist',
          base_url: 'https://grist.example.com',
          api_key: 'test-key',
          doc_id: 'doc123'
        })
      }))
      expect(resultDiv.innerHTML).toContain('Connexion Grist réussie')
      expect(resultDiv.innerHTML).toContain('fr-alert--success')
      expect(showNotification).toHaveBeenCalledWith('Connexion Grist réussie', 'success')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when connection fails', async () => {
      document.getElementById('grist_api_key').value  = 'test-key'
      document.getElementById('grist_base_url').value = 'https://grist.example.com'
      document.getElementById('grist_doc_id').value   = 'doc123'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: false, message: 'Erreur Grist' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testGristConnection()

      const resultDiv = document.getElementById('grist_test_result')

      expect(resultDiv.innerHTML).toContain('Erreur Grist')
      expect(resultDiv.innerHTML).toContain('fr-alert--error')
      expect(showNotification).toHaveBeenCalledWith('Erreur Grist', 'error')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should reload config when no key in input but config exists', async () => {
      document.getElementById('grist_api_key').value  = ''
      document.getElementById('grist_base_url').value = 'https://grist.example.com'
      document.getElementById('grist_doc_id').value   = 'doc123'

      const mockConfigResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ configs: [{ has_grist_key: true }] })
      }
      global.fetch.mockResolvedValue(mockConfigResponse)

      const result = await testGristConnection()

      expect(global.getGristContext).toHaveBeenCalled()
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).not.toHaveBeenCalledWith('/api/test-connection', expect.any(Object))
      expect(result).toBe(true)
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no key available', async () => {
      document.getElementById('grist_api_key').value  = ''
      document.getElementById('grist_base_url').value = 'https://grist.example.com'
      document.getElementById('grist_doc_id').value   = 'doc123'

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => ({ configs: [{ has_grist_key: false }] })
      })

      await testGristConnection()

      expect(document.getElementById('grist_test_result').innerHTML).toContain('Clé API Grist requise')
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).not.toHaveBeenCalledWith('/api/test-connection', expect.any(Object))
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no base URL', async () => {
      document.getElementById('grist_api_key').value  = 'test-key'
      document.getElementById('grist_base_url').value = ''
      document.getElementById('grist_doc_id').value   = 'doc123'

      await testGristConnection()

      expect(document.getElementById('grist_test_result').innerHTML).toContain('URL de base Grist requise')
      expect(global.fetch).not.toHaveBeenCalled()
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no doc ID', async () => {
      document.getElementById('grist_api_key').value  = 'test-key'
      document.getElementById('grist_base_url').value = 'https://grist.example.com'
      document.getElementById('grist_doc_id').value   = ''

      await testGristConnection()

      expect(document.getElementById('grist_test_result').innerHTML).toContain('ID du document Grist requis')
      expect(global.fetch).not.toHaveBeenCalled()
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should handle fetch error', async () => {
      document.getElementById('grist_api_key').value = 'test-key'
      document.getElementById('grist_base_url').value = 'https://grist.example.com'
      document.getElementById('grist_doc_id').value = 'doc123'
      global.fetch.mockRejectedValue(new Error('Network error'))

      await testGristConnection()

      expect(document.getElementById('grist_test_result').innerHTML).toContain('Erreur de connexion: Network error')
      expect(showNotification).toHaveBeenCalledWith('Erreur lors du test de connexion', 'error')
      expect(global.console.error).toHaveBeenCalledWith('Erreur lors du test Grist:', expect.any(Error))
    }
  )
})

describe('testWebSocket', () => {
  let mockStatusDiv, mockSocket

  beforeEach(() => {
    // Mock DOM
    mockStatusDiv = { innerHTML: '' }
    document.getElementById = jest.fn().mockReturnValue(mockStatusDiv)

    // Mock Socket.IO
    mockSocket = {
      on: jest.fn(),
      disconnect: jest.fn(),
      id: 'test-socket-id'
    }
    global.io = jest.fn().mockReturnValue(mockSocket)

    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.useRealTimers()
    jest.clearAllMocks()
  })

  it(
    'displays success message on WebSocket connect',
    () => {
      testWebSocket()

      // Trigger connect event
      const connectCallback = mockSocket.on.mock.calls.find(call => call[0] === 'connect')[1]
      connectCallback()

      expect(mockStatusDiv.innerHTML).toContain('WebSocket connecté avec succès')
      expect(mockStatusDiv.innerHTML).toContain('test-socket-id')
      expect(mockSocket.disconnect).toHaveBeenCalled()
    }
  )

  it(
    'displays error message on WebSocket connect_error',
    () => {
      const mockError = { message: 'Connection failed' }
      testWebSocket()

      // Trigger connect_error event
      const errorCallback = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')[1]
      errorCallback(mockError)

      expect(mockStatusDiv.innerHTML).toContain('Erreur de connexion WebSocket')
      expect(mockStatusDiv.innerHTML).toContain('Connection failed')
    }
  )

  it(
    'displays timeout warning when connection takes too long',
    () => {
      testWebSocket()

      // Advance time past timeout
      jest.advanceTimersByTime(5000)

      expect(mockStatusDiv.innerHTML).toContain('Timeout de connexion WebSocket')
      expect(mockSocket.disconnect).toHaveBeenCalled()
    }
  )

  it(
    'clears timeout on successful connection',
    () => {
      testWebSocket()

      // Trigger connect before timeout
      const connectCallback = mockSocket.on.mock.calls.find(call => call[0] === 'connect')[1]
      connectCallback()

      // Timeout should be cleared, so advancing time shouldn't trigger timeout
      jest.advanceTimersByTime(5000)

      expect(mockStatusDiv.innerHTML).toContain('WebSocket connecté avec succès')
    }
  )
})

describe('testExternalConnections', () => {
  let mockResultDiv

  beforeEach(() => {
    mockResultDiv = { innerHTML: '' }
    document.getElementById = jest.fn().mockReturnValue(mockResultDiv)
    global.fetch = jest.fn()
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it(
    'tests both connections successfully',
    async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            configs: [{
              otp_config_id: 1,
              ds_api_token: 'valid-token',
              demarche_number: '123',
              grist_api_key: 'valid-key',
              grist_base_url: 'https://grist.example.com',
              grist_doc_id: 'doc123'
            }]
          })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            message: '2/2 tests réussis',
            results: [
              { type: 'demarches', success: true, message: 'DS OK' },
              { type: 'grist', success: true, message: 'Grist OK' }
            ]
          })
        })

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Démarches Simplifiées')
      expect(mockResultDiv.innerHTML).toContain('DS OK')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--success')
    }
  )

  it(
    'shows partial failure results',
    async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            configs: [{
              otp_config_id: 1,
              ds_api_token: 'valid-token',
              demarche_number: '123',
              grist_api_key: 'valid-key',
              grist_base_url: 'https://grist.example.com',
              grist_doc_id: 'doc123'
            }]
          })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: false,
            message: '1/2 tests réussis',
            results: [
              { type: 'demarches', success: true, message: 'DS OK' },
              { type: 'grist', success: false, message: 'Grist failed' }
            ]
          })
        })

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Grist')
      expect(mockResultDiv.innerHTML).toContain('Grist failed')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--error')
    }
  )

  it(
    'handles backend errors',
    async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            configs: [{
              otp_config_id: 1,
              ds_api_token: 'valid-token',
              demarche_number: '123',
              grist_api_key: 'valid-key',
              grist_base_url: 'https://grist.example.com',
              grist_doc_id: 'doc123'
            }]
          })
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 400,
          json: () => Promise.resolve({
            success: false,
            message: 'Token API Démarches Simplifiées non configuré'
          })
        })

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Token API Démarches Simplifiées non configuré')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--error')
    }
  )

  it(
    'handles fetch errors gracefully',
    async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'))

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Erreur: Network error')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--error')
    }
  )

  it(
    'shows success notification for all successful tests',
    async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            configs: [{
              otp_config_id: 1,
              ds_api_token: 'valid-token',
              demarche_number: '123',
              grist_api_key: 'valid-key',
              grist_base_url: 'https://grist.example.com',
              grist_doc_id: 'doc123'
            }]
          })
      })

      // Deuxième appel : POST /api/test-connection
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          message: '2/2 tests réussis',
          results: [
            { type: 'demarches', success: true, message: 'DS OK' },
            { type: 'grist', success: true, message: 'Grist OK' }
          ]
        })
      })

      await testExternalConnections()

      expect(showNotification).toHaveBeenCalledWith('Tous les tests réussis (2/2)', 'success')
    }
  )

  it(
    'shows warning notification for partial success',
    async () => {
      // Premier appel : GET /api/config
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          configs: [
            {
              otp_config_id: 1,
              ds_api_token: 'valid-token',
              demarche_number: '123',
              grist_api_key: 'valid-key',
              grist_base_url: 'https://grist.example.com',
              grist_doc_id: 'doc123'
            }
          ]
        })
      })

      // Deuxième appel : POST /api/test-connection
      fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: false,
          message: '1/2 tests réussis',
          results: [
            { type: 'demarches', success: true, message: 'DS OK' },
            { type: 'grist', success: false, message: 'Grist failed' }
          ]
        })
      })

      await testExternalConnections()

      expect(showNotification).toHaveBeenCalledWith('1/2 connexions réussies', 'warning')
    }
  )
})
