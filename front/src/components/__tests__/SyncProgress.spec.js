import { vi, describe, beforeAll, afterAll, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import SyncProgress from '../SyncProgress.vue'
import { useSyncTask } from '../../composables/useSyncTask'

const { setCurrentTaskId, setTasks, seriesTasks } = useSyncTask()

const mockOn = vi.fn()
const mockDisconnect = vi.fn()
const mockSocket = { on: mockOn, disconnect: mockDisconnect }

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket)
}))

const scrollIntoView = vi.fn()
Element.prototype.scrollIntoView = scrollIntoView

function triggerTaskUpdate(task, taskId = 'task_1') {
  const handler = mockOn.mock.calls.find(([event]) => event === 'task_update')?.[1]
  if (handler) handler({ task_id: taskId, task })
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
    setCurrentTaskId('task_1', '12345')
    wrapper = mount(SyncProgress)
  })

  afterEach(() => {
    wrapper?.unmount()
    setCurrentTaskId(null)
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

  it('display the démarche number without counter for a single sync', async () => {
    triggerTaskUpdate({ status: 'running', progress: 50, message: 'En cours' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Démarche n°12345')
    expect(wrapper.text()).not.toContain('/1')
  })

  it('display the démarche number and its position in a series', async () => {
    setTasks([
      { taskId: 'task_1', demarcheNumber: '111' },
      { taskId: 'task_2', demarcheNumber: '222' },
      { taskId: 'task_3', demarcheNumber: '333' }
    ])
    triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' }, 'task_1')
    triggerTaskUpdate({ status: 'running', progress: 10, message: 'En cours' }, 'task_2')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Démarche n°222 — 2/3')
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

  it('ignores task_update for a different task', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Autre synchro' }, 'task_2')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fr-card').exists()).toBe(false)
    expect(wrapper.emitted('sync-running-changed')).toBeFalsy()
    expect(wrapper.emitted('sync-started')).toBeFalsy()
    expect(wrapper.emitted('sync-finished')).toBeFalsy()
  })

  it('ignores all task_update when no current task is set', async () => {
    setCurrentTaskId(null)
    triggerTaskUpdate({ status: 'running', progress: 50, message: 'Quelque chose' }, 'task_3')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fr-card').exists()).toBe(false)
    expect(wrapper.emitted('sync-running-changed')).toBeFalsy()
  })

  it('resets currentTaskId on completion', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({
      status: 'completed', progress: 100, message: 'Terminé',
      result: { success_count: 5, error_count: 1 },
      end_time: 1752600000
    })
    await wrapper.vm.$nextTick()

    const { currentTaskId } = useSyncTask()
    expect(currentTaskId.value).toBe(null)
  })

  it('resets currentTaskId on error', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Test' })
    triggerTaskUpdate({ status: 'error', progress: 50, message: 'Erreur' })
    await wrapper.vm.$nextTick()

    const { currentTaskId } = useSyncTask()
    expect(currentTaskId.value).toBe(null)
  })

  describe('series', () => {
    beforeEach(() => {
      setTasks([
        { taskId: 'task_1', demarcheNumber: '111' },
        { taskId: 'task_2', demarcheNumber: '222' }
      ])
    })

    it('follows the next task when a démarche of the series ends', async () => {
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Première' }, 'task_1')
      triggerTaskUpdate({ status: 'error', progress: 50, message: 'Token DN périmé' }, 'task_1')
      triggerTaskUpdate({ status: 'running', progress: 20, message: 'Seconde' }, 'task_2')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Seconde')
      expect(wrapper.emitted('sync-running-changed')).toEqual([[true], [true]])
      expect(wrapper.emitted('sync-finished')).toBeFalsy()
    })

    it('ends only after the last démarche, keeping the bar displayed', async () => {
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Première' }, 'task_1')
      triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' }, 'task_1')
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Seconde' }, 'task_2')
      triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' }, 'task_2')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('sync-running-changed').at(-1)).toEqual([false])
      expect(wrapper.emitted('sync-finished')).toHaveLength(1)
      expect(wrapper.find('.fr-card').exists()).toBe(true)
      expect(wrapper.text()).toContain('Démarche n°222 — 2/2')
    })

    it('ignores updates of a démarche which is not the current one', async () => {
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Seconde' }, 'task_2')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.fr-card').exists()).toBe(false)
    })

    it('records the updates of every démarche of the series for the table', () => {
      triggerTaskUpdate({ status: 'queued', progress: 0, message: 'En attente…' }, 'task_2')
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Première' }, 'task_1')

      expect(seriesTasks.value.map(task => task.message)).toEqual(['Première', 'En attente…'])
    })
  })
})
