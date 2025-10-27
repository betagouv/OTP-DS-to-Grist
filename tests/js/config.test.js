/** @jest-environment jsdom */
const { checkConfiguration } = require('../../static/config.js')

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

    // Mock App.showNotification
    global.App = { showNotification: jest.fn() }

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
      expect(App.showNotification).not.toHaveBeenCalled() // Pas d'erreur
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
      expect(App.showNotification).not.toHaveBeenCalled() // Erreur affichée dans le DOM
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
      expect(App.showNotification).not.toHaveBeenCalled() // Erreur gérée dans le DOM
      expect(consoleErrorSpy).toHaveBeenCalledWith('Erreur lors de la vérification de la configuration:', error)
    }
  )
})
