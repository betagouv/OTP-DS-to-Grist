const { testDemarchesConnection } = require('../../static/js/connections.js')

describe('testDemarchesConnection', () => {
  let mockButton, mockResultDiv, mockTokenInput, mockUrlInput, mockDemarcheInput

  beforeEach(() => {
    // Mock DOM elements
    mockButton = {
      disabled: false,
      innerHTML: ''
    }
    mockResultDiv = {
      innerHTML: ''
    }
    mockTokenInput = { value: '' }
    mockUrlInput = { value: '' }
    mockDemarcheInput = { value: '' }

    global.document = {
      getElementById: jest.fn((id) => {
        switch (id) {
          case 'test_ds_btn': return mockButton
          case 'ds_test_result': return mockResultDiv
          case 'ds_api_token': return mockTokenInput
          case 'ds_api_url': return mockUrlInput
          case 'demarche_number': return mockDemarcheInput
          default: return null
        }
      })
    }

    // Mock fetch
    global.fetch = jest.fn()

    // Mock global variables
    global.currentConfig = { ds_api_token_exists: true }
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })
    global.App = { showNotification: jest.fn() }
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
          api_url: 'https://api.example.com',
          demarche_number: '123'
        })
      }))
      expect(mockResultDiv.innerHTML).toContain('Connexion réussie')
      expect(mockResultDiv.innerHTML).toContain('fr-alert--success')
      expect(global.App.showNotification).toHaveBeenCalledWith('Connexion réussie', 'success')
      expect(mockButton.disabled).toBe(false)
      expect(mockButton.innerHTML).toContain('Tester la connexion')
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
      expect(global.App.showNotification).toHaveBeenCalledWith('Erreur de connexion', 'error')
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
          api_url: '',
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
      global.currentConfig = { ds_api_token_exists: false }

      await testDemarchesConnection()

      expect(mockResultDiv.innerHTML).toContain('Token API requis')
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
      expect(global.App.showNotification).toHaveBeenCalledWith('Erreur lors du test de connexion', 'error')
      expect(global.console.error).toHaveBeenCalledWith('Erreur lors du test DS:', expect.any(Error))
    }
  )
})
