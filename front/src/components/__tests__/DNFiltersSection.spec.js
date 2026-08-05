import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import DNFiltersSection from '../DNFiltersSection.vue'
import OtpAlert from '../OtpAlert.vue'
import { DsfrMultiselect } from '@gouvminint/vue-dsfr'

const mountSection = (existingConfig = null) =>
  mount(DNFiltersSection, {
    props: { existingConfig }
  })

const setDate = (wrapper, testId, value) =>
  wrapper.find(`[data-test-id="${testId}"]`).setValue(value)

const toggleStatus = (wrapper, value) =>
  wrapper.find(`input[type="checkbox"][value="${value}"]`).setValue(true)

const DATE_DEBUT = 'filter-date-start'
const DATE_FIN = 'filter-date-end'

describe('DNFiltersSection', () => {
  it('returns empty dates when no config is loaded', () => {
    const wrapper = mountSection()
    expect(wrapper.vm.getData()).toEqual({
      filter_date_start: '',
      filter_date_end: '',
      filter_statuses: '',
      filter_groups: ''
    })
  })

  it('pre-fills dates from existingConfig', () => {
    const wrapper = mountSection({
      filter_date_start: '2023-01-01',
      filter_date_end: '2023-12-31'
    })
    expect(wrapper.vm.getData()).toEqual({
      filter_date_start: '2023-01-01',
      filter_date_end: '2023-12-31',
      filter_statuses: '',
      filter_groups: ''
    })
  })

  it('clears dates when config becomes null', async () => {
    const wrapper = mountSection({
      filter_date_start: '2023-01-01',
      filter_date_end: '2023-12-31'
    })
    await wrapper.setProps({ existingConfig: null })
    expect(wrapper.vm.getData()).toEqual({
      filter_date_start: '',
      filter_date_end: '',
      filter_statuses: '',
      filter_groups: ''
    })
  })

  it('emits change and reflects edited dates', async () => {
    const wrapper = mountSection()
    await setDate(wrapper, DATE_DEBUT, '2023-05-01')
    await setDate(wrapper, DATE_FIN, '2023-05-15')

    expect(wrapper.emitted('change')).toHaveLength(2)
    expect(wrapper.vm.getData()).toEqual({
      filter_date_start: '2023-05-01',
      filter_date_end: '2023-05-15',
      filter_statuses: '',
      filter_groups: ''
    })
  })

  it('reports no error for a valid range', async () => {
    const wrapper = mountSection()
    await setDate(wrapper, DATE_DEBUT, '2023-01-01')
    await setDate(wrapper, DATE_FIN, '2023-01-31')

    expect(wrapper.emitted('error-update').at(-1)).toEqual([''])
  })

  it('reports an error when end date is before start date', async () => {
    const wrapper = mountSection()
    await setDate(wrapper, DATE_DEBUT, '2023-12-31')
    await setDate(wrapper, DATE_FIN, '2023-01-01')

    expect(wrapper.emitted('error-update').at(-1)[0]).not.toBe('')
  })

  it('reports an error on load when saved range is inconsistent', () => {
    const wrapper = mountSection({
      filter_date_start: '2023-12-31',
      filter_date_end: '2023-01-01'
    })
    expect(wrapper.emitted('error-update').at(-1)[0]).not.toBe('')
  })

  it('clears the error when the range becomes valid again', async () => {
    const wrapper = mountSection()
    await setDate(wrapper, DATE_DEBUT, '2023-12-31')
    await setDate(wrapper, DATE_FIN, '2023-01-01')
    expect(wrapper.emitted('error-update').at(-1)[0]).not.toBe('')

    await setDate(wrapper, DATE_FIN, '2024-01-01')
    expect(wrapper.emitted('error-update').at(-1)).toEqual([''])
  })

  it('returns empty statuses when no config is loaded', () => {
    const wrapper = mountSection()
    expect(wrapper.vm.getData().filter_statuses).toBe('')
  })

  it('pre-fills statuses from existingConfig', () => {
    const wrapper = mountSection({
      filter_statuses: 'en_construction,accepte'
    })
    expect(wrapper.vm.getData().filter_statuses).toBe('en_construction,accepte')
  })

  it('clears statuses when config becomes null', async () => {
    const wrapper = mountSection({
      filter_statuses: 'en_construction,refuse'
    })
    await wrapper.setProps({ existingConfig: null })
    expect(wrapper.vm.getData().filter_statuses).toBe('')
  })

  it('does not emit change when loading a config', () => {
    const wrapper = mountSection({
      filter_statuses: 'en_construction'
    })
    expect(wrapper.emitted('change')).toBeUndefined()
  })

  it('emits change and reflects checked statuses', async () => {
    const wrapper = mountSection()
    await toggleStatus(wrapper, 'en_construction')
    await toggleStatus(wrapper, 'accepte')

    expect(wrapper.emitted('change')).toHaveLength(2)
    expect(wrapper.vm.getData().filter_statuses).toBe('en_construction,accepte')
  })

  it('does not emit error-update when toggling statuses', async () => {
    const wrapper = mountSection()
    const errorCountBefore = wrapper.emitted('error-update').length

    await toggleStatus(wrapper, 'sans_suite')

    expect(wrapper.emitted('error-update').length).toBe(errorCountBefore)
  })
})

