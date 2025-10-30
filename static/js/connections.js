const testDemarchesConnection = async () => {
  const button = document.getElementById('test_ds_btn')
  const resultDiv = document.getElementById('ds_test_result')

  button.disabled = true
  button.innerHTML = '<i class="fas fa-spinner fa-spin fr-mr-1w" aria-hidden="true"></i>Test en cours...'

  try {
    const ds_token_input = document.getElementById('ds_api_token').value || ''
    const ds_api_url = document.getElementById('ds_api_url').value || ''
    const demarche_number = document.getElementById('demarche_number').value || ''

    // Utiliser le token saisi OU recharger la config si vide
    let ds_token = ds_token_input
    if (!ds_token && currentConfig && currentConfig.ds_api_token_exists) {
      try {
        const gristContext = await getGristContext()
        const configResponse = await fetch(`/api/config${gristContext.params}`)

        if (configResponse.ok) {
          const latestConfig = await configResponse.json()
          ds_token = latestConfig.ds_api_token || ''
        }
      } catch (e) {
        console.error('Erreur rechargement config:', e)
      }
    }

    if (!ds_token)
      return resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
        <p>Token API requis. Veuillez saisir votre token ou vérifier qu'il est sauvegardé.</p>
      </div>`

    const response = await fetch('/api/test-connection', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: 'demarches',
        api_token: ds_token,
        api_url: ds_api_url,
        demarche_number: demarche_number
      })
    })

    const result = await response.json()

    if (result.success) {
      resultDiv.innerHTML = `<div class="fr-alert fr-alert--success">
        <p>${result.message}</p>
      </div>`
      return App.showNotification(result.message, 'success')
    }

    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>${result.message}</p>
    </div>`
    App.showNotification(result.message, 'error')

  } catch (error) {
    console.error('Erreur lors du test DS:', error)
    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>Erreur de connexion: ${error.message}</p>
    </div>`
    App.showNotification('Erreur lors du test de connexion', 'error')
  } finally {
    button.disabled = false
    button.innerHTML = '<i class="fas fa-plug fr-mr-1w" aria-hidden="true"></i>Tester la connexion'
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { testDemarchesConnection }
}
