import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { DsfrInput } from '@gouvminint/vue-dsfr'
import HelloWorld from '../HelloWorld.vue'

beforeEach(() => {
  window.getGristContext = vi.fn().mockResolvedValue({
    userId: 'user-abc123',
    docId: 'doc-xyz789',
    baseUrl: 'https://example.com/api'
  })
})

describe('HelloWorld', () => {
  it('calls getGristContext on mount', async () => {
    const wrapper = mount(HelloWorld, {
      global: {
        components: { DsfrInput }
      }
    })

    expect(window.getGristContext).toHaveBeenCalled()

    await wrapper.vm.$nextTick() // L'async onMounted termine, les refs sont assignées
    await wrapper.vm.$nextTick() // Vue réagit, le DOM est mis à jour

    const inputs = wrapper.findAllComponents(DsfrInput)
    expect(inputs).toHaveLength(3)

    const inputGristUserId = wrapper.find('[data-test-id="grist-user-id"]')
    expect(inputGristUserId.element.value).toBe('user-abc123')

    const inputGristDocId = wrapper.find('[data-test-id="grist-doc-id"]')
    expect(inputGristDocId.element.value).toBe('doc-xyz789')

    const inputGristBaseUrl = wrapper.find('[data-test-id="grist-base-url"]')
    expect(inputGristBaseUrl.element.value).toBe('https://example.com/api')
  })
})
