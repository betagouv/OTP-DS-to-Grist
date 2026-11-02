import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import SyncSeriesTable from '../SyncSeriesTable.vue'
import { useSyncTask } from '../../composables/useSyncTask'
import { useNotification } from '../../composables/useNotification'

const { setTasks, setCurrentTaskId, recordTaskUpdate } = useSyncTask()

const SERIES = [
  { taskId: 'task_1', demarcheNumber: '111', demarcheTitle: 'Première démarche' },
  { taskId: 'task_2', demarcheNumber: '222', demarcheTitle: null }
]

// Heure locale : le format attendu ne dépend pas du fuseau de la machine de test
const END_TIME = new Date(2026, 10, 2, 14, 41).getTime() / 1000

const rows = (wrapper) => wrapper.findAll('tbody tr')
const cells = (wrapper, index) => rows(wrapper)[index].findAll('td')

describe('SyncSeriesTable', () => {
  beforeEach(() => {
    setTasks(SERIES)
  })

  afterEach(() => {
    setCurrentTaskId(null)
    useNotification().notifications.value = []
    vi.restoreAllMocks()
  })

  it('is hidden when no sync is followed', () => {
    setCurrentTaskId(null)
    const wrapper = mount(SyncSeriesTable)

    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('shows one row for the sync of a single démarche', () => {
    setCurrentTaskId('task_1', '111', 'Première démarche')
    const wrapper = mount(SyncSeriesTable)

    expect(rows(wrapper)).toHaveLength(1)
    expect(cells(wrapper, 0)[0].text()).toBe('N°111 — Première démarche')
  })

  it('shows the header and one row per démarche', () => {
    const wrapper = mount(SyncSeriesTable)

    expect(wrapper.find('thead').text()).toBe('Détails des synchronisations')
    expect(rows(wrapper)).toHaveLength(2)
  })

  it('shows the démarche number and its title when known', () => {
    const wrapper = mount(SyncSeriesTable)

    expect(cells(wrapper, 0)[0].text()).toBe('N°111 — Première démarche')
    expect(cells(wrapper, 1)[0].text()).toBe('N°222')
  })

  it('renders the démarche as a tooltip, for when it is truncated', () => {
    const wrapper = mount(SyncSeriesTable)

    expect(cells(wrapper, 0)[0].attributes('title')).toBe('N°111 — Première démarche')
  })

  it('shows a grey pending badge before the démarche starts', () => {
    const wrapper = mount(SyncSeriesTable)
    const badge = cells(wrapper, 1)[2].find('.fr-badge')

    expect(badge.text()).toBe('En attente')
    expect(badge.classes().filter(name => name.startsWith('fr-badge--') && name !== 'fr-badge--sm')).toEqual([])
  })

  it('shows a running badge and the server message during the sync', async () => {
    const wrapper = mount(SyncSeriesTable)
    recordTaskUpdate('task_1', { status: 'running', message: 'Récupération des dossiers', logs: [] })
    await wrapper.vm.$nextTick()

    expect(cells(wrapper, 0)[1].text()).toBe('Récupération des dossiers')
    expect(cells(wrapper, 0)[2].text()).toContain('En cours')
  })

  it('shows the processed dossiers and a success badge when completed', async () => {
    const wrapper = mount(SyncSeriesTable)
    recordTaskUpdate('task_1', {
      status: 'completed',
      message: 'Tâche terminée avec succès',
      result: { success_count: 14, error_count: 0 },
      sync_reason: 'synced',
      logs: []
    })
    await wrapper.vm.$nextTick()

    expect(cells(wrapper, 0)[1].text()).toBe('14 dossiers mis à jour/ajoutés')
    expect(cells(wrapper, 0)[2].find('.fr-badge--success').text()).toBe('Terminée')
  })

  it('tells when Grist is already up to date', async () => {
    const wrapper = mount(SyncSeriesTable)
    recordTaskUpdate('task_1', {
      status: 'completed',
      message: 'Tâche terminée avec succès',
      result: { success_count: 0, error_count: 0 },
      sync_reason: 'already_up_to_date',
      logs: []
    })
    await wrapper.vm.$nextTick()

    expect(cells(wrapper, 0)[1].text()).toBe('Grist déjà à jour')
  })

  it('shows the number of failed dossiers in a red badge', async () => {
    const wrapper = mount(SyncSeriesTable)
    recordTaskUpdate('task_1', {
      status: 'error',
      message: 'Erreur lors de la synchronisation',
      result: { success_count: 12, error_count: 3 },
      logs: []
    })
    await wrapper.vm.$nextTick()

    expect(cells(wrapper, 0)[1].text()).toBe('Erreur lors de la synchronisation')
    expect(cells(wrapper, 0)[2].find('.fr-badge--error').text()).toBe('3 erreur(s)')
  })

  it('shows a plain error badge when no dossier failed', async () => {
    const wrapper = mount(SyncSeriesTable)
    recordTaskUpdate('task_1', {
      status: 'error',
      message: 'Token DN périmé',
      result: { success_count: 0, error_count: 0 },
      logs: []
    })
    await wrapper.vm.$nextTick()

    expect(cells(wrapper, 0)[1].text()).toBe('Token DN périmé')
    expect(cells(wrapper, 0)[2].find('.fr-badge--error').text()).toBe('Erreur')
  })

  it('renders the message as a tooltip, for when it is truncated', async () => {
    const wrapper = mount(SyncSeriesTable)
    recordTaskUpdate('task_1', { status: 'error', message: 'Token DN périmé', logs: [] })
    await wrapper.vm.$nextTick()

    expect(cells(wrapper, 0)[1].attributes('title')).toBe('Token DN périmé')
  })

  describe('date and type', () => {
    it('adds the end date after the final message', async () => {
      const wrapper = mount(SyncSeriesTable)
      recordTaskUpdate('task_1', {
        status: 'completed',
        message: 'Tâche terminée avec succès',
        result: { success_count: 14, error_count: 0 },
        end_time: END_TIME,
        logs: []
      })
      await wrapper.vm.$nextTick()

      expect(cells(wrapper, 0)[1].text()).toBe('14 dossiers mis à jour/ajoutés · 2026-11-02 14:41')
    })

    it('adds the end date after an error message', async () => {
      const wrapper = mount(SyncSeriesTable)
      recordTaskUpdate('task_1', { status: 'error', message: 'Token DN périmé', end_time: END_TIME, logs: [] })
      await wrapper.vm.$nextTick()

      expect(cells(wrapper, 0)[1].text()).toBe('Token DN périmé · 2026-11-02 14:41')
    })

    it('shows no date while the sync is running', async () => {
      const wrapper = mount(SyncSeriesTable)
      recordTaskUpdate('task_1', { status: 'running', message: 'Récupération des dossiers', logs: [] })
      await wrapper.vm.$nextTick()

      expect(cells(wrapper, 0)[1].text()).toBe('Récupération des dossiers')
    })

    it('shows a manual type badge next to the status', () => {
      const wrapper = mount(SyncSeriesTable)

      expect(cells(wrapper, 0)[2].find('[data-test-id="sync-type-badge"]').text()).toBe('Manuelle')
    })
  })

  describe('Copier les logs', () => {
    const copyButton = (wrapper, index) => cells(wrapper, index)[3].find('button')

    beforeEach(() => {
      Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
    })

    it('is disabled while the démarche has no logs', () => {
      const wrapper = mount(SyncSeriesTable)

      expect(copyButton(wrapper, 0).attributes('disabled')).toBeDefined()
    })

    it('copies only the logs of its row', async () => {
      const wrapper = mount(SyncSeriesTable)
      recordTaskUpdate('task_1', { status: 'running', message: '', logs: [{ message: 'un' }, { message: 'deux' }] })
      recordTaskUpdate('task_2', { status: 'queued', message: '', logs: [{ message: 'autre' }] })
      await wrapper.vm.$nextTick()

      await copyButton(wrapper, 0).trigger('click')
      await flushPromises()

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('un\ndeux')
      expect(useNotification().notifications.value.at(-1)).toMatchObject({
        message: 'Logs copiés dans le presse-papiers',
        type: 'success'
      })
    })

    it('notifies an error when the copy fails', async () => {
      navigator.clipboard.writeText = vi.fn().mockRejectedValue(new Error('refus'))
      const wrapper = mount(SyncSeriesTable)
      recordTaskUpdate('task_1', { status: 'running', message: '', logs: [{ message: 'un' }] })
      await wrapper.vm.$nextTick()

      await copyButton(wrapper, 0).trigger('click')
      await flushPromises()

      expect(useNotification().notifications.value.at(-1)).toMatchObject({
        message: 'Erreur lors de la copie des logs',
        type: 'error'
      })
    })
  })

  describe('latest syncs read at load', () => {
    const HISTORY = [
      {
        key: 'history_2',
        demarcheNumber: '222',
        status: 'error',
        message: 'Token DN périmé',
        result: { success_count: 0, error_count: 0 },
        syncReason: null,
        endTime: new Date(2026, 10, 2, 14, 41),
        auto: true
      },
      {
        key: 'history_1',
        demarcheNumber: '111',
        status: 'completed',
        message: 'Synchronisation terminée',
        result: { success_count: 14, error_count: 0 },
        syncReason: null,
        endTime: new Date(2026, 10, 1, 9, 5),
        auto: false
      }
    ]

    const mountWithHistory = () => mount(SyncSeriesTable, { props: { history: HISTORY } })

    beforeEach(() => {
      setCurrentTaskId(null)
    })

    it('shows one row per démarche with its latest sync', () => {
      const wrapper = mountWithHistory()

      expect(rows(wrapper)).toHaveLength(2)
      expect(cells(wrapper, 0)[0].text()).toBe('N°222')
      expect(cells(wrapper, 0)[1].text()).toBe('Token DN périmé · 2026-11-02 14:41')
      expect(cells(wrapper, 0)[2].find('.fr-badge--error').text()).toBe('Erreur')
      expect(cells(wrapper, 1)[1].text()).toBe('14 dossiers mis à jour/ajoutés · 2026-11-01 09:05')
    })

    it('shows whether each sync was automatic or manual', () => {
      const wrapper = mountWithHistory()
      const typeBadge = (index) => cells(wrapper, index)[2].find('[data-test-id="sync-type-badge"]')

      expect(typeBadge(0).text()).toBe('Auto')
      expect(typeBadge(1).text()).toBe('Manuelle')
    })

    it('has no logs column', () => {
      const wrapper = mountWithHistory()

      expect(wrapper.find('thead th').attributes('colspan')).toBe('3')
      expect(cells(wrapper, 0)).toHaveLength(3)
      expect(wrapper.text()).not.toContain('Copier les logs')
    })

    it('gives way to the syncs launched from the page', async () => {
      const wrapper = mountWithHistory()
      setTasks(SERIES)
      await wrapper.vm.$nextTick()

      expect(rows(wrapper)).toHaveLength(2)
      expect(cells(wrapper, 0)[0].text()).toBe('N°111 — Première démarche')
      expect(cells(wrapper, 0)).toHaveLength(4)
    })
  })
})
