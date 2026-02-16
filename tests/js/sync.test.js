/** @jest-environment jsdom */
jest.mock('../../static/js/utils.js', () => ({
  formatDuration: jest.fn(seconds => `${seconds}s`)
}))

beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn()
})

jest.mock('../../static/js/notifications.js', () => ({
  showNotification: jest.fn()
}))

const {
  startSync,
  updateTaskProgress,
  toggleAutoSync,
  loadAutoSyncState
} = require('../../static/js/sync.js')

describe('startSync', () => {
  beforeEach(() => {
    // Setup DOM simulé pour les éléments utilisés par startSync
    document.body.innerHTML = `<input id="date_debut" value="2023-10-01">
    <input id="date_fin" value="2023-10-31">
    <input type="checkbox" name="statuts" value="en_construction" checked>
    <input type="checkbox" name="groupes" value="1" checked>
    <div id="config_check_result"></div>
    `

    // Mocks existants
    global.getGristContext = jest.fn()
    global.fetch = jest.fn()
    global.App = { showNotification: jest.fn() }

    // Mock console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore() // Restaure console.log
  })

  it(
    'handle null config',
    async () => {

      // Appel de la fonction avec config falsy
      await startSync(null)  // Ou undefined, etc.

      // Vérifications
      expect(showNotification).toHaveBeenCalledWith('ID de configuration manquant', 'error')
      // Pas d'autres appels (pas de fetch, etc.)
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    }
  )

  it(
    'handle errors',
    async () => {
      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1', docId: 'doc', userId: 'user' })

      const error = new Error('Network error')

      // Mock fetch pour lever une erreur
      global.fetch = jest.fn().mockRejectedValue(error)

      // Appel de la fonction
      await startSync(123)

      // Vérifications
      expect(fetch).toHaveBeenCalled()  // Fetch a été tenté
      expect(showNotification).toHaveBeenCalledWith('Erreur lors du démarrage de la synchronisation', 'error')
      expect(consoleErrorSpy).toHaveBeenCalledWith('Erreur:', error)
    }
  )

  it(
    'success',
    async () => {
      // Setup DOM simulé (comme dans beforeEach)
      document.body.innerHTML += `
        <div id="sync_progress_container" style="display: none;"></div>
        <div id="sync_controls"></div>
        <div id="sync_progress" style="display: none;"></div>
        <div id="sync_result" style="display: block;"></div>
        <div id="progress_bar" style="width: 50%;"></div>
        <div id="progress_percentage">50%</div>
        <div id="elapsed_time">10s</div>
        <div id="processed_count">5</div>
        <div id="processing_speed">1.0 dossiers/s</div>
        <div id="eta">5s</div>
        <div id="logs_count">2</div>
        <div id="logs_content"></div>
        <div id="accordion-ds"></div>
        <div id="accordion-grist"></div>
        <div id="accordion-settings"></div>
      `

      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1', docId: 'doc', userId: 'user' })

      // Mock fetch avec réponse de succès
      global.fetch = jest.fn().mockResolvedValue({
        json: jest.fn().mockResolvedValue({ success: true, task_id: 'task123' })
      })

      // Appel de la fonction
      const taskId = await startSync(123)

      // Vérifications des éléments HTML modifiés
      expect(document.getElementById('sync_progress').style.display).toBe('block') // Affiché
      expect(document.getElementById('sync_result').style.display).toBe('none')   // Masqué
      expect(document.getElementById('progress_bar').style.width).toBe('0%')     // Reset
      expect(document.getElementById('progress_percentage').textContent).toBe('0%') // Reset
      expect(document.getElementById('elapsed_time').textContent).toBe('0s')     // Reset
      expect(document.getElementById('processed_count').textContent).toBe('0')   // Reset
      expect(document.getElementById('processing_speed').textContent).toBe('-')  // Reset
      expect(document.getElementById('eta').textContent).toBe('-')               // Reset
      expect(document.getElementById('logs_count').textContent).toBe('0')        // Reset
      expect(document.getElementById('logs_content').innerHTML).toBe('')         // Vidé
      expect(taskId).toBe('task123')
      expect(showNotification).toHaveBeenCalledWith('Synchronisation démarrée', 'success')
    }
  )
})

