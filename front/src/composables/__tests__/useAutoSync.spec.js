import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { useAutoSync } from '../useAutoSync'
import { api } from '../../utils/InternalApi'

vi.mock('../../utils/InternalApi', () => ({
  api: {
    getSchedule: vi.fn(),
    enableSchedule: vi.fn(),
    disableSchedule: vi.fn()
  }
}))

describe('useAutoSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    api.getSchedule.mockReset()
    api.enableSchedule.mockReset()
    api.disableSchedule.mockReset()
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

  describe('toggleSchedule', () => {
    it('calls enableSchedule and returns true on success', async () => {
      api.enableSchedule.mockResolvedValue({ success: true })

      const { scheduleEnabled, toggleSchedule } = useAutoSync()
      const result = await toggleSchedule(42, true, true)

      expect(api.enableSchedule).toHaveBeenCalledWith(42)
      expect(result).toBe(true)
      expect(scheduleEnabled.value).toBe(true)
    })

    it('calls disableSchedule and returns true on success', async () => {
      api.disableSchedule.mockResolvedValue({ success: true })

      const { scheduleEnabled, toggleSchedule } = useAutoSync()
      scheduleEnabled.value = true
      const result = await toggleSchedule(42, false, true)

      expect(api.disableSchedule).toHaveBeenCalledWith(42)
      expect(result).toBe(true)
      expect(scheduleEnabled.value).toBe(false)
    })

    it('reverts scheduleEnabled and returns false on API error response', async () => {
      api.enableSchedule.mockResolvedValue({ success: false, message: 'Clé grist manquante' })

      const { scheduleEnabled, toggleSchedule } = useAutoSync()
      const result = await toggleSchedule(42, true, true)

      expect(result).toBe(false)
      expect(scheduleEnabled.value).toBe(false)
    })

    it('reverts scheduleEnabled and returns false on network error', async () => {
      api.enableSchedule.mockRejectedValue(new Error('Network error'))

      const { scheduleEnabled, toggleSchedule } = useAutoSync()
      const result = await toggleSchedule(42, true, true)

      expect(result).toBe(false)
      expect(scheduleEnabled.value).toBe(false)
    })

    it('shows notification and returns false when hasGristKey is false', async () => {
      const { scheduleEnabled, toggleSchedule } = useAutoSync()
      const result = await toggleSchedule(42, true, false)

      expect(result).toBe(false)
      expect(scheduleEnabled.value).toBe(false)
      expect(api.enableSchedule).not.toHaveBeenCalled()
      expect(api.disableSchedule).not.toHaveBeenCalled()
    })
  })
})
