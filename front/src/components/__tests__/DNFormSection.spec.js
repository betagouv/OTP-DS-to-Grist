import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
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

describe('Save button', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(DNFormSection, {
      global: {
        components: { DsfrInput, DsfrInputGroup }
      }
    })
  })

  it('is disabled when canSave is false', async () => {
    await wrapper.setProps({ canSave: false })
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')

    expect(saveButton.attributes('disabled')).toBeDefined()
  })

  it('is enabled when canSave is true', async () => {
    await wrapper.setProps({ canSave: true })
    const saveButton = wrapper.find('[data-test-id="submit-form-button"]')

    expect(saveButton.attributes('disabled')).toBeUndefined()
  })

  it('emits save event when clicked and enabled', async () => {
    await wrapper.setProps({ canSave: true })
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
