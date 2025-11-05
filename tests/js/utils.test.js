/** @jest-environment jsdom */
const { escapeHtml, formatDate, formatDuration }  = require('../../static/js/utils.js')

describe('escapeHtml', () => {
  it(
    'Return simple string',
    () => expect(escapeHtml('abcd')).toBe('abcd')

  )

  it(
    'Escape specials characters',
    () => expect(escapeHtml(`<>&"'`)).toBe(`&lt;&gt;&amp;"'`)

  )
})

describe('formatDate', () => {
  it(
    'Return an iso 8601 (EU)',
    () => expect(formatDate('2025-10-24')).toBe('24/10/2025')
  )
})

describe('formatDuration', () => {
  it(
    'formats seconds only',
    () => {
      expect(formatDuration(45)).toBe('45s')
    }
  )

  it(
    'formats minutes and seconds',
    () => {
      expect(formatDuration(125)).toBe('2m 5s')
    }
  )

  it(
    'formats hours, minutes and seconds',
    () => {
      expect(formatDuration(3665)).toBe('1h 1m 5s')
    }
  )

  it(
    'formats zero seconds',
    () => {
      expect(formatDuration(0)).toBe('0s')
    }
  )

  it(
    'formats large duration',
    () => {
      expect(formatDuration(7265)).toBe('2h 1m 5s')
    }
  )
})
