import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import OTPForm from '../OTPForm.vue'
import GristFormSection from '../GristFormSection.vue'
import DNFormSection from '../DNFormSection.vue'
import OtpAlert from '../ui/OtpAlert.vue'
import { useSyncTask } from '../../composables/useSyncTask'

describe('hasUnsavedSection computation', () => {
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123' }

  beforeEach(() => {
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] })
    })
  })

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('is true when serverConfigs is empty (fallback [null])', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [] })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasUnsavedSection).toBe(true)
  })

  it('is true when config has otp_config_id null', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: null }] })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasUnsavedSection).toBe(true)
  })

  it('is false when all configs have a valid otp_config_id', async () => {
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasUnsavedSection).toBe(false)
  })

  it('is true when mixing saved config and null entry', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    wrapper.vm.serverConfigs.push(null)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasUnsavedSection).toBe(true)
  })
})

describe('Add demarche button', () => {
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123' }

  beforeEach(() => {
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] })
    })
  })

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('is rendered with correct test id', async () => {
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const button = wrapper.find('[data-test-id="add-dn-section-button"]')
    expect(button.exists()).toBe(true)
  })

  it('is disabled when hasUnsavedSection is true', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [] })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const button = wrapper.find('[data-test-id="add-dn-section-button"]')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('is enabled when hasUnsavedSection is false', async () => {
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const button = wrapper.find('[data-test-id="add-dn-section-button"]')
    expect(button.attributes('disabled')).toBeUndefined()
  })
})

describe('handleAddDemarche', () => {
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123' }

  beforeEach(() => {
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] })
    })
  })

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('adds a null entry to serverConfigs', async () => {
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const initialLength = wrapper.vm.serverConfigs.length
    wrapper.vm.handleAddDemarche()
    expect(wrapper.vm.serverConfigs.length).toBe(initialLength + 1)
    expect(wrapper.vm.serverConfigs[initialLength]).toBeNull()
  })

  it('renders a new DNFormSection after add', async () => {
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    wrapper.vm.handleAddDemarche()
    await wrapper.vm.$nextTick()

    const dnSections = wrapper.findAllComponents(DNFormSection)
    expect(dnSections.length).toBeGreaterThanOrEqual(2)
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
    wrapper.vm.serverConfigs = [{ otp_config_id: 42 }]
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(DNFormSection).props('canSync')).toBe(true)
  })

  it('is false when syncRunning is true', async () => {
    wrapper.vm.serverConfigs = [{ otp_config_id: 42 }]
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
      ok: true,
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
      demarche_number: '12345',
      filter_date_start: '2023-01-01',
      filter_date_end: '2023-12-31',
      filter_statuses: 'en_construction,accepte',
      filter_groups: '1,3'
    })
    await wrapper.vm.$nextTick()
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await wrapper.vm.$nextTick()

    expect(mockFetch).toHaveBeenCalledWith('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ds_api_token: 'dn-token',
        demarche_number: '12345',
        grist_base_url: 'https://grist.example.com',
        grist_api_key: 'grist-token',
        filter_date_start: '2023-01-01',
        filter_date_end: '2023-12-31',
        filter_statuses: 'en_construction,accepte',
        filter_groups: '1,3'
      })
    })
  })

})

describe('Config loading on mount', () => {
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123', baseUrl: 'https://grist.example.com/api' }
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
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1, grist_base_url: 'https://example.com' }] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.getGristContext).toHaveBeenCalled()
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/config?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
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

  it('renders the Grist section only once the config is loaded', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    let resolveConfig
    globalThis.fetch.mockReturnValue(new Promise((resolve) => { resolveConfig = resolve }))

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)

    // Pas de null provisoire transmis au bloc Grist pendant le chargement
    expect(wrapper.findComponent(GristFormSection).exists()).toBe(false)

    resolveConfig({ json: () => Promise.resolve({ configs: [] }) })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
  })

  it('handles getGristContext error gracefully', async () => {
    globalThis.getGristContext.mockRejectedValue(new Error('context error'))

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.configError).toBe('Erreur lors du chargement de la configuration')
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

    expect(wrapper.vm.configError).toBe('Erreur lors du chargement de la configuration')
    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
  })

  it('emits config-loaded after successful load', async () => {
    const configs = [
      { otp_config_id: 1, grist_base_url: 'https://example.com' },
      { otp_config_id: 2, grist_base_url: 'https://other.com' }
    ]
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('config-loaded')).toHaveLength(1)
  })
})

