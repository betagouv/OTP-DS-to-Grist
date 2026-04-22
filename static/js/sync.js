if (typeof formatDuration === 'undefined')
  ({ formatDuration } = require('./utils.js'))

if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

const showSyncBanner = (
  containerId,
  status,
  successCount,
  errorCount,
  timestamp,
  syncType
) => {
  const container = document.getElementById(containerId)
  const subContainer = container.querySelector('.sync_banner_template')
  if (!container || !subContainer) return

  const isSuccess = status === 'success'
  const isWarning = status === 'warning'
  const alertClass = isSuccess ? 'fr-alert--success' : isWarning ? 'fr-alert--warning' : 'fr-alert--error'
  const typeLabel = syncType === 'auto' ? 'automatique' : syncType === 'manual' ? 'manuelle' : ''
  const message = isSuccess ? 'Synchronisation terminée avec succès' : 'Synchronisation terminée avec erreur(s)'
  const title = typeLabel ? `${message} (${typeLabel})` : message
  const count = `${successCount} dossiers traités avec succès, ${errorCount} en échec`
  const date = timestamp ? new Date(timestamp).toLocaleString('fr-FR') : ''

  subContainer.querySelector('.fr-alert').classList.add(alertClass)
  subContainer.querySelector('h3').innerText = title
  subContainer.querySelector('.sync-banner-count').innerText = count
  subContainer.querySelector('.sync-banner-date').innerText = date

  container.style.display = 'block'
}

