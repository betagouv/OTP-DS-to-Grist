import { describe, it, expect } from 'vitest'

import { sortConfigs, canDeleteConfig, canSyncConfig } from '../configUtils'

describe('sortConfigs', () => {
  it('trie les configs sauvegardées par otp_config_id ascendant', () => {
    const configs = [{ otp_config_id: 10 }, { otp_config_id: 2 }, { otp_config_id: 7 }]

    const result = sortConfigs(configs)

    expect(result.map(c => c.otp_config_id)).toEqual([2, 7, 10])
  })

  it('place les entrées non sauvegardées (null) à la fin', () => {
    const configs = [{ otp_config_id: 5 }, null, { otp_config_id: 3 }]

    const result = sortConfigs(configs)

    expect(result.map(c => c?.otp_config_id ?? null)).toEqual([3, 5, null])
  })

  it('retourne [null] quand aucun config', () => {
    expect(sortConfigs([null])).toEqual([null])
  })

  it('retourne un tableau vide si entré un tableau vide', () => {
    expect(sortConfigs([])).toEqual([])
  })

  it('ne mute pas le tableau original', () => {
    const configs = [{ otp_config_id: 10 }, { otp_config_id: 2 }]

    sortConfigs(configs)

    expect(configs.map(c => c.otp_config_id)).toEqual([10, 2])
  })
})

describe('canDeleteConfig', () => {
  it('retourne true si otp_config_id existe', () => {
    expect(canDeleteConfig({ otp_config_id: 1 })).toBe(true)
  })

  it('retourne false si otp_config_id est null', () => {
    expect(canDeleteConfig({ otp_config_id: null })).toBe(false)
  })

  it('retourne false si config est null', () => {
    expect(canDeleteConfig(null)).toBe(false)
  })

  it('retourne false si config est undefined', () => {
    expect(canDeleteConfig(undefined)).toBe(false)
  })
})

describe('canSyncConfig', () => {
  it('retourne true si otp_config_id existe et syncRunning est false', () => {
    expect(canSyncConfig({ otp_config_id: 1 }, false)).toBe(true)
  })

  it('retourne false si syncRunning est true', () => {
    expect(canSyncConfig({ otp_config_id: 1 }, true)).toBe(false)
  })

  it('retourne false si pas de otp_config_id', () => {
    expect(canSyncConfig(null, false)).toBe(false)
  })

  it('retourne false si config est undefined', () => {
    expect(canSyncConfig(undefined, false)).toBe(false)
  })
})
