const showNotification = (message, type = 'info') => {
  const typeMap = {
    success: 'fr-notice--success',
    error: 'fr-notice--error',
    warning: 'fr-notice--warning',
    info: 'fr-notice--info'
  }

  const notification = document.createElement('div')
  notification.className = `fr-notice ${typeMap[type]} notification fade-in`
  notification.innerHTML = `<div class="fr-container">
    <div class="fr-notice__body">
      <p class="fr-notice__title">
        ${message}
      </p>
      <button class="fr-btn--close fr-btn" title="Masquer le message" onclick="this.closest('.fr-notice').remove()">
        Masquer le message
      </button>
    </div>
  </div>`

  document.body.appendChild(notification)

  // Auto-remove après X secondes
  setTimeout(
    () => {
      if (notification.parentNode)
        notification.remove()
    }, type === 'error' ? 10000 : 5000
  )
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { showNotification }
}
