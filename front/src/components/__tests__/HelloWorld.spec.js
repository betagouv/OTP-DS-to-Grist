import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import HelloWorld from '../HelloWorld.vue'

beforeEach(() => {
  window.getGristContext = vi.fn().mockResolvedValue({ sample: 'context' })
})

describe('HelloWorld', () => {
  it('calls getGristContext on mount', () => {
    mount(HelloWorld)
    expect(window.getGristContext).toHaveBeenCalled()
  })
})
