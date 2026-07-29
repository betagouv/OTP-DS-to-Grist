import { describe, it, expect, vi, afterEach } from 'vitest'

import { debounce } from '../debounce'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('debounce', () => {
  it('appelle la fonction après le délai par défaut de 500ms', () => {
    vi.spyOn(globalThis, 'setTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn)

    debounced()

    expect(setTimeout).toHaveBeenCalledTimes(1)
    expect(setTimeout).toHaveBeenCalledWith(expect.any(Function), 500)

    const callback = setTimeout.mock.calls[0][0]
    callback()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('appelle la fonction après un délai personnalisé', () => {
    vi.spyOn(globalThis, 'setTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn, 200)

    debounced()

    expect(setTimeout).toHaveBeenCalledWith(expect.any(Function), 200)

    const callback = setTimeout.mock.calls[0][0]
    callback()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('réinitialise le timer à chaque appel rapproché', () => {
    vi.spyOn(globalThis, 'setTimeout')
    vi.spyOn(globalThis, 'clearTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn)

    debounced()
    debounced()
    debounced()

    expect(clearTimeout).toHaveBeenCalledTimes(3)
    expect(setTimeout).toHaveBeenCalledTimes(3)

    const lastCallback = setTimeout.mock.calls[2][0]
    lastCallback()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('passe les arguments à la fonction originale', () => {
    vi.spyOn(globalThis, 'setTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn)

    debounced('a', 42)

    const callback = setTimeout.mock.calls[0][0]
    callback()
    expect(fn).toHaveBeenCalledWith('a', 42)
  })

  it('fonctionne avec plusieurs bursts indépendants', () => {
    vi.spyOn(globalThis, 'setTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn)

    debounced()
    let callback = setTimeout.mock.calls[0][0]
    callback()
    expect(fn).toHaveBeenCalledTimes(1)

    debounced()
    callback = setTimeout.mock.calls[1][0]
    callback()
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('fonctionne avec delay à 0', () => {
    vi.spyOn(globalThis, 'setTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn, 0)

    debounced()

    expect(setTimeout).toHaveBeenCalledWith(expect.any(Function), 0)

    const callback = setTimeout.mock.calls[0][0]
    callback()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('fonctionne sans argument', () => {
    vi.spyOn(globalThis, 'setTimeout')
    const fn = vi.fn()
    const debounced = debounce(fn)

    debounced()

    const callback = setTimeout.mock.calls[0][0]
    callback()
    expect(fn).toHaveBeenCalledWith()
  })
})
