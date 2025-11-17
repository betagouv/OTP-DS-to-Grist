/** @jest-environment jsdom */
const { checkConfiguration, loadConfiguration, saveConfiguration } = require('../../static/js/config.js')
const { showNotification } = require('../../static/js/notifications.js')

jest.mock('../../static/js/notifications.js', () => ({
  showNotification: jest.fn()
}))

describe('checkConfiguration', () => {
  beforeEach(() => {
    // Setup DOM simulé
    document.body.innerHTML = `
      <div id="config_check_result"></div>
      <button id="start_sync_btn"></button>`

    // Mock getGristContext
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })

    // Mock fetch
    global.fetch = jest.fn()

    // Mock console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore() // Restaure console.log
  })

  it(
    'display config and enable button',
    async () => {
      // Mock réponse API valide
      fetch.mockResolvedValue({
        json: jest.fn().mockResolvedValue({
          ds_api_token: 'token',
          demarche_number: 123,
          grist_base_url: 'url',
          grist_api_key: 'key',
          grist_doc_id: 'doc'
        })
      })

      // Appel de la fonction
      await checkConfiguration()

      const resultDiv = document.getElementById('config_check_result')
      expect(resultDiv.innerHTML).toContain('Configuration complète')
      expect(document.getElementById('start_sync_btn').disabled).toBe(false)
      expect(showNotification).not.toHaveBeenCalled() // Pas d'erreur
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    }
  )

  it(
    'display error for incomplete config and disable button',
    async () => {
      // Mock réponse API incomplète (champ manquant)
      fetch.mockResolvedValue({
        json: jest.fn().mockResolvedValue({
          ds_api_token: 'token',
          demarche_number: 123,
          // grist_base_url manquant
          grist_api_key: 'key',
          grist_doc_id: 'doc'
        })
      })

      // Appel de la fonction
      await checkConfiguration()

      // Vérifications
      const resultDiv = document.getElementById('config_check_result')
      expect(resultDiv.innerHTML).toContain('Configuration incomplète')
      expect(resultDiv.innerHTML).toContain('grist_base_url') // Champ manquant listé
      expect(document.getElementById('start_sync_btn').disabled).toBe(true)
      expect(showNotification).not.toHaveBeenCalled() // Erreur affichée dans le DOM
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    }
  )

  it(
    'handle errors and display error',
    async () => {
      // Mock fetch pour lever une erreur
      const error = new Error('Network error')
      fetch.mockRejectedValue(error)

      // Appel de la fonction
      await checkConfiguration()

      // Vérifications
      const resultDiv = document.getElementById('config_check_result')
      expect(resultDiv.innerHTML).toContain('Erreur lors de la vérification')
      expect(document.getElementById('start_sync_btn').disabled).toBe(true)
      expect(showNotification).not.toHaveBeenCalled() // Erreur gérée dans le DOM
      expect(consoleErrorSpy).toHaveBeenCalledWith('Erreur lors de la vérification de la configuration:', error)
    }
  )
})

