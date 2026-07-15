import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

import App from '../../App.vue'
import SyncResultBanner from '../SyncResultBanner.vue'
import { useSyncStatus } from '../../composables/useSyncStatus'

vi.mock('../../composables/useSyncStatus')

const mockLastAutoSync = ref(null)
const mockLastManualSync = ref(null)
const mockFetchAllLatestSyncs = vi.fn().mockResolvedValue(undefined)

useSyncStatus.mockReturnValue({
  lastAutoSync: mockLastAutoSync,
  lastManualSync: mockLastManualSync,
  fetchAllLatestSyncs: mockFetchAllLatestSyncs
})

const SyncProgressStub = {
  template: '<div data-testid="sync-progress" />',
  emits: ['sync-running-changed', 'sync-started', 'sync-finished']
}

const OTPFormStub = {
  template: '<div data-testid="otp-form" />',
  emits: ['config-loaded']
}

function createWrapper() {
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
    mockLastAutoSync.value = null
    mockLastManualSync.value = null
    mockFetchAllLatestSyncs.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls fetchAllLatestSyncs when OTPForm emits config-loaded', async () => {
    const wrapper = createWrapper()
    const configs = [{ otp_config_id: 1 }, { otp_config_id: 2 }]

    wrapper.findComponent(OTPFormStub).vm.$emit('config-loaded', configs)
    await wrapper.vm.$nextTick()

    expect(mockFetchAllLatestSyncs).toHaveBeenCalledWith(configs)
  })

  it('clears live result when SyncProgress emits sync-started', async () => {
    const wrapper = createWrapper()
    const syncProgress = wrapper.findComponent(SyncProgressStub)

    syncProgress.vm.$emit('sync-finished', {
      status: 'completed', success_count: 5, error_count: 0, timestamp: '2026-07-15T10:00:00'
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.findAllComponents(SyncResultBanner).length).toBe(1)

    syncProgress.vm.$emit('sync-started')
    await wrapper.vm.$nextTick()

    expect(wrapper.findAllComponents(SyncResultBanner).length).toBe(0)
  })

  it('sets live result when SyncProgress emits sync-finished', async () => {
    const wrapper = createWrapper()

    wrapper.findComponent(SyncProgressStub).vm.$emit('sync-finished', {
      status: 'completed', success_count: 5, error_count: 1, timestamp: '2026-07-15T10:00:00'
    })
    await wrapper.vm.$nextTick()

    const banner = wrapper.findComponent(SyncResultBanner)
    expect(banner.exists()).toBe(true)
    expect(banner.props('status')).toBe('success')
    expect(banner.props('successCount')).toBe(5)
    expect(banner.props('errorCount')).toBe(1)
    expect(banner.props('syncType')).toBe('manual')
  })

  it('maps completed status to success for the banner', async () => {
    const wrapper = createWrapper()

    wrapper.findComponent(SyncProgressStub).vm.$emit('sync-finished', {
      status: 'completed', success_count: 10, error_count: 0, timestamp: '2026-07-15T11:00:00'
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(SyncResultBanner).props('status')).toBe('success')
  })

  it('maps error status to error for the banner', async () => {
    const wrapper = createWrapper()

    wrapper.findComponent(SyncProgressStub).vm.$emit('sync-finished', {
      status: 'error', success_count: 2, error_count: 3, timestamp: '2026-07-15T11:00:00'
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(SyncResultBanner).props('status')).toBe('error')
  })

  it('shows auto sync banner from page load when lastAutoSync exists', async () => {
    mockLastAutoSync.value = {
      status: 'success', success_count: 3, error_count: 0, timestamp: '2026-07-15T08:00:00'
    }
    const wrapper = createWrapper()

    const banner = wrapper.findComponent(SyncResultBanner)
    expect(banner.exists()).toBe(true)
    expect(banner.props('syncType')).toBe('auto')
    expect(banner.props('successCount')).toBe(3)
  })

  it('live result takes priority over auto/manual banners', async () => {
    mockLastAutoSync.value = {
      status: 'success', success_count: 3, error_count: 0, timestamp: '2026-07-15T08:00:00'
    }
    mockLastManualSync.value = {
      status: 'error', success_count: 1, error_count: 2, timestamp: '2026-07-15T09:00:00'
    }
    const wrapper = createWrapper()

    expect(wrapper.findAllComponents(SyncResultBanner).length).toBe(2)

    wrapper.findComponent(SyncProgressStub).vm.$emit('sync-finished', {
      status: 'completed', success_count: 10, error_count: 0, timestamp: '2026-07-15T11:00:00'
    })
    await wrapper.vm.$nextTick()

    const banners = wrapper.findAllComponents(SyncResultBanner)
    expect(banners.length).toBe(1)
    expect(banners[0].props('successCount')).toBe(10)
    expect(banners[0].props('syncType')).toBe('manual')
  })
})