describe('Save with existing config (UPDATE)', () => {
  let wrapper
  let consoleSpy = null

  beforeEach(async () => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
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
      ok: true,
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
      token: 'dn-token',
      demarche_number: '12345',
      filter_date_start: '2023-06-01',
      filter_date_end: '2023-06-30'
    })
    await wrapper.vm.$nextTick()
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ds_api_token: 'dn-token',
        demarche_number: '12345',
        grist_base_url: 'https://grist.example.com',
        grist_api_key: 'grist-token',
        filter_date_start: '2023-06-01',
        filter_date_end: '2023-06-30',
        otp_config_id: 1
      })
    })
  })

  it('re-fetches config after successful save', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] }) })
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
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: expect.any(String)
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/schedule', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: 1 })
    })
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/config?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    )
    expect(wrapper.getComponent(GristFormSection).props('existingConfig'))
      .toEqual({ otp_config_id: 1 })
  })

  it('enables schedule (POST /api/schedule) after save when auto_sync_enabled is true', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] }) })
    globalThis.fetch = fetchMock

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345', auto_sync_enabled: true
    })
    await wrapper.vm.$nextTick()
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: 1 })
    })
    expect(wrapper.vm.actionErrors[0]).toBeNull()
  })

  it('shows an error when the schedule save fails after config save', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, message: 'Clé grist manquante' }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] }) })
    globalThis.fetch = fetchMock

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345', auto_sync_enabled: true
    })
    await wrapper.vm.$nextTick()
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0])
      .toBe("Configuration sauvegardée, mais la synchronisation automatique n'a pas pu être enregistrée")
  })

  it('handles save error gracefully without crashing', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      ok: true,
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
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('Erreur de typage')
  })

  it('does not leave an empty section after save', async () => {
    wrapper.vm.serverConfigs = [null]
    await wrapper.vm.$nextTick()

    globalThis.fetch.mockReset()
    globalThis.fetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] }) })

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
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.serverConfigs.some(c => c === null)).toBe(false)
  })

  it('sets actionErrors on handleSave network error', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockRejectedValue(new Error('network error'))

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
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('Erreur lors de la sauvegarde')
  })

  it('shows the server message when handleSave is refused', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({
        success: false,
        message: 'Accès propriétaire requis sur le document Grist'
      })
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
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('Accès propriétaire requis sur le document Grist')
  })
})

