/** @jest-environment jsdom */
const {
  toggleLogs,
  parseLogMessage,
  updateStatsFromLog,
  copyLogs
} = require('../../static/js/logs.js')

describe('toggleLogs', () => {
  beforeEach(() => {
    // Setup DOM réel en jsdom
    document.body.innerHTML = `
        <div id="logs_container" style="height: 300px; overflow-y: auto;"></div>
        <i id="logs_toggle_icon" class="fas fa-chevron-down fr-mr-1w"></i>
        <span id="logs_toggle_text">Afficher les logs</span>
        `
    // Reset variable globale

    // Mock setTimeout pour contrôler le scroll
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.clearAllTimers()
    jest.useRealTimers()
  })

  it('display logs dans scroll bottom', () => {
    const container = document.getElementById('logs_container')
    const icon = document.getElementById('logs_toggle_icon')
    const text = document.getElementById('logs_toggle_text')

    // Ajouter du contenu pour simuler scrollHeight > 0
    container.innerHTML = '<div style="height: 600px;">Log content</div>'

    toggleLogs(false)

    // expect(global.logsVisible).toBe(true)
    expect(container.style.display).toBe('block')
    expect(icon.className).toBe('fas fa-chevron-up fr-mr-1w')
    expect(text.textContent).toBe('Masquer les logs')

    // Avancer les timers pour déclencher le scroll
    jest.runAllTimers()
    expect(container.scrollTop).toBe(container.scrollHeight)
  })

  it('hide logs', () => {
    const container = document.getElementById('logs_container')
    const icon = document.getElementById('logs_toggle_icon')
    const text = document.getElementById('logs_toggle_text')

    toggleLogs(true)

    // expect(global.logsVisible).toBe(false)
    expect(container.style.display).toBe('none')
    expect(icon.className).toBe('fas fa-chevron-down fr-mr-1w')
    expect(text.textContent).toBe('Afficher les logs')
  })
})

describe('updateStatsFromLog', () => {
  beforeEach(() => {
    // Setup DOM simulé pour les éléments utilisés par updateStatsFromLog
    document.body.innerHTML = '<div id="processed_count">0</div>'

    // Reset des variables globales
    global.totalDossiers = 0
    global.successCount = 0
    global.errorCount = 0

    document.body.innerHTML = `
        <div id="processed_count">0</div>
        <div id="logs_count">0</div>`
  })

  it('extract total number of "dossiers"', () => {
    const nbDossiers = 150
    // Setup : Mock des variables globales utilisées par la fonction
    global.totalDossiers = 0
    global.successCount = 0
    global.errorCount = 0

    const message = `Nombre total de dossiers trouvés: ${nbDossiers}`

    updateStatsFromLog(message)

    expect(global.totalDossiers).toBe(150)
    expect(global.successCount).toBe(0)
    expect(global.errorCount).toBe(0)
  })

  it('extract number of succeded "dossiers"', () => {
    const nbDossiers = 75

    // Setup : Mock des variables globales
    global.totalDossiers = 0
    global.successCount = 0
    global.errorCount = 0

    const message = `Dossiers traités avec succès: ${nbDossiers}`

    updateStatsFromLog(message)

    expect(global.successCount).toBe(nbDossiers)
    expect(global.totalDossiers).toBe(0)
    expect(global.errorCount).toBe(0)
    expect(document.getElementById('processed_count').textContent).toBe(
      nbDossiers.toString()
    )
  })

  it('extract number of fail', () => {
    const nbDossiers = 10
    // Setup : Mock des variables globales et DOM (comme dans beforeEach)
    global.totalDossiers = 0
    global.successCount = 0
    global.errorCount = 0

    const message = `Dossiers en échec: ${nbDossiers}`

    updateStatsFromLog(message)

    expect(global.errorCount).toBe(10)
    expect(global.totalDossiers).toBe(0)
    expect(global.successCount).toBe(0)
  })

  it('check ratio of fail', () => {
    const nbDossiers = 50
    // Setup : Mock des variables globales et DOM
    global.totalDossiers = 0
    global.successCount = 0
    global.errorCount = 0

    const message = `${nbDossiers}/100 dossiers récupérés (50%)`

    updateStatsFromLog(message)

    expect(global.errorCount).toBe(50)
    expect(global.totalDossiers).toBe(0)
    expect(global.successCount).toBe(0)
  })
})

describe('copyLogs', () => {
  let clipboardWriteTextMock
  let showNotificationMock
  let consoleErrorSpy

  beforeEach(() => {
    // Setup DOM
    document.body.innerHTML = `
        <div id="logs_content">Sample log text</div>
      `

    // Mock navigator.clipboard
    clipboardWriteTextMock = jest.fn()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: clipboardWriteTextMock },
      writable: true
    })

    // Mock showNotification
    showNotificationMock = jest.fn()
    global.showNotification = showNotificationMock

    // Spy on console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
    jest.restoreAllMocks()
  })

  it('copy logs text to clipboard successfully', async () => {
    clipboardWriteTextMock.mockResolvedValue()

    copyLogs()

    await new Promise((resolve) => setTimeout(resolve, 0)) // Wait for promise

    expect(clipboardWriteTextMock).toHaveBeenCalledWith('Sample log text')
    expect(showNotificationMock).toHaveBeenCalledWith(
      'Logs copiés dans le presse-papiers',
      'success'
    )
    expect(consoleErrorSpy).not.toHaveBeenCalled()
  })

  it('handles clipboard copy error', async () => {
    const error = new Error('Clipboard error')
    clipboardWriteTextMock.mockRejectedValue(error)

    copyLogs()

    await new Promise((resolve) => setTimeout(resolve, 0)) // Wait for promise

    expect(clipboardWriteTextMock).toHaveBeenCalledWith('Sample log text')
    expect(showNotificationMock).toHaveBeenCalledWith(
      'Erreur lors de la copie des logs',
      'error'
    )
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Erreur lors de la copie:',
      error
    )
  })

  it('uses textContent if innerText is not available', () => {
    // textContent and innerText are similar in jsdom, but test fallback
    const logsElement = document.getElementById('logs_content')
    logsElement.textContent = 'Text content'
    logsElement.innerText = '' // Simulate no innerText

    clipboardWriteTextMock.mockResolvedValue()

    copyLogs()

    expect(clipboardWriteTextMock).toHaveBeenCalledWith('Text content')
  })
})

