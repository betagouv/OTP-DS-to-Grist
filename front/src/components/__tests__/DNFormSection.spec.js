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

  it('pre-fills demarche_number from existingConfig when config is loaded', async () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    expect(wrapper.vm.inputDNNumber).toBe('')

    await wrapper.setProps({ existingConfig: { demarche_number: '67890' } })

    expect(wrapper.vm.inputDNNumber).toBe('67890')
    expect(wrapper.vm.getData().demarche_number).toBe('67890')
  })

  it('shows placeholder **** and emits empty error-update when has_ds_token is true', async () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({ existingConfig: { has_ds_token: true } })

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.attributes('placeholder')).toMatch(/\*{3,}/)

    expect(wrapper.emitted('error-update')).toBeTruthy()
    expect(wrapper.emitted('error-update')[0]).toEqual([''])
  })

  it('keeps default placeholder when has_ds_token is false', async () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    await wrapper.setProps({ existingConfig: { demarche_number: '67890', has_ds_token: false } })

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.attributes('placeholder')).toBe('Saisissez votre clé Démarche Numérique')
  })
})
