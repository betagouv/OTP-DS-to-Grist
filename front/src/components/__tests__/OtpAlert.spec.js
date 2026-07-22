import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import OtpAlert from '../OtpAlert.vue'
import { DsfrAlert } from '@gouvminint/vue-dsfr'

const scrollIntoView = vi.fn()
Element.prototype.scrollIntoView = scrollIntoView

describe('OtpAlert', () => {
  beforeEach(() => {
    scrollIntoView.mockClear()
  })

  it('renders DsfrAlert with correct props', () => {
    const wrapper = mount(OtpAlert, {
      props: { type: 'error', title: 'Erreur test', closeable: true },
      global: { components: { DsfrAlert } }
    })

    const alert = wrapper.findComponent(DsfrAlert)
    expect(alert.exists()).toBe(true)
    expect(alert.props('type')).toBe('error')
    expect(alert.props('title')).toBe('Erreur test')
    expect(alert.props('closeable')).toBe(true)
  })

  it('emits close event when DsfrAlert emits close', async () => {
    const wrapper = mount(OtpAlert, {
      props: { type: 'error', title: 'Erreur', closeable: true },
      global: { components: { DsfrAlert } }
    })

    const alert = wrapper.findComponent(DsfrAlert)
    alert.vm.$emit('close')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('scrolls into view when title is set', async () => {
    const wrapper = mount(OtpAlert, {
      props: { type: 'error', title: 'Error' },
      global: { components: { DsfrAlert } }
    })

    await wrapper.setProps({ title: 'Nouvelle erreur' })
    await wrapper.vm.$nextTick()

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
  })
})
