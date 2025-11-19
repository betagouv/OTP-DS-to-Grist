if (typeof formatDuration === 'undefined')
  ({ formatDuration } = require('./utils.js'))

if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

const startSync = async (config) => {
  if (!config)
    return showNotification('Configuration non chargée', 'error')

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
      return showNotification(result.message, 'error')

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

    showNotification('Synchronisation démarrée', 'success')

    return result.task_id
  } catch (error) {
    console.error('Erreur:', error)
    showNotification('Erreur lors du démarrage de la synchronisation', 'error')
  }
}

const updateTaskProgress = (task) => {
  if (!task) return

  const etaElement = document.getElementById('eta')
  const processingSpeedElement = document.getElementById('processing_speed')

  // Mettre à jour la barre de progression
  const progress = Math.round(task.progress || 0)
  document.getElementById('progress_bar').style.width = `${progress}%`
  document.getElementById('progress_percentage').textContent = `${progress}%`

  // Mettre à jour le statut
  document.getElementById('current_status').textContent = task.message || 'En cours...'

  // Mettre à jour le temps écoulé
  if (startTime) {
    const elapsed = (Date.now() - startTime) / 1000
    document.getElementById('elapsed_time').textContent = formatDuration(elapsed)

    // Calculer la vitesse en dossiers/s et l'ETA seulement si on a des données valides
    if (elapsed > 10 && successCount > 0) { // Attendre au moins 10 secondes pour un calcul stable
      const dossiersPerSecond = successCount / elapsed
      processingSpeedElement.textContent = `${dossiersPerSecond.toFixed(1)} dossiers/s`

      // Calculer l'ETA basé sur la progression et non sur le nombre total de dossiers
      if (progress > 0 && progress < 100) {
        const progressRate = progress / elapsed // pourcentage par seconde
        const remainingProgress = 100 - progress
        const remainingTime = remainingProgress / progressRate

        if (remainingTime > 0 && remainingTime < 86400) { // Limiter à 24h max
          etaElement.textContent = formatDuration(remainingTime)
        } else {
          etaElement.textContent = '-'
        }
      } else {
        etaElement.textContent = '-'
      }
    } else if (elapsed > 0 && successCount === 0) {
      // Si aucun dossier traité après un certain temps
      processingSpeedElement.textContent = '0.0 dossiers/s'
      etaElement.textContent = '-'
    } else {
      // Phase d'initialisation
      processingSpeedElement.textContent = '-'
      etaElement.textContent = '-'
    }
  }

  // Ajouter les nouveaux logs
  if (task.logs && task.logs.length > logsCount) {
    const newLogs = task.logs.slice(logsCount)
    const logsContent = document.getElementById('logs_content')

    newLogs.forEach(log => {
      const logTime = new Date(log.timestamp * 1000).toLocaleTimeString()
      const message = log.message

      // Détecter les erreurs pour les mettre en couleur
      const isError = message.toLowerCase().includes('erreur') || 
        message.toLowerCase().includes('error') || 
        message.toLowerCase().includes('échec') ||
        message.toLowerCase().includes('failed')

      const logStyle = isError ? 'color: #ce0500; font-weight: bold;' : ''

      logsContent.innerHTML += `<div style="color: #666; font-size: 0.8rem;">
        [${logTime}]</div><div style="margin-bottom: 0.5rem; ${logStyle}">${escapeHtml(message)}
      </div>`

      // Extraire les statistiques depuis les logs
      extractStatsFromLog(message)
    })

    logsCount = task.logs.length
    document.getElementById('logs_count').textContent = logsCount

    // Auto-scroll vers le bas si les logs sont visibles
    if (logsVisible)
      logsContent.scrollTop = logsContent.scrollHeight
  }

  // Gérer la fin de la tâche
  if (task.status === 'completed' || task.status === 'error') {
    document.getElementById('sync_result').style.display = 'block'
    document.getElementById('sync_controls').style.display = 'block'

    const resultContent = document.getElementById('result_content')

    // Déterminer le type de résultat en fonction des erreurs détectées
    const hasSignificantErrors = errorCount > 0 || task.status === 'error'
    const successRate = totalDossiers > 0 ? (successCount / totalDossiers) * 100 : 0

    if (task.status === 'completed' && !hasSignificantErrors) {
      resultContent.innerHTML = `<div class="fr-alert fr-alert--success">
        <h3 class="fr-alert__title">Synchronisation terminée avec succès!</h3>
        <p>${task.message}</p>
        <p><strong>${successCount}</strong> dossiers traités avec succès</p>
      </div>`

      showNotification('Synchronisation terminée avec succès!', 'success')
    } else if (task.status === 'completed' && hasSignificantErrors && successCount > 0) {
      resultContent.innerHTML = ` <div class="fr-alert fr-alert--warning">
        <h3 class="fr-alert__title">Synchronisation terminée avec des erreurs</h3>
        <p>${task.message}</p>
        <p><strong>${successCount}</strong> dossiers traités avec succès, <strong>${errorCount}</strong> en échec</p>
        <p>Taux de réussite: ${successRate.toFixed(1)}%</p>
      </div>`
      showNotification('Synchronisation terminée avec des erreurs', 'warning')
    } else {
      resultContent.innerHTML = `<div class="fr-alert fr-alert--error">
        <h3 class="fr-alert__title">Erreur lors de la synchronisation</h3>
        <p>${task.message}</p>
        ${errorCount > 0 ? `<p><strong>${errorCount}</strong> erreurs détectées</p>` : ''}
      </div>
      `
      showNotification('Erreur lors de la synchronisation', 'error')
    }

  }
}

