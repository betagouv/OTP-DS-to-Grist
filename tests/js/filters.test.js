/** @jest-environment jsdom */  
const { resetFilters } = require('../../static/filters.js')

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
