if (typeof showNotification === 'undefined')
  ({ showNotification } = require('./notifications.js'))

const testDemarchesConnection = async (silent = false) => {
  const resultDiv = document.getElementById('ds_test_result')

  try {
    const ds_token_input = document.getElementById('ds_api_token').value || ''
    const ds_api_url = document.getElementById('ds_api_url').value || ''
    const demarche_number = document.getElementById('demarche_number').value || ''

    // Utiliser le token saisi OU recharger la config si vide
    let ds_token = ds_token_input
    if (!ds_token) {
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

    if (!ds_token) {
      resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
        <p>Token API requis. Veuillez saisir votre token ou vérifier qu'il est sauvegardé.</p>
      </div>`
      showNotification('Token API démarches simplifiées requis. Veuillez saisir votre token ou vérifier qu’il est sauvegardé.', 'error')
      return false
    }

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
      if (!silent) showNotification(result.message, 'success')
      return true
    }

    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>${result.message}</p>
    </div>`
    showNotification(result.message, 'error')
    return false

  } catch (error) {
    console.error('Erreur lors du test DS:', error)
    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>Erreur de connexion: ${error.message}</p>
    </div>`
    showNotification('Erreur lors du test de connexion', 'error')
    return false
  }
}

const testGristConnection = async (silent = false) => {
  const resultDiv = document.getElementById('grist_test_result')

  try {
    const gristKeyInputValue = document.getElementById('grist_api_key').value
    const gristBaseUrlValue  = document.getElementById('grist_base_url').value
    const gristDocIdValue    = document.getElementById('grist_doc_id').value

    // Utiliser la clé saisie OU recharger la config si vide
    let grist_key = gristKeyInputValue

    if (!grist_key) {
      try {
        const gristContext   = await getGristContext()
        const configResponse = await fetch(`/api/config${gristContext.params}`)
        const latestConfig   = await configResponse.json()
        grist_key            = latestConfig.grist_api_key
      } catch (e) {
        console.error('Erreur rechargement config:', e)
      }
    }

    if (!grist_key) {
      showNotification('Token Grist requis. Veuillez saisir votre token ou vérifier qu’il est sauvegardé.', 'error')
      return resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
        <p>Clé API Grist requise. Veuillez saisir votre clé ou vérifier qu'elle est sauvegardée.</p>
      </div>`
    }

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
      if (!silent) showNotification(result.message, 'success')
      return true
    }

    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>${result.message}</p>
    </div>`

    showNotification(result.message, 'error')
    return false

  } catch (error) {
    console.error('Erreur lors du test Grist:', error)
    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <p>Erreur de connexion: ${error.message}</p>
    </div>`
    showNotification('Erreur lors du test de connexion', 'error')
    return false
  }
}

const testWebSocket = () => {
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

const testExternalConnections = async () => {
  const resultDiv = document.getElementById('external_tests_result')

  resultDiv.innerHTML = `<div class="fr-alert fr-alert--info">
    <p>Test des connexions externes en cours...</p>
  </div>`

  try {
    // Charger la configuration actuelle
    const gristContext   = await getGristContext()
    const configResponse = await fetch(`/api/config${gristContext.params}`)
    const config         = await configResponse.json()
    const tests          = []

    // Test Démarches Simplifiées si configuré
    if (config.ds_api_token && config.ds_api_token !== '***' && config.ds_api_url) {
      tests.push({
        name: 'Démarches Simplifiées',
        test: fetch('/api/test-connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'demarches',
            api_token: config.ds_api_token,
            api_url: config.ds_api_url,
            demarche_number: config.demarche_number
          })
        }).then(r => r.json())
      })
    }

    // Test Grist si configuré
    if (config.grist_api_key && config.grist_api_key !== '***' && config.grist_base_url && config.grist_doc_id) {
      tests.push({
        name: 'Grist',
        test: fetch('/api/test-connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'grist',
            base_url: config.grist_base_url,
            api_key: config.grist_api_key,
            doc_id: config.grist_doc_id
          })
        }).then(r => r.json())
      })
    }

    if (tests.length === 0)
      return resultDiv.innerHTML = `<div class="fr-alert fr-alert--warning">
        <h3 class="fr-alert__title">Aucune API configurée pour le test</h3>
        <p>Configurez d'abord vos connexions dans l'onglet Configuration</p>
      </div>`

    // Exécuter tous les tests en parallèle
    const results = await Promise.allSettled(tests.map(t => t.test))

    let html = '<div class="fr-grid-row fr-grid-row--gutters">'

    results.forEach((result, index) => {
      const testName = tests[index].name

      if (result.status === 'fulfilled' && result.value) {
        const success = result.value.success
        const message = result.value.message

        html += `<div class="fr-col-12">
          <div class="fr-alert ${success ? 'fr-alert--success' : 'fr-alert--error'}">
            <h4 class="fr-alert__title">${testName}</h4>
            <p>${message}</p>
          </div>
        </div>`
      } else {
        html += `<div class="fr-col-12">
          <div class="fr-alert fr-alert--error">
            <h4 class="fr-alert__title">${testName}</h4>
            <p>Erreur de test de connexion</p>
          </div>
        </div>`
      }
    })

    html += '</div>'
    resultDiv.innerHTML = html

    // Notification globale
    const successCount = results.filter(r => r.status === 'fulfilled' && r.value && r.value.success).length
    const totalCount = results.length

    if (successCount === totalCount) 
      return showNotification(`Tous les tests de connexion réussis (${successCount}/${totalCount})`, 'success')

    showNotification(`${successCount}/${totalCount} connexions réussies`, 'warning')

  } catch (error) {
    console.error('Erreur lors des tests de connexion:', error)
    resultDiv.innerHTML = `<div class="fr-alert fr-alert--error">
      <h3 class="fr-alert__title">Erreur lors des tests</h3>
      <p>${error.message}</p>
    </div>`

    showNotification('Erreur lors des tests de connexion', 'error')
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    testDemarchesConnection,
    testGristConnection,
    testWebSocket,
    testExternalConnections
  }
}
