import { vi, describe, beforeEach, it, expect } from 'vitest'
import { useConnectionCheck, CONNECTION_STATUS } from '../useConnectionCheck'
import { api } from '../../utils/InternalApi'

vi.mock('../../utils/InternalApi', () => ({
  api: {
    testConnection: vi.fn()
  }
}))

const BODY = { type: 'grist', api_key: 'cle' }

describe('useConnectionCheck', () => {
  beforeEach(() => {
    api.testConnection.mockReset()
  })

  it('starts untested, with no error', () => {
    const { status, errorMessage } = useConnectionCheck()

    expect(status.value).toBe(CONNECTION_STATUS.UNTESTED)
    expect(errorMessage.value).toBeNull()
  })

  it('is pending while the test runs', () => {
    api.testConnection.mockReturnValue(new Promise(() => {}))
    const { status, errorMessage, check } = useConnectionCheck()

    check(BODY)

    expect(api.testConnection).toHaveBeenCalledWith(BODY)
    expect(status.value).toBe(CONNECTION_STATUS.PENDING)
    expect(errorMessage.value).toBeNull()
  })

  it('is verified with an empty error when the test succeeds', async () => {
    const result = { success: true, title: 'Ma démarche' }
    api.testConnection.mockResolvedValue(result)
    const { status, errorMessage, check } = useConnectionCheck()

    expect(await check(BODY)).toEqual(result)
    expect(status.value).toBe(CONNECTION_STATUS.VERIFIED)
    expect(errorMessage.value).toBe('')
  })

  it('fails with the server message when the test is refused', async () => {
    api.testConnection.mockResolvedValue({ success: false, message: 'Clé invalide' })
    const { status, errorMessage, check } = useConnectionCheck()

    await check(BODY)

    expect(status.value).toBe(CONNECTION_STATUS.FAILED)
    expect(errorMessage.value).toBe('Clé invalide')
  })

  it('fails with the network message and rethrows when the request fails', async () => {
    const error = new Error('network error')
    api.testConnection.mockRejectedValue(error)
    const { status, errorMessage, check } = useConnectionCheck({ networkErrorMessage: 'Erreur réseau' })

    await expect(check(BODY)).rejects.toBe(error)
    expect(status.value).toBe(CONNECTION_STATUS.FAILED)
    expect(errorMessage.value).toBe('Erreur réseau')
  })

  it('has no error message on request failure when none is given', async () => {
    api.testConnection.mockRejectedValue(new Error('network error'))
    const { status, errorMessage, check } = useConnectionCheck()

    await expect(check(BODY)).rejects.toThrow()
    expect(status.value).toBe(CONNECTION_STATUS.FAILED)
    expect(errorMessage.value).toBeNull()
  })

  it('goes back to untested on reset', async () => {
    api.testConnection.mockResolvedValue({ success: false, message: 'Clé invalide' })
    const { status, errorMessage, check, reset } = useConnectionCheck()
    await check(BODY)

    reset()

    expect(status.value).toBe(CONNECTION_STATUS.UNTESTED)
    expect(errorMessage.value).toBeNull()
  })
})
