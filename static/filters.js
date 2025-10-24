const resetFilters = () => {
  // Réinitialiser tous les champs de filtre
  document.getElementById('date_debut').value = ''
  document.getElementById('date_fin').value = ''

  document.querySelectorAll('input[name="statuts"]').forEach(el => el.checked = false)
  document.querySelectorAll('input[name="groupes"]').forEach(el => el.checked = false)

  // Masquer les filtres actifs
  document.getElementById('active_filters').style.display = 'none'

  App.showNotification('Filtres réinitialisés', 'info')
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { resetFilters }
}
