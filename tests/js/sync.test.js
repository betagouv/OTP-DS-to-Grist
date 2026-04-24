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
  loadAutoSyncState,
  showSyncBanner
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
        <span id="sync-progress-text">Progression</span>
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
        <span id="sync-progress-text">Progression</span>
        <div id="progress_percentage">0%</div>
        <div id="progress_bar" style="width: 0%;"></div>
        <div id="elapsed_time">0s</div>
        <div id="processing_speed">-</div>
        <div id="eta">-</div>
      </div>
      <div id="sync_result">
        <div id="result_content_auto">
          <div class="sync_banner_template">
            <div class="fr-alert" role="alert">
              <h3 class="fr-alert__title"></h3>
              <p class="sync-banner-count"></p>
              <p class="sync-banner-date fr-text--sm"></p>
            </div>
          </div>
        </div>

        <div id="result_content_manual">
          <div class="sync_banner_template">
            <div class="fr-alert" role="alert">
              <h3 class="fr-alert__title"></h3>
              <p class="sync-banner-count"></p>
              <p class="sync-banner-date fr-text--sm"></p>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div id="sync_controls"></div>`

    // Variables globales pour la progression (comme dans le code réel)
    globalThis.startTime = null
    globalThis.successCount = 10
    globalThis.errorCount = 0
    globalThis.totalDossiers = 10
    globalThis.logsCount = 0
    globalThis.logsVisible = false
    globalThis.extractStatsFromLog = () => {}

    // Objet tâche simulé (complétée)
    const mockTask = { status: 'completed', message: 'Sync terminée', progress: 100 }

    // Appel de la fonction
    updateTaskProgress(mockTask)

    // Vérifications
    expect(document.getElementById('sync_result').style.display).toBe('block')
    const resultContentManual = document.getElementById('result_content_manual')
    const h3 = resultContentManual.querySelector('h3')
    // Utiliser textContent car innerText ne fonctionne pas dans JSDOM
    const titleText = h3.textContent || h3.innerText || ''
    expect(titleText).toContain('Synchronisation terminée avec succès')
    expect(resultContentManual.querySelector('.fr-alert').classList.contains('fr-alert--success')).toBe(true)
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

describe('showSyncBanner', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="result_content_auto" class="fr-col hide">
        <div class="sync_banner_template">
          <div class="fr-alert" role="alert">
            <h3 class="fr-alert__title sync-banner-message"></h3>
            <p class="sync-banner-count"></p>
            <p class="sync-banner-date fr-text--sm"></p>
          </div>
        </div>
      </div>
      <div id="result_content_manual" class="fr-col hide">
        <div class="sync_banner_template">
          <div class="fr-alert" role="alert">
            <h3 class="fr-alert__title sync-banner-message"></h3>
            <p class="sync-banner-count"></p>
            <p class="sync-banner-date fr-text--sm"></p>
          </div>
        </div>
      </div>
    `
  })

  describe('sync réussie', () => {
    it('affiche une bannière verte pour sync automatique réussie', () => {
      const timestamp = '2026-04-24T10:30:00Z'
      showSyncBanner('result_content_auto', 'success', 10, 0, timestamp, 'auto')

      const alert = document.querySelector('#result_content_auto .fr-alert')
      expect(alert.classList.contains('fr-alert--success')).toBe(true)

      const h3 = document.querySelector('#result_content_auto h3')
      const titleText = h3.textContent || h3.innerText || ''
      expect(titleText).toContain('Synchronisation terminée avec succès')
      expect(titleText).toContain('(automatique)')

      const count = document.querySelector('#result_content_auto .sync-banner-count')
      const countText = count.textContent || count.innerText || ''
      expect(countText).toContain('10')
      expect(countText).toContain('0')
    })

    it('affiche une bannière verte pour sync manuelle réussie', () => {
      const timestamp = '2026-04-24T14:00:00Z'
      showSyncBanner('result_content_manual', 'success', 5, 0, timestamp, 'manual')

      const h3 = document.querySelector('#result_content_manual h3')
      const titleText = h3.textContent || h3.innerText || ''
      expect(titleText).toContain('Synchronisation terminée avec succès')
      expect(titleText).toContain('(déclenchée manuellement)')

      const alert = document.querySelector('#result_content_manual .fr-alert')
      expect(alert.classList.contains('fr-alert--success')).toBe(true)
    })
  })

  describe('sync avec erreurs', () => {
    it('affiche une bannière orange pour sync avec avertissements', () => {
      const timestamp = '2026-04-24T15:00:00Z'
      showSyncBanner('result_content_manual', 'warning', 8, 2, timestamp, 'manual')

      const alert = document.querySelector('#result_content_manual .fr-alert')
      expect(alert.classList.contains('fr-alert--warning')).toBe(true)

      const h3 = document.querySelector('#result_content_manual h3')
      const titleText = h3.textContent || h3.innerText || ''
      expect(titleText).toContain('erreur')
    })
  })

  describe('sync échouée', () => {
    it('affiche une bannière rouge pour sync échouée', () => {
      const timestamp = '2026-04-24T16:00:00Z'
      showSyncBanner('result_content_auto', 'error', 0, 3, timestamp, 'auto')

      const alert = document.querySelector('#result_content_auto .fr-alert')
      expect(alert.classList.contains('fr-alert--error')).toBe(true)

      const h3 = document.querySelector('#result_content_auto h3')
      const titleText = h3.textContent || h3.innerText || ''
      expect(titleText).toContain('erreur')
    })
  })

  describe('affichage et layout', () => {
    it('affiche le container après appel', () => {
      showSyncBanner('result_content_manual', 'success', 5, 0, null, 'manual')

      const container = document.getElementById('result_content_manual')
      expect(container.style.display).toBe('block')
    })

    it('permet le layout en colonne quand les deux bannières sont visibles', () => {
      showSyncBanner('result_content_auto', 'success', 10, 0, null, 'auto')
      showSyncBanner('result_content_manual', 'success', 5, 0, null, 'manual')

      const auto = document.getElementById('result_content_auto')
      const manual = document.getElementById('result_content_manual')

      expect(auto.style.display).toBe('block')
      expect(manual.style.display).toBe('block')
    })
  })

  describe('gestion des erreurs', () => {
    it('lance une erreur si le container nexiste pas', () => {
      let errorThrown = false
      try {
        showSyncBanner('inexistant', 'success', 5, 0, null, 'manual')
      } catch (e) {
        errorThrown = true
      }
      expect(errorThrown).toBe(true)
    })

    it('ne fait rien si le template nexiste pas (pas derreur)', () => {
      document.body.innerHTML = `<div id="sans_template"></div>`
      let errorThrown = false
      try {
        showSyncBanner('sans_template', 'success', 5, 0, null, 'manual')
      } catch (e) {
        errorThrown = true
      }
      expect(errorThrown).toBe(false)
    })
  })
})

