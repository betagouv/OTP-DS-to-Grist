/** @jest-environment jsdom */
const { showNotification }  = require('../../static/js/notifications.js')

describe('showNotification', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it(
    'creates a notification with default info type',
    () => {
      showNotification('Test message')

      const notification = document.querySelector('.fr-notice')
      expect(notification).toBeTruthy()
      expect(notification.classList.contains('fr-notice--info')).toBe(true)
      expect(notification.textContent).toContain('Test message')
    }
  )

  it(
    'creates a notification with success type',
    () => {
      showNotification('Success message', 'success')

      const notification = document.querySelector('.fr-notice')
      expect(notification.classList.contains('fr-notice--success')).toBe(true)
      expect(notification.textContent).toContain('Success message')
    }
  )

  it(
    'creates a notification with error type',
    () => {
      showNotification('Error message', 'error')

      const notification = document.querySelector('.fr-notice')
      expect(notification.classList.contains('fr-notice--error')).toBe(true)
      expect(notification.textContent).toContain('Error message')
    }
  )

  it(
    'auto-removes notification after 5 seconds for non-error types',
    () => {
      showNotification('Info message', 'info')

      expect(document.querySelector('.fr-notice')).toBeTruthy()

      jest.advanceTimersByTime(5000)
      expect(document.querySelector('.fr-notice')).toBeFalsy()
    }
  )

  it(
    'auto-removes notification after 10 seconds for error type',
    () => {
      showNotification('Error message', 'error')

      expect(document.querySelector('.fr-notice')).toBeTruthy()

      jest.advanceTimersByTime(10000)
      expect(document.querySelector('.fr-notice')).toBeFalsy()
    }
  )

  it(
    'includes close button in notification',
    () => {
      showNotification('Test message')

      const closeButton = document.querySelector('.fr-btn--close')
      expect(closeButton).toBeTruthy()
      expect(closeButton.title).toBe('Masquer le message')
    }
  )
})
