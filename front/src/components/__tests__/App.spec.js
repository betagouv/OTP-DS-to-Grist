import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import App from '../../App.vue'
import SyncSeriesTable from '../SyncSeriesTable.vue'
import OtpAlert from '../OtpAlert.vue'
import { useSyncHistory } from '../../composables/useSyncHistory'
import { isWidgetReadOnly } from '../../utils/gristContext'

vi.mock('../../composables/useSyncHistory')
vi.mock('../../utils/gristContext', () => ({ isWidgetReadOnly: vi.fn() }))

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

const mountApp = () => mount(App, {
  global: {
    stubs: {
      SyncProgress: SyncProgressStub,
      OTPForm: OTPFormStub
    }
  }
})

// Monte l'application une fois l'accès au document connu
const createWrapper = async () => {
  const wrapper = mountApp()
  await flushPromises()

  return wrapper
}

describe('App', () => {
  beforeEach(() => {
    mockFetchHistory.mockClear()
    isWidgetReadOnly.mockResolvedValue(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches the latest sync of each démarche when OTPForm emits config-loaded', async () => {
    const wrapper = await createWrapper()

    wrapper.findComponent(OTPFormStub).vm.$emit('config-loaded')
    await wrapper.vm.$nextTick()

    expect(mockFetchHistory).toHaveBeenCalledTimes(1)
  })

  it('passes the démarche titles received from OTPForm to the sync table', async () => {
    const wrapper = await createWrapper()

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
    const wrapper = await createWrapper()

    wrapper.findComponent(OTPFormStub).vm.$emit('config-loaded')
    await new Promise(process.nextTick)

    expect(wrapper.findComponent(SyncSeriesTable).props('history')).toEqual(rows)
  })

  describe('read-only document', () => {
    it('shows a single editor access alert instead of the application', async () => {
      isWidgetReadOnly.mockResolvedValue(true)
      const wrapper = await createWrapper()

      expect(wrapper.findComponent(OtpAlert).props('title')).toBe('Accès éditeur requis')
      expect(wrapper.findComponent(OTPFormStub).exists()).toBe(false)
      expect(wrapper.findComponent(SyncProgressStub).exists()).toBe(false)
      expect(wrapper.findComponent(SyncSeriesTable).exists()).toBe(false)
    })

    it('shows the application for an editor', async () => {
      const wrapper = await createWrapper()

      expect(wrapper.findComponent(OtpAlert).exists()).toBe(false)
      expect(wrapper.findComponent(OTPFormStub).exists()).toBe(true)
      expect(wrapper.findComponent(SyncProgressStub).exists()).toBe(true)
    })

    it('shows nothing while the document access is unknown', () => {
      isWidgetReadOnly.mockReturnValue(new Promise(() => {}))
      const wrapper = mountApp()

      expect(wrapper.findComponent(OTPFormStub).exists()).toBe(false)
      expect(wrapper.findComponent(OtpAlert).exists()).toBe(false)
    })
  })
})
