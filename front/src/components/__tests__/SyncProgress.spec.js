import { vi, describe, beforeAll, afterAll, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import SyncProgress from '../SyncProgress.vue'
import { useDemarcheContext } from '../../composables/useDemarcheContext'

const mockOn = vi.fn()
const mockDisconnect = vi.fn()
const mockSocket = { on: mockOn, disconnect: mockDisconnect }

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket)
}))

const mockNotify = vi.fn()
vi.mock('../../composables/useNotification.js', () => ({
  useNotification: () => ({ notify: mockNotify })
}))

const scrollIntoView = vi.fn()
Element.prototype.scrollIntoView = scrollIntoView

function triggerTaskUpdate(task) {
  const handler = mockOn.mock.calls.find(([event]) => event === 'task_update')?.[1]
  if (handler) handler({ task })
}

describe('SyncProgress', () => {
  let wrapper

  beforeAll(() => {
    globalThis.parseLogMessage = vi.fn((msg, counts = { success: 0, error: 0, total: 0 }) => {
      const r = { ...counts }
      if (msg.includes('succès')) r.success++
      if (msg === 'error') r.error++
      return r
    })
  })

  afterAll(() => {
    delete globalThis.parseLogMessage
  })

  beforeEach(() => {
    mockOn.mockClear()
    mockDisconnect.mockClear()
    scrollIntoView.mockClear()
    mockNotify.mockClear()
    const { setDemarcheCount } = useDemarcheContext()
    setDemarcheCount(0)
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

  it('emit sync-started on running', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('sync-started')).toBeTruthy()
    expect(wrapper.emitted('sync-started').length).toBe(1)
  })

  it('emit sync-finished with result on completed', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({
      status: 'completed', progress: 100, message: 'Terminé',
      result: { success_count: 5, error_count: 1 },
      end_time: 1752600000,
      sync_reason: 'synced'
    })
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('sync-finished')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toEqual({
      status: 'completed',
      success_count: 5,
      error_count: 1,
      timestamp: new Date(1752600000 * 1000).toISOString(),
      sync_reason: 'synced',
      message: 'Terminé'
    })
  })

  it('emit sync-finished with error on error', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({
      status: 'error', progress: 50, message: 'Erreur',
      result: { success_count: 2, error_count: 3 },
      end_time: 1752600000,
      sync_reason: 'synced'
    })
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('sync-finished')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toEqual({
      status: 'error',
      success_count: 2,
      error_count: 3,
      timestamp: new Date(1752600000 * 1000).toISOString(),
      sync_reason: 'synced',
      message: 'Erreur'
    })
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

  it('calls notify with success message on sync completed', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({
      status: 'completed', progress: 100, message: 'Terminé',
      logs: [{ message: 'succès' }]
    })
    await wrapper.vm.$nextTick()

    expect(mockNotify).toHaveBeenCalledWith(
      'Synchronisation terminée : 1 dossier(s) synchronisé(s)',
      'success'
    )
  })

  it('calls notify with error message on sync error', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({
      status: 'error', progress: 50, message: 'Erreur',
      logs: [{ message: 'error' }]
    })
    await wrapper.vm.$nextTick()

    expect(mockNotify).toHaveBeenCalledWith(
      'Échec de la synchronisation (1 erreur(s))',
      'error'
    )
  })

  it('calls notify with generic error message when no error count', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({
      status: 'error', progress: 50, message: 'Erreur',
      logs: []
    })
    await wrapper.vm.$nextTick()

    expect(mockNotify).toHaveBeenCalledWith(
      'Échec de la synchronisation',
      'error'
    )
  })
})
