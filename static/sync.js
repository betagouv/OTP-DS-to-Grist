const startSync = async (config) => {
  if (!config)
    return App.showNotification('Configuration non chargée', 'error')

  // Collecter les filtres
  const filters = {
    date_depot_debut: document.getElementById('date_debut').value,
    date_depot_fin: document.getElementById('date_fin').value,
    statuts_dossiers: Array.from(
      document.querySelectorAll('input[name="statuts"]:checked')
    ).map(el => el.value).join(','),
    groupes_instructeurs: Array.from(
      document.querySelectorAll('input[name="groupes"]:checked')
    ).map(el => el.value).join(',')
  }

  const gristContext = await getGristContext()
  const gristDocId = gristContext.docId
  const gristUserId = gristContext.userId

  try {
    const response = await fetch('/api/start-sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        config,
        filters: filters,
        grist_user_id: gristUserId,
        grist_doc_id: gristDocId
      })
    })

    const result = await response.json()

    if (!result.success)
      return App.showNotification(result.message, 'error')

    currentTaskId = result.task_id
    startTime = Date.now()

    // Réinitialiser les compteurs
    errorCount = 0
    successCount = 0
    totalDossiers = 0

    // Afficher la zone de progression
    document.getElementById('sync_controls').style.display = 'none'
    document.getElementById('sync_progress').style.display = 'block'
    document.getElementById('sync_result').style.display = 'none'

    // Réinitialiser les compteurs et l'affichage
    logsCount = 0
    document.getElementById('logs_count').textContent = '0'
    document.getElementById('logs_content').innerHTML = ''

    // Réinitialiser les statistiques
    document.getElementById('progress_bar').style.width = '0%'
    document.getElementById('progress_percentage').textContent = '0%'
    document.getElementById('current_status').textContent = 'Initialisation...'
    document.getElementById('elapsed_time').textContent = '0s'
    document.getElementById('processed_count').textContent = '0'
    document.getElementById('processing_speed').textContent = '-'
    document.getElementById('eta').textContent = '-'

    App.showNotification('Synchronisation démarrée', 'success')

  } catch (error) {
    console.error('Erreur:', error)
    App.showNotification('Erreur lors du démarrage de la synchronisation', 'error')
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { startSync }
}
