import { describe, beforeEach, it, expect } from 'vitest'
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
