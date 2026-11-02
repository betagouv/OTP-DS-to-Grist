import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import App from '../../App.vue'
import SyncSeriesTable from '../SyncSeriesTable.vue'
import { useSyncHistory } from '../../composables/useSyncHistory'

vi.mock('../../composables/useSyncHistory')

const mockFetchHistory = vi.fn().mockResolvedValue([])
useSyncHistory.mockReturnValue({ fetchHistory: mockFetchHistory })

const SyncProgressStub = {
  template: '<div data-testid="sync-progress" />',
  emits: ['sync-running-changed']
}

const OTPFormStub = {
  template: '<div data-testid="otp-form" />',
  emits: ['config-loaded', 'title-loaded']
}

const createWrapper = () => {
  return mount(App, {
    global: {
      stubs: {
        SyncProgress: SyncProgressStub,
        OTPForm: OTPFormStub
      }
    }
  })
}

describe('App', () => {
  beforeEach(() => {
    mockFetchHistory.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches the latest sync of each démarche when OTPForm emits config-loaded', async () => {
    const wrapper = createWrapper()

    wrapper.findComponent(OTPFormStub).vm.$emit('config-loaded')
    await wrapper.vm.$nextTick()

    expect(mockFetchHistory).toHaveBeenCalledTimes(1)
  })

  it('passes the démarche titles received from OTPForm to the sync table', async () => {
    const wrapper = createWrapper()

    wrapper.findComponent(OTPFormStub).vm.$emit('title-loaded', '111', 'Ma démarche')
    wrapper.findComponent(OTPFormStub).vm.$emit('title-loaded', '222', 'Autre démarche')
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(SyncSeriesTable).props('titles')).toEqual({
      111: 'Ma démarche',
      222: 'Autre démarche'
    })
  })

  it('passes the loaded history to the sync table', async () => {
    const rows = [{ key: 'history_1', demarcheNumber: '111' }]
    mockFetchHistory.mockResolvedValueOnce(rows)
    const wrapper = createWrapper()

    wrapper.findComponent(OTPFormStub).vm.$emit('config-loaded')
    await new Promise(process.nextTick)

    expect(wrapper.findComponent(SyncSeriesTable).props('history')).toEqual(rows)
  })

})
