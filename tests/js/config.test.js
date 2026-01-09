/** @jest-environment jsdom */
const {
  getConfiguration,
  checkConfiguration,
  loadConfiguration,
  saveConfiguration,
  deleteConfig,
  updateDeleteButton
} = require('../../static/js/config.js')

// Mock the module that contains showNotification
jest.mock('../../static/js/notifications.js', () => ({
  showNotification: jest.fn()
}))

// Mock showNotification globally since it's imported conditionally in config.js
global.showNotification = jest.fn()

jest.mock('../../static/js/filters.js', () => ({
  loadGroupes: jest.fn(),
  resetFilters: jest.fn(),
  applyFilters: jest.fn()
}))

describe('getConfiguration', () => {
  beforeEach(() => {
    // Mock getGristContext
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })

    // Mock fetch
    global.fetch = jest.fn()
  })

  it(
    'returns config on successful fetch',
    async () => {
      const mockConfig = {
        otp_config_id: 123,
        demarche_number: 456,
        has_ds_token: true,
        has_grist_key: false
      }

      fetch.mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(mockConfig)
      })

      const result = await getConfiguration()

      expect(fetch).toHaveBeenCalledWith('/api/config?test=1')
      expect(result).toEqual(mockConfig)
    }
  )

  it(
    'throws error on fetch failure',
    async () => {
      fetch.mockResolvedValue({
        ok: false,
        status: 500
      })

      await expect(getConfiguration()).rejects.toThrow('Erreur HTTP 500')
    }
  )

  it(
    'throws error on network error',
    async () => {
      const error = new Error('Network error')
      fetch.mockRejectedValue(error)

      await expect(getConfiguration()).rejects.toThrow('Network error')
    }
  )
})

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
        ok: true,
        json: jest.fn().mockResolvedValue({
          otp_config_id: 123,
          demarche_number: 123,
          grist_base_url: 'url',
          grist_doc_id: 'doc',
          grist_user_id: 'user',
          has_ds_token: true,
          has_grist_key: true
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
        ok: true,
        json: jest.fn().mockResolvedValue({
          otp_config_id: 123,
          demarche_number: 123,
          // grist_base_url manquant
          grist_doc_id: 'doc',
          has_ds_token: true,
          has_grist_key: true
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

  it(
    'configuration partielle valide (sans clé Grist)',
    async () => {
      // Mock réponse API partielle
      fetch.mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({
          otp_config_id: 123,
          demarche_number: 123,
          grist_base_url: 'https://grist.numerique.gouv.fr/api',
          grist_doc_id: 'doc123',
          grist_user_id: 'user123',
          has_ds_token: true,
          has_grist_key: false // Manquant mais acceptable
        })
      })

      // Appel de la fonction
      await checkConfiguration()

      // Vérifications
      const resultDiv = document.getElementById('config_check_result')
      expect(resultDiv.innerHTML).toContain('Configuration complète')
      expect(document.getElementById('start_sync_btn').disabled).toBe(false)
      expect(showNotification).not.toHaveBeenCalled()
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    }
  )

  it(
    'configuration partielle invalide (manque token DS)',
    async () => {
      // Mock réponse API incomplète
      fetch.mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({
          otp_config_id: 123,
          demarche_number: 123,
          grist_base_url: 'https://grist.numerique.gouv.fr/api',
          grist_doc_id: 'doc123',
          grist_user_id: 'user123',
          has_ds_token: false, // Manquant
          has_grist_key: true
        })
      })

      // Appel de la fonction
      await checkConfiguration()

      // Vérifications
      const resultDiv = document.getElementById('config_check_result')
      expect(resultDiv.innerHTML).toContain('Configuration incomplète')
      expect(resultDiv.innerHTML).toContain('has_ds_token') // Champ manquant listé
      expect(document.getElementById('start_sync_btn').disabled).toBe(true)
      expect(showNotification).not.toHaveBeenCalled()
      expect(consoleErrorSpy).not.toHaveBeenCalled()
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
      <input id="demarche_number">
      <input id="grist_api_key">
      <input id="date_debut">
      <input id="date_fin">
      <input type="checkbox" name="statuts" value="en_construction">
      <input type="checkbox" name="statuts" value="en_instruction">
      <input type="checkbox" name="groupes" value="1">
      <input type="checkbox" name="groupes" value="2">
      <div id="ds_token_status"></div>
      <div id="grist_key_status"></div>
      <button id="accordion-ds"></button>
      <button id="accordion-grist"></button>`

    // Mocks
    global.getGristContext = jest.fn()
    global.fetch = jest.fn()
    window.updateDSTokenStatus = jest.fn()
    window.updateGristKeyStatus = jest.fn()
    global.applyFilters = jest.fn()
    
    // Reset showNotification mock
    showNotification.mockClear()
    jest.clearAllMocks()
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
          otp_config_id: 123,
          demarche_number: 123,
          grist_base_url: 'x/xx/x',
          grist_doc_id: 'doc123',
          filter_date_start: '2023-01-01',
          filter_date_end: '2023-12-31',
          filter_statuses: 'en_construction,en_instruction',
          filter_groups: '1,2',
          batch_size: 50,
          max_workers: 4,
          parallel: true,
          has_ds_token: true,
          has_grist_key: true
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
      expect(document.getElementById('demarche_number').value).toBe('123')
      expect(document.getElementById('grist_api_key').value).toBe('')

      // Vérifications des filtres
      expect(document.getElementById('date_debut').value).toBe('2023-01-01')
      expect(document.getElementById('date_fin').value).toBe('2023-12-31')
      expect(document.querySelector('input[name="statuts"][value="en_construction"]').checked).toBe(true)
      expect(document.querySelector('input[name="statuts"][value="en_instruction"]').checked).toBe(true)
      expect(document.querySelector('input[name="groupes"][value="1"]').checked).toBe(true)
      expect(document.querySelector('input[name="groupes"][value="2"]').checked).toBe(true)

      // Vérifications des appels de fonctions
      expect(window.updateDSTokenStatus).toHaveBeenCalled()
      expect(window.updateGristKeyStatus).toHaveBeenCalled()
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
      expect(document.getElementById('grist_doc_id').value).toBe('doc123')
      expect(document.getElementById('grist_user_id').value).toBe('5')
      expect(document.getElementById('grist_base_url').value).toBe('http://localhost:8484/o/docs/api')

      // Vérifications des appels
      expect(consoleErrorSpy).toHaveBeenCalledWith('Erreur lors du chargement de la configuration:', error)
      expect(updateDSTokenStatus).not.toHaveBeenCalled()
      expect(updateGristKeyStatus).not.toHaveBeenCalled()

      consoleErrorSpy.mockRestore()
  })
})

describe('saveConfiguration', () => {
  beforeEach(() => {
    // Reset showNotification mock
    showNotification.mockClear()
    jest.clearAllMocks()
  })

  it(
    'cas nominal : sauvegarde la configuration avec succès',
    async () => {
      // Setup DOM simulé
      document.body.innerHTML = `
        <input id="ds_api_token" value="new_token">
        <input id="demarche_number" value="123">
        <input id="grist_base_url" value="https://grist.example.com">
        <input id="grist_api_key" value="new_key">
        <input id="grist_doc_id" value="doc123">
        <input id="grist_user_id" value="5">
        <input id="date_debut" value="2023-01-01">
        <input id="date_fin" value="2023-12-31">
        <input type="checkbox" name="statuts" value="en_construction" checked>
        <input type="checkbox" name="statuts" value="en_instruction">
        <input type="checkbox" name="groupes" value="1" checked>
        <input type="checkbox" name="groupes" value="2">
        <button onclick="saveConfiguration()">Save</button>
        <div id="ds_token_status"></div>
        <div id="grist_key_status"></div>
        <div id="config_check_result"></div>
        <button id="start_sync_btn"></button>`

      // Mock config
      window.config = {
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
        demarche_number: '123',
        grist_base_url: 'https://grist.example.com',
        grist_api_key: 'new_key',
        grist_doc_id: 'doc123',
        grist_user_id: '5',
        filter_date_start: '2023-01-01',
        filter_date_end: '2023-12-31',
        filter_statuses: 'en_construction',
        filter_groups: '1'
      })

      expect(showNotification).toHaveBeenCalledWith('Configuration sauvegardée avec succès', 'success')
    }
  )

  it(
    'sauvegarde partielle sans clé API Grist',
    async () => {
      // Setup DOM simulé
      document.body.innerHTML = `
        <input id="ds_api_token" value="test_token">
        <input id="demarche_number" value="123">
        <input id="grist_base_url" value="https://grist.numerique.gouv.fr/api">
        <input id="grist_api_key" value=""> <!-- Vide pour sauvegarde partielle -->
        <input id="grist_doc_id" value="doc123">
        <input id="grist_user_id" value="5">
        <input id="date_debut" value="2023-01-01">
        <input id="date_fin" value="2023-12-31">
        <input type="checkbox" name="statuts" value="en_construction" checked>
        <input type="checkbox" name="groupes" value="1" checked>
        <div id="ds_token_status"></div>
        <div id="grist_key_status"></div>
        <div id="config_check_result"></div>
        <button id="start_sync_btn"></button>`

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
      
      // Vérifier que la clé API Grist n'est pas incluse si vide
      expect(body).toEqual({
        otp_config_id: undefined,
        ds_api_token: 'test_token',
        demarche_number: '123',
        grist_base_url: 'https://grist.numerique.gouv.fr/api',
        grist_doc_id: 'doc123',
        grist_user_id: '5',
        filter_date_start: '2023-01-01',
        filter_date_end: '2023-12-31',
        filter_statuses: 'en_construction',
        filter_groups: '1'
      })

      // Vérifier que grist_api_key n'est pas dans le body
      expect(body.grist_api_key).toBeUndefined()

      expect(showNotification).toHaveBeenCalledWith('Configuration sauvegardée avec succès', 'success')
    }
  )

  it(
    'échec sauvegarde si champ minimum manquant',
    async () => {
      // Setup DOM simulé
      document.body.innerHTML = `
        <input id="ds_api_token" value=""> <!-- Manquant -->
        <input id="demarche_number" value="123">
        <input id="grist_base_url" value="https://grist.numerique.gouv.fr/api">
        <input id="grist_api_key" value="">
        <input id="grist_doc_id" value="doc123">
        <input id="grist_user_id" value="5">
        <input id="date_debut" value="">
        <input id="date_fin" value="">`

      // Mock fetch (ne devrait pas être appelé)
      global.fetch = jest.fn()

      // Appel
      await saveConfiguration()

      // Vérifications
      expect(fetch).not.toHaveBeenCalled()
      expect(showNotification).toHaveBeenCalledWith('Le champ "Token API Démarches Simplifiées" est requis', 'error')
    }
  )
})

describe('updateDeleteButton', () => {
  beforeEach(() => {
    document.body.innerHTML = '<button id="delete_config_btn"></button>'
  })

  it(
    'désactive le bouton si pas de config',
    () => {
      updateDeleteButton(null)

      expect(document.getElementById('delete_config_btn').disabled).toBe(true)
      expect(document.getElementById('delete_config_btn').title).toBe('Aucune configuration à supprimer')
    }
  )

  it(
    'désactive le bouton si pas d’id de config',
    () => {
      window.otp_config_id = undefined
      updateDeleteButton()

      expect(document.getElementById('delete_config_btn').disabled).toBe(true)
    }
  )

  it(
    'active le bouton si il y’a une config', () => {
      window.otp_config_id = 123
      updateDeleteButton()

      expect(document.getElementById('delete_config_btn').disabled).toBe(false)
      expect(document.getElementById('delete_config_btn').title).toBe('')
    }
  )
})

describe('deleteConfig', () => {
  beforeEach(() => {
    // Reset showNotification mock
    showNotification.mockClear()
    jest.clearAllMocks()

    // Mock confirm
    global.confirm = jest.fn()

    // Mock fetch
    global.fetch = jest.fn()

    // Mock console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
    jest.clearAllMocks()
  })

  it(
    'lance une erreur si otp_config_id est null',
    async () => {
      await expect(deleteConfig(null)).rejects.toThrow('ID de configuration requis pour la suppression')
      expect(confirm).not.toHaveBeenCalled()
      expect(fetch).not.toHaveBeenCalled()
    }
  )

  it(
    'annule la suppression si l\'utilisateur refuse la confirmation',
    async () => {
      // Mock confirm pour refuser
      confirm.mockReturnValue(false)

      await deleteConfig(123)

      expect(confirm).toHaveBeenCalledWith('Êtes-vous sûr de vouloir supprimer cette configuration ? Cette action est irréversible.')
      expect(fetch).not.toHaveBeenCalled()
      expect(showNotification).not.toHaveBeenCalled()
    }
  )

  it(
    'supprime avec succès et redirige',
    async () => {
      // Mock confirm pour accepter
      confirm.mockReturnValue(true)

      // Mock fetch succès
      fetch.mockResolvedValue({
        json: jest.fn().mockResolvedValue({ success: true })
      })

      await deleteConfig(123)

      expect(confirm).toHaveBeenCalled()
      expect(fetch).toHaveBeenCalledWith('/api/config/123', { method: 'DELETE' })
      expect(showNotification).toHaveBeenCalledWith('Configuration supprimée avec succès', 'success')
    }
  )

  it(
    'gère les erreurs de suppression',
    async () => {
      // Mock confirm pour accepter
      confirm.mockReturnValue(true)

      // Mock fetch erreur
      fetch.mockResolvedValue({
        json: jest.fn().mockResolvedValue({ success: false, message: 'Erreur serveur' })
      })

      await deleteConfig(456)

      expect(confirm).toHaveBeenCalled()
      expect(fetch).toHaveBeenCalledWith('/api/config/456', { method: 'DELETE' })
      expect(showNotification).toHaveBeenCalledWith('Erreur serveur', 'error')
    }
  )

  it(
    'gère les erreurs réseau',
    async () => {
      // Mock confirm pour accepter
      confirm.mockReturnValue(true)

      // Mock fetch pour lever une erreur
      const error = new Error('Network error')
      fetch.mockRejectedValue(error)

      await deleteConfig(789)

      expect(confirm).toHaveBeenCalled()
      expect(fetch).toHaveBeenCalledWith('/api/config/789', { method: 'DELETE' })
      expect(consoleErrorSpy).toHaveBeenCalledWith('Erreur lors de la suppression:', error)
      expect(showNotification).toHaveBeenCalledWith('Erreur lors de la suppression', 'error')
    }
  )
})

