import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { useSyncStatus } from '../useSyncStatus'

describe('useSyncStatus', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('fetchLatestSync', () => {
    it('populates lastAutoSync and lastManualSync from API response', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          auto: { status: 'success', success_count: 5, error_count: 1, timestamp: '2026-07-15T10:00:00' },
          manual: { status: 'error', success_count: 2, error_count: 3, timestamp: '2026-07-15T11:00:00' }
        })
      })

      const { lastAutoSync, lastManualSync, fetchLatestSync } = useSyncStatus()
      await fetchLatestSync(42)

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/sync-log/latest?otp_config_id=42')
      expect(lastAutoSync.value).toEqual({ status: 'success', success_count: 5, error_count: 1, timestamp: '2026-07-15T10:00:00' })
      expect(lastManualSync.value).toEqual({ status: 'error', success_count: 2, error_count: 3, timestamp: '2026-07-15T11:00:00' })
    })

    it('sets refs to null when API returns no sync logs', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, auto: null, manual: null })
      })

      const { lastAutoSync, lastManualSync, fetchLatestSync } = useSyncStatus()
      await fetchLatestSync(1)

      expect(lastAutoSync.value).toBeNull()
      expect(lastManualSync.value).toBeNull()
    })

    it('does not update refs when API returns success: false', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: false, message: 'Config not found' })
      })

      const { lastAutoSync, lastManualSync, fetchLatestSync } = useSyncStatus()
      await fetchLatestSync(99)

      expect(lastAutoSync.value).toBeNull()
      expect(lastManualSync.value).toBeNull()
    })

    it('propagates fetch errors to the caller', async () => {
      globalThis.fetch.mockRejectedValue(new Error('Network error'))

      const { fetchLatestSync } = useSyncStatus()

      await expect(fetchLatestSync(1)).rejects.toThrow('Network error')
    })
  })

  describe('fetchAllLatestSyncs', () => {
    it('aggregates sync logs from multiple configs', async () => {
      globalThis.fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            auto: { status: 'success', success_count: 3, error_count: 0, timestamp: '2026-07-15T08:00:00' },
            manual: null
          })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            auto: { status: 'success', success_count: 5, error_count: 1, timestamp: '2026-07-15T09:00:00' },
            manual: { status: 'success', success_count: 2, error_count: 0, timestamp: '2026-07-15T10:00:00' }
          })
        })

      const { lastAutoSync, lastManualSync, fetchAllLatestSyncs } = useSyncStatus()
      await fetchAllLatestSyncs([
        { otp_config_id: 1 },
        { otp_config_id: 2 }
      ])

      expect(globalThis.fetch).toHaveBeenCalledTimes(2)
      expect(lastAutoSync.value).toEqual({ status: 'success', success_count: 5, error_count: 1, timestamp: '2026-07-15T09:00:00' })
      expect(lastManualSync.value).toEqual({ status: 'success', success_count: 2, error_count: 0, timestamp: '2026-07-15T10:00:00' })
    })

    it('keeps the most recent sync when multiple autos exist', async () => {
      globalThis.fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            auto: { status: 'success', success_count: 10, error_count: 0, timestamp: '2026-07-15T12:00:00' },
            manual: null
          })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            auto: { status: 'error', success_count: 2, error_count: 5, timestamp: '2026-07-15T08:00:00' },
            manual: null
          })
        })

      const { lastAutoSync, fetchAllLatestSyncs } = useSyncStatus()
      await fetchAllLatestSyncs([{ otp_config_id: 1 }, { otp_config_id: 2 }])

      expect(lastAutoSync.value.timestamp).toBe('2026-07-15T12:00:00')
      expect(lastAutoSync.value.success_count).toBe(10)
    })

    it('does nothing when configs have no otp_config_id and no fallbackDocId', async () => {
      const { lastAutoSync, lastManualSync, fetchAllLatestSyncs } = useSyncStatus()
      await fetchAllLatestSyncs([null, { grist_doc_id: 'abc' }])

      expect(globalThis.fetch).not.toHaveBeenCalled()
      expect(lastAutoSync.value).toBeNull()
      expect(lastManualSync.value).toBeNull()
    })

    it('falls back to docId when no configs have otp_config_id', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          auto: { status: 'success', success_count: 7, error_count: 0, timestamp: '2026-07-15T14:00:00' },
          manual: null
        })
      })

      const { lastAutoSync, fetchAllLatestSyncs } = useSyncStatus()
      await fetchAllLatestSyncs([null], 'doc-fallback')

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/sync-log/latest?grist_doc_id=doc-fallback')
      expect(lastAutoSync.value).toEqual({ status: 'success', success_count: 7, error_count: 0, timestamp: '2026-07-15T14:00:00' })
    })

    it('skips configs whose API call fails', async () => {
      globalThis.fetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ success: false })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            auto: { status: 'success', success_count: 4, error_count: 0, timestamp: '2026-07-15T10:00:00' },
            manual: null
          })
        })

      const { lastAutoSync, fetchAllLatestSyncs } = useSyncStatus()
      await fetchAllLatestSyncs([{ otp_config_id: 1 }, { otp_config_id: 2 }])

      expect(lastAutoSync.value).toEqual({ status: 'success', success_count: 4, error_count: 0, timestamp: '2026-07-15T10:00:00' })
    })
  })
})
