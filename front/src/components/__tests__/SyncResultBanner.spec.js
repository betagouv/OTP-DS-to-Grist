import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SyncResultBanner from '../SyncResultBanner.vue'

describe('SyncResultBanner', () => {
  const defaultProps = {
    status: 'success',
    successCount: 3,
    errorCount: 0,
    timestamp: '2026-07-15T11:26:02',
    syncType: 'manual'
  }

  it('affiche une alerte de succès', () => {
    const wrapper = mount(SyncResultBanner, { props: defaultProps })

    expect(wrapper.text()).toContain('Synchronisation terminée avec succès')
  })

  it('affiche une alerte d\'erreur', () => {
    const wrapper = mount(SyncResultBanner, {
      props: { ...defaultProps, status: 'error' }
    })

    expect(wrapper.text()).toContain('Synchronisation terminée avec erreur(s)')
  })

  it('affiche les compteurs de dossiers', () => {
    const wrapper = mount(SyncResultBanner, {
      props: { ...defaultProps, successCount: 12, errorCount: 3 }
    })

    expect(wrapper.text()).toContain('12 dossiers traités avec succès, 3 en échec')
  })

  it('affiche la date formatée en français', () => {
    const wrapper = mount(SyncResultBanner, { props: defaultProps })

    expect(wrapper.text()).toContain('15/07/2026')
  })

  it('affiche "(automatique)" pour une synchro auto', () => {
    const wrapper = mount(SyncResultBanner, {
      props: { ...defaultProps, syncType: 'auto' }
    })

    expect(wrapper.text()).toContain('(automatique)')
  })

  it('affiche "(déclenchée manuellement)" pour une synchro manuelle', () => {
    const wrapper = mount(SyncResultBanner, {
      props: { ...defaultProps, syncType: 'manual' }
    })

    expect(wrapper.text()).toContain('(déclenchée manuellement)')
  })

  it('affiche "Grist déjà à jour" avec alerte info quand sync_reason est already_up_to_date', () => {
    const wrapper = mount(SyncResultBanner, {
      props: {
        status: 'success',
        successCount: 0,
        errorCount: 0,
        timestamp: '2026-07-15T11:26:02',
        syncType: 'manual',
        syncReason: 'already_up_to_date'
      }
    })

    expect(wrapper.text()).toContain('Grist déjà à jour')
    expect(wrapper.text()).toContain('Aucun dossier nouveau ou modifié depuis la dernière synchronisation.')
  })

  it('détecte "Grist déjà à jour" via les compteurs quand sync_reason est absent (logs historiques)', () => {
    const wrapper = mount(SyncResultBanner, {
      props: {
        status: 'success',
        successCount: 0,
        errorCount: 0,
        timestamp: '2026-07-15T11:26:02',
        syncType: 'auto',
        syncReason: null
      }
    })

    expect(wrapper.text()).toContain('Grist déjà à jour')
    expect(wrapper.findComponent({ name: 'DsfrAlert' }).exists())
  })

  it('affiche le message de la tâche quand présent', () => {
    const wrapper = mount(SyncResultBanner, {
      props: {
        ...defaultProps,
        message: 'Synchronisation terminée: 5/5 dossiers synchronisés'
      }
    })

    expect(wrapper.text()).toContain('Synchronisation terminée: 5/5 dossiers synchronisés')
  })
})
