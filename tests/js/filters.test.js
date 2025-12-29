const { JSDOM } = require('jsdom')
const {
  resetFilters,
  loadGroupes
} = require('../../static/js/filters.js')

// Setup DOM environment
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost:3000',
  pretendToBeVisual: true,
  resources: 'usable'
})

global.window = dom.window
global.document = dom.window.document
global.navigator = dom.window.navigator

describe('filters', () => {
  beforeEach(() => {
    // Reset DOM before each test
    document.body.innerHTML = `
      <input id="date_debut" value="2023-01-01">
      <input id="date_fin" value="2023-12-31">
      <input type="checkbox" name="statuts" checked>
      <input type="checkbox" name="statuts" checked>
      <input type="checkbox" name="groupes" checked>
      <div id="active_filters" style="display: block;"></div>
      <div id="groupes_container"></div>
    `

    // Mock saveConfiguration
    global.saveConfiguration = jest.fn().mockResolvedValue()
  })

  describe('resetFilters', () => {
    it(
      'reset all inputs and hide enabled filters',
      async () => {
        await resetFilters()

        // Check dates
        expect(document.getElementById('date_debut').value).toBe('')
        expect(document.getElementById('date_fin').value).toBe('')

        // Check checkboxes
        document.querySelectorAll('input[name="statuts"]').forEach(el => {
          expect(el.checked).toBe(false)
        })
        document.querySelectorAll('input[name="groupes"]').forEach(el => {
          expect(el.checked).toBe(false)
        })

        // Check active filters visibility
        const activeFilters = document.getElementById('active_filters')
        expect(activeFilters.style.display).toBe('none')

        // Check saveConfiguration was called
        expect(saveConfiguration).toHaveBeenCalled()
      }
    )
  })

  describe('loadGroupes', () => {
    it(
      'should load and display groups with otp_config_id',
      async () => {
        // Mock fetch avec données de groupes
        global.fetch = jest.fn().mockResolvedValue({
          json: jest.fn().mockResolvedValue([
            [1, 'Groupe A'],
            [2, 'Groupe B']
          ])
        })

        // Mock console.error pour éviter les logs en test
        global.console.error = jest.fn()

        // Appel de la fonction avec otp_config_id
        await loadGroupes(123)

        // Vérifications
        const container = document.getElementById('groupes_container')
        expect(container.innerHTML).toContain('Groupe A')
        expect(container.innerHTML).toContain('Groupe B')
        expect(container.innerHTML).toContain('<input type="checkbox" id="groupe_1"')
        expect(console.error).not.toHaveBeenCalled()
      }
    )

    it(
      'should display message if no group found',
      async () => {
        // Mock fetch avec liste vide
        global.fetch = jest.fn().mockResolvedValue({
          json: jest.fn().mockResolvedValue([])  // Aucun groupe
        })

        // Mock console.error
        global.console.error = jest.fn()

        // Appel de la fonction avec otp_config_id
        await loadGroupes(456)

        // Vérifications
        const container = document.getElementById('groupes_container')
        expect(container.innerHTML).toContain('Aucun groupe instructeur disponible')
        expect(console.error).not.toHaveBeenCalled()
      }
    )

    it(
      'should handle errors and display message',
      async () => {
        // Mock fetch pour lever une erreur
        global.fetch = jest.fn().mockRejectedValue(new Error('Network error'))

        // Mock console.error
        global.console.error = jest.fn()

        // Appel de la fonction avec otp_config_id
        await loadGroupes(789)

        // Vérifications
        const container = document.getElementById('groupes_container')
        expect(container.innerHTML).toContain('Erreur lors du chargement des groupes instructeurs')
        expect(console.error).toHaveBeenCalledWith('Erreur lors du chargement des groupes:', expect.any(Error))
      }
    )

    it(
      'should not make request when otp_config_id is falsy',
      async () => {
        // Mock fetch pour vérifier qu'il n'est pas appelé
        global.fetch = jest.fn()

        // Mock console.log pour vérifier le message
        global.console.log = jest.fn()

        // Appel de la fonction sans otp_config_id
        await loadGroupes(null)

        // Vérifications
        expect(fetch).not.toHaveBeenCalled()
        expect(console.log).toHaveBeenCalledWith('Aucun otp_config_id fourni, pas de chargement des groupes')

        const container = document.getElementById('groupes_container')
        expect(container.innerHTML).toContain('Aucun identifiant de configuration disponible')
      }
    )

    it(
      'should not make request when otp_config_id is undefined',
      async () => {
        // Mock fetch pour vérifier qu'il n'est pas appelé
        global.fetch = jest.fn()

        // Mock console.log pour vérifier le message
        global.console.log = jest.fn()

        // Appel de la fonction sans otp_config_id
        await loadGroupes(undefined)

        // Vérifications
        expect(fetch).not.toHaveBeenCalled()
        expect(console.log).toHaveBeenCalledWith('Aucun otp_config_id fourni, pas de chargement des groupes')

        const container = document.getElementById('groupes_container')
        expect(container.innerHTML).toContain('Aucun identifiant de configuration disponible')
      }
    )

    it(
      'should call API with correct otp_config_id parameter',
      async () => {
        // Mock fetch avec données de groupes
        const mockFetch = jest.fn().mockResolvedValue({
          json: jest.fn().mockResolvedValue([
            [42, 'Test Group']
          ])
        })
        global.fetch = mockFetch

        // Mock console.error pour éviter les logs en test
        global.console.error = jest.fn()

        // Appel de la fonction avec un otp_config_id spécifique
        await loadGroupes(999)

        // Vérifications
        expect(mockFetch).toHaveBeenCalledWith('/api/groups?otp_config_id=999')
        expect(mockFetch).toHaveBeenCalledTimes(1)

        const container = document.getElementById('groupes_container')
        expect(container.innerHTML).toContain('Test Group')
        expect(container.innerHTML).toContain('groupe_42')
      }
    )
  })
})
