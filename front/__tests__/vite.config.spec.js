// @vitest-environment node
// Configuration lue par Node : l'URL de jsdom refuserait les chemins de fichiers

import { describe, it, expect, vi, afterEach } from 'vitest'

import viteConfigFactory from '../vite.config'

afterEach(() => {
  vi.unstubAllEnvs()
})

// Les variables déjà présentes dans l'environnement priment sur le .env racine
const serverConfig = (command, origin) => {
  vi.stubEnv('VITE_DEV_ORIGIN', origin)

  return viteConfigFactory({ command, mode: 'development' }).server
}

describe('server', () => {
  it('refuse de lancer le serveur de dev sans VITE_DEV_ORIGIN', () => {
    // Sans origine, les URL des polices du DSFR partiraient vers Flask (404)
    expect(() => serverConfig('serve', '')).toThrow(
      'VITE_DEV_ORIGIN manquante dans le .env racine (voir .env.example)'
    )
  })

  it.each(['build', 'test'])('ne demande pas VITE_DEV_ORIGIN hors du serveur de dev (%s)', (command) => {
    expect(serverConfig(command, '')).toEqual({})
  })

  it("reprend l'origine et le port de VITE_DEV_ORIGIN", () => {
    expect(serverConfig('serve', 'http://localhost:5174')).toEqual({
      origin: 'http://localhost:5174',
      port: 5174
    })
  })

  it("garde le port de Vite quand l'origine n'en précise pas (URL publique d'un Codespace)", () => {
    expect(serverConfig('serve', 'https://exemple-5173.app.github.dev')).toEqual({
      origin: 'https://exemple-5173.app.github.dev'
    })
  })
})
