// Seule méthode de chargement documentée par Grist : pas de paquet npm maintenu
const GRIST_PLUGIN_API_URL = 'https://docs.getgrist.com/grist-plugin-api.js'

let loading = null

// API des widgets Grist (global `grist`), chargée une seule fois au premier
// besoin ; `null` si le script ne se charge pas (réseau, blocage)
export const loadGristPluginApi = () => {
  if (loading) return loading

  loading = new Promise((resolve) => {
    const script = document.createElement('script')
    script.src = GRIST_PLUGIN_API_URL
    script.onload = () => resolve(window.grist ?? null)
    script.onerror = () => resolve(null)
    document.head.appendChild(script)
  })

  return loading
}
