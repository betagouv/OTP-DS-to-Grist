if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

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

    const gristApiKeyElement  = document.getElementById('grist_api_key')
    const gristKeyStatus      = document.getElementById('grist_key_status')
    const gristBaseUrlElement = document.getElementById('grist_base_url')
    const dsApiTokenElement   = document.getElementById('ds_api_token')
    const dsTokenStatus       = document.getElementById('ds_token_status')
    const dsApiUrlElement     = document.getElementById('ds_api_url')
    const dsNumberElement     = document.getElementById('demarche_number')

    // Remplir les autres champs seulement si une configuration a été trouvée
    dsApiTokenElement.value   = ''
    dsApiUrlElement.value     = hasConfig && config.ds_api_url || 'https://www.demarches-simplifiees.fr/api/v2/graphql' 
    dsNumberElement.value     = hasConfig && config.demarche_number || ''
    gristBaseUrlElement.value = hasConfig && config.grist_base_url || (gristBaseUrl || 'https://grist.numerique.gouv.fr/api')
    gristApiKeyElement.value  = ''

    // Mettre à jour les statuts initiaux
    updateDSTokenStatus(config)
    updateGristKeyStatus(config)

    // Ajouter les listeners pour mise à jour en temps réel
    dsApiTokenElement.addEventListener('input', updateDSTokenStatus)
    gristApiKeyElement.addEventListener('input', updateGristKeyStatus)

    // Afficher le statut des tokens
    if (config.ds_api_token) {
      dsTokenStatus.innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
          <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Token configuré
        </span>`
      dsApiTokenElement.placeholder = 'Token déjà configuré (laissez vide pour conserver)'
      document.querySelector('#accordion-ds').setAttribute('aria-expanded', false)
    } else {
      dsTokenStatus.innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm">
          <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Token requis
        </span>`
      dsApiTokenElement.placeholder = ''
      document.querySelector('#accordion-ds').setAttribute('aria-expanded', true)
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
    showNotification(`Erreur lors du chargement de la configuration : ${error.message}`, 'error')
  }
}

const saveConfiguration = async () => {
  checkConfiguration()
  const dsApiTokenElement = document.getElementById('ds_api_token')
  const dsToken = dsApiTokenElement.value
  const gristKeyElement = document.getElementById('grist_api_key')
  const grist_key = gristKeyElement.value

  const config = {
    ds_api_token: dsToken || currentConfig.ds_api_token || '',
    ds_api_url: document.getElementById('ds_api_url').value,
    demarche_number: document.getElementById('demarche_number').value,
    grist_base_url: document.getElementById('grist_base_url').value,
    grist_api_key: grist_key || currentConfig.grist_api_key || '',
    grist_doc_id: document.getElementById('grist_doc_id').value,
    grist_user_id: document.getElementById('grist_user_id').value,
  }

  // Validation basique
  const requiredFields = [
    {key: 'ds_api_token', name: 'Token API Démarches Simplifiées'},
    {key: 'ds_api_url', name: 'URL API Démarches Simplifiées'},
    {key: 'demarche_number', name: 'Numéro de démarche'},
    {key: 'grist_base_url', name: 'URL de base Grist'},
    {key: 'grist_api_key', name: 'Clé API Grist'},
    {key: 'grist_doc_id', name: 'ID du document Grist'},
    {key: 'grist_user_id', name: 'ID utilisateur Grist'}
  ]

  for (const field of requiredFields) {
    if (!config[field.key]) {
      showNotification(`Le champ "${field.name}" est requis`, 'error')
      return
    }
  }

  try {
    // Afficher un indicateur de chargement
    const saveButton = document.querySelector('button[onclick="saveConfiguration()"]')
    const originalText = saveButton.innerHTML
    saveButton.disabled = true
    saveButton.innerHTML = '<i class="fas fa-spinner fa-spin fr-mr-1w" aria-hidden="true"></i>Sauvegarde...'

    const response = await fetch('/api/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config)
    })

    const result = await response.json()

    if (result.success) {
      showNotification('Configuration sauvegardée avec succès', 'success')

      // Mettre à jour immédiatement le statut des tokens si saisis
      if (dsToken) {
        document.getElementById('ds_token_status').innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
            <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Token configuré
          </span>`
        dsApiTokenElement.placeholder = 'Token déjà configuré (laissez vide pour conserver)'
      }

      if (grist_key) {
        document.getElementById('grist_key_status').innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
            <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Clé API configurée
          </span>`
        gristKeyElement.placeholder = 'Clé API déjà configurée (laissez vide pour conserver)'
      }
      // Recharger la configuration pour mettre à jour les statuts
      setTimeout(async () => {
        currentConfig = await loadConfiguration()
        await loadAutoSyncState()
      }, 500)
    } else {
      showNotification(result.message || 'Erreur lors de la sauvegarde', 'error')
    }

    // Restaurer le bouton
    saveButton.disabled = false
    saveButton.innerHTML = originalText

  } catch (error) {
    console.error('Erreur:', error)
    showNotification('Erreur lors de la sauvegarde', 'error')

    // Restaurer le bouton en cas d'erreur
    const saveButton = document.querySelector('button[onclick="saveConfiguration()"]')
    saveButton.disabled = false
    saveButton.innerHTML = '<i class="fas fa-save fr-mr-1w" aria-hidden="true"></i>Sauvegarder la configuration'
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    checkConfiguration,
    loadConfiguration,
    saveConfiguration
  }
}
