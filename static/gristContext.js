async function getGristContext() {
  let gristParams = '';
  let gristUserId = '';
  let gristDocId = '';

  if (typeof grist !== 'undefined') {
    try {
      grist.ready();
      const tokenInfo = await grist.docApi.getAccessToken({readOnly: false});
      const payload = JSON.parse(atob(tokenInfo.token.split('.')[1]));
      const {docId, userId} = payload;

      if (userId && docId) {
        gristParams = `?grist_user_id=${encodeURIComponent(userId)}&grist_doc_id=${encodeURIComponent(docId)}`;
        gristUserId = userId;
        gristDocId = docId;
      }
    } catch (error) {
      console.warn('Contexte Grist non disponible ou erreur:', error);
    }
  }

  return { params: gristParams, userId: gristUserId, docId: gristDocId };
}
