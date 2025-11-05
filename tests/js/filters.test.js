/** @jest-environment jsdom */  
jest.mock('../../static/js/utils.js', () => ({
  formatDate: jest.fn(date => '01/10/2023'),
  escapeHtml: jest.fn(text => text)
}))

jest.mock('../../static/js/notifications.js', () => ({
  showNotification: jest.fn()
}))

const { resetFilters, applyFilters, loadGroupes } = require('../../static/js/filters.js')
const { formatDate } = require('../../static/js/utils.js')

describe('resetFilters', () => {
  beforeEach(() => {
    // Setup DOM simulé
    document.body.innerHTML = `
      <input id="date_debut" value="2023-01-01">
      <input id="date_fin" value="2023-12-31">
      <input type="checkbox" name="statuts" checked>
      <input type="checkbox" name="statuts" checked>
      <input type="checkbox" name="groupes" checked>
      <div id="active_filters" style="display: block;"></div>
      `
  })

  it(
    'reset all inputs and hide enabled filters',
    () => {
      resetFilters()

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

      // Check hided enabled filters
      expect(document.getElementById('active_filters').style.display).toBe('none')

      // Check notification
      expect(showNotification).toHaveBeenCalledWith('Filtres réinitialisés', 'info')
    })
})

describe('applyFilters', () => {
  beforeEach(() => {
    // Setup DOM simulé avec des éléments de filtre
    document.body.innerHTML = `
      <input id="date_debut" value="2023-10-01">
      <input id="date_fin" value="2023-10-31">
      <input type="checkbox" name="statuts" value="en_construction" checked>
      <input type="checkbox" name="statuts" value="en_instruction">
      <input type="checkbox" name="groupes" value="1" checked><label>Groupe A</label>
      <input type="checkbox" name="groupes" value="2"><label>Groupe B</label>
      <div id="active_filters" style="display: none;"></div>
      <div id="active_filters_list"></div>
    `

    formatDate.mockImplementation(date => {
      if (date === '2023-10-01') return '01/10/2023'
      if (date === '2023-10-31') return '31/10/2023'
      return '01/10/2023' // Défaut
    })
  })

  it(
    'get and show filters',
    () => {
      applyFilters()
      const activeFiltersDiv = document.getElementById('active_filters')
      const activeFiltersList = document.getElementById('active_filters_list')

      expect(activeFiltersDiv.style.display).toBe('block')

      // Vérifier le contenu HTML généré (avec formatDate et escapeHtml)
      const expectedHtml = '<ul class="fr-list">' +
        '<li><i class="fas fa-check fr-mr-1w" aria-hidden="true"></i>Date de début: 01/10/2023</li>' +
        '<li><i class="fas fa-check fr-mr-1w" aria-hidden="true"></i>Date de fin: 31/10/2023</li>' +
        '<li><i class="fas fa-check fr-mr-1w" aria-hidden="true"></i>Statuts: en_construction</li>' +
        '<li><i class="fas fa-check fr-mr-1w" aria-hidden="true"></i>Groupes: Groupe A</li>' +
        '</ul>'

      expect(activeFiltersList.innerHTML).toBe(expectedHtml)

      // Vérifier la notification
      expect(showNotification).toHaveBeenCalledWith('Filtres appliqués avec succès', 'success')
    }
  )

  it(
    'hide filters if none is enabled',
    () => {
      // Reset les valeurs
      document.getElementById('date_debut').value = ''
      document.getElementById('date_fin').value = ''
      document.querySelectorAll('input[type="checkbox"]').forEach(el => el.checked = false)

      applyFilters()

      expect(document.getElementById('active_filters').style.display).toBe('none')
    }
  )
})

describe('loadGroupes', () => {
  it(
    'load and display groups',
    async () => {
      // Setup DOM simulé
      document.body.innerHTML = '<div id="groupes_container"></div>'

      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })

      // Mock fetch avec données de groupes
      global.fetch = jest.fn().mockResolvedValue({
        json: jest.fn().mockResolvedValue([
          [1, 'Groupe A'],
          [2, 'Groupe B']
        ])
      })

      // Mock console.error pour éviter les logs en test
      global.console.error = jest.fn()

      // Appel de la fonction
      await loadGroupes()

      // Vérifications
      const container = document.getElementById('groupes_container')
      expect(container.innerHTML).toContain('Groupe A')
      expect(container.innerHTML).toContain('Groupe B')
      expect(container.innerHTML).toContain('<input type="checkbox" id="groupe_1"')
      expect(console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'display message if no group found',
    async () => {
      // Setup DOM simulé
      document.body.innerHTML = `<div id="groupes_container"></div>`

      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })

      // Mock fetch avec liste vide
      global.fetch = jest.fn().mockResolvedValue({
        json: jest.fn().mockResolvedValue([])  // Aucun groupe
      })

      // Mock console.error
      global.console.error = jest.fn()

      // Appel de la fonction
      await loadGroupes()

      // Vérifications
      const container = document.getElementById('groupes_container')
      expect(container.innerHTML).toContain('Aucun groupe instructeur disponible')
      expect(console.error).not.toHaveBeenCalled()
    }
  )

  it(
    'handle errors and display message',
    async () => {
      // Setup DOM simulé
      document.body.innerHTML = `<div id="groupes_container"></div>`

      // Mock getGristContext
      global.getGristContext = jest.fn().mockResolvedValue({ params: '?test=1' })

      // Mock fetch pour lever une erreur
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'))

      // Mock console.error
      global.console.error = jest.fn()

      // Appel de la fonction
      await loadGroupes()

      // Vérifications
      const container = document.getElementById('groupes_container')
      expect(container.innerHTML).toContain('Erreur lors du chargement des groupes instructeurs')
      expect(console.error).toHaveBeenCalledWith('Erreur lors du chargement des groupes:', expect.any(Error))
    }
  )
})
