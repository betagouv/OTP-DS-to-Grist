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

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('mauvais-numéro')

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
        demarche_number: 'mauvais-numéro',
        api_token: 'mauvais-token',
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

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('bon-numéro')

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
        demarche_number: 'bon-numéro',
        api_token: 'bon-token',
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

  it('does not call API when only token is filled', async () => {
    const mockFetch = vi.fn()
    globalThis.fetch = mockFetch
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('un-token')

    expect(mockFetch).not.toHaveBeenCalled()
    expect(wrapper.emitted('error-update')).toBeTruthy()
    expect(wrapper.emitted('error-update')[0]).toEqual([null])
  })

  it('does not call API when only number is filled', async () => {
    const mockFetch = vi.fn()
    globalThis.fetch = mockFetch
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')

    expect(mockFetch).not.toHaveBeenCalled()
    expect(wrapper.emitted('error-update')[0]).toEqual([null])
  })

  it('sends otp_config_id when token empty and config has otp_config_id', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } },
      props: { existingConfig: { otp_config_id: 42, has_ds_token: true } }
    })

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        api_url: 'https://www.demarches-simplifiees.fr/api/v2/graphql',
        demarche_number: '12345',
        otp_config_id: 42
      })
    })
  })

  it('uses explicit token over otp_config_id', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } },
      props: { existingConfig: { otp_config_id: 42, has_ds_token: true } }
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('explicit-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')

    const callBody = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(callBody.api_token).toBe('explicit-token')
    expect(callBody.otp_config_id).toBeUndefined()
  })

  it('clears error when a field is emptied after failed test', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ success: false, message: 'Erreur de connexion' })
    })
    globalThis.fetch = mockFetch
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('mauvais-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')

    expect(wrapper.find('.fr-error-text').exists()).toBe(true)

    await tokenInput.setValue('')

    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
    expect(mockFetch).toHaveBeenCalledTimes(1) // seulement la première fois
  })
})

describe('Save button', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(DNFormSection, {
      props: { existingConfig: { otp_config_id: 1 } },
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })
  })

  it('is disabled when configValid is false', async () => {
    await wrapper.setProps({ configValid: false })
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')

    expect(saveButton.attributes('disabled')).toBeDefined()
  })

  it('is enabled when configValid is true', async () => {
    await wrapper.setProps({ configValid: true })
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')

    expect(saveButton.attributes('disabled')).toBeUndefined()
  })

  it('emits save event when clicked and enabled', async () => {
    await wrapper.setProps({ configValid: true })
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')
    await saveButton.trigger('click')

    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('does not emit save event when clicked and disabled', async () => {
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')
    await saveButton.trigger('click')

    expect(wrapper.emitted('save')).toBeFalsy()
  })
})

describe('Delete button', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(DNFormSection, {
      props: { existingConfig: { otp_config_id: 1 } },
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })
  })

  it('is disabled when canDelete is false', async () => {
    await wrapper.setProps({ canDelete: false })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')

    expect(deleteButton.attributes('disabled')).toBeDefined()
  })

  it('is enabled when canDelete is true', async () => {
    await wrapper.setProps({ canDelete: true })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')

    expect(deleteButton.attributes('disabled')).toBeUndefined()
  })

  it('emits delete event when clicked and enabled', async () => {
    await wrapper.setProps({ canDelete: true })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')
    await deleteButton.trigger('click')

    expect(wrapper.emitted('delete')).toBeTruthy()
  })

  it('does not emit delete event when clicked and disabled', async () => {
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')
    await deleteButton.trigger('click')

    expect(wrapper.emitted('delete')).toBeFalsy()
  })
})

describe('Sync button', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(DNFormSection, {
      props: { existingConfig: { otp_config_id: 1 } },
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })
  })

  it('is disabled when canSync is false', async () => {
    await wrapper.setProps({ canSync: false })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')

    expect(syncButton.attributes('disabled')).toBeDefined()
  })

  it('is enabled when canSync is true', async () => {
    await wrapper.setProps({ canSync: true })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')

    expect(syncButton.attributes('disabled')).toBeUndefined()
  })

  it('emits sync event when clicked and enabled', async () => {
    await wrapper.setProps({ canSync: true })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')
    await syncButton.trigger('click')

    expect(wrapper.emitted('sync')).toBeTruthy()
  })

  it('does not emit sync event when clicked and disabled', async () => {
    const syncButton = wrapper.find('[data-test-id="sync-button"]')
    await syncButton.trigger('click')

    expect(wrapper.emitted('sync')).toBeFalsy()
  })
})

describe('sectionEmpty computed', () => {
  it('is true when existingConfig is null and inputs are empty', () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    expect(wrapper.vm.sectionEmpty).toBe(true)
  })

  it('is true when existingConfig has otp_config_id null and inputs are empty', async () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    await wrapper.setProps({ existingConfig: { otp_config_id: null } })
    expect(wrapper.vm.sectionEmpty).toBe(true)
  })

  it('is false when no existingConfig but a token is filled', async () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('some-token')
    expect(wrapper.vm.sectionEmpty).toBe(false)
  })

  it('is false when existingConfig has a valid otp_config_id', () => {
    const wrapper = mount(DNFormSection, {
      props: { existingConfig: { otp_config_id: 42 } },
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    expect(wrapper.vm.sectionEmpty).toBe(false)
  })

  it('disables Save button when sectionEmpty is true', async () => {
    const wrapper = mount(DNFormSection, {
      props: { configValid: true },
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')
    expect(saveButton.attributes('disabled')).toBeDefined()
  })

  it('disables Sync button when sectionEmpty is true', async () => {
    const wrapper = mount(DNFormSection, {
      props: { canSync: true },
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')
    expect(syncButton.attributes('disabled')).toBeDefined()
  })

  it('disables Delete button when sectionEmpty is true', async () => {
    const wrapper = mount(DNFormSection, {
      props: { canDelete: true },
      global: { components: { DsfrInput, DsfrInputGroup } }
    })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')
    expect(deleteButton.attributes('disabled')).toBeDefined()
  })
})
