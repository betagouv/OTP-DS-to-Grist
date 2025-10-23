const escapeHtml = text => {
  const div = document.createElement('div')
  div.textContent = text

  return div.innerHTML
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { escapeHtml }
}
