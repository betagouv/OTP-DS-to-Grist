if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

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
      return showNotification(result.message, 'success')
    }

    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>${result.message}</p>
    </div>`
    showNotification(result.message, 'error')

  } catch (error) {
    console.error('Erreur lors du test DS:', error)
    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>Erreur de connexion: ${error.message}</p>
    </div>`
    showNotification('Erreur lors du test de connexion', 'error')
  } finally {
    button.disabled = false
    button.innerHTML = '<i class="fas fa-plug fr-mr-1w" aria-hidden="true"></i>Tester la connexion'
  }
}

const testGristConnection = async () => {
  const button = document.getElementById('test_grist_btn')
  const resultDiv = document.getElementById('grist_test_result')

  button.disabled = true
  button.innerHTML = '<i class="fas fa-spinner fa-spin fr-mr-1w" aria-hidden="true"></i>Test en cours...'

  try {
    const gristKeyInputValue = document.getElementById('grist_api_key').value
    const gristBaseUrlValue  = document.getElementById('grist_base_url').value
    const gristDocIdValue    = document.getElementById('grist_doc_id').value

    // Utiliser la clé saisie OU recharger la config si vide
    let grist_key = gristKeyInputValue

    if (!grist_key && currentConfig.grist_api_key_exists) {
      try {
        const gristContext   = await getGristContext()
        const configResponse = await fetch(`/api/config${gristContext.params}`)
        const latestConfig   = await configResponse.json()
        grist_key            = latestConfig.grist_api_key
      } catch (e) {
        console.error('Erreur rechargement config:', e)
      }
    }

    if (!grist_key)
      return resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
        <p>Clé API Grist requise. Veuillez saisir votre clé ou vérifier qu'elle est sauvegardée.</p>
      </div>`

    if (!gristBaseUrlValue)
      return resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
        <p>URL de base Grist requise</p>
      </div>`

    if (!gristDocIdValue)
      return resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
        <p>ID du document Grist requis</p>
      </div>`

    const response = await fetch('/api/test-connection', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: 'grist',
        base_url: gristBaseUrlValue,
        api_key: grist_key,
        doc_id: gristDocIdValue
      })
    })

    const result = await response.json()

    if (result.success) {
      resultDiv.innerHTML = `<div class="fr-alert fr-alert--success">
        <p>${result.message}</p>
      </div>`
      return showNotification(result.message, 'success')
    }

    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>${result.message}</p>
    </div>`

    showNotification(result.message, 'error')

  } catch (error) {
    console.error('Erreur lors du test Grist:', error)
    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>Erreur de connexion: ${error.message}</p>
    </div>`
    showNotification('Erreur lors du test de connexion', 'error')
  } finally {
    button.disabled = false
    button.innerHTML = '<i class="fas fa-plug fr-mr-1w" aria-hidden="true"></i>Tester la connexion'
  }
}

function testWebSocket() {
  const statusDiv = document.getElementById('websocket_status')

  // Réinitialiser l'état
  statusDiv.innerHTML = `<div class="fr-alert fr-alert--info">
    <p>Test de connexion WebSocket en cours...</p>
  </div>`

  // Tester la connexion WebSocket
  let wsConnected = false

  const testSocket = io()

  testSocket.on('connect', () => {
    wsConnected = true
    clearTimeout(wsTestTimeout)

    statusDiv.innerHTML = `<div class="fr-alert fr-alert--success">
      <h3 class="fr-alert__title">WebSocket connecté avec succès</h3>
      <p>ID de connexion: ${testSocket.id}</p>
    </div>`

    showNotification('WebSocket connecté', 'success')
    testSocket.disconnect()
  })

  testSocket.on('connect_error', (error) => {
    clearTimeout(wsTestTimeout)

    statusDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <h3 class="fr-alert__title">Erreur de connexion WebSocket</h3>
      <p>Erreur: ${error.message || 'Connexion impossible'}</p>
    </div>`

    showNotification('Erreur WebSocket', 'error')
  })

  // Timeout après 5 secondes
  wsTestTimeout = setTimeout(
    () => {
      if (!wsConnected) {
        statusDiv.innerHTML = `<div class="fr-alert fr-alert--warning">
          <h3 class="fr-alert__title">Timeout de connexion WebSocket</h3>
          <p>La connexion a pris trop de temps</p>
        </div>`

        showNotification('Timeout WebSocket', 'warning')
        testSocket.disconnect()
      }
    },
    5000
  )
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    testDemarchesConnection,
    testGristConnection,
    testWebSocket
  }
}
