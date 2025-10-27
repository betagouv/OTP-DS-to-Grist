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
    setTimeout(
      () => container.scrollTop = container.scrollHeight
      , 100
    )
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
  let totalMatch = message.match(/Nombre total de dossiers trouvés:\s*(\d+)/i);

  if (!totalMatch)
    totalMatch = message.match(/Après filtrage:\s*(\d+)\s+dossiers/i);

  if (!totalMatch)
    totalMatch = message.match(/(\d+)\s+dossiers?\s+(?:trouvés?|à traiter)/i);

  if (totalMatch) {
    const newTotal = parseInt(totalMatch[1]);

    if (newTotal > totalDossiers) {
      totalDossiers = newTotal;
      console.log(`Total dossiers mis à jour: ${totalDossiers}`);
    }
  }

  // NOUVELLE LOGIQUE : Extraire le nombre de dossiers traités avec succès
  let successMatch = null;

  // 1. Rechercher le message final de succès
  successMatch = message.match(/Dossiers traités avec succès:\s*(\d+)/i);

  // 2. Rechercher les messages de lot de succès
  if (!successMatch) {
    const lotMatch = message.match(/Lot\s+\d+\s+terminé:\s*(\d+)\s+dossiers?\s+traités?\s+avec\s+succès/i);

    if (lotMatch) {
      const lotSuccess = parseInt(lotMatch[1]);
      successCount += lotSuccess; // Additionner au lieu de remplacer
      processedCountElement.textContent = successCount;
      console.log(`Dossiers du lot ajoutés: +${lotSuccess}, total: ${successCount}`);
    }
  }

  // 3. Rechercher les messages de création/mise à jour réussies
  if (!successMatch) {
    // Upsert par lot réussi
    const upsertMatch = message.match(/Upsert par lot de\s*(\d+)\s+dossiers.../i);
    if (upsertMatch && !message.includes('ERREUR')) {
      const upsertSuccess = parseInt(upsertMatch[1]);
      successCount = Math.max(successCount, upsertSuccess);
      processedCountElement.textContent = successCount;
      console.log(`Upsert dossiers détecté: ${upsertSuccess}`);
    }
  }

  // 4. Rechercher les créations par lot
  if (!successMatch) {
    const createMatch = message.match(/Création par lot:\s*(\d+)\s+enregistrements?\s+créés?\s+avec\s+succès/i);
    if (createMatch) {
      const createSuccess = parseInt(createMatch[1]);
      successCount += createSuccess; // Additionner
      processedCountElement.textContent = successCount;
      console.log(`Créations ajoutées: +${createSuccess}, total: ${successCount}`);
    }
  }

  // 5. Rechercher les mises à jour par lot
  if (!successMatch) {
    const updateMatch = message.match(/Mise à jour par lot:\s*(\d+)\s+enregistrements?\s+mis à jour avec succès/i);
    if (updateMatch) {
      const updateSuccess = parseInt(updateMatch[1]);
      successCount += updateSuccess; // Additionner
      processedCountElement.textContent = successCount;
      console.log(`Mises à jour ajoutées: +${updateSuccess}, total: ${successCount}`);
    }
  }

  // 6. Traitement du message final de succès (écrase le compteur)
  if (successMatch) {
    const newSuccess = parseInt(successMatch[1]);
    successCount = newSuccess; // Utiliser la valeur finale
    processedCountElement.textContent = successCount;
    console.log(`Succès final: ${successCount}`);
  }

  // Extraire le nombre d'erreurs/échecs
  let errorMatch = message.match(/(\d+)\s+dossiers?\s+en\s+échec/i);
  if (!errorMatch)
    errorMatch = message.match(/Échecs?:\s*(\d+)/i);

  if (!errorMatch)
    errorMatch = message.match(/(\d+)\s+erreurs?\s+détectées?/i);

  if (!errorMatch)
    errorMatch = message.match(/(\d+)\s+dossiers?\s+n'ont\s+pas\s+pu\s+être\s+récupérés/i);

  if (errorMatch) {
    const newErrors = parseInt(errorMatch[1]);
    if (newErrors > errorCount) {
      errorCount = newErrors;
      console.log(`Erreurs mises à jour: ${errorCount}`);
    }
  }

  // Détecter les pourcentages de récupération faibles (signe d'erreurs)
  let recoveryMatch = message.match(/(\d+)\/(\d+)\s+dossiers?\s+récupérés?\s+\((\d+(?:\.\d+)?)%\)/i);

  if (recoveryMatch) {
    const recovered = parseInt(recoveryMatch[1]);
    const total = parseInt(recoveryMatch[2]);
    const percentage = parseFloat(recoveryMatch[3]);

    if (percentage < 80) { // Si moins de 80% récupérés, c'est problématique
      const failedCount = total - recovered;
      errorCount = Math.max(errorCount, failedCount);
      console.log(`Échecs détectés depuis taux de récupération: ${failedCount}`);
    }
  }

  // Détecter les messages d'erreur individuels pour incrémenter le compteur
  if (
    message.toLowerCase().includes('erreur lors de la récupération du dossier') ||
    message.toLowerCase().includes('max retries exceeded') ||
    message.toLowerCase().includes('sslerror') ||
    message.toLowerCase().includes('connection') && message.toLowerCase().includes('failed') ||
    message.toLowerCase().includes('timeout')
  ) {
    errorCount++;
    console.log(`Erreur individuelle détectée, total erreurs: ${errorCount}`);
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { toggleLogs, extractStatsFromLog }
}
