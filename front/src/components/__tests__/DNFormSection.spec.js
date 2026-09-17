import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

import { DsfrInput, DsfrInputGroup, DsfrMultiselect } from '@gouvminint/vue-dsfr'
import DNFormSection from '../DNFormSection.vue'

// Microtask pour que le v-model ait le temps de setter les refs avant validation
vi.mock(
  '../../utils/debounce',
  () => ({ debounce: (fn) => (...args) => Promise.resolve().then(() => fn(...args)) })
)

beforeEach(() => {
  globalThis.formatDate = (dateString) => dateString.split('-').reverse().join('/')
  window.HELP_LINKS = {
    token_api: 'https://fake-url.example.com/token-api',
    grist_api_key: 'https://fake-url.example.com/grist-api-key',
    faq: 'https://fake-url.example.com/faq'
  }
})

afterEach(() => {
  delete globalThis.formatDate
})


const globalComponents = { components: { DsfrInput, DsfrInputGroup } }
const DEMARCHE_NUMBER = '67890'

describe('DN form section', () => {
  it('shows error message when form validation fails', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Token invalide' })
    })

    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('mauvais-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('mauvais-numéro')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        demarche_number: 'mauvais-numéro',
        api_token: 'mauvais-token',
      })
    })

    const errorText = wrapper.find('.fr-error-text')

    expect(errorText.exists()).toBe(true)
    expect(errorText.text()).toBe('Token invalide')
  })

  it('shows no error when form is valid', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })

    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('bon-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('bon-numéro')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        demarche_number: 'bon-numéro',
        api_token: 'bon-token',
      })
    })
    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
  })

  it('pre-fills demarche_number from existingConfig when config is loaded', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })

    expect(wrapper.vm.inputDNNumber).toBe('')

    await wrapper.setProps({ existingConfig: { demarche_number: DEMARCHE_NUMBER } })

    expect(wrapper.vm.inputDNNumber).toBe(DEMARCHE_NUMBER)
    expect(wrapper.vm.getData().demarche_number).toBe(DEMARCHE_NUMBER)
  })

  it('shows placeholder **** when has_ds_token is true', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })

    await wrapper.setProps({ existingConfig: { has_ds_token: true } })

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.attributes('placeholder')).toMatch(/\*{3,}/)
  })

  it('keeps default placeholder when has_ds_token is false', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })

    await wrapper.setProps({ existingConfig: { demarche_number: DEMARCHE_NUMBER, has_ds_token: false } })

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.attributes('placeholder')).toBe('Saisissez votre clé Démarche Numérique')
  })

  it('does not call API when only token is filled', async () => {
    const mockFetch = vi.fn()
    globalThis.fetch = mockFetch
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('un-token')

    expect(mockFetch).not.toHaveBeenCalled()
    expect(wrapper.emitted('error-update')).toBeTruthy()
    expect(wrapper.emitted('error-update')[0]).toEqual([null])
  })

  it('does not call API when only number is filled', async () => {
    const mockFetch = vi.fn()
    globalThis.fetch = mockFetch
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')

    expect(mockFetch).not.toHaveBeenCalled()
    expect(wrapper.emitted('error-update')[0]).toEqual([null])
  })

  it('sends otp_config_id when token empty and config has otp_config_id', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: { index: 0, existingConfig: { otp_config_id: 42, has_ds_token: true } },
      global: globalComponents
    })

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        demarche_number: '12345',
        otp_config_id: 42
      })
    })
  })

  it('uses explicit token over otp_config_id', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: { index: 0, existingConfig: { otp_config_id: 42, has_ds_token: true } },
      global: globalComponents
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('explicit-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')
    await flushPromises()

    const testConnectionCall = mockFetch.mock.calls.find(
      ([url]) => String(url).includes('/api/test-connection')
    )
    const callBody = JSON.parse(testConnectionCall[1].body)
    expect(callBody.api_token).toBe('explicit-token')
    expect(callBody.otp_config_id).toBeUndefined()
  })

  it('clears error when a field is emptied after failed test', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Erreur de connexion' })
    })
    globalThis.fetch = mockFetch
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('mauvais-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')
    await flushPromises()

    expect(wrapper.find('.fr-error-text').exists()).toBe(true)

    await tokenInput.setValue('')

    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
    expect(mockFetch).toHaveBeenCalledTimes(1) // seulement la première fois
  })

  it('validates DS connection automatically on load with existing config', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, title: 'Ma démarche' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: DEMARCHE_NUMBER, has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'demarches',
        demarche_number: DEMARCHE_NUMBER,
        otp_config_id: 42
      })
    })

    expect(wrapper.vm.dnErrorMessage).toBe('')
    expect(wrapper.vm.accordionTitleDN).toBe(`N°${DEMARCHE_NUMBER} — Ma démarche`)
    expect(wrapper.find('.fr-error-text').exists()).toBe(false)
  })

  it('shows error on load when DS connection fails automatically', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Token invalide' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: DEMARCHE_NUMBER, has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()

    expect(wrapper.vm.dnErrorMessage).toBe('Token invalide')
    expect(wrapper.vm.accordionTitleDN).toBe('Échec')
    expect(wrapper.find('.fr-error-text').text()).toBe('Token invalide')
  })

  it('sets dnErrorMessage when test-connection fetch fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('network error'))
    const wrapper = mount(DNFormSection, {
      props: { index: 0},
      global: { components: { DsfrInput, DsfrInputGroup } }
    })

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('some-token')

    const numberInput = wrapper.find('[data-test-id="dn-number"]')
    await numberInput.setValue('12345')
    await flushPromises()

    expect(wrapper.vm.dnErrorMessage).toBe('Erreur lors du test de connexion')
    expect(wrapper.emitted('error-update')).toBeTruthy()
    const lastEmit = wrapper.emitted('error-update').at(-1)
    expect(lastEmit).toEqual(['Erreur lors du test de connexion'])
  })

  it('emits clear-error when OtpAlert close is triggered', async () => {
    const wrapper = mount(DNFormSection, {
      global: { components: { DsfrInput, DsfrInputGroup } },
      props: { error: 'Une erreur', index: 0 }
    })

    const alert = wrapper.find('.fr-alert')
    expect(alert.exists()).toBe(true)

    await alert.find('button').trigger('click')

    expect(wrapper.emitted('clear-error')).toHaveLength(1)
  })
})

