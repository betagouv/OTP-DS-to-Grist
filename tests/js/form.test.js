/** @jest-environment jsdom */

const { updateDSTokenStatus, updateGristKeyStatus } = require('../../static/js/form.js')

describe('updateDSTokenStatus', () => {

  beforeEach(() => {
    // Context DOM elements
    document.body.innerHTML = `
      <input id="ds_api_token">
    `
  })

  it(
    'should set success badge and placeholder when token is present in input',
    () => {
      const input = document.getElementById('ds_api_token')
      input.value = 'some-token'
      const config = {}

      updateDSTokenStatus(config)

      expect(input.placeholder).toBe('************************************************************************************')
    }
  )

  it(
    'should set success badge and placeholder when token is present in config',
    () => {
      const input = document.getElementById('ds_api_token')
      input.value = ''
      const config = { ds_api_token: 'config-token' }

      updateDSTokenStatus(config)

      expect(input.placeholder).toBe('************************************************************************************')
    }
  )

  it(
    'should set error badge and empty placeholder when no token is present',
    () => {
      const input = document.getElementById('ds_api_token')
      input.value = ''
      const config = {}

      updateDSTokenStatus(config)

      expect(input.placeholder).toBe('')
    }
  )
})

describe('updateGristKeyStatus', () => {
  beforeEach(() => {
    // Context DOM elements
    document.body.innerHTML = `
      <input id="grist_api_key">
    `
  })

  it(
    'should set success badge and placeholder when key is present in input',
    () => {
      const input = document.getElementById('grist_api_key')
      input.value = 'some-key'
      const config = {}

      updateGristKeyStatus(config)

      expect(input.placeholder).toBe('****************************************')
    }
  )

  it(
    'should set success badge and placeholder when key is present in config',
    () => {
      const input = document.getElementById('grist_api_key')
      input.value = ''
      const config = { grist_api_key: 'config-key' }

      updateGristKeyStatus(config)

      expect(input.placeholder).toBe('****************************************')
    }
  )

  it(
    'should set error badge and empty placeholder when no key is present',
    () => {
      const input = document.getElementById('grist_api_key')
      input.value = ''
      const config = {}

      updateGristKeyStatus(config)

      expect(input.placeholder).toBe('')
    }
  )
})