describe('DNFiltersSection — groupes instructeurs', () => {
  const mountWithConfig = (existingConfig) =>
    mount(DNFiltersSection, { props: { existingConfig } })

  const mockGroupsResponse = (groups) => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(groups)
    })
  }

  const hasGroupsSection = (wrapper) =>
    wrapper.findAll('legend').some((l) => l.text() === 'Filtrer par groupe instructeur')

  afterEach(() => {
    delete globalThis.fetch
  })

  it('masks the groups section when there is no saved config', () => {
    const wrapper = mountSection()
    expect(hasGroupsSection(wrapper)).toBe(false)
    expect(wrapper.vm.getData().filter_groups).toBe('')
  })

  it('shows the loading indicator while groups are loading', () => {
    globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
    const wrapper = mountWithConfig({ otp_config_id: 1 })

    expect(hasGroupsSection(wrapper)).toBe(true)
    expect(wrapper.find('p').text()).toBe('...')
  })

  it('shows an error alert when groups loading fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('network error'))
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    const alert = wrapper.findComponent(OtpAlert)
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('Erreur lors du chargement des groupes instructeurs')
  })

  it('masks the groups section when the groups list is empty', async () => {
    mockGroupsResponse([])
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    expect(hasGroupsSection(wrapper)).toBe(false)
  })

  it('renders the group options once loaded', async () => {
    mockGroupsResponse([[1, 'Groupe A'], [2, 'Groupe B']])
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    expect(wrapper.findComponent(DsfrMultiselect).props('options')).toEqual([
      { number: 1, label: 'Groupe A' },
      { number: 2, label: 'Groupe B' }
    ])
  })

  it('emits change and returns selected groups in getData', async () => {
    mockGroupsResponse([[1, 'Groupe A'], [2, 'Groupe B']])
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    await wrapper.findComponent(DsfrMultiselect).vm.$emit('update:modelValue', [1, 2])

    expect(wrapper.emitted('change')).toHaveLength(1)
    expect(wrapper.vm.getData().filter_groups).toBe('1,2')
  })

  it('pre-fills selected groups from existingConfig without emitting change', () => {
    mockGroupsResponse([])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1,3' })

    expect(wrapper.vm.getData().filter_groups).toBe('1,3')
    expect(wrapper.emitted('change')).toBeUndefined()
  })

  it('resets groups when config becomes null', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1' })
    await flushPromises()

    await wrapper.setProps({ existingConfig: null })

    expect(wrapper.vm.getData().filter_groups).toBe('')
    expect(hasGroupsSection(wrapper)).toBe(false)
  })
})