describe('index prop', () => {
  it('accepts index prop', () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 3 },
      global: globalComponents
    })
    expect(wrapper.props('index')).toBe(3)
  })
})


describe('Auto-save', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn((url, opts) => {
      if (String(url).includes('/api/schedule'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, enabled: false }) })
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
  })

  afterEach(() => {
    delete globalThis.fetch
  })

  it('auto-saves after editing DN inputs (debounced)', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 2, gristError: '' },
      global: globalComponents
    })

    await wrapper.find('[data-test-id="dn-token"]').setValue('token')
    await wrapper.find('[data-test-id="dn-number"]').setValue('12345')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')[0]).toEqual([2])
  })

  it('does not auto-save while the Grist connection is invalid', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0, gristError: 'Clé API Grist invalide' },
      global: globalComponents
    })

    await wrapper.find('[data-test-id="dn-token"]').setValue('token')
    await wrapper.find('[data-test-id="dn-number"]').setValue('12345')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeFalsy()
  })

  it('does not auto-save while the DN connection test fails, then auto-saves once it succeeds', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ success: false, message: 'Token invalide' }) })
    )

    const wrapper = mount(DNFormSection, {
      props: { index: 0, gristError: '' },
      global: globalComponents
    })

    await wrapper.find('[data-test-id="dn-token"]').setValue('mauvais-token')
    await wrapper.find('[data-test-id="dn-number"]').setValue('12345')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeFalsy()

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    )

    await wrapper.find('[data-test-id="dn-token"]').setValue('bon-token')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('does not auto-save an empty section once all inputs are cleared', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0, gristError: '' },
      global: globalComponents
    })

    await wrapper.find('[data-test-id="dn-token"]').setValue('token')
    await wrapper.find('[data-test-id="dn-number"]').setValue('12345')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
    const savesAfterFill = wrapper.emitted('save').length

    await wrapper.find('[data-test-id="dn-number"]').setValue('')
    await wrapper.find('[data-test-id="dn-token"]').setValue('')
    await flushPromises()

    expect(wrapper.emitted('save').length).toBe(savesAfterFill)
  })

  it('auto-saves after a filter change', async () => {
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        gristError: '',
        existingConfig: { otp_config_id: 1, demarche_number: DEMARCHE_NUMBER, has_ds_token: true }
      },
      global: globalComponents
    })
    await flushPromises()

    await wrapper.find('[data-test-id="filter-date-start"]').setValue('2023-01-01')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('auto-saves after toggling auto-sync', async () => {
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        gristError: '',
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    await wrapper.find('[data-test-id="auto-sync-toggle"]').setChecked(true)
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('does not overwrite local edits when existingConfig changes during an in-flight save (reload)', async () => {
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        gristError: '',
        existingConfig: { otp_config_id: 42, has_ds_token: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('edit-local')
    await flushPromises()
    expect(wrapper.vm.isDirty).toBe(true)

    await wrapper.setProps({
      existingConfig: { otp_config_id: 42, has_ds_token: true, demarche_number: DEMARCHE_NUMBER }
    })
    await flushPromises()

    expect(wrapper.vm.isDirty).toBe(true)
    expect(wrapper.vm.getData().token).toBe('edit-local')
  })
})

describe('Delete button', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(DNFormSection, {
      props: { index: 0, existingConfig: { otp_config_id: 1 } },
      global: globalComponents
    })
  })

  it('is disabled when canDelete is false', async () => {
    await wrapper.setProps({ canDelete: false })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')

    expect(deleteButton.attributes('disabled')).toBeDefined()
  })

  it('is enabled when canDelete is true', async () => {
    await wrapper.setProps({ canDelete: true })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')

    expect(deleteButton.attributes('disabled')).toBeUndefined()
  })

  it('emits delete event with index when clicked and enabled', async () => {
    await wrapper.setProps({ canDelete: true })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')
    await deleteButton.trigger('click')

    expect(wrapper.emitted('delete')).toBeTruthy()
    expect(wrapper.emitted('delete')[0]).toEqual([0])
  })

  it('does not emit delete event when clicked and disabled', async () => {
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')
    await deleteButton.trigger('click')

    expect(wrapper.emitted('delete')).toBeFalsy()
  })
})

