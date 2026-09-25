import { describe, it, expect, beforeEach } from 'vitest'
import { useSyncTask } from '../useSyncTask'

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
})