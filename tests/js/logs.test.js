/** @jest-environment jsdom */  
const { toggleLogs, extractStatsFromLog }  = require('../../static/logs.js')

describe(
  'toggleLogs',
  () => {
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

    it('affiche les logs et scroll vers le bas', () => {
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

    it('masque les logs', () => {
      const container = document.getElementById('logs_container')
      const icon = document.getElementById('logs_toggle_icon')
      const text = document.getElementById('logs_toggle_text')

      toggleLogs(true)

      // expect(global.logsVisible).toBe(false)
      expect(container.style.display).toBe('none')
      expect(icon.className).toBe('fas fa-chevron-down fr-mr-1w')
      expect(text.textContent).toBe('Afficher les logs')
    }) 
}
)

describe(
  'extractStatsFromLog',
  () => {
    beforeEach(() => {
      // Setup DOM simulé pour les éléments utilisés par extractStatsFromLog
      document.body.innerHTML = ` <div id="processed_count">0</div>`

      // Reset des variables globales
      global.totalDossiers = 0
      global.successCount = 0
      global.errorCount = 0

      consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {}) // Supprime console.log

      document.body.innerHTML = `
        <div id="processed_count">0</div>
        <div id="logs_count">0</div>`
    })

    afterEach(() => {
      consoleLogSpy.mockRestore() // Restaure console.log
    })

    it(
      'extract total number of "dossiers"',
      () => {
        const nbDossiers = 150
        // Setup : Mock des variables globales utilisées par la fonction
        global.totalDossiers = 0
        global.successCount = 0
        global.errorCount = 0

        const message = `Nombre total de dossiers trouvés: ${nbDossiers}`

        extractStatsFromLog(message)

        expect(global.totalDossiers).toBe(150)
        expect(global.successCount).toBe(0)
        expect(global.errorCount).toBe(0)
        expect(consoleLogSpy).toHaveBeenCalledWith(`Total dossiers mis à jour: ${nbDossiers}`)
      }
    )

    it(
      'extract number of succeded "dossiers"',
      () => {
        const nbDossiers = 75

        // Setup : Mock des variables globales
        global.totalDossiers = 0
        global.successCount = 0
        global.errorCount = 0

        const message = `Dossiers traités avec succès: ${nbDossiers}`

        extractStatsFromLog(message)

        expect(global.successCount).toBe(nbDossiers)
        expect(global.totalDossiers).toBe(0)
        expect(global.errorCount).toBe(0)
        expect(consoleLogSpy).toHaveBeenCalledWith(`Succès final: ${nbDossiers}`)
        expect(document.getElementById('processed_count').textContent).toBe(nbDossiers.toString())
      }
    )

    it(
      'extract number of fail',
      () => {
        const nbDossiers = 10
        // Setup : Mock des variables globales et DOM (comme dans beforeEach)
        global.totalDossiers = 0
        global.successCount = 0
        global.errorCount = 0

        const message = `${nbDossiers} dossiers en échec`

        extractStatsFromLog(message)

        expect(global.errorCount).toBe(10);
        expect(global.totalDossiers).toBe(0)
        expect(global.successCount).toBe(0)
        expect(consoleLogSpy).toHaveBeenCalledWith(`Erreurs mises à jour: ${nbDossiers}`)
      }
    )

    it(
      'check ratio of fail',
      () => {
        const nbDossiers = 50
        // Setup : Mock des variables globales et DOM
        global.totalDossiers = 0
        global.successCount = 0
        global.errorCount = 0

        const message = `${nbDossiers}/100 dossiers récupérés (50%)`

        extractStatsFromLog(message)

        expect(global.errorCount).toBe(50)
        expect(global.totalDossiers).toBe(0)
        expect(global.successCount).toBe(0)
        expect(consoleLogSpy).toHaveBeenCalledWith(`Échecs détectés depuis taux de récupération: ${nbDossiers}`)
      }
    )
  }
)
