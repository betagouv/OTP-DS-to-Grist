const checkConfiguration = async () => {
  const resultDiv = document.getElementById('config_check_result')
  const syncBtn   = document.getElementById('start_sync_btn')
  syncBtn.disabled = true

  try {
    // Récupérer le contexte Grist pour conditionner le chargement de la configuration
    const gristContext = await getGristContext()
    const response = await fetch(`/api/config${gristContext.params}`)
    const config = await response.json()
    currentConfig = config

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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { checkConfiguration }
}
