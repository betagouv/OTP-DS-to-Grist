const { getGristContext, getApiBaseUrlFromDocBaseUrl }  = require('../../static/js/gristContext.js')

beforeEach(() => {
  consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {}) // Supprime console.warn
})

 afterEach(() => {
  consoleWarnSpy.mockRestore() // Restaure console.warn
})

it(
  'should throw error if grist global is undefined',
  async () => {
    await expect(getGristContext()).rejects.toThrow('grist not available')
  }
)

it(
  'should throw error if docId or userId is missing',
  async () => {
    global.grist = { ready: jest.fn(), docApi: { getAccessToken: jest.fn() } }
    grist.docApi.getAccessToken.mockResolvedValue({
      token: 'header.eyJ1c2VySWQiOiIxMjMifQ.signature',
      baseUrl: '/'
    })

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
  'should return all needed data',
  async () => {
    const mockToken = createMockToken('123', '456')
    grist.docApi.getAccessToken.mockResolvedValue({
      token: mockToken,
      baseUrl: 'http://0.0.0.0:8484/o/docs/api/docs/aD23FiUYPFeo'
    })

    const result = await getGristContext()

    expect(result).toEqual({
      params: '?grist_user_id=123&grist_doc_id=456',
      userId: '123',
      docId: '456',
      baseUrl: 'http://0.0.0.0:8484/o/docs/api'
    })
    expect(consoleWarnSpy).not.toHaveBeenCalled()
  }
)

it(
  'should return a correct baseUrl',
  () => {
    expect(
      getApiBaseUrlFromDocBaseUrl(
        'https://grist.numerique.gouv.fr/o/docs/api/docs/95tJUFWsbqhDHvB1t86RWF'
      )
    ).toBe('https://grist.numerique.gouv.fr/o/docs/api')
  }
)