describe('loadAutoSyncState', () => {
  beforeEach(() => {
    // Setup DOM simulé pour les éléments utilisés par loadAutoSyncState
    document.body.innerHTML = `
      <input type="checkbox" id="auto_sync_enabled">
      <div id="sync_progress_container">
        <div id="result_content_auto"><div class="sync_banner_template"><div class="fr-alert" role="alert"><h3 class="fr-alert__title"></h3><p class="sync-banner-count"></p><p class="sync-banner-date fr-text--sm"></p></div></div></div>
        <div id="result_content_manual"><div class="sync_banner_template"><div class="fr-alert" role="alert"><h3 class="fr-alert__title"></h3><p class="sync-banner-count"></p><p class="sync-banner-date fr-text--sm"></p></div></div>
      </div>
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
    }
  )

it(
    'activer la case et afficher l\'état',
    async () => {
      // Mock fetch pour /api/config, /api/schedule et /api/sync-log/latest
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
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            success: true,
            auto: {
              timestamp: '2024-01-15T10:00:00',
              status: 'success',
              success_count: 10,
              error_count: 0
            },
            manual: {
              timestamp: '2024-01-15T09:00:00',
              status: 'success',
              success_count: 5,
              error_count: 1
            }
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const checkbox = document.getElementById('auto_sync_enabled')
      expect(checkbox.disabled).toBe(false)
      expect(checkbox.checked).toBe(true)
      
      // Les deux banners sont affichées
      const autoDiv = document.getElementById('result_content_auto')
      expect(autoDiv.style.display).toBe('block')
      const h3 = autoDiv.querySelector('h3')
      const titleText = h3.textContent || h3.innerText || ''
      expect(titleText).toContain('Synchronisation terminée avec succès')
      expect(autoDiv.querySelector('.fr-alert').classList.contains('fr-alert--success')).toBe(true)
    }
  )

it(
    'afficher l\'état désactivé quand la programmation n\'est pas activée',
    async () => {
      // Mock fetch pour /api/config, /api/schedule et /api/sync-log/latest
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
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            success: true,
            auto: null,
            manual: null
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const checkbox = document.getElementById('auto_sync_enabled')
      expect(checkbox.disabled).toBe(false)
      expect(checkbox.checked).toBe(false)
      // sync_progress_container caché
      expect(document.getElementById('sync_progress_container').style.display).toBe('none')
    }
  )

it(
    'afficher l\'erreur de la dernière synchronisation',
    async () => {
      // Mock fetch pour /api/config, /api/schedule et /api/sync-log/latest
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
        .mockResolvedValueOnce({
          json: jest.fn().mockResolvedValue({
            success: true,
            auto: {
              timestamp: '2024-01-15T10:00:00',
              status: 'error',
              success_count: 8,
              error_count: 2
            },
            manual: null
          })
        })

      // Appel de la fonction
      await loadAutoSyncState()

      // Vérifications
      const autoDiv = document.getElementById('result_content_auto')
      expect(autoDiv.style.display).toBe('block')
      const h3 = autoDiv.querySelector('h3')
      const titleText = h3.textContent || h3.innerText || ''
      expect(titleText).toContain('Synchronisation terminée avec erreur')
      expect(autoDiv.querySelector('.fr-alert').classList.contains('fr-alert--error')).toBe(true)
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