const startSync = async (otp_config_id) => {
  document.getElementById('config_check_result').style.display = 'none'
  if (!otp_config_id)
    return showNotification('ID de configuration manquant', 'error')

  // Collecter les filtres
  const filters = {
    date_depot_debut: document.getElementById('date_debut').value,
    date_depot_fin: document.getElementById('date_fin').value,
    statuts_dossiers: Array.from(
      document.querySelectorAll('input[name="statuts"]:checked')
    )
      .map((el) => el.value)
      .join(','),
    groupes_instructeurs: Array.from(
      document.querySelectorAll('input[name="groupes"]:checked')
    )
      .map((el) => el.value)
      .join(',')
  }

  const gristContext = await getGristContext()
  const gristDocId = gristContext.docId
  const gristUserId = gristContext.userId

  try {
    const response = await fetch('/api/start-sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        otp_config_id,
        filters: filters,
        grist_user_id: gristUserId,
        grist_doc_id: gristDocId
      })
    })

    const result = await response.json()

    if (!result.success) return showNotification(result.message, 'error')

    startTime = Date.now()

    // Réinitialiser les compteurs
    errorCount = 0
    successCount = 0
    totalDossiers = 0

    // Ferme les volets
    document
      .getElementById('accordion-ds')
      .setAttribute('aria-expanded', 'false')
    document
      .getElementById('accordion-grist')
      .setAttribute('aria-expanded', 'false')
    document
      .getElementById('accordion-settings')
      .setAttribute('aria-expanded', 'false')

    // Afficher la zone de progression
    document.getElementById('sync_progress').style.display = 'block'
    document.getElementById('sync_progress_container').style.display = 'block'
    document.getElementById('sync_result').style.display = 'none'

    document
      .getElementById('sync_progress_container')
      .scrollIntoView({ behavior: 'smooth' })

    // Réinitialiser les compteurs et l'affichage
    logsCount = 0
    document.getElementById('logs_count').textContent = '0'
    document.getElementById('logs_content').innerHTML = ''

    // Réinitialiser les statistiques
    document.getElementById('progress_bar').style.width = '0%'
    document.getElementById('progress_percentage').textContent = '0%'
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
  document.getElementById('sync-progress-text').textContent = `${task.message}`

  // Mettre à jour le temps écoulé
  if (startTime) {
    const elapsed = (Date.now() - startTime) / 1000
    document.getElementById('elapsed_time').textContent =
      formatDuration(elapsed)

    // Calculer la vitesse en dossiers/s et l'ETA seulement si on a des données valides
    if (elapsed > 10 && successCount > 0) {
      // Attendre au moins 10 secondes pour un calcul stable
      const dossiersPerSecond = successCount / elapsed
      processingSpeedElement.textContent = `${dossiersPerSecond.toFixed(1)} dossiers/s`

      // Calculer l'ETA basé sur la progression et non sur le nombre total de dossiers
      if (progress > 0 && progress < 100) {
        const progressRate = progress / elapsed // pourcentage par seconde
        const remainingProgress = 100 - progress
        const remainingTime = remainingProgress / progressRate

        if (remainingTime > 0 && remainingTime < 86400) {
          // Limiter à 24h max
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

    newLogs.forEach((log) => {
      const logTime = new Date(log.timestamp * 1000).toLocaleTimeString()
      const message = log.message

      // Détecter les erreurs pour les mettre en couleur
      const isError =
        message.toLowerCase().includes('erreur') ||
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

    // Afficher le bouton de copie si des logs existent
    const copyBtn = document.getElementById('copy_logs_btn')
    if (logsCount > 0) {
      copyBtn.style.display = 'inline-block'
    } else {
      copyBtn.style.display = 'none'
    }

    // Auto-scroll vers le bas si les logs sont visibles
    if (logsVisible) logsContent.scrollTop = logsContent.scrollHeight
  }

  // Gérer la fin de la tâche
  if (task.status === 'completed' || task.status === 'error') {
    const syncResultDiv = document.getElementById('sync_result')
    if (syncResultDiv) syncResultDiv.style.display = 'block'

    // Clear auto banner and show manual result
    const resultContentAuto = document.getElementById('result_content_auto')
    const resultContentManual = document.getElementById('result_content_manual')
    if (resultContentAuto) resultContentAuto.innerHTML = ''

    // Déterminer le type de résultat en fonction des erreurs détectées
    const hasSignificantErrors = errorCount > 0 || task.status === 'error'

    if (task.status === 'completed' && !hasSignificantErrors) {
      if (task.sync_reason === 'already_up_to_date') {
        if (resultContentManual) resultContentManual.innerHTML = `<div class="fr-alert fr-alert--info">
          <h3 class="fr-alert__title">Grist déjà à jour</h3>
          <p>Aucun dossier nouveau ou modifié depuis la dernière synchronisation.</p>
          <p>${task.message}</p>
        </div>`
        showNotification('Grist déjà à jour', 'info')
      } else {
        showSyncBanner('result_content_manual', 'success', successCount, errorCount)
        showNotification('Synchronisation terminée avec succès!', 'success')
      }
    } else if (
      task.status === 'completed' &&
      hasSignificantErrors &&
      successCount > 0
    ) {
      showSyncBanner('result_content_manual', 'warning', successCount, errorCount)
      showNotification('Synchronisation terminée avec des erreurs', 'warning')
    } else {
      showSyncBanner('result_content_manual', 'error', successCount, errorCount)
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
      showNotification(
        "Configuration non sauvegardée. Veuillez sauvegarder la configuration avant d'activer la synchronisation automatique.",
        'error'
      )
      // Revert checkbox
      document.getElementById('auto_sync_enabled').checked = false
      return
    }

    if (!config.has_grist_key) {
      showNotification('Clé grist manquante', 'error')
      // Revert checkbox
      document.getElementById('auto_sync_enabled').checked = false
      return
    }

    const method = enabled ? 'POST' : 'DELETE'
    const response = await fetch('/api/schedule', {
      method: method,
      headers: {
        'Content-Type': 'application/json'
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
      showNotification(
        result.message || 'Erreur lors de la modification',
        'error'
      )
      // Revert checkbox
      document.getElementById('auto_sync_enabled').checked = !enabled
    }
  } catch (error) {
    console.error('Erreur:', error)
    showNotification(
      'Erreur lors de la modification de la synchronisation automatique',
      'error'
    )
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

    if (!config.otp_config_id) {
      if (checkbox) {
        checkbox.disabled = true
        checkbox.checked = false
      }
      return
    }

    if (checkbox) checkbox.disabled = false

    const scheduleResponse = await fetch(`/api/schedule?otp_config_id=${config.otp_config_id}`)
    const scheduleResult = await scheduleResponse.json()

    if (checkbox) checkbox.checked = scheduleResult.enabled || false

    const syncLogResponse = await fetch(`/api/sync-log/latest?otp_config_id=${config.otp_config_id}`)
    const syncLogResult = await syncLogResponse.json()

    let hasBanner = false

    if (syncLogResult.success && syncLogResult.auto) {
      const auto = syncLogResult.auto
      showSyncBanner(
        'result_content_auto',
        auto.status,
        auto.success_count,
        auto.error_count,
        auto.timestamp,
        'auto'
      )
      hasBanner = true
    }

    if (syncLogResult.success && syncLogResult.manual) {
      const manual = syncLogResult.manual
      showSyncBanner(
        'result_content_manual',
        manual.status,
        manual.success_count,
        manual.error_count,
        manual.timestamp,
        'manual'
      )
      hasBanner = true
    }

    const syncProgressContainer = document.getElementById('sync_progress_container')
    if (syncProgressContainer) {
      syncProgressContainer.style.display = hasBanner ? 'block' : 'none'
    }
  } catch (error) {
    console.error("Erreur lors du chargement de l'état auto sync:", error)
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    startSync,
    updateTaskProgress,
    toggleAutoSync,
    loadAutoSyncState,
    showSyncBanner
  }
}
