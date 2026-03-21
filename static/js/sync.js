if (typeof formatDuration === 'undefined')
  ({ formatDuration } = require('./utils.js'))

if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

const startSync = async (otp_config_id) => {
  document.getElementById('config_check_result').style.display = 'none'
  if (!otp_config_id)
    return showNotification('ID de configuration manquant', 'error')

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
      headers: { 'Content-Type': 'application/json' },
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
    errorCount = 0
    successCount = 0
    totalDossiers = 0

    document.getElementById('accordion-ds').setAttribute('aria-expanded', 'false')
    document.getElementById('accordion-grist').setAttribute('aria-expanded', 'false')
    document.getElementById('accordion-settings').setAttribute('aria-expanded', 'false')

    document.getElementById('sync_progress').style.display = 'block'
    document.getElementById('sync_progress_container').style.display = 'block'
    document.getElementById('sync_result').style.display = 'none'

    document.getElementById('sync_progress_container').scrollIntoView({ behavior: 'smooth' })

    logsCount = 0
    document.getElementById('logs_count').textContent = '0'
    document.getElementById('logs_content').innerHTML = ''

    document.getElementById('progress_bar').style.width = '0%'
    document.getElementById('progress_percentage').textContent = '0%'
    document.getElementById('elapsed_time').textContent = '0s'
    document.getElementById('processed_count').textContent = '0'
    document.getElementById('processing_speed').textContent = '-'
    document.getElementById('eta').textContent = '-'

    // Réinitialiser le poney
    const ponyWrapper = document.getElementById('pony-wrapper')
    const ponyEl = document.getElementById('pony')
    if (ponyWrapper && ponyEl) {
      ponyWrapper.style.left = '0px'
      ponyEl.style.animationPlayState = 'running'
    }

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

  // Mettre à jour le poney
  const ponyWrapper = document.getElementById('pony-wrapper')
  const ponyEl = document.getElementById('pony')
  if (ponyWrapper && ponyEl) {
    const barContainer = document.getElementById('progress_bar').parentElement
    const trackWidth = barContainer.offsetWidth
    const clampedProgress = Math.min(progress, 97)
    const ponyLeft = Math.max(0, (clampedProgress / 100) * trackWidth - 42)
    ponyWrapper.style.left = ponyLeft + 'px'
    const isFinished = task.status === 'completed' || task.status === 'error'
    ponyEl.style.animationPlayState = isFinished ? 'paused' : 'running'
  }

  // Mettre à jour le message de statut
  const statusEl = document.getElementById('current_status')
  if (statusEl) statusEl.textContent = task.message || 'En cours...'

  // Mettre à jour le temps écoulé
  if (startTime) {
    const elapsed = (Date.now() - startTime) / 1000
    document.getElementById('elapsed_time').textContent = formatDuration(elapsed)

    if (elapsed > 10 && successCount > 0) {
      const dossiersPerSecond = successCount / elapsed
      processingSpeedElement.textContent = `${dossiersPerSecond.toFixed(1)} dossiers/s`

      if (progress > 0 && progress < 100) {
        const progressRate = progress / elapsed
        const remainingProgress = 100 - progress
        const remainingTime = remainingProgress / progressRate

        if (remainingTime > 0 && remainingTime < 86400) {
          etaElement.textContent = formatDuration(remainingTime)
        } else {
          etaElement.textContent = '-'
        }
      } else {
        etaElement.textContent = '-'
      }
    } else if (elapsed > 0 && successCount === 0) {
      processingSpeedElement.textContent = '0.0 dossiers/s'
      etaElement.textContent = '-'
    } else {
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

      const isError =
        message.toLowerCase().includes('erreur') ||
        message.toLowerCase().includes('error') ||
        message.toLowerCase().includes('échec') ||
        message.toLowerCase().includes('failed')

      const logStyle = isError ? 'color: #ce0500; font-weight: bold;' : ''

      logsContent.innerHTML += `<div style="color: #666; font-size: 0.8rem;">[${logTime}]</div><div style="margin-bottom: 0.5rem; ${logStyle}">${escapeHtml(message)}</div>`

      extractStatsFromLog(message)
    })

    logsCount = task.logs.length
    document.getElementById('logs_count').textContent = logsCount

    const copyBtn = document.getElementById('copy_logs_btn')
    if (logsCount > 0) {
      copyBtn.style.display = 'inline-block'
    } else {
      copyBtn.style.display = 'none'
    }

    if (logsVisible) logsContent.scrollTop = logsContent.scrollHeight
  }

  // Gérer la fin de la tâche
  if (task.status === 'completed' || task.status === 'error') {
    document.getElementById('sync_result').style.display = 'block'

    const resultContent = document.getElementById('result_content')
    const hasSignificantErrors = errorCount > 0 || task.status === 'error'
    const successRate = totalDossiers > 0 ? (successCount / totalDossiers) * 100 : 0

    if (task.status === 'completed' && !hasSignificantErrors) {
      if (task.sync_reason === 'already_up_to_date') {
        resultContent.innerHTML = `<div class="fr-alert fr-alert--info">
          <h3 class="fr-alert__title">Grist déjà à jour</h3>
          <p>Aucun dossier nouveau ou modifié depuis la dernière synchronisation.</p>
          <p>${task.message}</p>
        </div>`
        showNotification('Grist déjà à jour', 'info')
      } else {
        resultContent.innerHTML = `<div class="fr-alert fr-alert--success">
          <h3 class="fr-alert__title">Synchronisation terminée avec succès!</h3>
          <p>${task.message}</p>
          <p><strong>${successCount}</strong> dossiers traités avec succès</p>
        </div>`
        showNotification('Synchronisation terminée avec succès!', 'success')
      }
    } else if (task.status === 'completed' && hasSignificantErrors && successCount > 0) {
      resultContent.innerHTML = `<div class="fr-alert fr-alert--warning">
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
      </div>`
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
      document.getElementById('auto_sync_enabled').checked = false
      return
    }

    if (!config.has_grist_key) {
      showNotification('Clé grist manquante', 'error')
      document.getElementById('auto_sync_enabled').checked = false
      return
    }

    const method = enabled ? 'POST' : 'DELETE'
    const response = await fetch('/api/schedule', {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: config.otp_config_id })
    })

    const result = await response.json()

    if (result.success) {
      const status = enabled ? 'activée' : 'désactivée'
      showNotification(`Synchronisation automatique ${status}`, 'success')
    } else {
      showNotification(result.message || 'Erreur lors de la modification', 'error')
      document.getElementById('auto_sync_enabled').checked = !enabled
    }
  } catch (error) {
    console.error('Erreur:', error)
    showNotification('Erreur lors de la modification de la synchronisation automatique', 'error')
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

    const response = await fetch(`/api/schedule?otp_config_id=${config.otp_config_id}`)
    const result = await response.json()

    checkbox.checked = result.enabled || false

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
    console.error("Erreur lors du chargement de l'état auto sync:", error)
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    startSync,
    updateTaskProgress,
    toggleAutoSync,
    loadAutoSyncState
  }
}
