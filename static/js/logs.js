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

const extractStatsFromLog = (message) => {
  const processedCountElement = document.getElementById('processed_count')

  // Extraire le nombre total de dossiers
  let totalMatch = message.match(/Nombre total de dossiers trouvés:\s*(\d+)/i)

  if (!totalMatch)
    totalMatch = message.match(/Après filtrage:\s*(\d+)\s+dossiers/i)

  if (!totalMatch)
    totalMatch = message.match(/(\d+)\s+dossiers?\s+(?:trouvés?|à traiter)/i)

  if (totalMatch) {
    const newTotal = parseInt(totalMatch[1])

    if (newTotal > totalDossiers) {
      totalDossiers = newTotal
      console.log(`Total dossiers mis à jour: ${totalDossiers}`)
    }
  }

  // NOUVELLE LOGIQUE : Extraire le nombre de dossiers traités avec succès
  let successMatch = null

  // 1. Rechercher le message final de succès
  successMatch = message.match(/Dossiers traités avec succès:\s*(\d+)/i)

  // 2. Résumé upsert table dossiers uniquement
  if (!successMatch) {
    const resumeMatch = message.match(
      /Résumé upsert table.*_dossiers.*:\s*(\d+)\s+succès/i
    )
    if (resumeMatch) {
      const lotSuccess = parseInt(resumeMatch[1])
      successCount += lotSuccess
      processedCountElement.textContent = successCount
      console.log(
        `Dossiers lot ajoutés: +${lotSuccess}, total: ${successCount}`
      )
    }
  }

  // 3. Traitement du message final de succès (écrase le compteur)
  if (successMatch) {
    const newSuccess = parseInt(successMatch[1])
    successCount = newSuccess // Utiliser la valeur finale
    processedCountElement.textContent = successCount
    console.log(`Succès final: ${successCount}`)
  }

  // Extraire le nombre d'erreurs/échecs
  let errorMatch = message.match(/Dossiers en échec:\s*(\d+)/i)
  if (!errorMatch) errorMatch = message.match(/Échecs?:\s*(\d+)/i)

  if (!errorMatch) errorMatch = message.match(/(\d+)\s+erreurs?\s+détectées?/i)

  if (!errorMatch)
    errorMatch = message.match(
      /(\d+)\s+dossiers?\s+n'ont\s+pas\s+pu\s+être\s+récupérés/i
    )

  if (errorMatch) {
    const newErrors = parseInt(errorMatch[1])
    if (newErrors > errorCount) {
      errorCount = newErrors
      console.log(`Erreurs mises à jour: ${errorCount}`)
    }
  }

  // Détecter les pourcentages de récupération faibles (signe d'erreurs)
  let recoveryMatch = message.match(
    /(\d+)\/(\d+)\s+dossiers?\s+récupérés?\s+\((\d+(?:\.\d+)?)%\)/i
  )

  if (recoveryMatch) {
    const recovered = parseInt(recoveryMatch[1])
    const total = parseInt(recoveryMatch[2])
    const percentage = parseFloat(recoveryMatch[3])

    if (percentage < 80) {
      // Si moins de 80% récupérés, c'est problématique
      const failedCount = total - recovered
      errorCount = Math.max(errorCount, failedCount)
      console.log(`Échecs détectés depuis taux de récupération: ${failedCount}`)
    }
  }

  // Détecter les messages d'erreur individuels pour incrémenter le compteur
  if (
    message
      .toLowerCase()
      .includes('erreur lors de la récupération du dossier') ||
    message.toLowerCase().includes('max retries exceeded') ||
    message.toLowerCase().includes('sslerror') ||
    (message.toLowerCase().includes('connection') &&
      message.toLowerCase().includes('failed')) ||
    message.toLowerCase().includes('timeout')
  ) {
    errorCount++
    console.log(`Erreur individuelle détectée, total erreurs: ${errorCount}`)
  }
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
    extractStatsFromLog,
    copyLogs
  }
}
