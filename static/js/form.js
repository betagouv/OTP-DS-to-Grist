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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { updateDSTokenStatus }
}
