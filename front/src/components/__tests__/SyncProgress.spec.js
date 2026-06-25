import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SyncProgress from '../SyncProgress.vue'

const mockOn = vi.fn()
const mockDisconnect = vi.fn()
const mockSocket = { on: mockOn, disconnect: mockDisconnect }

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket)
}))

function triggerTaskUpdate(task) {
  const handler = mockOn.mock.calls.find(([event]) => event === 'task_update')?.[1]
  if (handler) handler({ task })
}

describe('SyncProgress', () => {
  let wrapper

  beforeEach(() => {
    vi.clearAllMocks()
    wrapper = mount(SyncProgress)
  })

  afterEach(() => {
    wrapper?.unmount()
  })

  it('hided by default', () => {
    expect(wrapper.find('.fr-card').exists()).toBe(false)
  })

  it('displayed once task_update is running', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Démarrage' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fr-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('Synchronisation')
  })

  it('display running message', async () => {
    triggerTaskUpdate({ status: 'running', progress: 42, message: 'Chargement...' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Chargement...')
  })

  it('display current percent', async () => {
    triggerTaskUpdate({ status: 'running', progress: 42, message: 'Test' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('42%')
  })

  it('update progression bar width', async () => {
    triggerTaskUpdate({ status: 'running', progress: 75, message: 'Test' })
    await wrapper.vm.$nextTick()

    const bar = wrapper.find('.progress-bar')
    expect(bar.attributes('style')).toContain('width: 75%')
  })

  it('emit sync-running-changed(true) on first event running', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('sync-running-changed')).toBeTruthy()
    expect(wrapper.emitted('sync-running-changed')[0][0]).toBe(true)
  })

  it('emit sync-running-changed(false) on finish', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' })
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('sync-running-changed')
    expect(emitted[0][0]).toBe(true)
    expect(emitted[1][0]).toBe(false)
  })

  it('emit sync-running-changed(false) on error', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({ status: 'error', progress: 50, message: 'Erreur' })
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('sync-running-changed')
    expect(emitted[0][0]).toBe(true)
    expect(emitted[1][0]).toBe(false)
  })

  it('disconnect socket on unmount', () => {
    const localWrapper = mount(SyncProgress)
    localWrapper.unmount()
    expect(mockDisconnect).toHaveBeenCalled()
  })
})
