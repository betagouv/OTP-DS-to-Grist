const toggleLogs = (logsVisible) => {
  const container = document.getElementById('logs_container')
  const icon = document.getElementById('logs_toggle_icon')
  const text = document.getElementById('logs_toggle_text')

  logsVisible = !logsVisible

  if (logsVisible) {
    container.style.display = 'block'
    icon.className = 'fas fa-chevron-up fr-mr-1w'
    text.textContent = 'Masquer les logs'

    // Auto-scroll vers le bas
    setTimeout(
      () => container.scrollTop = container.scrollHeight
      , 100
    )
  } else {
    container.style.display = 'none'
    icon.className = 'fas fa-chevron-down fr-mr-1w'
    text.textContent = 'Afficher les logs'
  }

  return logsVisible
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { toggleLogs }
}