const toggleAutoSync = async (enabled) => {
  try {
    const gristContext = await getGristContext()
    const configResponse = await fetch(`/api/config${gristContext.params}`)
    const config = await configResponse.json()

    if (!config.otp_config_id) {
      showNotification('Configuration non sauvegardée. Veuillez sauvegarder la configuration avant d\'activer la synchronisation automatique.', 'error')
      // Revert checkbox
      document.getElementById('auto_sync_enabled').checked = false
      return
    }

    const method = enabled ? 'POST' : 'DELETE'
    const response = await fetch('/api/schedule', {
      method: method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        otp_config_id: config.otp_config_id
      })
    })

    const result = await response.json()

    if (result.success) {
      const status = enabled ? 'activée' : 'désactivée'
      showNotification(`Synchronisation automatique ${status}`, 'success')
    } else {
      showNotification(result.message || 'Erreur lors de la modification', 'error')
      // Revert checkbox
      document.getElementById('auto_sync_enabled').checked = !enabled
    }
  } catch (error) {
    console.error('Erreur:', error)
    showNotification('Erreur lors de la modification de la synchronisation automatique', 'error')
    // Revert checkbox
    document.getElementById('auto_sync_enabled').checked = !enabled
  }
}

const loadAutoSyncState = async () => {
  try {
    const gristContext = await getGristContext()
    const configResponse = await fetch(`/api/config${gristContext.params}`)
    const config = await configResponse.json()

    const checkbox = document.getElementById('auto_sync_enabled')
    const statusDiv = document.getElementById('last_sync_status')

    if (!config.otp_config_id) {
      checkbox.disabled = true
      checkbox.checked = false
      statusDiv.style.display = 'none'
      return
    }

    checkbox.disabled = false

    // Check if schedule exists and is enabled
    const response = await fetch(`/api/schedule?otp_config_id=${config.otp_config_id}`)
    const result = await response.json()

    checkbox.checked = result.enabled || false

    // Afficher le statut de la dernière synchronisation si activé
    if (result.enabled && result.last_run) {
      const lastRunDate = new Date(result.last_run + '+00:00').toLocaleString('fr-FR')
      const statusClass = result.last_status === 'success' ? 'fr-alert--success' : 'fr-alert--error'
      const statusText = result.last_status === 'success' ? 'Succès' : 'Échec'
      const icon = result.last_status === 'success' ? 'check-circle' : 'exclamation-triangle'

      statusDiv.innerHTML = `
        <div class="fr-alert ${statusClass} fr-alert--sm">
          <p><i class="fas fa-${icon} fr-mr-1v" aria-hidden="true"></i>
          Dernière synchronisation automatique : ${statusText} (${lastRunDate})</p>
        </div>`
      statusDiv.style.display = 'block'
    } else {
      statusDiv.style.display = 'none'
    }
  } catch (error) {
    console.error('Erreur lors du chargement de l\'état auto sync:', error)
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { startSync, updateTaskProgress, toggleAutoSync, loadAutoSyncState }
}
