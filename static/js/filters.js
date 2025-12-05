if (typeof formatDate === 'undefined')
  ({ formatDate } = require('./utils.js'))

if (typeof escapeHtml === 'undefined')
  ({ escapeHtml } = require('./utils.js'))

if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

const resetFilters = async () => {
  // Réinitialiser tous les champs de filtre
  document.getElementById('date_debut').value = ''
  document.getElementById('date_fin').value = ''

  document.querySelectorAll('input[name="statuts"]').forEach(el => el.checked = false)
  document.querySelectorAll('input[name="groupes"]').forEach(el => el.checked = false)

  // Masquer les filtres actifs
  document.getElementById('active_filters').style.display = 'none'

  showNotification('Filtres réinitialisés', 'info')

  // Sauvegarder la configuration sans filtres
  try {
    await saveConfiguration()
  } catch (error) {
    console.error('Erreur lors de la sauvegarde après reset des filtres:', error)
    showNotification('Erreur lors de la sauvegarde des filtres réinitialisés', 'error')
  }
}

const applyFilters = () => {
  const activeFilters = []

  // Collecter les filtres de date
  const dateDebut = document.getElementById('date_debut').value
  const dateFin = document.getElementById('date_fin').value

  if (dateDebut)
    activeFilters.push(`Date de début: ${formatDate(dateDebut)}`)

  if (dateFin)
    activeFilters.push(`Date de fin: ${formatDate(dateFin)}`)

  // Collecter les statuts sélectionnés
  const statutsSelected = Array.from(
    document.querySelectorAll('input[name="statuts"]:checked')
  ).map(el => el.value)

  if (statutsSelected.length > 0)
    activeFilters.push(`Statuts: ${statutsSelected.join(', ')}`)

  // Collecter les groupes sélectionnés
  const groupesSelected = Array.from(
    document.querySelectorAll('input[name="groupes"]:checked')
  ).map(el => el.value)

  if (groupesSelected.length > 0) {
    const groupeLabels = groupesSelected.map(num => {
      const checkbox = document.querySelector(`input[name="groupes"][value="${num}"]`)
      return checkbox ? checkbox.nextElementSibling.textContent : `Groupe #${num}`
    })
    activeFilters.push(`Groupes: ${groupeLabels.join(', ')}`)
  }

  // Afficher les filtres actifs
  const activeFiltersDiv = document.getElementById('active_filters')
  const activeFiltersList = document.getElementById('active_filters_list')

  if (activeFilters.length > 0) {
    let filtersHtml = '<ul class="fr-tags-group">'
    activeFilters.forEach(filter => {
      filtersHtml += `<li><button class="fr-tag fr-tag--high-blue-france">${escapeHtml(filter)}</button><li>`
    })
    filtersHtml += '</ul>'
    activeFiltersList.innerHTML = filtersHtml
    activeFiltersDiv.style.display = 'block'
  } else {
    activeFiltersDiv.style.display = 'none'
  }

  showNotification('Filtres appliqués avec succès', 'success')
}

const loadGroupes = async () => {
  const container = document.getElementById('groupes_container')

  try {
    const gristContext = await getGristContext()
    const response = await fetch(`/api/groups${gristContext.params}`)
    const groups = await response.json()

    if (groups.length === 0)
      return container.innerHTML = `<div class="fr-alert fr-alert--info">
        <p>Aucun groupe instructeur disponible ou connexion non établie</p>
      </div>`

    let html = '<div class="fr-grid-row fr-grid-row--gutters">'
    groups.forEach(([number, label]) => {
      html += `<div class="fr-col-12 fr-col-md-6 fr-col-lg-4">
        <div class="fr-checkbox-group">
          <input type="checkbox" id="groupe_${number}" name="groupes" value="${number}">
          <label class="fr-label" for="groupe_${number}">${label} (#${number})</label>
        </div>
      </div>`
    })
    html += '</div>'

    container.innerHTML = html

    // Ajouter les event listeners pour les groupes
    document.querySelectorAll('input[name="groupes"]').forEach(el => {
      el.addEventListener('change', applyFilters)
    })

  } catch (error) {
    console.error('Erreur lors du chargement des groupes:', error)
    container.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>Erreur lors du chargement des groupes instructeurs</p>
    </div>
    `
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { resetFilters, applyFilters, loadGroupes }
}
