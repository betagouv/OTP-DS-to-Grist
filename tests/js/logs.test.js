/** @jest-environment jsdom */  
const { toggleLogs }  = require('../../static/logs.js')

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
})