describe('Multi-section save', () => {
  let wrapper
  let consoleSpy = null

  beforeEach(async () => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        configs: [
          { otp_config_id: 1, demarche_number: '11111' },
          { otp_config_id: 2, demarche_number: '22222' }
        ]
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

  it('sends correct otp_config_id when saving a section', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const dnSections = wrapper.findAllComponents(DNFormSection)

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    dnSections[0].vm.$emit('error-update', '')
    dnSections[1].vm.$emit('error-update', '')

    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[0].vm.getData = () => ({ token: 'dn-token-2', demarche_number: '22222' })
    dnSections[1].vm.getData = () => ({ token: 'dn-token-1', demarche_number: '11111' })

    await wrapper.vm.$nextTick()
    dnSections[0].vm.$emit('save', 0)
    await wrapper.vm.$nextTick()

    expect(mockFetch).toHaveBeenCalledWith('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ds_api_token: 'dn-token-2',
        demarche_number: '22222',
        grist_base_url: 'https://grist.example.com',
        grist_api_key: 'grist-token',
        otp_config_id: 2
      })
    })
  })

  it('does not mix data between sections', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const dnSections = wrapper.findAllComponents(DNFormSection)

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    dnSections[0].vm.$emit('error-update', '')
    dnSections[1].vm.$emit('error-update', '')

    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[0].vm.getData = () => ({ token: 'token-bbb', demarche_number: '22222' })
    dnSections[1].vm.getData = () => ({ token: 'token-aaa', demarche_number: '11111' })

    await wrapper.vm.$nextTick()
    dnSections[1].vm.$emit('save', 1)
    await wrapper.vm.$nextTick()

    const body = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(body.ds_api_token).toBe('token-aaa')
    expect(body.demarche_number).toBe('11111')
    expect(body.otp_config_id).toBe(1)
  })

  it('clears only the error of the section being saved', async () => {
    const mockFetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ configs: [
        { otp_config_id: 1, demarche_number: '11111' },
        { otp_config_id: 2, demarche_number: '22222' }
      ] }) })
    globalThis.fetch = mockFetch

    const dnSections = wrapper.findAllComponents(DNFormSection)

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    dnSections[0].vm.$emit('error-update', '')
    dnSections[1].vm.$emit('error-update', '')

    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[0].vm.getData = () => ({ token: 'dn-token-1', demarche_number: '11111' })
    dnSections[1].vm.getData = () => ({ token: 'dn-token-2', demarche_number: '22222' })

    wrapper.vm.actionErrors[0] = 'erreur section 0'
    wrapper.vm.actionErrors[1] = 'erreur section 1'
    await wrapper.vm.$nextTick()

    dnSections[1].vm.$emit('save', 1)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('erreur section 0')
    expect(wrapper.vm.actionErrors[1]).toBeNull()
  })

  it('shows the save error on the failing section', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Erreur de typage' })
    })

    const dnSections = wrapper.findAllComponents(DNFormSection)

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    dnSections[0].vm.$emit('error-update', '')
    dnSections[1].vm.$emit('error-update', '')

    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[0].vm.getData = () => ({ token: 'dn-token-1', demarche_number: '11111' })
    dnSections[1].vm.getData = () => ({ token: 'dn-token-2', demarche_number: '22222' })

    dnSections[1].vm.$emit('save', 1)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[1]).toBe('Erreur de typage')
    expect(wrapper.vm.actionErrors[0]).toBeUndefined()
  })

  it('shows the network error on the failing section', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockRejectedValue(new Error('network error'))

    const dnSections = wrapper.findAllComponents(DNFormSection)

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    dnSections[0].vm.$emit('error-update', '')
    dnSections[1].vm.$emit('error-update', '')

    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[0].vm.getData = () => ({ token: 'dn-token-1', demarche_number: '11111' })
    dnSections[1].vm.getData = () => ({ token: 'dn-token-2', demarche_number: '22222' })

    dnSections[1].vm.$emit('save', 1)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[1]).toBe('Erreur lors de la sauvegarde')
    expect(wrapper.vm.actionErrors[0]).toBeUndefined()
  })

})

