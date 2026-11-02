import { describe, it, expect, beforeEach } from 'vitest'
import { useSyncTask } from '../useSyncTask'

const SERIES = [
  { taskId: 'task_1', demarcheNumber: '111' },
  { taskId: 'task_2', demarcheNumber: '222' },
  { taskId: 'task_3', demarcheNumber: '333' }
]

describe('useSyncTask', () => {
  beforeEach(() => {
    const { setCurrentTaskId } = useSyncTask()
    setCurrentTaskId(null)
  })

  it('returns null currentTaskId by default', () => {
    const { currentTaskId } = useSyncTask()

    expect(currentTaskId.value).toBe(null)
  })

  it('updates currentTaskId reactively via setCurrentTaskId', () => {
    const { currentTaskId, setCurrentTaskId } = useSyncTask()
    setCurrentTaskId('task_3')

    expect(currentTaskId.value).toBe('task_3')
  })

  it('sets null when given null', () => {
    const { currentTaskId, setCurrentTaskId } = useSyncTask()
    setCurrentTaskId('task_1')
    setCurrentTaskId(null)

    expect(currentTaskId.value).toBe(null)
  })

  it('is shared as a singleton across multiple calls', () => {
    const a = useSyncTask()
    const b = useSyncTask()
    a.setCurrentTaskId('task_7')

    expect(b.currentTaskId.value).toBe('task_7')
  })

  it('returns 0 totalDemarches by default', () => {
    const { totalDemarches } = useSyncTask()

    expect(totalDemarches.value).toBe(0)
  })

  it('returns 1 demarcheIndex by default', () => {
    const { demarcheIndex } = useSyncTask()

    expect(demarcheIndex.value).toBe(1)
  })

  it('stores the demarche number of a single sync', () => {
    const { demarcheNumber, totalDemarches, setCurrentTaskId } = useSyncTask()
    setCurrentTaskId('task_1', '12345')

    expect(demarcheNumber.value).toBe('12345')
    expect(totalDemarches.value).toBe(1)
  })

  describe('series', () => {
    it('follows the first task of the series', () => {
      const { currentTaskId, demarcheNumber, demarcheIndex, totalDemarches, setTasks } = useSyncTask()
      setTasks(SERIES)

      expect(currentTaskId.value).toBe('task_1')
      expect(demarcheNumber.value).toBe('111')
      expect(demarcheIndex.value).toBe(1)
      expect(totalDemarches.value).toBe(3)
    })

    it('moves to the next task while the series is not over', () => {
      const { currentTaskId, demarcheNumber, demarcheIndex, setTasks, finishCurrentTask } = useSyncTask()
      setTasks(SERIES)

      expect(finishCurrentTask()).toBe(true)
      expect(currentTaskId.value).toBe('task_2')
      expect(demarcheNumber.value).toBe('222')
      expect(demarcheIndex.value).toBe(2)
    })

    it('ends after the last task, keeping its démarche displayed', () => {
      const { currentTaskId, demarcheNumber, demarcheIndex, setTasks, finishCurrentTask } = useSyncTask()
      setTasks(SERIES)
      finishCurrentTask()
      finishCurrentTask()

      expect(finishCurrentTask()).toBe(false)
      expect(currentTaskId.value).toBe(null)
      expect(demarcheNumber.value).toBe('333')
      expect(demarcheIndex.value).toBe(3)
    })

    it('ends right away for a single sync', () => {
      const { currentTaskId, setCurrentTaskId, finishCurrentTask } = useSyncTask()
      setCurrentTaskId('task_1', '12345')

      expect(finishCurrentTask()).toBe(false)
      expect(currentTaskId.value).toBe(null)
    })

    it('restarts from the first task when a new series is set', () => {
      const { currentTaskId, demarcheIndex, setTasks, finishCurrentTask } = useSyncTask()
      setTasks(SERIES)
      finishCurrentTask()
      setTasks([{ taskId: 'task_9', demarcheNumber: '999' }])

      expect(currentTaskId.value).toBe('task_9')
      expect(demarcheIndex.value).toBe(1)
    })
  })

  describe('seriesTasks', () => {
    it('is empty when no sync is followed', () => {
      const { seriesTasks } = useSyncTask()

      expect(seriesTasks.value).toEqual([])
    })

    it('lists the single sync of one démarche, with its title', () => {
      const { seriesTasks, setCurrentTaskId } = useSyncTask()
      setCurrentTaskId('task_1', '12345', 'Ma démarche')

      expect(seriesTasks.value).toHaveLength(1)
      expect(seriesTasks.value[0]).toMatchObject({
        taskId: 'task_1',
        demarcheNumber: '12345',
        demarcheTitle: 'Ma démarche',
        status: 'queued'
      })
    })

    it('lists every task of the series as queued at start', () => {
      const { seriesTasks, setTasks } = useSyncTask()
      setTasks(SERIES)

      expect(seriesTasks.value.map(task => [task.taskId, task.status])).toEqual([
        ['task_1', 'queued'], ['task_2', 'queued'], ['task_3', 'queued']
      ])
    })

    it('is kept for a series of a single démarche', () => {
      const { seriesTasks, setTasks } = useSyncTask()
      setTasks([SERIES[0]])

      expect(seriesTasks.value).toHaveLength(1)
    })

    it('records status, message, result and accumulates log deltas', () => {
      const { seriesTasks, setTasks, recordTaskUpdate } = useSyncTask()
      setTasks(SERIES)
      recordTaskUpdate('task_2', { status: 'running', message: 'En cours', logs: [{ message: 'a' }] })
      recordTaskUpdate('task_2', {
        status: 'completed',
        message: 'Tâche terminée avec succès',
        result: { success_count: 14, error_count: 0 },
        sync_reason: 'synced',
        logs: [{ message: 'b' }]
      })

      const task = seriesTasks.value[1]
      expect(task.status).toBe('completed')
      expect(task.message).toBe('Tâche terminée avec succès')
      expect(task.result).toEqual({ success_count: 14, error_count: 0 })
      expect(task.syncReason).toBe('synced')
      expect(task.logs.map(log => log.message)).toEqual(['a', 'b'])
      expect(seriesTasks.value[0].status).toBe('queued')
    })

    it('ignores updates of a task which is not tracked', () => {
      const { seriesTasks, setTasks, recordTaskUpdate } = useSyncTask()
      setTasks(SERIES)
      recordTaskUpdate('task_99', { status: 'running', message: 'Autre', logs: [] })

      expect(seriesTasks.value.every(task => task.status === 'queued')).toBe(true)
    })

    it('starts from fresh states when a new series is set', () => {
      const { seriesTasks, setTasks, recordTaskUpdate } = useSyncTask()
      setTasks(SERIES)
      recordTaskUpdate('task_1', { status: 'error', message: 'KO', logs: [{ message: 'a' }] })
      setTasks(SERIES)

      expect(seriesTasks.value[0].status).toBe('queued')
      expect(seriesTasks.value[0].logs).toEqual([])
    })
  })
})
