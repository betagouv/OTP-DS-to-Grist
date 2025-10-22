const { getGristContext }  = require('../static/gristContext.js')

it(
  'Should throw error if grist global is undefined',
  async () => {
    await expect(getGristContext()).rejects.toThrow('grist not available');
  }
)

it(
  'Should throw error if docId or userId is missing',
  async () => {
    global.grist = { ready: jest.fn(), docApi: { getAccessToken: jest.fn() } };
    grist.docApi.getAccessToken.mockResolvedValue({ token: 'header.eyJ1c2VySWQiOiIxMjMifQ.signature' });

    await expect(getGristContext()).rejects.toThrow('Veuillez donner au widget l’accès complet au document');
  }
)
