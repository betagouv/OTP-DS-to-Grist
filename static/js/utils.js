const escapeHtml = text => {
  const div = document.createElement('div')
  div.textContent = text

  return div.innerHTML
}

const formatDate = dateString => (new Date(dateString)).toLocaleDateString('fr-FR')

const formatDuration = (seconds) => {
  const hours   = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs    = Math.floor(seconds % 60)

  if (hours > 0)
    return `${hours}h ${minutes}m ${secs}s`

  if (minutes > 0)
    return `${minutes}m ${secs}s`

  return `${secs}s`
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { 
    escapeHtml,
    formatDate,
    formatDuration
  }
}
