/** @jest-environment jsdom */  
jest.mock('../../static/utils.js', () => ({
  formatDate: jest.fn(date => '01/10/2023'),
  escapeHtml: jest.fn(text => text)
}))

const { resetFilters, applyFilters } = require('../../static/filters.js')
const { formatDate } = require('../../static/utils.js')

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

    // Mock App.showNotification
    global.App = { showNotification: jest.fn() }
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
      expect(global.App.showNotification).toHaveBeenCalledWith('Filtres réinitialisés', 'info')
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

    // Mock App.showNotification
    global.App = { showNotification: jest.fn() }

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
      expect(global.App.showNotification).toHaveBeenCalledWith('Filtres appliqués avec succès', 'success')
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
