import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import SyncProgress from '../SyncProgress.vue'
import { useSyncTask } from '../../composables/useSyncTask'

const { setCurrentTaskId, setTasks, seriesTasks, currentTaskId } = useSyncTask()

const mockOn = vi.fn()
const mockEmit = vi.fn()
const mockDisconnect = vi.fn()
const mockSocket = { on: mockOn, emit: mockEmit, disconnect: mockDisconnect }

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket)
}))

const scrollIntoView = vi.fn()
Element.prototype.scrollIntoView = scrollIntoView

// Connexion du socket ; le serveur répond à sync_state par `syncs`
async function triggerConnect(syncs = []) {
  mockEmit.mockImplementation((event, _data, ack) => {
    if (event === 'sync_state') ack(syncs)
  })
  const handler = mockOn.mock.calls.find(([event]) => event === 'connect')?.[1]
  await handler()
}

function triggerTaskUpdate(task, taskId = 'task_1') {
  const handler = mockOn.mock.calls.find(([event]) => event === 'task_update')?.[1]
  if (handler) handler({ task_id: taskId, task })
}

describe('SyncProgress', () => {
  let wrapper

  beforeEach(() => {
    mockOn.mockClear()
    mockEmit.mockReset()
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
    expect(wrapper.text()).toContain('Progression')
  })

  it('display the démarche number without counter for a single sync', async () => {
    triggerTaskUpdate({ status: 'running', progress: 50, message: 'En cours' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Progression de la démarche n°12345')
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

    expect(wrapper.text()).toContain('Progression de la démarche n°222 — 2/3')
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

  it('ignores task_update for a different task', async () => {
    triggerTaskUpdate({ status: 'running', progress: 0, message: 'Autre synchro' }, 'task_2')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fr-card').exists()).toBe(false)
    expect(wrapper.emitted('sync-running-changed')).toBeFalsy()
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

      expect(wrapper.text()).toContain('Progression de la démarche n°222 — 2/2')
      expect(wrapper.emitted('sync-running-changed')).toEqual([[true], [true]])
    })

    it('ends only after the last démarche, keeping the bar displayed', async () => {
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Première' }, 'task_1')
      triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' }, 'task_1')
      triggerTaskUpdate({ status: 'running', progress: 0, message: 'Seconde' }, 'task_2')
      triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' }, 'task_2')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('sync-running-changed')).toEqual([[true], [true], [false]])
      expect(wrapper.find('.fr-card').exists()).toBe(true)
      expect(wrapper.text()).toContain('Progression de la démarche n°222 — 2/2')
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

  describe('resume on connect', () => {
    const serverTask = (status, demarcheNumber, extra = {}) => ({
      status,
      demarche_number: demarcheNumber,
      progress: 0,
      message: '',
      logs: [],
      ...extra
    })

    beforeEach(() => {
      setCurrentTaskId(null)
      globalThis.getGristContext = vi.fn().mockResolvedValue({ userId: 'userA', docId: 'docA' })
    })

    afterEach(() => {
      delete globalThis.getGristContext
    })

    it('asks the server for the syncs of the user and document', async () => {
      await triggerConnect()

      expect(mockEmit).toHaveBeenCalledWith(
        'sync_state',
        { grist_user_id: 'userA', grist_doc_id: 'docA' },
        expect.any(Function)
      )
    })

    it('displays a running sync and reports it as running', async () => {
      await triggerConnect([{ task_id: 'task_7', task: serverTask('running', '111', { progress: 42 }) }])
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Progression de la démarche n°111')
      expect(wrapper.text()).toContain('42%')
      expect(wrapper.emitted('sync-running-changed')).toEqual([[true]])
    })

    it('displays the current démarche of a series and keeps all of them for the table', async () => {
      await triggerConnect([
        { task_id: 'task_1', task: serverTask('completed', '111') },
        { task_id: 'task_2', task: serverTask('running', '222', { progress: 10 }) },
        { task_id: 'task_3', task: serverTask('queued', '333') }
      ])
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Progression de la démarche n°222 — 2/3')
      expect(seriesTasks.value.map(task => task.status)).toEqual(['completed', 'running', 'queued'])
    })

    it('keeps following the restored sync with later updates', async () => {
      await triggerConnect([{ task_id: 'task_7', task: serverTask('running', '111') }])
      triggerTaskUpdate({ status: 'completed', progress: 100, message: 'Terminé' }, 'task_7')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('100%')
      expect(wrapper.emitted('sync-running-changed')).toEqual([[true], [false]])
    })

    it('changes nothing when the server has no sync', async () => {
      setCurrentTaskId('task_1', '12345')
      await triggerConnect([])
      await wrapper.vm.$nextTick()

      expect(currentTaskId.value).toBe('task_1')
      expect(wrapper.find('.fr-card').exists()).toBe(false)
      expect(wrapper.emitted('sync-running-changed')).toBeFalsy()
    })

    it('asks nothing without Grist context', async () => {
      globalThis.getGristContext = vi.fn().mockRejectedValue(new Error('grist not available'))
      await triggerConnect()

      expect(mockEmit).not.toHaveBeenCalled()
    })
  })
})