describe('Delete action', () => {
  let wrapper
  let consoleSpy = null
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123' }

  beforeEach(async () => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
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
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ configs: [] })
      })

    wrapper.getComponent(DNFormSection).vm.$emit('delete', 0)
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
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ configs: [] })
      })

    wrapper.getComponent(DNFormSection).vm.$emit('delete', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.getComponent(GristFormSection).props('existingConfig')).toBeNull()
    expect(wrapper.getComponent(DNFormSection).props('existingConfig')).toBeNull()
  })

  it('does not call API when confirm is cancelled', async () => {
    globalThis.confirm.mockReturnValue(false)
    globalThis.fetch.mockReset()

    wrapper.getComponent(DNFormSection).vm.$emit('delete', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('handles delete error gracefully', async () => {
    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Erreur de suppression' })
    })

    wrapper.getComponent(DNFormSection).vm.$emit('delete', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('Erreur lors de la suppression')
  })

  it('handles network error in catch block', async () => {
    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()
    globalThis.fetch.mockRejectedValue(new Error('network error'))

    wrapper.getComponent(DNFormSection).vm.$emit('delete', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('Erreur lors de la suppression')
  })

  it('does not delete when section has no otp_config_id', async () => {
    globalThis.getGristContext.mockResolvedValue(mockContext)
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [] })
    })

    const wrapperNoConfig = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    globalThis.confirm.mockReturnValue(true)
    globalThis.fetch.mockReset()

    wrapperNoConfig.getComponent(DNFormSection).vm.$emit('delete', 0)
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
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
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

    wrapper.getComponent(DNFormSection).vm.$emit('sync', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/start-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: 1 })
    })
  })

  it('calls sync API route with force_full_sync for a forced sync', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({ ok: true })

    wrapper.getComponent(DNFormSection).vm.$emit('sync', 0, { forceFullSync: true })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/start-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_config_id: 1, force_full_sync: true })
    })
  })

  it('stores task_id via useSyncTask when sync starts', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ task_id: 'task_1' })
    })

    wrapper.getComponent(DNFormSection).vm.$emit('sync', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const { currentTaskId } = useSyncTask()
    expect(currentTaskId.value).toBe('task_1')
  })

  it('does not call API when there is no config', async () => {
    globalThis.getGristContext.mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    })
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [] })
    })

    const wrapperNoConfig = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    globalThis.fetch.mockReset()

    wrapperNoConfig.getComponent(DNFormSection).vm.$emit('sync', 0)
    await new Promise(process.nextTick)
    await wrapperNoConfig.vm.$nextTick()

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('does not call sync API route when syncRunning is true', async () => {
    globalThis.getGristContext.mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    })
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
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

    wrapperSync.getComponent(DNFormSection).vm.$emit('sync', 0)

    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('sets actionErrors on handleSync network error', async () => {
    globalThis.fetch.mockReset()
    globalThis.fetch.mockRejectedValue(new Error('network error'))

    wrapper.getComponent(DNFormSection).vm.$emit('sync', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.actionErrors[0]).toBe('Erreur lors de la synchronisation')
  })

  it('passes the démarche number of the synced section to useSyncTask', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [
        { otp_config_id: 1, demarche_number: '111', grist_base_url: 'https://example.com' },
        { otp_config_id: 2, demarche_number: '222', grist_base_url: 'https://example.com' }
      ] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ task_id: 'task_1' })
    })
    // Tri décroissant : la 2e section est la config 1
    const dnSections = wrapper.findAllComponents(DNFormSection)
    dnSections[1].vm.$emit('sync', 1)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const { demarcheNumber, totalDemarches } = useSyncTask()
    expect(demarcheNumber.value).toBe('111')
    expect(totalDemarches.value).toBe(1)
  })

  it('re-emits the démarche title received from a section', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [
        { otp_config_id: 1, demarche_number: '111', grist_base_url: 'https://example.com' }
      ] })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    wrapper.findComponent(DNFormSection).vm.$emit('title-loaded', '111', 'Ma démarche')

    expect(wrapper.emitted('title-loaded')).toEqual([['111', 'Ma démarche']])
  })
})

describe('Sync all button', () => {
  const mountWithConfigs = async (configs, props = {}) => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } },
      props
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    return wrapper
  }

  const syncAllButton = (wrapper) => wrapper.find('[data-test-id="sync-all-button"]')

  beforeEach(() => {
    vi.restoreAllMocks()
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi'
    })
    useSyncTask().setCurrentTaskId(null)
  })

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('calls POST /api/start-sync-all and follows the returned series', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }, { otp_config_id: 2 }])
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        syncs: [
          { otp_config_id: 2, demarche_number: '222', task_id: 'task_1' },
          { otp_config_id: 1, demarche_number: '111', task_id: 'task_2' }
        ]
      })
    })

    await syncAllButton(wrapper).trigger('click')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/start-sync-all', { method: 'POST' })
    const { currentTaskId, demarcheNumber, totalDemarches } = useSyncTask()
    expect(currentTaskId.value).toBe('task_1')
    expect(demarcheNumber.value).toBe('222')
    expect(totalDemarches.value).toBe(2)
  })

  it('is disabled while a sync is running', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }], { syncRunning: true })

    expect(syncAllButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('is disabled when no démarche is saved', async () => {
    const wrapper = await mountWithConfigs([])

    expect(syncAllButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('is enabled with an unsaved section next to a saved one', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }])
    wrapper.vm.serverConfigs.push(null)
    await wrapper.vm.$nextTick()

    expect(syncAllButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('shows an error when the request fails', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }])
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 409 })

    await syncAllButton(wrapper).trigger('click')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Erreur lors de la synchronisation de toutes les démarches')
    expect(useSyncTask().currentTaskId.value).toBe(null)
  })

  it('shows the message sent by the server when there is one', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }])
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({
        success: false,
        message: 'Une synchronisation de toutes les démarches est déjà en cours'
      })
    })

    await syncAllButton(wrapper).trigger('click')
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Une synchronisation de toutes les démarches est déjà en cours')
    expect(wrapper.text()).not.toContain('Erreur lors de la synchronisation de toutes les démarches')
  })
})

