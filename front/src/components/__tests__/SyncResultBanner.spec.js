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
})
