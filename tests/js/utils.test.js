/** @jest-environment jsdom */  
const { escapeHtml, formatDate }  = require('../../static/js/utils.js')

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
