import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

describe('useNotification', () => {
  let useNotification
  let notifications
  let notify
  let remove

  beforeEach(async () => {
    vi.useFakeTimers()
    vi.resetModules()
    const mod = await import('../useNotification.js')
    useNotification = mod.useNotification
    ;({ notifications, notify, remove } = useNotification())
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    delete globalThis.Notification
  })

  it('adds toast when Notification API is unavailable', () => {
    notify('test message')

    expect(notifications.value).toHaveLength(1)
    expect(notifications.value[0].message).toBe('test message')
    expect(notifications.value[0].type).toBe('info')
  })

  it('adds toast when permission is denied', () => {
    globalThis.Notification = { permission: 'denied' }

    notify('test message')

    expect(notifications.value).toHaveLength(1)
    expect(notifications.value[0].message).toBe('test message')
  })

  it('sends browser notification when permission is granted', () => {
    const MockNotification = vi.fn()
    globalThis.Notification = MockNotification
    globalThis.Notification.permission = 'granted'

    notify('browser msg', 'success')

    expect(MockNotification).toHaveBeenCalledWith('browser msg')
    expect(notifications.value).toHaveLength(0)
  })

  it('falls back to toast when Notification constructor throws', () => {
    globalThis.Notification = vi.fn(() => { throw new Error('blocked') })
    globalThis.Notification.permission = 'granted'

    notify('fallback msg')

    expect(notifications.value).toHaveLength(1)
    expect(notifications.value[0].message).toBe('fallback msg')
  })

  it('uses 10s duration for error type', () => {
    notify('error msg', 'error')

    expect(notifications.value).toHaveLength(1)

    vi.advanceTimersByTime(9999)
    expect(notifications.value).toHaveLength(1)

    vi.advanceTimersByTime(1)
    expect(notifications.value).toHaveLength(0)
  })

  it('uses 5s duration for success type', () => {
    notify('success msg', 'success')

    expect(notifications.value).toHaveLength(1)

    vi.advanceTimersByTime(4999)
    expect(notifications.value).toHaveLength(1)

    vi.advanceTimersByTime(1)
    expect(notifications.value).toHaveLength(0)
  })

  it('remove() filters out the notification by id', () => {
    notify('msg1')
    notify('msg2')

    expect(notifications.value).toHaveLength(2)

    remove(notifications.value[0].id)

    expect(notifications.value).toHaveLength(1)
    expect(notifications.value[0].message).toBe('msg2')
  })

  it('notifications ref is shared across multiple useNotification calls', () => {
    const other = useNotification()

    notify('shared msg')

    expect(other.notifications.value).toHaveLength(1)
    expect(other.notifications.value[0].message).toBe('shared msg')
  })
})
