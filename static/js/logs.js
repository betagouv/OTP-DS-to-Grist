const toggleLogs = (logsVisible) => {
  const container = document.getElementById('logs_container')
  const icon = document.getElementById('logs_toggle_icon')
  const text = document.getElementById('logs_toggle_text')

  logsVisible = !logsVisible

  if (logsVisible) {
    container.style.display = 'block'
    icon.className = 'fas fa-chevron-up fr-mr-1w'
    text.textContent = 'Masquer les logs'

    // Auto-scroll vers le bas
    setTimeout(() => (container.scrollTop = container.scrollHeight), 100)
  } else {
    container.style.display = 'none'
    icon.className = 'fas fa-chevron-down fr-mr-1w'
    text.textContent = 'Afficher les logs'
  }

  return logsVisible
}

function parseLogMessage(message, counts = { success: 0, error: 0, total: 0 }) {
  const result = { ...counts }

  let m = message.match(/Nombre total de dossiers trouvés:\s*(\d+)/i)
  if (!m) m = message.match(/Après filtrage:\s*(\d+)\s+dossiers/i)
  if (!m) m = message.match(/(\d+)\s+dossiers?\s+(?:trouvés?|à traiter)/i)
  if (m) result.total = Math.max(result.total, parseInt(m[1]))

  const successMatch = message.match(/Dossiers traités avec succès:\s*(\d+)/i)
  if (successMatch) {
    result.success = parseInt(successMatch[1])
  } else {
    const resume = message.match(/Résumé upsert table.*_dossiers.*:\s*(\d+)\s+succès/i)
    if (resume) result.success += parseInt(resume[1])
  }

  let e = message.match(/Dossiers en échec:\s*(\d+)/i)
  if (!e) e = message.match(/Échecs?:\s*(\d+)/i)
  if (!e) e = message.match(/(\d+)\s+erreurs?\s+détectées?/i)
  if (!e) e = message.match(/(\d+)\s+dossiers?\s+n'ont\s+pas\s+pu\s+être\s+récupérés/i)
  if (e) result.error = Math.max(result.error, parseInt(e[1]))

  const rec = message.match(/(\d+)\/(\d+)\s+dossiers?\s+récupérés?\s+\((\d+(?:\.\d+)?)%\)/i)
  if (rec && parseFloat(rec[3]) < 80) {
    result.error = Math.max(result.error, parseInt(rec[2]) - parseInt(rec[1]))
  }

  const lc = message.toLowerCase()
  if (lc.includes('erreur lors de la récupération du dossier') ||
      lc.includes('max retries exceeded') ||
      lc.includes('sslerror') ||
      (lc.includes('connection') && lc.includes('failed')) ||
      lc.includes('timeout')) {
    result.error++
  }

  return result
}

const extractStatsFromLog = (message) => {
  const counts = parseLogMessage(message, {
    success: successCount,
    error: errorCount,
    total: totalDossiers
  })
  totalDossiers = counts.total
  successCount = counts.success
  errorCount = counts.error
  document.getElementById('processed_count').textContent = counts.success
}

const copyLogs = () => {
  const logsContent = document.getElementById('logs_content')
  const text = logsContent.textContent || logsContent.innerText
  navigator.clipboard
    .writeText(text)
    .then(() => {
      showNotification('Logs copiés dans le presse-papiers', 'success')
    })
    .catch((err) => {
      console.error('Erreur lors de la copie:', err)
      showNotification('Erreur lors de la copie des logs', 'error')
    })
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    toggleLogs,
    parseLogMessage,
    extractStatsFromLog,
    copyLogs
  }
}
