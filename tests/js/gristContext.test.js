const { getGristContext }  = require('../../static/gristContext.js')

beforeEach(() => {
  consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {}) // Supprime console.warn
})  

 afterEach(() => {
  consoleWarnSpy.mockRestore() // Restaure console.warn
})

it(
  'Should throw error if grist global is undefined',
  async () => {
    await expect(getGristContext()).rejects.toThrow('grist not available')
  }
)

it(
  'Should throw error if docId or userId is missing',
  async () => {
    global.grist = { ready: jest.fn(), docApi: { getAccessToken: jest.fn() } }
    grist.docApi.getAccessToken.mockResolvedValue({ token: 'header.eyJ1c2VySWQiOiIxMjMifQ.signature' })

    await expect(getGristContext()).rejects.toThrow('Veuillez donner au widget l’accès complet au document')
    expect(consoleWarnSpy).toHaveBeenCalledWith('Contexte Grist non disponible ou erreur :', expect.any(Error))
  }
)

const createMockToken = (userId, docId) => {
  const payload = { userId, docId }
  const encodedPayload = Buffer.from(JSON.stringify(payload)).toString('base64')
  return `header.${encodedPayload}.signature`
}

it(
  'Should return all needed data',
  async () => {
    const mockToken = createMockToken('123', '456')
    grist.docApi.getAccessToken.mockResolvedValue({ token: mockToken })

    const result = await getGristContext()

    expect(result).toEqual({
      params: '?grist_user_id=123&grist_doc_id=456',
      userId: '123',
      docId: '456'
    })
    expect(consoleWarnSpy).not.toHaveBeenCalled()
  }
)
