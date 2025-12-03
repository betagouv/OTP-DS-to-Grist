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

const { startSync, updateTaskProgress } = require('../../static/js/sync.js')

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
    'display error if falsy config',
    async () => {

      // Appel de la fonction avec config falsy
      await startSync(null)  // Ou undefined, etc.

      // Vérifications
      expect(showNotification).toHaveBeenCalledWith('Configuration non chargée', 'error')
      // Pas d'autres appels (pas de fetch, etc.)
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    }
  )

  it(
    'handle errors',
    async () => {
      // Mock config valide
      const mockConfig = { ds_api_token: 'token', demarche_number: 123 }

      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1', docId: 'doc', userId: 'user' })

      const error = new Error('Network error')

      // Mock fetch pour lever une erreur
      global.fetch = jest.fn().mockRejectedValue(error)

      // Appel de la fonction
      await startSync(mockConfig)

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
        <div id="sync_controls" style="display: block;"></div>
        <div id="sync_progress" style="display: none;"></div>
        <div id="sync_result" style="display: block;"></div>
        <div id="progress_bar" style="width: 50%;"></div>
        <div id="progress_percentage">50%</div>
        <div id="current_status">Test</div>
        <div id="elapsed_time">10s</div>
        <div id="processed_count">5</div>
        <div id="processing_speed">1.0 dossiers/s</div>
        <div id="eta">5s</div>
        <div id="logs_count">2</div>
        <div id="logs_content"></div>`

      // Mock config valide
      const mockConfig = { ds_api_token: 'token', demarche_number: 123 }

      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1', docId: 'doc', userId: 'user' })

      // Mock fetch avec réponse de succès
      global.fetch = jest.fn().mockResolvedValue({
        json: jest.fn().mockResolvedValue({ success: true, task_id: 'task123' })
      })

      // Appel de la fonction
      const taskId = await startSync(mockConfig)

      // Vérifications des éléments HTML modifiés
      expect(document.getElementById('sync_controls').style.display).toBe('none')  // Masqué
      expect(document.getElementById('sync_progress').style.display).toBe('block') // Affiché
      expect(document.getElementById('sync_result').style.display).toBe('none')   // Masqué
      expect(document.getElementById('progress_bar').style.width).toBe('0%')     // Reset
      expect(document.getElementById('progress_percentage').textContent).toBe('0%') // Reset
      expect(document.getElementById('current_status').textContent).toBe('Initialisation...') // Reset
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
        <div id="current_status">Initialisation...</div>
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
      expect(document.getElementById('current_status').textContent).toBe('Traitement en cours...')
      expect(formatDuration).toHaveBeenCalledWith(expect.closeTo(10, 0.1)) // Temps écoulé
  })

  it(
    'gère la fin de la tâche et met à jour l\'interface finale', () => {
    // Setup DOM simulé
    document.body.innerHTML = `<div id="sync_progress_container">
      <div id="sync_progress" style="display: block;">
        <div id="progress_percentage">0%</div>
        <div id="progress_bar" style="width: 0%;"></div>
        <div id="current_status">Initialisation...</div>
        <div id="elapsed_time">0s</div>
        <div id="processing_speed">-</div>
        <div id="eta">-</div>
      </div>
      <div id="sync_result" style="display: none;">
        <div id="result_content"></div>
      </div>
    </div>
    <div id="sync_controls" style="display: none;"></div>`

    // Objet tâche simulé (complétée)
    const mockTask = { status: 'completed', message: 'Sync terminée', progress: 100 }

    // Appel de la fonction
    updateTaskProgress(mockTask)

    // Vérifications
    expect(document.getElementById('sync_controls').style.display).toBe('block')
    expect(document.getElementById('sync_result').style.display).toBe('block')
    expect(document.getElementById('result_content').innerHTML).toContain('Synchronisation terminée avec succès')
    expect(showNotification).toHaveBeenCalledWith('Synchronisation terminée avec succès!', 'success')
  })
})
