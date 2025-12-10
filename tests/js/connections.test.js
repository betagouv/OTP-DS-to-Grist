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
  let mockResultDiv, mockTokenInput, mockUrlInput, mockDemarcheInput

  beforeEach(() => {
    // Mock DOM elements
    mockResultDiv = {
      innerHTML: ''
    }
    mockTokenInput = { value: '' }
    mockUrlInput = { value: '' }
    mockDemarcheInput = { value: '' }

    global.document = {
      getElementById: jest.fn((id) => {
        switch (id) {
          case 'ds_test_result': return mockResultDiv
          case 'ds_api_token': return mockTokenInput
          case 'demarche_number': return mockDemarcheInput
          default: return null
        }
      })
    }

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
      mockTokenInput.value = 'test-token'
      mockUrlInput.value = 'https://api.example.com'
      mockDemarcheInput.value = '123'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: true, message: 'Connexion réussie' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testDemarchesConnection()

      expect(global.fetch).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          type: 'demarches',
          api_token: 'test-token',
          api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
          demarche_number: '123'
        })
      }))
      expect(mockResultDiv.innerHTML).toContain('Connexion réussie')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--success')
      expect(showNotification).toHaveBeenCalledWith('Connexion réussie', 'success')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when connection fails',
    async () => {
      mockTokenInput.value = 'test-token'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: false, message: 'Erreur de connexion' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testDemarchesConnection()

      expect(mockResultDiv.innerHTML).toContain('Erreur de connexion')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--error')
      expect(showNotification).toHaveBeenCalledWith('Erreur de connexion', 'error')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should reload config when no token in input but config exists',
    async () => {
      mockTokenInput.value = ''
      global.currentConfig = { ds_api_token_exists: true }

      const mockConfigResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ ds_api_token: 'config-token' })
      }
      global.fetch
        .mockResolvedValueOnce(mockConfigResponse) // for config reload
        .mockResolvedValueOnce({
          ok: true,
          json: jest.fn().mockResolvedValue({ success: true, message: 'Connexion réussie' })
        })

      await testDemarchesConnection()

      expect(global.getGristContext).toHaveBeenCalled()
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
        body: JSON.stringify({
          type: 'demarches',
          api_token: 'config-token',
          api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
          demarche_number: ''
        })
      }))
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no token available',
    async () => {
      mockTokenInput.value = ''
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => ({ ds_api_token: '' })
      })

      await testDemarchesConnection()

      expect(mockResultDiv.innerHTML).toContain('Token API requis')
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).not.toHaveBeenCalledWith('/api/test-connection', expect.any(Object))
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should handle fetch error',
    async () => {
      mockTokenInput.value = 'test-token'
      global.fetch.mockRejectedValue(new Error('Network error'))

      await testDemarchesConnection()

      expect(mockResultDiv.innerHTML).toContain('Erreur de connexion: Network error')
      expect(showNotification).toHaveBeenCalledWith('Erreur lors du test de connexion', 'error')
      expect(global.console.error).toHaveBeenCalledWith('Erreur lors du test DS:', expect.any(Error))
    }
  )
})

