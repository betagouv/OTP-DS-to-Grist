import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { DsfrInput, DsfrInputGroup } from '@gouvminint/vue-dsfr'
import GristFormSection from '../GristFormSection.vue'

beforeEach(() => {
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
    await tokenInput.trigger('change')

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
    await tokenInput.trigger('change')

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

  it('set baseUrl from existingConfig when config is loaded', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput } }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.vm.baseUrl).toBe('https://example.com/api')

    await wrapper.setProps({ existingConfig: { grist_base_url: 'https://new-url.com' } })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.baseUrl).toBe('https://new-url.com')
    expect(wrapper.vm.getData().baseUrl).toBe('https://new-url.com')
  })

  it('shows placeholder **** and emits empty error-update when has_grist_key is true', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({ existingConfig: { has_grist_key: true } })

    const input = wrapper.find('input[type="password"]')

    expect(input.attributes('placeholder')).toMatch(/\*{3,}/)
    expect(wrapper.emitted('error-update')).toBeTruthy()
    expect(wrapper.emitted('error-update')[0]).toEqual([''])
  })

  it('keeps default placeholder when has_grist_key is false', async () => {
    const wrapper = mount(GristFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({ existingConfig: { grist_base_url: 'https://new-url.com', has_grist_key: false } })
    const input = wrapper.find('input[type="password"]')

    expect(input.attributes('placeholder')).toBe('Saisissez votre clé grist')
  })
})
