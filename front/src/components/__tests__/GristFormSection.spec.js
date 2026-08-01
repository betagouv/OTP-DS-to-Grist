import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import { DsfrInput, DsfrInputGroup } from '@gouvminint/vue-dsfr'
import GristFormSection from '../GristFormSection.vue'

// Microtask pour que le v-model ait le temps de setter les refs avant validation
vi.mock(
  '../../utils/debounce',
  () => ({ debounce: (fn) => (...args) => Promise.resolve().then(() => fn(...args)) })
)

beforeEach(() => {
  window.HELP_LINKS = {
    token_api: 'https://fake-url.example.com/token-api',
    grist_api_key: 'https://fake-url.example.com/grist-api-key',
    faq: 'https://fake-url.example.com/faq'
  }
  window.getGristContext = vi.fn().mockResolvedValue({
    userId: 'user-abc123',
    docId: 'doc-xyz789',
    baseUrl: 'https://example.com/api'
  })
})

describe('Grist form section', () => {
  it('load data from grist', async () => {
    const wrapper = mount(GristFormSection, {
      global: {
        components: { DsfrInput }
      }
    })

    expect(window.getGristContext).toHaveBeenCalled()

    await wrapper.vm.$nextTick() // Vue réagit, le DOM est mis à jour

    expect(wrapper.vm.userId).toBe('user-abc123')
    expect(wrapper.vm.docId).toBe('doc-xyz789')
    expect(wrapper.vm.baseUrl).toBe('https://example.com/api')
  })

  it('shows error message when token validation fails', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Token invalide' })
    })

    globalThis.fetch = mockFetch

    const wrapper = mount(GristFormSection, {
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })

    const tokenInput = wrapper.find('[data-test-id="grist-token"]')
    await tokenInput.setValue('mauvais-token')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'grist',
        base_url: 'https://example.com/api',
        api_key: 'mauvais-token',
        doc_id: 'doc-xyz789'
      })
    })
    const errorText = wrapper.find('.fr-error-text')
    expect(errorText.exists()).toBe(true)
    expect(errorText.text()).toBe('Token invalide')
  })

  it('shows no error when token is valid', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })

    globalThis.fetch = mockFetch

    const wrapper = mount(GristFormSection, {
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })

    const tokenInput = wrapper.find('[data-test-id="grist-token"]')
    await tokenInput.setValue('bon-token')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'grist',
        base_url: 'https://example.com/api',
        api_key: 'bon-token',
        doc_id: 'doc-xyz789'
      })
    })
    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
  })

  it('validates Grist connection automatically on load with existing config', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.vm.$nextTick()

    await wrapper.setProps({
      existingConfig: { otp_config_id: 42, grist_base_url: 'https://grist.example.com', has_grist_key: true }
    })
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'grist',
        base_url: 'https://grist.example.com',
        api_key: '',
        doc_id: 'doc-xyz789',
        otp_config_id: 42
      })
    })

    expect(wrapper.vm.gristTokenErrorMessage).toBe('')
    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
  })

  it('shows error on load when Grist connection fails automatically', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Clé invalide' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.vm.$nextTick()

    await wrapper.setProps({
      existingConfig: { otp_config_id: 42, grist_base_url: 'https://grist.example.com', has_grist_key: true }
    })
    await flushPromises()

    expect(wrapper.vm.gristTokenErrorMessage).toBe('Clé invalide')
    expect(wrapper.find('.fr-error-text').text()).toBe('Clé invalide')
  })

  it('does not overwrite baseUrl from existingConfig', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput } }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.vm.baseUrl).toBe('https://example.com/api')

    await wrapper.setProps({ existingConfig: {
      grist_base_url: 'https://new-url.com'
    } })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.baseUrl).toBe('https://example.com/api')
    expect(wrapper.vm.getData().baseUrl).toBe('https://example.com/api')
  })

  it('set baseUrl from existingConfig when config has otp_config_id', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput } }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.vm.baseUrl).toBe('https://example.com/api')

    await wrapper.setProps({ existingConfig: { otp_config_id: 1, grist_base_url: 'https://new-url.com' } })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.baseUrl).toBe('https://new-url.com')
    expect(wrapper.vm.getData().baseUrl).toBe('https://new-url.com')
  })

  it('keeps default placeholder when has_grist_key is false', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({ existingConfig: { grist_base_url: 'https://new-url.com', has_grist_key: false } })
    const input = wrapper.find('input[type="password"]')

    expect(input.attributes('placeholder')).toBe('Saisissez votre clé grist')
  })

  it('sets gristFetchError when getGristContext fails on mount', async () => {
    window.getGristContext = vi.fn().mockRejectedValue(new Error('context error'))

    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.gristFetchError).toBe('context error')
  })

  it('opens the accordion when existingConfig becomes empty', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({
      existingConfig: { otp_config_id: 42, grist_base_url: 'https://grist.example.com', has_grist_key: true }
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeAccordion).toBe(-1)

    await wrapper.setProps({ existingConfig: null })
    await wrapper.vm.$nextTick()

    const input = wrapper.find('input[type="password"]')
    expect(wrapper.vm.activeAccordion).toBe(0)
    expect(input.attributes('placeholder')).toBe('Saisissez votre clé grist')
  })

  it('closes the accordion when a saved config exists', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.vm.$nextTick()

    await wrapper.setProps({
      existingConfig: { otp_config_id: 42, grist_base_url: 'https://grist.example.com', has_grist_key: true }
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeAccordion).toBe(-1)
  })

  it('keeps the key masked for a saved config', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({
      existingConfig: { otp_config_id: 1, has_grist_key: true }
    })
    await wrapper.vm.$nextTick()

    const input = wrapper.find('input[type="password"]')
    expect(input.attributes('placeholder')).toMatch(/\*{3,}/)
    expect(wrapper.vm.activeAccordion).toBe(-1)
  })

  it('opens the accordion when the config is not saved', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.vm.$nextTick()

    await wrapper.setProps({
      existingConfig: { otp_config_id: null }
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.activeAccordion).toBe(0)
  })

  it('sets gristFetchError when test-connection fetch fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('network error'))

    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    const tokenInput = wrapper.find('[data-test-id="grist-token"]')
    await tokenInput.setValue('some-token')
    await flushPromises()

    expect(wrapper.vm.gristFetchError).toBe('Erreur lors du test de connexion Grist')
  })
})
