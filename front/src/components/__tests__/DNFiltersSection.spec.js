import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import DNFiltersSection from '../DNFiltersSection.vue'
import OtpAlert from '../OtpAlert.vue'
import { DsfrMultiselect } from '@gouvminint/vue-dsfr'

beforeEach(() => {
  globalThis.formatDate = (dateString) => dateString.split('-').reverse().join('/')
})

afterEach(() => {
  delete globalThis.formatDate
})

const mountSection = (existingConfig = null) =>
  mount(DNFiltersSection, {
    props: { existingConfig }
  })

const setDate = (wrapper, testId, value) =>
  wrapper.find(`[data-test-id="${testId}"]`).setValue(value)

const toggleStatus = (wrapper, value) =>
  wrapper.find(`input[type="checkbox"][value="${value}"]`).setValue(true)

const mountWithConfig = (existingConfig) =>
  mount(DNFiltersSection, { props: { existingConfig } })

const mockGroupsResponse = (groups) => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(groups)
  })
}

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

  it('masks the groups section when the demarche has a single default group', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    expect(hasGroupsSection(wrapper)).toBe(false)
  })

  it('keeps a valid saved group filter when the section is hidden (single group)', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1' })
    await flushPromises()

    expect(hasGroupsSection(wrapper)).toBe(false)
    expect(wrapper.vm.getData().filter_groups).toBe('1')
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

  it('clears removed groups and warns when none of the saved groups are available', async () => {
    mockGroupsResponse([])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1,3' })
    await flushPromises()

    expect(wrapper.vm.getData().filter_groups).toBe('')
    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('warning')
    expect(wrapper.emitted('change')).toHaveLength(1)
    expect(hasGroupsSection(wrapper)).toBe(true)
  })

  it('keeps available groups, warns and emits change when some saved groups disappeared', async () => {
    mockGroupsResponse([[1, 'Groupe A'], [3, 'Groupe C']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1,2' })
    await flushPromises()

    expect(wrapper.vm.getData().filter_groups).toBe('1')
    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('warning')
    expect(wrapper.emitted('change')).toHaveLength(1)
    expect(hasGroupsSection(wrapper)).toBe(true)
  })

  it('clears the filter and warns when a single remaining group no longer matches the saved filter', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '2' })
    await flushPromises()

    expect(wrapper.vm.getData().filter_groups).toBe('')
    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('warning')
    expect(wrapper.emitted('change')).toHaveLength(1)
    expect(hasGroupsSection(wrapper)).toBe(true)
  })

  it('keeps the saved groups without warning when they all still exist', async () => {
    mockGroupsResponse([[1, 'Groupe A'], [2, 'Groupe B']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1,2' })
    await flushPromises()

    expect(wrapper.vm.getData().filter_groups).toBe('1,2')
    expect(wrapper.findComponent(OtpAlert).exists()).toBe(false)
    expect(wrapper.emitted('change')).toBeUndefined()
  })

  it('does not warn when there is no saved group filter', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    expect(wrapper.findComponent(OtpAlert).exists()).toBe(false)
    expect(hasGroupsSection(wrapper)).toBe(false)
  })

  it('keeps the saved groups and shows no warning when the groups load fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('network error'))
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1' })
    await flushPromises()

    expect(wrapper.vm.getData().filter_groups).toBe('1')
    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('error')
    expect(wrapper.findComponent(OtpAlert).text()).toContain('Erreur lors du chargement des groupes instructeurs')
  })

  it('resets groups when config becomes null', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1' })
    await flushPromises()

    await wrapper.setProps({ existingConfig: null })

    expect(wrapper.vm.getData().filter_groups).toBe('')
    expect(hasGroupsSection(wrapper)).toBe(false)
  })

  it('shows a groups tag when groups are selected and the section is visible', async () => {
    mockGroupsResponse([[1, 'Groupe A'], [2, 'Groupe B']])
    const wrapper = mountWithConfig({ otp_config_id: 1 })
    await flushPromises()

    await wrapper.findComponent(DsfrMultiselect).vm.$emit('update:modelValue', [1])

    expect(wrapper.text()).toContain('Groupes: Groupe A')
  })

  it('shows no groups tag when the section is hidden (single group)', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '1' })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Groupes:')
  })
})

