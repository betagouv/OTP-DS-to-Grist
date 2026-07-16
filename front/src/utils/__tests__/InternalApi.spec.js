import { vi, describe, beforeEach, afterEach, it, expect } from 'vitest'
import { api } from '../InternalApi'

describe('InternalApi', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('getConfig', () => {
    it('calls GET /api/config with params and returns json', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, configs: [] })
      })

      const result = await api.getConfig('?grist_user_id=5&grist_doc_id=doc-123')

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/config?grist_user_id=5&grist_doc_id=doc-123')
      expect(result).toEqual({ success: true, configs: [] })
    })

    it('throws on non-ok response', async () => {
      globalThis.fetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(api.getConfig('?')).rejects.toThrow('Erreur HTTP 500')
    })
  })

  describe('saveConfig', () => {
    it('calls POST /api/config with config body', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      })

      const config = { ds_api_token: 'token', demarche_number: '12345' }
      const result = await api.saveConfig(config)

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      expect(result).toEqual({ success: true })
    })

    it('throws on non-ok response', async () => {
      globalThis.fetch.mockResolvedValue({ ok: false, status: 400 })

      await expect(api.saveConfig({})).rejects.toThrow('Erreur HTTP 400')
    })
  })

  describe('deleteConfig', () => {
    it('calls DELETE /api/config/:id', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      })

      const result = await api.deleteConfig(42)

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/config/42', {
        method: 'DELETE'
      })
      expect(result).toEqual({ success: true })
    })

    it('throws on non-ok response', async () => {
      globalThis.fetch.mockResolvedValue({ ok: false, status: 404 })

      await expect(api.deleteConfig(1)).rejects.toThrow('Erreur HTTP 404')
    })
  })

  describe('startSync', () => {
    it('calls POST /api/start-sync with otp_config_id and returns json', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, task_id: 'abc' })
      })

      const result = await api.startSync(7)

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/start-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ otp_config_id: 7 })
      })
      expect(result).toEqual({ success: true, task_id: 'abc' })
    })

    it('throws on non-ok response', async () => {
      globalThis.fetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(api.startSync(1)).rejects.toThrow('Erreur HTTP 500')
    })
  })

  describe('testConnection', () => {
    it('calls POST /api/test-connection with body', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, message: 'OK' })
      })

      const body = { type: 'grist', base_url: 'https://grist.example.com', api_key: 'key', doc_id: 'doc' }
      const result = await api.testConnection(body)

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      expect(result).toEqual({ success: true, message: 'OK' })
    })

    it('throws on non-ok response', async () => {
      globalThis.fetch.mockResolvedValue({ ok: false, status: 502 })

      await expect(api.testConnection({})).rejects.toThrow('Erreur HTTP 502')
    })
  })

  describe('getSyncLogLatest', () => {
    it('calls GET /api/sync-log/latest with otp_config_id', async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, auto: null, manual: null })
      })

      const result = await api.getSyncLogLatest(3)

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/sync-log/latest?otp_config_id=3')
      expect(result).toEqual({ success: true, auto: null, manual: null })
    })

    it('throws on non-ok response', async () => {
      globalThis.fetch.mockResolvedValue({ ok: false, status: 503 })

      await expect(api.getSyncLogLatest(1)).rejects.toThrow('Erreur HTTP 503')
    })
  })
})