describe('loadConfiguration', () => {
  beforeEach(() => {
    // Setup DOM simulé pour les champs du formulaire
    document.body.innerHTML = `
      <input id="grist_doc_id">
      <input id="grist_user_id">
      <input id="grist_base_url">
      <input id="ds_api_token">
      <input id="ds_api_url">
      <input id="demarche_number">
      <input id="grist_api_key">
      <div id="ds_token_status"></div>
      <div id="grist_key_status"></div>
      <button id="accordion-ds"></button>
      <button id="accordion-grist"></button>`

    // Mocks
    global.getGristContext = jest.fn()
    global.fetch = jest.fn()
    global.updateDSTokenStatus = jest.fn()
    global.updateGristKeyStatus = jest.fn()
  })

  it(
    'prefill all inputs with config',
    async () => {
      // Mock getGristContext
      getGristContext.mockResolvedValue({
        params: '?grist_user_id=5&grist_doc_id=doc123',
        userId: 5,
        docId: 'doc123',
        baseUrl: '/'
      })

      // Mock fetch avec config complète
      fetch.mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({
          ds_api_token: 'ds_token',
          ds_api_url: 'https://api.example.com',
          demarche_number: 123,
          grist_base_url: 'x/xx/x',
          grist_api_key: 'grist_key',
          grist_doc_id: 'doc123',
          batch_size: 50,
          max_workers: 4,
          parallel: true
        })
      })

      // Appel de la fonction
      await loadConfiguration()

      // Vérifications des champs pré-remplis depuis le contexte
      expect(document.getElementById('grist_doc_id').value).toBe('doc123')
      expect(document.getElementById('grist_user_id').value).toBe('5')
      expect(document.getElementById('grist_base_url').value).toBe('x/xx/x')

      // Vérifications des champs remplis depuis la config (car hasConfig = true)
      expect(document.getElementById('ds_api_token').value).toBe('')
      expect(document.getElementById('ds_api_url').value).toBe('https://api.example.com')
      expect(document.getElementById('demarche_number').value).toBe('123')
      expect(document.getElementById('grist_api_key').value).toBe('')

      // Vérifications des appels de fonctions
      expect(updateDSTokenStatus).toHaveBeenCalled()
      expect(updateGristKeyStatus).toHaveBeenCalled()
    }
  )

  it(
    'handle errors from fetch',
    async () => {
      // Mock getGristContext
      getGristContext.mockResolvedValue({
        params: '?grist_user_id=5&grist_doc_id=doc123',
        userId: 5,
        docId: 'doc123',
        baseUrl: 'http://localhost:8484/o/docs/api'
      })

      // Mock fetch pour lever une erreur
      const error = new Error('Network error')
      fetch.mockRejectedValue(error)

      // Mock console.error
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})

      // Appel de la fonction
      await loadConfiguration()

      // Vérifications : les champs restent vides ou par défaut
      expect(document.getElementById('grist_doc_id').value).toBe('')
      expect(document.getElementById('grist_user_id').value).toBe('')
      expect(document.getElementById('grist_base_url').value).toBe('')

      // Vérifications des appels
      expect(consoleErrorSpy).toHaveBeenCalledWith('Erreur lors du chargement de la configuration:', error)
      expect(updateDSTokenStatus).not.toHaveBeenCalled()
      expect(updateGristKeyStatus).not.toHaveBeenCalled()

      consoleErrorSpy.mockRestore()
  })
})

describe('saveConfiguration', () => {
  it('cas nominal : sauvegarde la configuration avec succès', async () => {
    // Setup DOM simulé
    document.body.innerHTML = `
      <input id="ds_api_token" value="new_token">
      <input id="ds_api_url" value="https://api.example.com">
      <input id="demarche_number" value="123">
      <input id="grist_base_url" value="https://grist.example.com">
      <input id="grist_api_key" value="new_key">
      <input id="grist_doc_id" value="doc123">
      <input id="grist_user_id" value="5">
      <button onclick="saveConfiguration()">Save</button>
      <div id="ds_token_status"></div>
      <div id="grist_key_status"></div>
      <div id="config_check_result"></div>
      <button id="start_sync_btn"></button>`

    // Mock currentConfig
    window.currentConfig = {
      ds_api_token: 'old_token',
      grist_api_key: 'old_key'
    }

    // Mock fetch
    global.fetch = jest.fn().mockResolvedValue({
      json: jest.fn().mockResolvedValue({ success: true })
    })

    // Mock App
    global.App = { showNotification: jest.fn() }

    // Mock loadConfiguration
    const mockLoadConfiguration = jest.fn()
    global.loadConfiguration = mockLoadConfiguration

    // Mock setTimeout
    jest.useFakeTimers()

    // Appel
    await saveConfiguration()

    // Vérifications
    expect(fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }))

    const callArgs = fetch.mock.calls[0][1]
    const body = JSON.parse(callArgs.body)
    expect(body).toEqual({
      ds_api_token: 'new_token',
      ds_api_url: 'https://api.example.com',
      demarche_number: '123',
      grist_base_url: 'https://grist.example.com',
      grist_api_key: 'new_key',
      grist_doc_id: 'doc123',
      grist_user_id: '5'
    })

    expect(showNotification).toHaveBeenCalledWith('Configuration sauvegardée avec succès', 'success')
  })
})
