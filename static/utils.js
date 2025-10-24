const escapeHtml = text => {
  const div = document.createElement('div')
  div.textContent = text

  return div.innerHTML
}

const formatDate = dateString => (new Date(dateString)).toLocaleDateString('fr-FR')

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { 
    escapeHtml,
    formatDate
  }
}
