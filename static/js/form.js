const updateDSTokenStatus = (config) => {
  const dsTokenElement = document.getElementById('ds_api_token')
  const dsTokenElementvalue = dsTokenElement.value
  const dsTokenStatusElement = document.getElementById('ds_token_status')

  if (dsTokenElementvalue || config.ds_api_token) {
    dsTokenStatusElement.innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
        <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Token configuré
      </span>`
    dsTokenElement.placeholder = 'Token déjà configuré (laissez vide pour conserver)'
  } else {
    dsTokenStatusElement.innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm">
        <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Token requis
      </span>`
    dsTokenElement.placeholder = ''
  }
}

const updateGristKeyStatus = (config) => {
  const gristKeyElement = document.getElementById('grist_api_key');
  const gristKeyElementValue = gristKeyElement.value;

  if (gristKeyElementValue || config.grist_api_key) {
    document.getElementById('grist_key_status').innerHTML = `<span class="fr-badge fr-badge--success fr-badge--sm">
      <i class="fas fa-check-circle fr-mr-1v" aria-hidden="true"></i>Clé API configurée
    </span>`
    gristKeyElement.placeholder = 'Clé API déjà configurée (laissez vide pour conserver)'
  } else {
    document.getElementById('grist_key_status').innerHTML = `<span class="fr-badge fr-badge--error fr-badge--sm">
      <i class="fas fa-exclamation-circle fr-mr-1v" aria-hidden="true"></i>Clé API requise
    </span>`
    gristKeyElement.placeholder = ''
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { updateDSTokenStatus, updateGristKeyStatus }
}
