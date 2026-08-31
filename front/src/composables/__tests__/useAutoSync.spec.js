import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { useAutoSync } from '../useAutoSync'
import { api } from '../../utils/InternalApi'

vi.mock('../../utils/InternalApi', () => ({
  api: {
    getSchedule: vi.fn()
  }
}))

describe('useAutoSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    api.getSchedule.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('fetchSchedule', () => {
    it('sets scheduleEnabled to true when schedule is enabled', async () => {
      api.getSchedule.mockResolvedValue({ success: true, enabled: true })

      const { scheduleEnabled, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)

      expect(api.getSchedule).toHaveBeenCalledWith(42)
      expect(scheduleEnabled.value).toBe(true)
    })

    it('sets scheduleEnabled to false when schedule is disabled', async () => {
      api.getSchedule.mockResolvedValue({ success: true, enabled: false })

      const { scheduleEnabled, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)

      expect(scheduleEnabled.value).toBe(false)
    })

    it('sets scheduleEnabled to false on fetch error', async () => {
      api.getSchedule.mockRejectedValue(new Error('Network error'))

      const { scheduleEnabled, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)

      expect(scheduleEnabled.value).toBe(false)
    })
  })
})
