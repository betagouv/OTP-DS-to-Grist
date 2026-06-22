import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { DsfrInput, DsfrInputGroup } from '@gouvminint/vue-dsfr'
import DNFormSection from '../DNFormSection.vue'

describe('DN form section', () => {
  it('shows error message when form validation fails', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ success: false, message: 'Token invalide' })
    })

    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('mauvais-token')
    await tokenInput.trigger('change')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('mauvais-numéro')
    await numberInput.trigger('change')

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        api_token: 'mauvais-token',
        api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
        demarche_number: 'mauvais-numéro',
      })
    })
    const errorText = wrapper.find('.fr-error-text')
    expect(errorText.exists()).toBe(true)
    expect(errorText.text()).toBe('Token invalide')
  })

  it('shows no error when form is valid', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })

    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('bon-token')
    await tokenInput.trigger('change')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('bon-numéro')
    await numberInput.trigger('change')

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        api_token: 'bon-token',
        api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
        demarche_number: 'bon-numéro',
      })
    })
    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
  })
})
