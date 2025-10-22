const { getGristContext }  = require('../static/gristContext.js')

describe('getGristContext', () => {

  it(
    'Should throw error if grist global is undefined',
    async () => {
      await expect(getGristContext()).rejects.toThrow('grist not available');
    }
  )
})