describe('updateTaskProgress', () => {
  it(
    'update progress and status with a valid task',
    () => {
      // Setup DOM simulé
      document.body.innerHTML = `<div id="progress_bar" style="width: 0%;"></div>
        <div id="progress_percentage">0%</div>
        <div id="elapsed_time">0s</div>
        <div id="processed_count">0</div>
        <div id="processing_speed">-</div>
        <div id="eta">-</div>`

      // Mock startTime globale
      global.startTime = Date.now() - 10000 // 10 secondes écoulées

      // Objet tâche simulé
      const mockTask = { progress: 50, message: 'Traitement en cours...' }

      // Appel de la fonction
      updateTaskProgress(mockTask)

      // Vérifications
      expect(document.getElementById('progress_bar').style.width).toBe('50%')
      expect(document.getElementById('progress_percentage').textContent).toBe('50%')
      expect(formatDuration).toHaveBeenCalledWith(expect.closeTo(10, 0.1)) // Temps écoulé
  })

  it(
    'gère la fin de la tâche et met à jour l\'interface finale', () => {
    // Setup DOM simulé
    document.body.innerHTML = `<div id="sync_progress_container">
      <div id="sync_progress" style="display: block;">
        <div id="progress_percentage">0%</div>
        <div id="progress_bar" style="width: 0%;"></div>
        <div id="elapsed_time">0s</div>
        <div id="processing_speed">-</div>
        <div id="eta">-</div>
      </div>
      <div id="sync_result" style="display: none;">
        <div id="result_content"></div>
      </div>
    </div>
    <div id="sync_controls"></div>`

    // Objet tâche simulé (complétée)
    const mockTask = { status: 'completed', message: 'Sync terminée', progress: 100 }

    // Appel de la fonction
    updateTaskProgress(mockTask)

    // Vérifications
    expect(document.getElementById('sync_result').style.display).toBe('block')
    expect(document.getElementById('result_content').innerHTML).toContain('Synchronisation terminée avec succès')
    expect(showNotification).toHaveBeenCalledWith('Synchronisation terminée avec succès!', 'success')
  })
})

describe('toggleAutoSync', () => {
  beforeEach(() => {
    // Setup DOM simulé pour les éléments utilisés par toggleAutoSync
    document.body.innerHTML = `<input type="checkbox" id="auto_sync_enabled" checked>`

    // Mocks
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })
    global.fetch = jest.fn()
    global.App = { showNotification: jest.fn() }

    // Mock console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it(
    'ne pas autoriser sans la clé grist',
    async () => {
      // Mock fetch pour /api/config retournant une config sans clé Grist
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: 123,
            has_grist_key: false
          })
        })

      // Appel de la fonction pour activer
      await toggleAutoSync(true)

      // Vérifications
      expect(showNotification).toHaveBeenCalledWith('Clé grist manquante', 'error')
      expect(document.getElementById('auto_sync_enabled').checked).toBe(false)
      // Pas d'appel à /api/schedule
      expect(fetch).toHaveBeenCalledTimes(1)
      expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/config'))
    }
  )

  it(
    'ne pas autoriser sans configuration sauvegardée',
    async () => {
      // Mock fetch pour /api/config retournant une config sans otp_config_id
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: null,
            has_grist_key: true
          })
        })

      // Appel de la fonction pour activer
      await toggleAutoSync(true)

      // Vérifications
      expect(showNotification).toHaveBeenCalledWith(
        'Configuration non sauvegardée. Veuillez sauvegarder la configuration avant d\'activer la synchronisation automatique.',
        'error'
      )
      expect(document.getElementById('auto_sync_enabled').checked).toBe(false)
    }
  )

  it(
    'succès d’activation',
    async () => {
      // Mock fetch pour /api/config et /api/schedule
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: 123,
            has_grist_key: true
          })
        })
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({ success: true })
        })

      // Appel de la fonction pour activer
      await toggleAutoSync(true)

      // Vérifications
      expect(fetch).toHaveBeenCalledTimes(2)
      expect(fetch).toHaveBeenNthCalledWith(2, '/api/schedule', expect.objectContaining({
        method: 'POST'
      }))
      expect(showNotification).toHaveBeenCalledWith('Synchronisation automatique activée', 'success')
    }
  )

  it(
    'succès de désactivation',
    async () => {
      // Mock fetch pour /api/config et /api/schedule
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: 123,
            has_grist_key: true
          })
        })
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({ success: true })
        })

      // Appel de la fonction pour désactiver
      await toggleAutoSync(false)

      // Vérifications
      expect(fetch).toHaveBeenCalledTimes(2)
      expect(fetch).toHaveBeenNthCalledWith(2, '/api/schedule', expect.objectContaining({
        method: 'DELETE'
      }))
      expect(showNotification).toHaveBeenCalledWith('Synchronisation automatique désactivée', 'success')
    }
  )

  it(
    'gestion d’erreur réseau',
    async () => {
      // Mock fetch pour lever une erreur
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'))

      // Appel de la fonction
      await toggleAutoSync(true)

      // Vérifications
      expect(consoleErrorSpy).toHaveBeenCalled()
      expect(showNotification).toHaveBeenCalledWith(
        'Erreur lors de la modification de la synchronisation automatique',
        'error'
      )
      expect(document.getElementById('auto_sync_enabled').checked).toBe(false)
    }
  )
})

