const checkConfiguration = async () => {
  const resultDiv = document.getElementById('config_check_result')
  const syncBtn   = document.getElementById('start_sync_btn')
  syncBtn.disabled = true

  try {
    // Récupérer le contexte Grist pour conditionner le chargement de la configuration
    const gristContext = await getGristContext()
    const response = await fetch(`/api/config${gristContext.params}`)
    const config = await response.json()

    // Vérifier que tous les champs requis sont présents
    const requiredFields = [
      'ds_api_token',
      'demarche_number', 
      'grist_base_url',
      'grist_api_key',
      'grist_doc_id'
    ]

    const missingFields = requiredFields.filter(field => !config[field] || config[field] === '***')

    if (missingFields.length !== 0)
      return resultDiv.innerHTML = `
        <div class="fr-alert fr-alert--error">
          <h3 class="fr-alert__title">Configuration incomplète</h3>
          <p>Champs manquants: ${missingFields.join(', ')}</p>
          <p><a href="/" class="fr-link">Aller à la configuration</a></p>
        </div>`

    resultDiv.innerHTML = `
      <div class="fr-alert fr-alert--success">
        <h3 class="fr-alert__title">Configuration complète</h3>
        <p>Démarche ${config.demarche_number} → Document Grist ${config.grist_doc_id}</p>
      </div>`
    syncBtn.disabled = false

    return config
  } catch (error) {
    console.error('Erreur lors de la vérification de la configuration:', error)
    syncBtn.disabled = true
    resultDiv.innerHTML = `
      <div class="fr-alert fr-alert--error">
        <h3 class="fr-alert__title">Erreur lors de la vérification</h3>
        <p>Impossible de charger la configuration</p>
      </div>`
  }
}

const loadConfiguration = async () => {
  try {
    // Récupérer d'abord le contexte Grist pour conditionner le chargement de la configuration
    const gristContext = await getGristContext()
    let gristParams = gristContext.params
    let gristUserId = gristContext.userId
    let gristDocId = gristContext.docId
    let gristBaseUrl = gristContext.baseUrl
    const response = await fetch(`/api/config${gristParams}`)
    const config = await response.json()

    if (!response.ok)
      throw new Error(config.message)

    // Déterminer si une configuration a été trouvée pour ce contexte Grist
    const hasConfig = gristUserId && gristDocId && config.ds_api_token

    // Pré-remplir TOUJOURS les IDs Grist depuis le contexte
    document.getElementById('grist_doc_id').value = gristDocId || ''
    document.getElementById('grist_user_id').value = gristUserId || ''
    const gristApiKeyElement = document.getElementById('grist_api_key')
    const gristKeyStatus = document.getElementById('grist_key_status')
    const gristBaseUrlElement = document.getElementById('grist_base_url')
    gristBaseUrlElement.value = gristBaseUrl || ''


    const dsApiTokenElement = document.getElementById('ds_api_token')
    const dsTokenStatus = document.getElementById('ds_token_status')
    const dsApiUrlElement = document.getElementById('ds_api_url')
    const dsNumberElement = document.getElementById('demarche_number')
    const batchSizeElement = document.getElementById('batch_size')
    const maxWorkersElement = document.getElementById('max_workers')
    const parallelElement = document.getElementById('parallel')

    // Remplir les autres champs seulement si une configuration a été trouvée
    if (hasConfig) {
      dsApiTokenElement.value = ''
      dsApiUrlElement.value = config.ds_api_url || 'https://www.demarches-simplifiees.fr/api/v2/graphql'
      dsNumberElement.value = config.demarche_number || ''
      gristBaseUrlElement.value = config.grist_base_url || 'https://grist.numerique.gouv.fr/api'
      gristApiKeyElement.value = ''
      batchSizeElement.value = config.batch_size || 25
      maxWorkersElement.value = config.max_workers || 2
      parallelElement.value = config.parallel ? 'true' : 'false'
    } else {
      // Aucune configuration trouvée, laisser tous les champs vides (sauf grist ids)
      dsApiTokenElement.value = ''
      dsApiUrlElement.value = 'https://www.demarches-simplifiees.fr/api/v2/graphql'
      dsNumberElement.value = ''
      gristApiKeyElement.value = ''
      batchSizeElement.value = '25'
      maxWorkersElement.value = '2'
      parallelElement.value = 'true'
    }

    // Mettre à jour les statuts initiaux
    updateDSTokenStatus()
    updateGristKeyStatus()

    // Ajouter les listeners pour mise à jour en temps réel
    dsApiTokenElement.addEventListener('input', updateDSTokenStatus)
    gristApiKeyElement.addEventListener('input', updateGristKeyStatus)

    // Afficher le statut des tokens
    if (config.ds_api_token) {
      dsTokenStatus.innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
          <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Token configuré
        </span>`
      dsApiTokenElement.placeholder = 'Token déjà configuré (laissez vide pour conserver)'
    } else {
      dsTokenStatus.innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm">
          <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Token requis
        </span>`
      dsApiTokenElement.placeholder = ''
    }

    if (config.grist_api_key) {
      gristKeyStatus.innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
          <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Clé API configurée
        </span>`
      gristApiKeyElement.placeholder = 'Clé API déjà configurée (laissez vide pour conserver)'
    } else {
      gristKeyStatus.innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm">
          <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Clé API requise
        </span>`
    }

    return config
  } catch (error) {
    console.error('Erreur lors du chargement de la configuration:', error)
    App.showNotification(`Erreur lors du chargement de la configuration : ${error.message}`, 'error')
  }
}


if (typeof module !== 'undefined' && module.exports) {
  module.exports = { checkConfiguration, loadConfiguration }
}
