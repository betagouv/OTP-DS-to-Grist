if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

if (typeof loadGroupes === 'undefined')
  ({ showNotification } = require('./filters.js'))

const checkConfiguration = async (silent = false) => {
  const resultDiv = document.getElementById('config_check_result')
  if (!silent) resultDiv.style.display = 'block'
  const syncBtn   = document.getElementById('start_sync_btn')
  syncBtn.disabled = true

  try {
    // Récupérer le contexte Grist pour conditionner le chargement de la configuration
    const gristContext = await getGristContext()
    const response = await fetch(`/api/config${gristContext.params}`)
    const config = await response.json()

    // Vérifier que tous les champs requis sont présents
    const requiredFields = [
      'has_ds_token',
      'demarche_number',
      'grist_base_url',
      'has_grist_key',
    ]

    const missingFields = requiredFields.filter(field => !config[field])

    if (missingFields.length !== 0) {
      if (silent)
        return

      return resultDiv.innerHTML = `
        <div class="fr-alert fr-alert--error">
          <h3 class="fr-alert__title">Configuration incomplète</h3>
          <p>Champs manquants: ${missingFields.join(', ')}</p>
        </div>`
    }

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

    // Pré-remplir TOUJOURS les IDs Grist depuis le contexte
    document.getElementById('grist_doc_id').value = gristDocId || ''
    document.getElementById('grist_user_id').value = gristUserId || ''

    // Set default base url
    document.getElementById('grist_base_url').value = gristBaseUrl || 'https://grist.numerique.gouv.fr/api'

    const response = await fetch(`/api/config${gristParams}`)
    const config = await response.json()

    if (!response.ok)
      throw new Error(config.message)

    // Déterminer si une configuration a été trouvée
    const hasConfig = !!config.otp_config_id

    const gristApiKeyElement  = document.getElementById('grist_api_key')
    const gristKeyStatus      = document.getElementById('grist_key_status')
    const gristBaseUrlElement = document.getElementById('grist_base_url')
    const dsApiTokenElement   = document.getElementById('ds_api_token')
    const dsTokenStatus       = document.getElementById('ds_token_status')
    const dsNumberElement     = document.getElementById('demarche_number')

    // Remplir les autres champs seulement si une configuration a été trouvée
    dsApiTokenElement.value   = ''
    dsNumberElement.value     = hasConfig && config.demarche_number || ''
    gristBaseUrlElement.value = hasConfig && config.grist_base_url || gristBaseUrlElement.value
    gristApiKeyElement.value  = ''

    // Peupler les filtres
    document.getElementById('date_debut').value = hasConfig && config.filter_date_start || ''
    document.getElementById('date_fin').value = hasConfig && config.filter_date_end || ''

    if (hasConfig) {
      // Statuts
      const filterStatuses = config.filter_statuses ? config.filter_statuses.split(',') : []
      document.querySelectorAll('input[name="statuts"]').forEach(el => {
        el.checked = filterStatuses.includes(el.value)
      })

      // Groupes
      const filterGroups = config.filter_groups ? config.filter_groups.split(',') : []
      document.querySelectorAll('input[name="groupes"]').forEach(el => {
        el.checked = filterGroups.includes(el.value)
      })
    } else {
      // Aucun config : décocher tous les filtres
      document.querySelectorAll('input[name="statuts"]').forEach(el => el.checked = false)
      document.querySelectorAll('input[name="groupes"]').forEach(el => el.checked = false)
    }

    // Mettre à jour les statuts initiaux
    updateDSTokenStatus(config)
    updateGristKeyStatus(config)

    // Ajouter les listeners pour mise à jour en temps réel
    dsApiTokenElement.addEventListener('input', updateDSTokenStatus)
    gristApiKeyElement.addEventListener('input', updateGristKeyStatus)

    // Afficher le statut des tokens
    if (config.has_ds_token) {
      dsTokenStatus.innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm fr-badge--no-icon">
          <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Token configuré
        </span>`
      dsApiTokenElement.placeholder = 'Token déjà configuré (laissez vide pour conserver)'
      document.querySelector('#accordion-ds').setAttribute('aria-expanded', false)
    } else {
      dsTokenStatus.innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm fr-badge--no-icon">
          <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Token requis
        </span>`
      dsApiTokenElement.placeholder = ''
      document.querySelector('#accordion-ds').setAttribute('aria-expanded', true)
    }

    if (config.has_grist_key) {
      gristKeyStatus.innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm fr-badge--no-icon">
          <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Clé API configurée
        </span>`
      gristApiKeyElement.placeholder = 'Clé API déjà configurée (laissez vide pour conserver)'
      document.querySelector('#accordion-grist').setAttribute('aria-expanded', false)
    } else {
      gristKeyStatus.innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm fr-badge--no-icon">
          <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Clé API requise
        </span>`
      gristApiKeyElement.placeholder = ''
      document.querySelector('#accordion-grist').setAttribute('aria-expanded', true)
    }

    // Afficher le résumé des filtres actifs si présents
    const hasActiveFilters = document.getElementById('date_debut').value ||
                             document.getElementById('date_fin').value ||
                             document.querySelectorAll('input[name="statuts"]:checked').length > 0 ||
                             document.querySelectorAll('input[name="groupes"]:checked').length > 0
    if (hasActiveFilters) {
      applyFilters()
    }

    return config
  } catch (error) {
    console.error('Erreur lors du chargement de la configuration:', error)
    showNotification(`Erreur lors du chargement de la configuration : ${error.message}`, 'error')
  }
}