describe('Sync button', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(DNFormSection, {
      props: { index: 0, existingConfig: { otp_config_id: 1 } },
      global: globalComponents
    })
  })

  it('is disabled when canSync is false', async () => {
    await wrapper.setProps({ canSync: false })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')

    expect(syncButton.attributes('disabled')).toBeDefined()
  })

  it('is enabled when canSync is true', async () => {
    await wrapper.setProps({ canSync: true })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')

    expect(syncButton.attributes('disabled')).toBeUndefined()
  })

  it('emits sync event with index when clicked and enabled', async () => {
    await wrapper.setProps({ canSync: true })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')
    await syncButton.trigger('click')

    expect(wrapper.emitted('sync')).toBeTruthy()
    expect(wrapper.emitted('sync')[0]).toEqual([0])
  })

  it('does not emit sync event when clicked and disabled', async () => {
    const syncButton = wrapper.find('[data-test-id="sync-button"]')
    await syncButton.trigger('click')

    expect(wrapper.emitted('sync')).toBeFalsy()
  })
})

describe('sectionEmpty computed', () => {
  it('is true when existingConfig is null and inputs are empty', () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    expect(wrapper.vm.sectionEmpty).toBe(true)
  })

  it('is true when existingConfig has otp_config_id null and inputs are empty', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    await wrapper.setProps({ existingConfig: { otp_config_id: null } })
    expect(wrapper.vm.sectionEmpty).toBe(true)
  })

  it('is false when no existingConfig but a token is filled', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    const tokenInput = wrapper.find('[data-test-id="dn-token"]')
    await tokenInput.setValue('some-token')
    expect(wrapper.vm.sectionEmpty).toBe(false)
  })

  it('is false when existingConfig has a valid otp_config_id', () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0, existingConfig: { otp_config_id: 42 } },
      global: globalComponents
    })
    expect(wrapper.vm.sectionEmpty).toBe(false)
  })

  it('disables Sync button when sectionEmpty is true', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0, canSync: true },
      global: globalComponents
    })
    const syncButton = wrapper.find('[data-test-id="sync-button"]')
    expect(syncButton.attributes('disabled')).toBeDefined()
  })

  it('disables Delete button when sectionEmpty is true', async () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0, canDelete: true },
      global: globalComponents
    })
    const deleteButton = wrapper.find('[data-test-id="delete-config-button"]')
    expect(deleteButton.attributes('disabled')).toBeDefined()
  })
})