describe('sortConfigs', () => {
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123' }

  beforeEach(() => {
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
  })

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('sorts saved configs by otp_config_id descending', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [
        { otp_config_id: 10 },
        { otp_config_id: 2 },
        { otp_config_id: 7 }
      ] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.configs.map(c => c.otp_config_id)).toEqual([10, 7, 2])
  })

  it('places unsaved entries (null) at the beginning', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [
        { otp_config_id: 5 },
        { otp_config_id: 3 }
      ] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    wrapper.vm.serverConfigs.push(null)
    await wrapper.vm.$nextTick()

    const ids = wrapper.vm.configs.map(c => c?.otp_config_id ?? null)
    expect(ids).toEqual([null, 5, 3])
  })

  it('returns [null] when no configs exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.configs).toEqual([null])
  })

  it('keeps stable keys after reordering', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [
        { otp_config_id: 8 },
        { otp_config_id: 3 }
      ] })
    })

    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const dnSections = wrapper.findAllComponents(DNFormSection)
    expect(dnSections[0].props('existingConfig').otp_config_id).toBe(8)
    expect(dnSections[1].props('existingConfig').otp_config_id).toBe(3)
  })
})

describe('Accordion DN state', () => {
  const mockContext = { params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi', docId: 'doc-123' }

  const mountWithConfigs = async (configs) => {
    globalThis.getGristContext = vi.fn().mockResolvedValue(mockContext)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    return wrapper
  }

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('opens the empty section even when there is already one config', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }, null])
    expect(wrapper.vm.activeDnAccordion).toBe(0)
  })

  it('closes all sections on initial load when none is empty', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }, { otp_config_id: 2 }])
    expect(wrapper.vm.activeDnAccordion).toBe(-1)
  })

  it('closes all sections after starting a sync', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }])
    wrapper.vm.activeDnAccordion = 0
    await wrapper.vm.$nextTick()

    wrapper.getComponent(DNFormSection).vm.$emit('sync', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeDnAccordion).toBe(-1)
  })

  it('keeps the saved section open after a save', async () => {
    const wrapper = await mountWithConfigs([null])
    expect(wrapper.vm.activeDnAccordion).toBe(0)

    globalThis.fetch.mockReset()
    globalThis.fetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true, otp_config_id: 1 }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ configs: [{ otp_config_id: 1 }] }) })

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(DNFormSection).vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    wrapper.getComponent(DNFormSection).vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    wrapper.getComponent(DNFormSection).vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeDnAccordion).toBe(0)
  })

  it('opens the most recent config after save even when the server returns an outdated otp_config_id', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 6 }, null])
    expect(wrapper.vm.activeDnAccordion).toBe(0)

    globalThis.fetch.mockReset()
    globalThis.fetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true, otp_config_id: 1 }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ configs: [{ otp_config_id: 6 }, { otp_config_id: 1 }] })
      })

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    const dnSections = wrapper.findAllComponents(DNFormSection)
    dnSections[0].vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[0].vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    dnSections[0].vm.$emit('save', 0)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeDnAccordion).toBe(1)
  })

  it('keeps the edited config open at its own index after a save', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 6 }, { otp_config_id: 1 }])
    expect(wrapper.vm.activeDnAccordion).toBe(-1)

    wrapper.vm.activeDnAccordion = 1
    await wrapper.vm.$nextTick()

    globalThis.fetch.mockReset()
    globalThis.fetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true, otp_config_id: 1 }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ configs: [{ otp_config_id: 6 }, { otp_config_id: 1 }] })
      })

    wrapper.getComponent(GristFormSection).vm.$emit('error-update', '')
    const dnSections = wrapper.findAllComponents(DNFormSection)
    dnSections[1].vm.$emit('error-update', '')
    wrapper.getComponent(GristFormSection).vm.getData = () => ({
      userId: '5', docId: 'doc-123', baseUrl: 'https://grist.example.com', token: 'grist-token'
    })
    dnSections[1].vm.getData = () => ({
      token: 'dn-token', demarche_number: '12345'
    })
    await wrapper.vm.$nextTick()
    dnSections[1].vm.$emit('save', 1)
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeDnAccordion).toBe(1)
  })
})

