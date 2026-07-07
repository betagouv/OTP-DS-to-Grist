import { describe, it, expect, beforeEach } from 'vitest'
import { useDemarcheContext } from '../useDemarcheContext'

describe('useDemarcheContext', () => {
  beforeEach(() => {
    const { setDemarcheCount } = useDemarcheContext()
    setDemarcheCount(0)
  })

  it('returns 0 totalDemarches by default', () => {
    const { totalDemarches } = useDemarcheContext()

    expect(totalDemarches.value).toBe(0)
  })

  it('returns 1 demarcheIndex by default', () => {
    const { demarcheIndex } = useDemarcheContext()

    expect(demarcheIndex.value).toBe(1)
  })

  it('updates totalDemarches reactively via setDemarcheCount', () => {
    const { totalDemarches, setDemarcheCount } = useDemarcheContext()
    setDemarcheCount(3)

    expect(totalDemarches.value).toBe(3)
  })

  it('is shared as a singleton across multiple calls', () => {
    const a = useDemarcheContext()
    const b = useDemarcheContext()
    a.setDemarcheCount(42)

    expect(b.totalDemarches.value).toBe(42)
  })
})