describe('Accordion title', () => {
  it('shows default title for empty section', () => {
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    expect(wrapper.vm.accordionTitleDN).toBe('Configurer votre démarche')
  })

  it('shows demarche title after successful validation on load', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, title: 'Draaf-Srfd Occitanie Prévisions' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: DEMARCHE_NUMBER, has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()

    expect(wrapper.vm.accordionTitleDN).toBe(`N°${DEMARCHE_NUMBER} — Draaf-Srfd Occitanie Prévisions`)
  })

  it('shows "Échec" after failed validation on load', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: 'Token invalide' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: DEMARCHE_NUMBER, has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()

    expect(wrapper.vm.accordionTitleDN).toBe('Échec')
  })

  it('formats the title as N°{number} — {title}', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, title: 'Mon Titre' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: '12345', has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()

    expect(wrapper.vm.accordionTitleDN).toBe('N°12345 — Mon Titre')
  })

  it('renders the title as a tooltip', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, title: 'Mon Titre' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: '12345', has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()

    const titleSpan = wrapper.find('.otp-accordion-title')
    expect(titleSpan.attributes('title')).toBe('N°12345 — Mon Titre')
    expect(titleSpan.text()).toBe('N°12345 — Mon Titre')
  })

  it('resets title to default when config is cleared', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, title: 'Ma démarche' })
    })
    globalThis.fetch = mockFetch

    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, demarche_number: DEMARCHE_NUMBER, has_ds_token: true }
      },
      global: globalComponents
    })

    await flushPromises()
    expect(wrapper.vm.accordionTitleDN).toBe(`N°${DEMARCHE_NUMBER} — Ma démarche`)

    await wrapper.setProps({ existingConfig: null })
    expect(wrapper.vm.accordionTitleDN).toBe('Configurer votre démarche')
  })
})

