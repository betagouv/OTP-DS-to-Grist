import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { DsfrInput, DsfrInputGroup } from '@gouvminint/vue-dsfr'
import GristContext from '../GristFormSection.vue'

beforeEach(() => {
  window.getGristContext = vi.fn().mockResolvedValue({
    userId: 'user-abc123',
    docId: 'doc-xyz789',
    baseUrl: 'https://example.com/api'
  })
})

describe('GristContext', () => {
  it('load data from grist', async () => {
    const wrapper = mount(GristContext, {
      global: {
        components: { DsfrInput }
      }
    })

    expect(window.getGristContext).toHaveBeenCalled()

    await wrapper.vm.$nextTick() // L'async onMounted termine, les refs sont assignées
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

    const wrapper = mount(GristContext, {
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

    const wrapper = mount(GristContext, {
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
})
