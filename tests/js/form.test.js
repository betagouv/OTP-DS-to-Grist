const { updateDSTokenStatus } = require('../../static/js/form.js')

describe('updateDSTokenStatus', () => {
  let mockInput, mockStatusElement

  beforeEach(() => {
    // Mock DOM elements
    mockInput = {
      value: '',
      placeholder: ''
    }
    mockStatusElement = {
      innerHTML: ''
    }

    global.document = {
      getElementById: jest.fn((id) => {
        if (id === 'ds_api_token') return mockInput
        if (id === 'ds_token_status') return mockStatusElement
        return null
      })
    }
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it(
    'should set success badge and placeholder when token is present in input',
    () => {
      mockInput.value = 'some-token'
      const config = {}

      updateDSTokenStatus(config)

      expect(mockStatusElement.innerHTML).toContain('Token configuré')
      expect(mockStatusElement.innerHTML).toContain('fr-badge--success')
      expect(mockInput.placeholder).toBe('Token déjà configuré (laissez vide pour conserver)')
    }
  )

  it(
    'should set success badge and placeholder when token is present in config',
    () => {
      mockInput.value = ''
      const config = { ds_api_token: 'config-token' }

      updateDSTokenStatus(config)

      expect(mockStatusElement.innerHTML).toContain('Token configuré')
      expect(mockStatusElement.innerHTML).toContain('fr-badge--success')
      expect(mockInput.placeholder).toBe('Token déjà configuré (laissez vide pour conserver)')
    }
  )

  it(
    'should set error badge and empty placeholder when no token is present',
    () => {
      mockInput.value = ''
      const config = {}

      updateDSTokenStatus(config)

      expect(mockStatusElement.innerHTML).toContain('Token requis')
      expect(mockStatusElement.innerHTML).toContain('fr-badge--error')
      expect(mockInput.placeholder).toBe('')
    }
  )
})