describe('Grist key access', () => {
  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  // Le refus d'une clé non propriétaire s'affiche sous la clé (test de connexion
  // du bloc Grist), pas dans une alerte globale du formulaire
  it('shows no global alert for a stored key without owner access', async () => {
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi',
      docId: 'doc-123'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs: [{ otp_config_id: 1, grist_key_access: 'editors' }] })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(OtpAlert).exists()).toBe(false)
  })
})

describe('No saved demarche text', () => {
  const NO_DEMARCHE_TEXT = 'Aucune démarche n’est encore configurée.'
    + ' Pour commencer, ajoutez le jeton API et le numéro de la Démarche Numérique à synchroniser avec Grist.'

  const mountWithConfigs = async (configs) => {
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi',
      docId: 'doc-123'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    return wrapper
  }

  const noDemarcheText = (wrapper) => wrapper.find('[data-test-id="no-demarche-text"]')

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('shows the text when no demarche is saved', async () => {
    const wrapper = await mountWithConfigs([])

    expect(noDemarcheText(wrapper).text()).toBe(NO_DEMARCHE_TEXT)
  })

  it('hides the text once a demarche is saved', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }])

    expect(noDemarcheText(wrapper).exists()).toBe(false)
  })

  it('hides the text while the configuration is loading', () => {
    globalThis.getGristContext = vi.fn(() => new Promise(() => {}))
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })

    expect(noDemarcheText(wrapper).exists()).toBe(false)
  })

  it('hides the text when the configuration failed to load', async () => {
    globalThis.getGristContext = vi.fn().mockResolvedValue({ params: '' })
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('network error'))
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(noDemarcheText(wrapper).exists()).toBe(false)
  })
})

describe('Demarche section title', () => {
  const mountWithConfigs = async (configs) => {
    globalThis.getGristContext = vi.fn().mockResolvedValue({
      params: '?grist_base_url=https%3A%2F%2Fgrist.example.com%2Fapi',
      docId: 'doc-123'
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ configs })
    })
    const wrapper = mount(OTPForm, {
      global: { stubs: { GristFormSection: true, DNFormSection: true } }
    })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    return wrapper
  }

  const title = (wrapper) => wrapper.find('[data-test-id="demarche-section-title"]').text()

  afterEach(() => {
    delete globalThis.getGristContext
    vi.restoreAllMocks()
  })

  it('counts the saved demarches', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }, { otp_config_id: 2 }])

    expect(title(wrapper)).toBe('2. Démarche numérique (2)')
  })

  it('does not count an unsaved section', async () => {
    const wrapper = await mountWithConfigs([{ otp_config_id: 1 }])

    wrapper.vm.serverConfigs.push(null)
    await wrapper.vm.$nextTick()

    expect(title(wrapper)).toBe('2. Démarche numérique (1)')
  })

  it('shows zero when no demarche is saved', async () => {
    const wrapper = await mountWithConfigs([])

    expect(title(wrapper)).toBe('2. Démarche numérique (0)')
  })
})
