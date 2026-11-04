import { describe, it, expect, afterEach, vi } from 'vitest'
import { useSyncHistory } from '../useSyncHistory'

const mockSyncs = (syncs) => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, syncs })
  })
}

const sync = (overrides) => ({
  otp_config_id: 1,
  demarche_number: '111',
  timestamp: '2026-11-02T14:41:00',
  status: 'success',
  success_count: 14,
  error_count: 0,
  message: 'Synchronisation terminée',
  auto: true,
  ...overrides
})

describe('useSyncHistory', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns each latest sync as a table row', async () => {
    mockSyncs([sync()])

    const rows = await useSyncHistory().fetchHistory()

    expect(rows).toEqual([{
      key: 'history_1',
      demarcheNumber: '111',
      status: 'completed',
      message: 'Synchronisation terminée',
      result: { success_count: 14, error_count: 0 },
      syncReason: null,
      endTime: new Date(2026, 10, 2, 14, 41),
      auto: true
    }])
  })

  it('maps a failed sync to the error status', async () => {
    mockSyncs([sync({ status: 'error', message: 'Token DN périmé', success_count: 0 })])

    const [row] = await useSyncHistory().fetchHistory()

    expect(row.status).toBe('error')
    expect(row.message).toBe('Token DN périmé')
    expect(row.syncReason).toBe(null)
  })

  it('deduces an up to date Grist from a success without dossier', async () => {
    mockSyncs([sync({ success_count: 0, error_count: 0 })])

    const [row] = await useSyncHistory().fetchHistory()

    expect(row.syncReason).toBe('already_up_to_date')
  })

  it('returns no row when no démarche was synced', async () => {
    mockSyncs([])

    expect(await useSyncHistory().fetchHistory()).toEqual([])
  })
})
