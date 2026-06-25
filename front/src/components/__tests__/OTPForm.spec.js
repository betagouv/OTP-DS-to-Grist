import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import OTPForm from '../OTPForm.vue'
import GristFormSection from '../GristFormSection.vue'
import DNFormSection from '../DNFormSection.vue'

describe('Save button state', () => {
  let wrapper
  let saveButton

  beforeEach(() => {
    // Pour rendre silencieux `console.error`
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
    saveButton = wrapper.find('[data-test-id="submit-form-button"]')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('disabled on load', () => {
    expect(saveButton.element.hasAttribute('disabled')).toBe(true)
  })

  it('disabled when Grist has error', async () => {
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', 'Erreur de connexion')
    await wrapper.vm.$nextTick()

    expect(saveButton.element.hasAttribute('disabled')).toBe(true)
  })

  it('disabled when DN has error', async () => {
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', 'Erreur de connexion')
    await wrapper.vm.$nextTick()

    expect(saveButton.element.hasAttribute('disabled')).toBe(true)
  })

  it('enabled when both verifications succeed', async () => {
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    await wrapper.vm.$nextTick()

    expect(saveButton.element.hasAttribute('disabled')).toBe(false)
  })
})

describe('Save button action', () => {
  let wrapper
  let saveButton

  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
    saveButton = wrapper.find('[data-test-id="submit-form-button"]')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sends correct config to API on save', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })

    globalThis.fetch = mockFetch
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5',
      docId: 'doc-123',
      baseUrl: 'https://grist.example.com',
      token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token',
      demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    await saveButton.trigger('click')

    expect(mockFetch).toHaveBeenCalledWith('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ds_api_token: 'dn-token',
        demarche_number: '12345',
        grist_base_url: 'https://grist.example.com',
        grist_doc_id: 'doc-123',
        grist_user_id: '5',
        grist_api_key: 'grist-token'
      })
    })
  })

  it('does not call API when button is disabled', async () => {
    const mockFetch = vi.fn()
    globalThis.fetch = mockFetch
    await saveButton.trigger('click')

    expect(mockFetch).not.toHaveBeenCalled()
  })
})

describe('Config loading on mount', () => {
  const mockContext = { params: '?grist_user_id=5&grist_doc_id=doc-123' }
  let consoleSpy = null

  beforeEach(() => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn()
    globalThis.fetch = vi.fn()
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    delete globalThis.getGristContext
    consoleSpy.mockRestore()
  })

  it('loads existing config via GET /api/config with Grist context params', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1, grist_base_url: 'https://example.com' }] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.getGristContext).toHaveBeenCalled()
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/config?grist_user_id=5&grist_doc_id=doc-123'
    )
    expect(wrapper.getComponent(GristFormSection).props('existingConfig'))
      .toEqual({ otp_config_id: 1, grist_base_url: 'https://example.com' })
    expect(wrapper.getComponent(DNFormSection).props('existingConfig'))
      .toEqual({ otp_config_id: 1, grist_base_url: 'https://example.com' })
  })

  it('sets existingConfig to null when API returns no configs', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ configs: [] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
    expect(wrapper.getComponent(DNFormSection).props('existingConfig')).toBeNull()
  })

  it('handles getGristContext error gracefully', async () => {
    globalThis.getGristContext.mockRejectedValue(new Error('context error'))

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(consoleSpy).toHaveBeenCalled()
    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
  })

  it('handles fetch error gracefully', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch.mockRejectedValue(new Error('network error'))

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(consoleSpy).toHaveBeenCalled()
    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
  })
})

describe('Save with existing config (UPDATE)', () => {
  let wrapper
  let saveButton
  let consoleSpy = null

  beforeEach(async () => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_user_id=5&grist_doc_id=doc-123'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        configs: [{
          otp_config_id: 1,
          grist_base_url: 'https://example.com'
        }]
      })
    })

    wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    saveButton = wrapper.find('[data-test-id="submit-form-button"]')
  })

  afterEach(() => {
    delete globalThis.getGristContext
    consoleSpy.mockRestore()
  })

  it('includes otp_config_id in POST body when updating', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5',
      docId: 'doc-123',
      baseUrl: 'https://grist.example.com',
      token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    await saveButton.trigger('click')

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ds_api_token: 'dn-token',
        demarche_number: '12345',
        grist_base_url: 'https://grist.example.com',
        grist_doc_id: 'doc-123',
        grist_user_id: '5',
        grist_api_key: 'grist-token',
        otp_config_id: 1
      })
    })
  })

  it('re-fetches config after successful save', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] }) })
    globalThis.fetch = fetchMock

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5',
      docId: 'doc-123',
      baseUrl: 'https://grist.example.com',
      token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    await saveButton.trigger('click')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: expect.any(String)
    })
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
    '/api/config?grist_user_id=5&grist_doc_id=doc-123'
    )
    expect(wrapper.getComponent(GristFormSection).props('existingConfig'))
      .toEqual({ otp_config_id: 1 })
  })

  it('handles save error gracefully without crashing', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ success: false, message: 'Erreur de typage' })
    })

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5',
      docId: 'doc-123',
      baseUrl: 'https://grist.example.com',
      token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    await saveButton.trigger('click')

    expect(consoleSpy).toHaveBeenCalledWith('Erreur lors de la sauvegarde :', 'Erreur de typage')
  })
})