describe('parseLogMessage', () => {
  it('return default counts with empty message', () => {
    const result = parseLogMessage('')
    expect(result).toEqual({ success: 0, error: 0, total: 0 })
  })

  it('extract "Nombre total de dossiers trouvés"', () => {
    const result = parseLogMessage('Nombre total de dossiers trouvés: 150')
    expect(result.total).toBe(150)
  })

  it('extract "Après filtrage: N dossiers"', () => {
    const result = parseLogMessage('Après filtrage: 120 dossiers')
    expect(result.total).toBe(120)
  })

  it('extract "N dossiers trouvés"', () => {
    const result = parseLogMessage('120 dossiers trouvés')
    expect(result.total).toBe(120)
  })

  it('extract "N dossiers à traiter"', () => {
    const result = parseLogMessage('88 dossiers à traiter')
    expect(result.total).toBe(88)
  })

  it('extract "Dossiers traités avec succès"', () => {
    const result = parseLogMessage('Dossiers traités avec succès: 75')
    expect(result.success).toBe(75)
  })

  it('extract "Résumé upsert table..._dossiers...: N succès"', () => {
    const result = parseLogMessage(
      'Résumé upsert table Demarche_123_dossiers: 10 succès, 2 échecs'
    )
    expect(result.success).toBe(10)
  })

  it('accumulated success from upsert', () => {
    const result = parseLogMessage(
      'Résumé upsert table Demarche_123_dossiers: 10 succès, 2 échecs',
      { success: 5, error: 0, total: 0 }
    )
    expect(result.success).toBe(15)
  })

  it('extract "Dossiers en échec"', () => {
    const result = parseLogMessage('Dossiers en échec: 5')
    expect(result.error).toBe(5)
  })

  it('extract "Échec: N"', () => {
    const result = parseLogMessage('Échec: 3')
    expect(result.error).toBe(3)
  })

  it('extract "Échecs: N"', () => {
    const result = parseLogMessage('Échecs: 3')
    expect(result.error).toBe(3)
  })

  it('extract "N erreurs détectées"', () => {
    const result = parseLogMessage('3 erreurs détectées')
    expect(result.error).toBe(3)
  })

  it('extract "N dossiers n\'ont pas pu être récupérés"', () => {
    const result = parseLogMessage("5 dossiers n'ont pas pu être récupérés")
    expect(result.error).toBe(5)
  })

  it('ne compte pas comme erreur un ratio >= 80%', () => {
    const result = parseLogMessage('80/100 dossiers récupérés (80%)')
    expect(result.error).toBe(0)
  })

  it('error if ratio < 80%', () => {
    const result = parseLogMessage('50/100 dossiers récupérés (50%)')
    expect(result.error).toBe(50)
  })

  it('detect "Erreur lors de la récupération du dossier"', () => {
    const result = parseLogMessage(
      'Erreur lors de la récupération du dossier 12345'
    )
    expect(result.error).toBe(1)
  })

  it('detect "max retries exceeded"', () => {
    const result = parseLogMessage('max retries exceeded for request')
    expect(result.error).toBe(1)
  })

  it('detect "sslerror" (insensitive case)', () => {
    const result = parseLogMessage('SSLerror during request')
    expect(result.error).toBe(1)
  })

  it('detect "connection failed"', () => {
    const result = parseLogMessage('The connection failed')
    expect(result.error).toBe(1)
  })

  it('detect "timeout"', () => {
    const result = parseLogMessage('Request timeout after 30s')
    expect(result.error).toBe(1)
  })

  it('accumulated counts from initial object', () => {
    const result = parseLogMessage('', { success: 1, error: 2, total: 3 })
    expect(result).toEqual({ success: 1, error: 2, total: 3 })
  })

  it('100 maximum', () => {
    const result = parseLogMessage(
      'Nombre total de dossiers trouvés: 200',
      { success: 0, error: 0, total: 100 }
    )
    expect(result.total).toBe(200)
  })

  it('dont replace with lower value', () => {
    const result = parseLogMessage(
      'Nombre total de dossiers trouvés: 50',
      { success: 0, error: 0, total: 100 }
    )

    expect(result.total).toBe(100)
  })

  it('conserve la plus grande valeur d\'erreur', () => {
    const result = parseLogMessage(
      'Dossiers en échec: 10',
      { success: 0, error: 3, total: 0 }
    )

    expect(result.error).toBe(10)
  })
})
