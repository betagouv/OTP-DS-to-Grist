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

  describe('nextRun', () => {
    it('stores next_run from the schedule response', async () => {
      api.getSchedule.mockResolvedValue({
        success: true,
        enabled: true,
        next_run: '2026-09-03T09:14:00+00:00'
      })

      const { nextRun, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)

      expect(nextRun.value).toBe('2026-09-03T09:14:00+00:00')
    })

    it('keeps nextRun null when next_run is absent', async () => {
      api.getSchedule.mockResolvedValue({ success: true, enabled: true })

      const { nextRun, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)

      expect(nextRun.value).toBeNull()
    })

    it('resets nextRun to null on fetch error', async () => {
      api.getSchedule.mockRejectedValue(new Error('Network error'))

      const { nextRun, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)

      expect(nextRun.value).toBeNull()
    })

    it('clears nextRun when schedule is disabled', async () => {
      api.getSchedule.mockResolvedValue({
        success: true,
        enabled: true,
        next_run: '2026-09-03T09:14:00+00:00'
      })

      const { nextRun, setScheduleEnabled, fetchSchedule } = useAutoSync()
      await fetchSchedule(42)
      expect(nextRun.value).toBe('2026-09-03T09:14:00+00:00')

      setScheduleEnabled(false)
      expect(nextRun.value).toBeNull()
    })
  })

  describe('setScheduleEnabled', () => {
    it('sets scheduleEnabled to the given value', () => {
      const { scheduleEnabled, setScheduleEnabled } = useAutoSync()

      setScheduleEnabled(true)
      expect(scheduleEnabled.value).toBe(true)

      setScheduleEnabled(false)
      expect(scheduleEnabled.value).toBe(false)
    })
  })
})
