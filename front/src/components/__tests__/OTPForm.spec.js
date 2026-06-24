import { vi, describe, beforeEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import OTPForm from '../OTPForm.vue'
import GristFormSection from '../GristFormSection.vue'
import DNFormSection from '../DNFormSection.vue'

describe('Save button state', () => {
  let wrapper
  let saveButton

  beforeEach(() => {
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
    saveButton = wrapper.find('[data-test-id="submit-form-button"]')
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
    wrapper = mount(OTPForm, {
      global: {
        stubs: { GristFormSection: true, DNFormSection: true }
      }
    })
    saveButton = wrapper.find('[data-test-id="submit-form-button"]')
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