describe('testGristConnection', () => {
  let mockResultDiv, mockKeyInput, mockUrlInput, mockDocInput

  beforeEach(() => {
    // Mock DOM elements
    mockResultDiv = {
      innerHTML: ''
    }
    mockKeyInput = { value: '' }
    mockUrlInput = { value: '' }
    mockDocInput = { value: '' }

    global.document = {
      getElementById: jest.fn((id) => {
        switch (id) {
          case 'grist_test_result': return mockResultDiv
          case 'grist_api_key': return mockKeyInput
          case 'grist_base_url': return mockUrlInput
          case 'grist_doc_id': return mockDocInput
          default: return null
        }
      })
    }

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
      mockKeyInput.value = 'test-key'
      mockUrlInput.value = 'https://grist.example.com'
      mockDocInput.value = 'doc123'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: true, message: 'Connexion Grist réussie' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testGristConnection()

      expect(global.fetch).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          type: 'grist',
          base_url: 'https://grist.example.com',
          api_key: 'test-key',
          doc_id: 'doc123'
        })
      }))
      expect(mockResultDiv.innerHTML).toContain('Connexion Grist réussie')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--success')
      expect(showNotification).toHaveBeenCalledWith('Connexion Grist réussie', 'success')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when connection fails', async () => {
      mockKeyInput.value = 'test-key'
      mockUrlInput.value = 'https://grist.example.com'
      mockDocInput.value = 'doc123'

      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ success: false, message: 'Erreur Grist' })
      }
      global.fetch.mockResolvedValue(mockResponse)

      await testGristConnection()

      expect(mockResultDiv.innerHTML).toContain('Erreur Grist')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--error')
      expect(showNotification).toHaveBeenCalledWith('Erreur Grist', 'error')
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should reload config when no key in input but config exists', async () => {
      mockKeyInput.value = ''
      mockUrlInput.value = 'https://grist.example.com'
      mockDocInput.value = 'doc123'
      global.currentConfig = { grist_api_key_exists: true }

      const mockConfigResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({ grist_api_key: 'config-key' })
      }
      global.fetch
        .mockResolvedValueOnce(mockConfigResponse)
        .mockResolvedValueOnce({
          ok: true,
          json: jest.fn().mockResolvedValue({ success: true, message: 'Connexion réussie' })
        })

      await testGristConnection()

      expect(global.getGristContext).toHaveBeenCalled()
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
        body: JSON.stringify({
          type: 'grist',
          base_url: 'https://grist.example.com',
          api_key: 'config-key',
          doc_id: 'doc123'
        })
      }))
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no key available', async () => {
      mockKeyInput.value = ''
      mockUrlInput.value = 'https://grist.example.com'
      mockDocInput.value = 'doc123'
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => ({ grist_api_key: '' })
      })

      await testGristConnection()

      expect(mockResultDiv.innerHTML).toContain('Clé API Grist requise')
      expect(global.fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(global.fetch).not.toHaveBeenCalledWith('/api/test-connection', expect.any(Object))
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no base URL', async () => {
      mockKeyInput.value = 'test-key'
      mockUrlInput.value = ''
      mockDocInput.value = 'doc123'

      await testGristConnection()

      expect(mockResultDiv.innerHTML).toContain('URL de base Grist requise')
      expect(global.fetch).not.toHaveBeenCalled()
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should show error when no doc ID', async () => {
      mockKeyInput.value = 'test-key'
      mockUrlInput.value = 'https://grist.example.com'
      mockDocInput.value = ''

      await testGristConnection()

      expect(mockResultDiv.innerHTML).toContain('ID du document Grist requis')
      expect(global.fetch).not.toHaveBeenCalled()
      expect(global.console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'should handle fetch error', async () => {
      mockKeyInput.value = 'test-key'
      mockUrlInput.value = 'https://grist.example.com'
      mockDocInput.value = 'doc123'
      global.fetch.mockRejectedValue(new Error('Network error'))

      await testGristConnection()

      expect(mockResultDiv.innerHTML).toContain('Erreur de connexion: Network error')
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
    'shows warning when no APIs are configured',
    async () => {
      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({
          ds_api_token: '***',
          grist_api_key: '***'
        })
      })

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Aucune API configurée pour le test')
    }
  )

  it(
    'tests DS connection successfully',
    async () => {
      fetch
        .mockResolvedValueOnce({
          json: () => Promise.resolve({
            ds_api_token: 'valid-token',
            demarche_number: '123'
          })
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ success: true, message: 'DS OK' })
        })

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Démarches Simplifiées')
      expect(mockResultDiv.innerHTML).toContain('DS OK')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--success')
    }
  )

  it(
    'tests Grist connection with failure',
    async () => {
      fetch
        .mockResolvedValueOnce({
          json: () => Promise.resolve({
            grist_api_key: 'valid-key',
            grist_base_url: 'https://grist.example.com',
            grist_doc_id: 'doc123'
          })
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ success: false, message: 'Grist failed' })
        })

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Grist')
      expect(mockResultDiv.innerHTML).toContain('Grist failed')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--error')
    }
  )

  it(
    'handles fetch errors gracefully',
    async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'))

      await testExternalConnections()

      expect(mockResultDiv.innerHTML).toContain('Erreur lors des tests')
      expect(mockResultDiv.innerHTML).toContain('Network error')
    }
  )

  it(
    'shows success notification for all successful tests',
    async () => {
      fetch
        .mockResolvedValueOnce({
          json: () => Promise.resolve({
            ds_api_token: 'token',
            demarche_number: '123',
            grist_api_key: 'key',
            grist_base_url: 'base',
            grist_doc_id: 'doc'
          })
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ success: true, message: 'DS OK' })
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ success: true, message: 'Grist OK' })
        })

      await testExternalConnections()

      expect(showNotification).toHaveBeenCalledWith('Tous les tests de connexion réussis (2/2)', 'success')
    }
  )

  it(
    'shows warning notification for partial success',
    async () => {
      fetch
        .mockResolvedValueOnce({
          json: () => Promise.resolve({
            ds_api_token: 'token',
            demarche_number: '123',
            grist_api_key: 'key',
            grist_base_url: 'base',
            grist_doc_id: 'doc'
          })
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ success: true, message: 'DS OK' })
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ success: false, message: 'Grist failed' })
        })

      await testExternalConnections()

      expect(showNotification).toHaveBeenCalledWith('1/2 connexions réussies', 'warning')
    }
  )
})