const saveConfiguration = async () => {
  const dsApiTokenElement = document.getElementById('ds_api_token')
  const dsToken = dsApiTokenElement.value
  const gristKeyElement = document.getElementById('grist_api_key')
  const grist_key = gristKeyElement.value

  const isUpdate = !!window.otp_config_id

  const config = {
    otp_config_id: window.otp_config_id || undefined,
    demarche_number: document.getElementById('demarche_number').value,
    grist_base_url: document.getElementById('grist_base_url').value,
    grist_doc_id: document.getElementById('grist_doc_id').value,
    grist_user_id: document.getElementById('grist_user_id').value,
    filter_date_start: document.getElementById('date_debut').value,
    filter_date_end: document.getElementById('date_fin').value,
    filter_statuses: Array.from(document.querySelectorAll('input[name="statuts"]:checked')).map(el => el.value).join(','),
    filter_groups: Array.from(document.querySelectorAll('input[name="groupes"]:checked')).map(el => el.value).join(','),
  }

  // Inclure tokens seulement si saisis
  if (dsToken) config.ds_api_token = dsToken
  if (grist_key) config.grist_api_key = grist_key

  // Validation basique
  const requiredFields = [
    {key: 'demarche_number', name: 'Numéro de démarche'},
    {key: 'grist_base_url', name: 'URL de base Grist'},
    {key: 'grist_doc_id', name: 'ID du document Grist'},
    {key: 'grist_user_id', name: 'ID utilisateur Grist'}
  ]

  if (!isUpdate) {
    // Pour création, requérir tokens
    requiredFields.push(
      {key: 'ds_api_token', name: 'Token API Démarches Simplifiées'},
      {key: 'grist_api_key', name: 'Clé API Grist'}
    )
  }

  for (const field of requiredFields) {
    if (!config[field.key]) {
      showNotification(`Le champ "${field.name}" est requis`, 'error')
      return
    }
  }

  try {
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
        document.getElementById('ds_token_status').innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm fr-badge--no-icon">
            <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Token configuré
          </span>`
        dsApiTokenElement.placeholder = 'Token déjà configuré (laissez vide pour conserver)'
      }

      if (grist_key) {
        document.getElementById('grist_key_status').innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm fr-badge--no-icon">
            <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Clé API configurée
          </span>`
        gristKeyElement.placeholder = 'Clé API déjà configurée (laissez vide pour conserver)'
      }
       // Recharger la configuration pour mettre à jour les statuts
       setTimeout(async () => {
         const reloadedConfig = await loadConfiguration()
         window.otp_config_id = reloadedConfig.otp_config_id
         await loadAutoSyncState()
         updateDeleteButton()
       }, 500)
    } else {
      showNotification(result.message || 'Erreur lors de la sauvegarde', 'error')
    }
  } catch (error) {
    console.error('Erreur:', error)
    showNotification('Erreur lors de la sauvegarde', 'error')
  }
}

const deleteConfig = async (configId = null) => {
  if (!configId)
    throw new Error('ID de configuration requis pour la suppression')

  const confirmed = confirm('Êtes-vous sûr de vouloir supprimer cette configuration ? Cette action est irréversible.')
  if (!confirmed) return

  try {
    const response = await fetch(`/api/config/${configId}`, {
      method: 'DELETE'
    })

    const result = await response.json()

    if (result.success) {
      showNotification('Configuration supprimée avec succès', 'success')
      // Redirect to configuration page or reload
      window.location.href = '/'
    } else {
      showNotification(result.message || 'Erreur lors de la suppression', 'error')
    }
  } catch (error) {
    console.error('Erreur lors de la suppression:', error)
    showNotification('Erreur lors de la suppression', 'error')
  }
}

// Fonctions utilitaires pour l'UI de configuration
const updateDeleteButton = () => {
  const deleteBtn = document.getElementById('delete_config_btn')
  if (!window.otp_config_id) {
    deleteBtn.disabled = true
    deleteBtn.title = 'Aucune configuration à supprimer'
  } else {
    deleteBtn.disabled = false
    deleteBtn.title = ''
  }
}

const saveConfigAction = async () => {
  if (!await testGristConnection(true))
    return false

  if (!await testDemarchesConnection(true))
    return false

  await saveConfiguration()
  await checkConfiguration()
  await loadGroupes()
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    checkConfiguration,
    loadConfiguration,
    saveConfiguration,
    deleteConfig,
    updateDeleteButton,
    saveConfigAction
  }
}