describe('loadAutoSyncState', () => {
  beforeEach(() => {
    // Setup DOM simulé pour les éléments utilisés par loadAutoSyncState
    document.body.innerHTML = `
      <input type="checkbox" id="auto_sync_enabled">
      <div id="last_sync_status" style="display: block;"></div>
    `

    // Mocks
    global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })
    global.fetch = jest.fn()

    // Mock console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it(
    'désactiver la case quand la config n’existe pas',
    async () => {
      // Mock fetch pour /api/config retournant une config sans otp_config_id
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: null,
            has_grist_key: false
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const checkbox = document.getElementById('auto_sync_enabled')
      expect(checkbox.disabled).toBe(true)
      expect(checkbox.checked).toBe(false)
      expect(document.getElementById('last_sync_status').style.display).toBe('none')
    }
  )

  it(
    'activer la case et afficher l’état',
    async () => {
      // Mock fetch pour /api/config et /api/schedule
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: 123,
            has_grist_key: true
          })
        })
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            enabled: true,
            last_run: '2024-01-15T10:00:00Z',
            last_status: 'success'
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const checkbox = document.getElementById('auto_sync_enabled')
      expect(checkbox.disabled).toBe(false)
      expect(checkbox.checked).toBe(true)
      expect(document.getElementById('last_sync_status').style.display).toBe('block')
      expect(document.getElementById('last_sync_status').innerHTML).toContain('Succès')
    }
  )

  it(
    'afficher l’état désactivé quand la programmation n’est pas activée',
    async () => {
      // Mock fetch pour /api/config et /api/schedule
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: 123,
            has_grist_key: true
          })
        })
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            enabled: false,
            last_run: null,
            last_status: null
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const checkbox = document.getElementById('auto_sync_enabled')
      expect(checkbox.disabled).toBe(false)
      expect(checkbox.checked).toBe(false)
      expect(document.getElementById('last_sync_status').style.display).toBe('none')
    }
  )

  it(
    'afficher l’erreur de la dernière synchronisation',
    async () => {
      // Mock fetch pour /api/config et /api/schedule
      global.fetch = jest.fn()
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            otp_config_id: 123,
            has_grist_key: true
          })
        })
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            enabled: true,
            last_run: '2024-01-15T10:00:00Z',
            last_status: 'error'
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const statusDiv = document.getElementById('last_sync_status')
      expect(statusDiv.style.display).toBe('block')
      expect(statusDiv.innerHTML).toContain('Échec')
    }
  )

  it(
    'gestion d’erreur réseau',
    async () => {
      // Mock fetch pour lever une erreur
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'))

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications - ne doit pas planter, juste logger l'erreur
      expect(consoleErrorSpy).toHaveBeenCalled()
    }
  )
})