describe('Filters section integration', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
  })

  afterEach(() => {
    delete globalThis.fetch
  })

  const mountWithValidConfig = (existingConfig = {}) =>
    mount(DNFormSection, {
      props: {
        index: 0,
        gristError: '',
        existingConfig: {
          otp_config_id: 1,
          demarche_number: DEMARCHE_NUMBER,
          has_ds_token: true,
          ...existingConfig
        }
      },
      global: globalComponents
    })

  it('includes pre-filled filter dates in getData', () => {
    const wrapper = mountWithValidConfig({
      filter_date_start: '2023-01-01',
      filter_date_end: '2023-12-31'
    })

    expect(wrapper.vm.getData().filter_date_start).toBe('2023-01-01')
    expect(wrapper.vm.getData().filter_date_end).toBe('2023-12-31')
  })

  it('returns empty filter dates in getData when config has none', () => {
    const wrapper = mountWithValidConfig()

    expect(wrapper.vm.getData().filter_date_start).toBe('')
    expect(wrapper.vm.getData().filter_date_end).toBe('')
  })

  it('auto-saves when a filter date is edited', async () => {
    const wrapper = mountWithValidConfig()
    await flushPromises()

    await wrapper.find('[data-test-id="filter-date-start"]').setValue('2023-01-01')
    await flushPromises()

    expect(wrapper.vm.isDirty).toBe(true)
    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('does not auto-save while the filter dates are inconsistent', async () => {
    const wrapper = mountWithValidConfig()
    await flushPromises()

    await wrapper.find('[data-test-id="filter-date-start"]').setValue('2023-12-31')
    await flushPromises()
    await wrapper.find('[data-test-id="filter-date-end"]').setValue('2023-01-01')
    await flushPromises()

    expect(wrapper.vm.dnFiltersError).not.toBe('')
    const savesWhileInvalid = wrapper.emitted('save')?.length ?? 0

    await wrapper.find('input[type="checkbox"][value="en_construction"]').setValue(true)
    await flushPromises()

    expect(wrapper.emitted('save')?.length ?? 0).toBe(savesWhileInvalid)
  })

  it('clears the filter error and auto-saves again once the dates are consistent', async () => {
    const wrapper = mountWithValidConfig()
    await flushPromises()

    await wrapper.find('[data-test-id="filter-date-start"]').setValue('2023-12-31')
    await wrapper.find('[data-test-id="filter-date-end"]').setValue('2023-01-01')
    await flushPromises()
    expect(wrapper.vm.dnFiltersError).not.toBe('')

    await wrapper.find('[data-test-id="filter-date-end"]').setValue('2024-01-01')
    await flushPromises()

    expect(wrapper.vm.dnFiltersError).toBe('')
    const savesAfterFix = wrapper.emitted('save')?.length ?? 0

    await wrapper.find('[data-test-id="filter-date-start"]').setValue('2023-10-10')
    await flushPromises()

    expect(wrapper.emitted('save')?.length ?? 0).toBeGreaterThan(savesAfterFix)
  })

  it('includes pre-filled filter statuses in getData', () => {
    const wrapper = mountWithValidConfig({
      filter_statuses: 'en_construction,accepte'
    })

    expect(wrapper.vm.getData().filter_statuses).toBe('en_construction,accepte')
  })

  it('returns empty filter statuses in getData when config has none', () => {
    const wrapper = mountWithValidConfig()

    expect(wrapper.vm.getData().filter_statuses).toBe('')
  })

  it('auto-saves when a status is toggled', async () => {
    const wrapper = mountWithValidConfig()
    await flushPromises()

    await wrapper
      .find('input[type="checkbox"][value="en_construction"]')
      .setValue(true)
    await flushPromises()

    expect(wrapper.vm.isDirty).toBe(true)
    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('includes pre-filled filter groups in getData', async () => {
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([[1, 'Groupe A'], [3, 'Groupe C']]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
    const wrapper = mountWithValidConfig({
      filter_groups: '1,3'
    })
    await flushPromises()

    expect(wrapper.vm.getData().filter_groups).toBe('1,3')
  })

  it('returns empty filter groups in getData when config has none', () => {
    const wrapper = mountWithValidConfig()

    expect(wrapper.vm.getData().filter_groups).toBe('')
  })

  it('auto-saves when a group is selected', async () => {
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([[1, 'Groupe A'], [2, 'Groupe B']]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
    const wrapper = mountWithValidConfig()
    await flushPromises()

    await wrapper.findComponent(DsfrMultiselect).vm.$emit('update:modelValue', [1])
    await flushPromises()

    expect(wrapper.vm.isDirty).toBe(true)
    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('keeps the section dirty and auto-saves after resetting the filters', async () => {
    const wrapper = mountWithValidConfig()
    await flushPromises()

    await wrapper.find('[data-test-id="filter-date-start"]').setValue('2023-01-01')
    await flushPromises()

    await wrapper.find('[data-test-id="reset-filters-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.vm.getData().filter_date_start).toBe('')
    expect(wrapper.vm.isDirty).toBe(true)
    expect(wrapper.emitted('save')).toBeTruthy()
  })
})

describe('Auto-sync toggle', () => {
  const mockFetchForSchedule = (scheduleResponse = { success: true, enabled: false }) => {
    globalThis.fetch = vi.fn((url, opts) => {
      if (String(url).includes('/api/schedule'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(scheduleResponse) })
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
  }

  afterEach(() => {
    delete globalThis.fetch
  })

  it('is enabled without existingConfig', async () => {
    mockFetchForSchedule()
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    await flushPromises()

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')
    expect(checkbox.attributes('disabled')).toBeUndefined()
  })

  it('is enabled when existingConfig has no has_grist_key', async () => {
    mockFetchForSchedule()
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: false, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')
    expect(checkbox.attributes('disabled')).toBeUndefined()
  })

  it('loads schedule state when existingConfig is provided', async () => {
    mockFetchForSchedule({ success: true, enabled: true })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const scheduleCall = globalThis.fetch.mock.calls.find(
      ([url]) => String(url).includes('/api/schedule')
    )
    expect(scheduleCall).toBeTruthy()
    expect(scheduleCall[0]).toBe('/api/schedule?otp_config_id=42')

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')
    expect(checkbox.element.checked).toBe(true)
  })

  it('only updates local state when checked (no API call)', async () => {
    mockFetchForSchedule({ success: true, enabled: false })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')
    await checkbox.setChecked(true)

    const scheduleCalls = globalThis.fetch.mock.calls.filter(
      ([url, opts]) => String(url).includes('/api/schedule')
    )
    expect(scheduleCalls).toHaveLength(1) // uniquement le GET de chargement
    expect(scheduleCalls[0][1]).toBeUndefined()
    expect(wrapper.vm.getData().auto_sync_enabled).toBe(true)
  })

  it('only updates local state when unchecked (no API call)', async () => {
    mockFetchForSchedule({ success: true, enabled: true })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')
    expect(checkbox.element.checked).toBe(true)
    await checkbox.setChecked(false)

    const scheduleCalls = globalThis.fetch.mock.calls.filter(
      ([url, opts]) => String(url).includes('/api/schedule')
    )
    expect(scheduleCalls).toHaveLength(1)
    expect(wrapper.vm.getData().auto_sync_enabled).toBe(false)
  })

  it('keeps server state (scheduleEnabled) unchanged after toggling locally', async () => {
    mockFetchForSchedule({ success: true, enabled: false })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    expect(wrapper.vm.scheduleEnabled).toBe(false)

    await wrapper.find('[data-test-id="auto-sync-toggle"]').setChecked(true)

    expect(wrapper.vm.scheduleEnabled).toBe(false)
    expect(wrapper.vm.getData().auto_sync_enabled).toBe(true)
  })

  it('exposes auto_sync_enabled in getData (default false)', async () => {
    mockFetchForSchedule({ success: true, enabled: false })
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    await flushPromises()

    expect(wrapper.vm.getData().auto_sync_enabled).toBe(false)
  })

  it('sets isDirty when toggling auto-sync', async () => {
    mockFetchForSchedule({ success: true, enabled: false })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        gristError: '',
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')

    expect(wrapper.vm.isDirty).toBe(false)

    await checkbox.setChecked(true)
    await flushPromises()

    expect(wrapper.vm.isDirty).toBe(true)
  })
})

describe('Auto-sync badge in accordion title', () => {
  const mockFetchForSchedule = (scheduleResponse = { success: true, enabled: false }) => {
    globalThis.fetch = vi.fn((url, opts) => {
      if (String(url).includes('/api/schedule'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(scheduleResponse) })
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
  }

  afterEach(() => {
    delete globalThis.fetch
  })

  it('is absent when no saved config', async () => {
    mockFetchForSchedule()
    const wrapper = mount(DNFormSection, {
      props: { index: 0 },
      global: globalComponents
    })
    await flushPromises()

    const badge = wrapper.find('.fr-badge')
    expect(badge.exists()).toBe(false)
  })

  it('shows "Manuelle" when config is saved with schedule disabled', async () => {
    mockFetchForSchedule({ success: true, enabled: false })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const badge = wrapper.find('.fr-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('Manuelle')
  })

  it('shows "Automatique" when config is saved with schedule enabled', async () => {
    mockFetchForSchedule({ success: true, enabled: true })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const badge = wrapper.find('.fr-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('Automatique')
  })

  it('shows "Manuelle" when config has no grist key (schedule inactive)', async () => {
    mockFetchForSchedule()
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: false, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const badge = wrapper.find('.fr-badge')
    expect(badge.text()).toBe('Manuelle')
  })

  it('stays on server state after toggling locally', async () => {
    globalThis.fetch = vi.fn((url, opts) => {
      if (String(url).includes('/api/schedule'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, enabled: true }) })
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    expect(wrapper.find('.fr-badge').text()).toBe('Automatique')

    const checkbox = wrapper.find('[data-test-id="auto-sync-toggle"]')
    await checkbox.setChecked(false)
    await flushPromises()

    expect(wrapper.find('.fr-badge').text()).toBe('Automatique')
  })
})

describe('Auto-sync next run display', () => {
  const mockFetchForSchedule = (scheduleResponse = { success: true, enabled: false }) => {
    globalThis.fetch = vi.fn((url, opts) => {
      if (String(url).includes('/api/schedule'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(scheduleResponse) })
      if (String(url).includes('/api/groups'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
    })
  }

  afterEach(() => {
    delete globalThis.fetch
  })

  it('is hidden when schedule is disabled', async () => {
    mockFetchForSchedule({ success: true, enabled: false })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const hint = wrapper.find('p.fr-hint-text')
    expect(hint.exists()).toBe(false)
  })

  it('is hidden when schedule is enabled without next_run', async () => {
    mockFetchForSchedule({ success: true, enabled: true })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const hint = wrapper.find('p.fr-hint-text')
    expect(hint.exists()).toBe(false)
  })

  it('shows the formatted next run when schedule is enabled', async () => {
    mockFetchForSchedule({
      success: true,
      enabled: true,
      next_run: '2026-09-03T09:14:00+00:00'
    })
    const wrapper = mount(DNFormSection, {
      props: {
        index: 0,
        existingConfig: { otp_config_id: 42, has_grist_key: true, demarche_number: DEMARCHE_NUMBER }
      },
      global: globalComponents
    })
    await flushPromises()

    const hint = wrapper.find('p.fr-hint-text')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('Prochaine synchronisation')
  })
})
