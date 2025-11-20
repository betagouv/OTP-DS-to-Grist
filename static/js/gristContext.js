const getGristContext = async () => {
  if (typeof grist === 'undefined')
    throw new Error('grist not available')

  try {
    grist.ready({requiredAccess: 'full'})

    const tokenInfo = await grist.docApi.getAccessToken({readOnly: false})
    const {token} = tokenInfo
    const docBaseUrl = tokenInfo.baseUrl
    const payload = JSON.parse(atob(tokenInfo.token.split('.')[1]))
    const {docId, userId} = payload
    const baseUrl = getApiBaseUrlFromDocBaseUrl(docBaseUrl)

    if (!userId || !docId)
      throw new Error('Impossible de récupérer le user id ou le doc id')

    const params = `?grist_user_id=${
                      encodeURIComponent(userId)
                    }&grist_doc_id=${
                      encodeURIComponent(docId)
                    }`

    return { params, userId, docId, baseUrl }
  } catch (error) {
    console.warn('Contexte Grist non disponible ou erreur :', error)
    throw new Error('Veuillez donner au widget l’accès complet au document')
  }
}

const getApiBaseUrlFromDocBaseUrl = (docBaseUrl) => docBaseUrl.match(/^(.+?\/api)/)?.[1]

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { getGristContext, getApiBaseUrlFromDocBaseUrl }
}
