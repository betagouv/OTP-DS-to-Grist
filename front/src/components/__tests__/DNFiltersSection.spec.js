import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import DNFiltersSection from '../DNFiltersSection.vue'

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
      filter_statuses: ''
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
      filter_statuses: ''
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
      filter_statuses: ''
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
      filter_statuses: ''
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
