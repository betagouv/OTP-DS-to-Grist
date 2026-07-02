import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SyncProgress from '../SyncProgress.vue'
import { useDemarcheContext } from '../../composables/useDemarcheContext'

const mockOn = vi.fn()
const mockDisconnect = vi.fn()
const mockSocket = { on: mockOn, disconnect: mockDisconnect }

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket)
}))

const scrollIntoView = vi.fn()
Element.prototype.scrollIntoView = scrollIntoView

function triggerTaskUpdate(task) {
  const handler = mockOn.mock.calls.find(([event]) => event === 'task_update')?.[1]
  if (handler) handler({ task })
}

describe('SyncProgress', () => {
  let wrapper

  beforeEach(() => {
    mockOn.mockClear()
    mockDisconnect.mockClear()
    scrollIntoView.mockClear()
    const { setDemarcheCount } = useDemarcheContext()
    setDemarcheCount(0)
    globalThis.parseLogMessage = vi.fn((msg, counts = { success: 0, error: 0, total: 0 }) => {
      const r = { ...counts }
      if (msg.includes('succès')) r.success++
      if (msg === 'error') r.error++
      return r
    })
    wrapper = mount(SyncProgress)
  })

  afterEach(() => {
    wrapper?.unmount()
    delete globalThis.parseLogMessage
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

  it('display démarches count from shared context', async () => {
    const { setDemarcheCount } = useDemarcheContext()
    setDemarcheCount(3)
    triggerTaskUpdate({ status: 'running', progress: 50, message: 'En cours' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('1/3 démarche(s) synchronisée(s)')
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

  it('scrolls into view when sync starts running', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Démarrage' })

    await new Promise(resolve => setTimeout(resolve))

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' })
  })

  it('does not scroll on subsequent progress updates', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Démarrage' })

    await new Promise(resolve => setTimeout(resolve))
    scrollIntoView.mockClear()

    triggerTaskUpdate({ status: 'running', progress: 50, message: 'Progression' })

    await new Promise(resolve => setTimeout(resolve))

    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('disconnect socket on unmount', () => {
    const localWrapper = mount(SyncProgress)
    localWrapper.unmount()
    expect(mockDisconnect).toHaveBeenCalled()
  })

  it('display success card from logs', async () => {
    triggerTaskUpdate({
      status: 'running', progress: 50, message: 'En cours',
      logs: [{ message: 'succès' }]
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Dossiers synchronisés')
  })

  it('display success and failed cards', async () => {
    triggerTaskUpdate({
      status: 'running', progress: 50, message: 'En cours',
      logs: [{ message: 'succès' }, { message: 'error' }]
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Dossiers synchronisés')
    expect(wrapper.text()).toContain('Échecs')
  })

  it('hide card without log', async () => {
    triggerTaskUpdate({
      status: 'running', progress: 50, message: 'En cours',
      logs: [{ message: 'autre information' }]
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Dossiers synchronisés')
    expect(wrapper.text()).not.toContain('Échecs')
  })
})
