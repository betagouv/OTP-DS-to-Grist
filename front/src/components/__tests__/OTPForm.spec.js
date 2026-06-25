import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import OTPForm from '../OTPForm.vue'
import GristFormSection from '../GristFormSection.vue'
import DNFormSection from '../DNFormSection.vue'

describe('canSave computation', () => {
  let wrapper

  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('is false on load', () => {
    expect(wrapper.getComponent(DNFormSection).props('canSave')).toBe(false)
  })

  it('is false when Grist has error', async () => {
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', 'Erreur de connexion')
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(DNFormSection).props('canSave')).toBe(false)
  })

  it('is false when DN has error', async () => {
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', 'Erreur de connexion')
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(DNFormSection).props('canSave')).toBe(false)
  })

  it('is true when both verifications succeed', async () => {
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(DNFormSection).props('canSave')).toBe(true)
  })
})

describe('canSync computation', () => {
  let wrapper

  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('is false when there is no config', () => {
    expect(wrapper.getComponent(DNFormSection).props('canSync')).toBe(false)
  })

  it('is true when config exists and not syncing', async () => {
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.vm.otpConfigId = 42
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(DNFormSection).props('canSync')).toBe(true)
  })

  it('is false when syncRunning is true', async () => {
    wrapper.vm.otpConfigId = 42
    await wrapper.setProps({ syncRunning: true })
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(DNFormSection).props('canSync')).toBe(false)
  })
})

describe('Save button action', () => {
  let wrapper

  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
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
    wrapper.getComponent(DNFormSection).vm.$emit('save')
    await wrapper.vm.$nextTick()

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

  it('does not call API when canSave is false', async () => {
    const mockFetch = vi.fn()
    globalThis.fetch = mockFetch
    wrapper.getComponent(DNFormSection).vm.$emit('save')
    await wrapper.vm.$nextTick()

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
    wrapper.getComponent(DNFormSection).vm.$emit('save')
    await wrapper.vm.$nextTick()

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
    wrapper.getComponent(DNFormSection).vm.$emit('save')
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
    wrapper.getComponent(DNFormSection).vm.$emit('save')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(consoleSpy).toHaveBeenCalledWith('Erreur lors de la sauvegarde :', 'Erreur de typage')
  })
})

describe('Delete action', () => {
  let wrapper
  let consoleSpy = null
  const mockContext = { params: '?grist_user_id=5&grist_doc_id=doc-123' }

  beforeEach(async () => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        configs: [{
          otp_config_id: 1,
          grist_base_url: 'https://example.com'
        }]
      })
    })
    globalThis.confirm = vi.fn()
    globalThis.location = { href: '' }

    wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
  })

  afterEach(() => {
    delete globalThis.getGristContext
    delete globalThis.confirm
    delete globalThis.location
    consoleSpy.mockRestore()
  })

  it('calls DELETE route when config exists', async () => {
    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })

    wrapper.getComponent(DNFormSection).vm.$emit('delete')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.confirm).toHaveBeenCalled()
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/config/1', {
      method: 'DELETE'
    })
  })

  it('resets config refs after successful deletion', async () => {
    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })

    wrapper.getComponent(DNFormSection).vm.$emit('delete')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
    expect(wrapper.getComponent(DNFormSection).props('existingConfig')).toBeNull()
  })

  it('does not call API when confirm is cancelled', async () => {
    globalThis.confirm.mockReturnValue(false)
    globalThis.fetch.mockReset()

    wrapper.getComponent(DNFormSection).vm.$emit('delete')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('handles delete error gracefully', async () => {
    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ success: false, message: 'Erreur de suppression' })
    })

    wrapper.getComponent(DNFormSection).vm.$emit('delete')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(consoleSpy).toHaveBeenCalledWith('Erreur lors de la suppression :', 'Erreur de suppression')
  })

  it('handles network error in catch block', async () => {
    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()
    globalThis.fetch.mockRejectedValue(new Error('network error'))

    wrapper.getComponent(DNFormSection).vm.$emit('delete')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(consoleSpy).toHaveBeenCalledWith(
      'Erreur lors de la suppression :',
      'network error'
    )
  })

  it('does not delete when there is no otpConfigId', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ configs: [] })
    })

    const wrapperNoConfig = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()

    wrapperNoConfig.getComponent(DNFormSection).vm.$emit('delete')
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })
})

describe('Sync action', () => {
  let wrapper

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

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
  })

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('calls sync API route with otp_config_id in body', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({ ok: true })

    wrapper.getComponent(DNFormSection).vm.$emit('sync')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/start-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: 1 })
    })
  })

  it('does not call API when there is no config', async () => {
    globalThis.getGristContext.mockResolvedValue({
      params: '?grist_user_id=5&grist_doc_id=doc-123'
    })
    globalThis.fetch.mockResolvedValue({
      json: () => Promise.resolve({ configs: [] })
    })

    const wrapperNoConfig = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    globalThis.fetch.mockReset()

    wrapperNoConfig.getComponent(DNFormSection).vm.$emit('sync')
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it("does not call sync API route when syncRunning is true", async () => {
    globalThis.getGristContext.mockResolvedValue({
      params: '?grist_user_id=5&grist_doc_id=doc-123'
    })
    const fetchSpy = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ configs: [{
        otp_config_id: 1,
        grist_base_url: 'https://example.com'
      }] })
    })
    globalThis.fetch = fetchSpy

    const wrapperSync = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } },
      props: { syncRunning: true }
    })
    await new Promise(process.nextTick)
    await wrapperSync.vm.$nextTick()

    wrapperSync.getComponent(DNFormSection).vm.$emit('sync')

    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('calls fetch even when it fails', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockRejectedValue(new Error('network error'))

    wrapper.getComponent(DNFormSection).vm.$emit('sync')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/start-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: 1 })
    })
  })
})