describe('DNFiltersSection — Filtres actifs', () => {
  it('shows no active filters block when nothing is selected', () => {
    const wrapper = mountSection()
    expect(wrapper.find('h5').exists()).toBe(false)
  })

  it('shows date tags from existingConfig', () => {
    const wrapper = mountSection({
      filter_date_start: '2023-01-01',
      filter_date_end: '2023-12-31'
    })
    expect(wrapper.text()).toContain('Date de début: 01/01/2023')
    expect(wrapper.text()).toContain('Date de fin: 31/12/2023')
  })

  it('shows a status tag with labels', () => {
    const wrapper = mountSection({
      filter_statuses: 'en_construction,accepte'
    })
    expect(wrapper.text()).toContain('Statuts: En construction, Accepté')
  })

  it('hides a date tag when the date is cleared', async () => {
    const wrapper = mountSection({
      filter_date_start: '2023-01-01'
    })
    expect(wrapper.text()).toContain('Date de début: 01/01/2023')

    await setDate(wrapper, DATE_DEBUT, '')

    expect(wrapper.text()).not.toContain('Date de début:')
  })

  it('renders tags as non-interactive spans', () => {
    const wrapper = mountSection({
      filter_date_start: '2023-01-01'
    })
    const tag = wrapper.find('.fr-tag')
    expect(tag.element.tagName).toBe('SPAN')
  })
})

describe('DNFiltersSection — Réinitialiser', () => {
  const resetButton = (wrapper) =>
    wrapper.find('[data-test-id="reset-filters-button"]')

  afterEach(() => {
    delete globalThis.fetch
  })

  it('is present and disabled when no filter is active', () => {
    const wrapper = mountSection()
    expect(resetButton(wrapper).exists()).toBe(true)
    expect(resetButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('is enabled when a filter is active', async () => {
    const wrapper = mountSection()
    await setDate(wrapper, DATE_DEBUT, '2023-01-01')
    expect(resetButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('clears all filters, emits change and hides the active filters block', async () => {
    const wrapper = mountSection({
      filter_date_start: '2023-01-01',
      filter_statuses: 'en_construction'
    })
    expect(resetButton(wrapper).attributes('disabled')).toBeUndefined()

    await resetButton(wrapper).trigger('click')

    expect(wrapper.vm.getData()).toEqual({
      filter_date_start: '',
      filter_date_end: '',
      filter_statuses: '',
      filter_groups: ''
    })
    expect(wrapper.emitted('change')).toHaveLength(1)
    expect(wrapper.find('h5').exists()).toBe(false)
    expect(resetButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('keeps the groups warning after a reset', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({
      otp_config_id: 1,
      filter_groups: '2',
      filter_date_start: '2023-01-01'
    })
    await flushPromises()
    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('warning')
    expect(resetButton(wrapper).attributes('disabled')).toBeUndefined()

    await resetButton(wrapper).trigger('click')

    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('warning')
    expect(wrapper.vm.getData().filter_date_start).toBe('')
  })

  it('clears the groups warning when the reset is saved (reload with empty filter)', async () => {
    mockGroupsResponse([[1, 'Groupe A']])
    const wrapper = mountWithConfig({ otp_config_id: 1, filter_groups: '2' })
    await flushPromises()
    expect(wrapper.findComponent(OtpAlert).props('type')).toBe('warning')

    await wrapper.setProps({ existingConfig: { otp_config_id: 1, filter_groups: '' } })
    await flushPromises()

    expect(wrapper.findComponent(OtpAlert).exists()).toBe(false)
    expect(wrapper.vm.getData().filter_groups).toBe('')
  })
})
