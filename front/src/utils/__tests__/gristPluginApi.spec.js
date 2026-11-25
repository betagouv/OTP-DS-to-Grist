import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'

const GRIST_PLUGIN_API_URL = 'https://docs.getgrist.com/grist-plugin-api.js'

const injectedScripts = () =>
  [...document.head.querySelectorAll('script')].filter((script) => script.src === GRIST_PLUGIN_API_URL)

describe('loadGristPluginApi', () => {
  let loadGristPluginApi

  // Module neuf à chaque test : le chargement mémorisé ne fuit pas d'un test à l'autre
  const importFreshModule = () => {
    vi.resetModules()

    return import('../gristPluginApi')
  }

  beforeEach(async () => {
    ({ loadGristPluginApi } = await importFreshModule())
  })

  afterEach(() => {
    injectedScripts().forEach((script) => script.remove())
    delete window.grist
  })

  it('injects the Grist plugin API script', () => {
    loadGristPluginApi()

    expect(injectedScripts()).toHaveLength(1)
  })

  it('resolves the grist global once the script is loaded', async () => {
    const loading = loadGristPluginApi()
    window.grist = { ready: vi.fn() }
    injectedScripts()[0].dispatchEvent(new Event('load'))

    expect(await loading).toBe(window.grist)
  })

  it('resolves null when the script fails to load', async () => {
    const loading = loadGristPluginApi()
    injectedScripts()[0].dispatchEvent(new Event('error'))

    expect(await loading).toBeNull()
  })

  it('loads the script only once', async () => {
    const first = loadGristPluginApi()
    const second = loadGristPluginApi()

    expect(second).toBe(first)
    expect(injectedScripts()).toHaveLength(1)
  })
})
