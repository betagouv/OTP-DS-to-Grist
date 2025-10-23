/** @jest-environment jsdom */  
const { escapeHtml }  = require('../../static/utils.js')

it(
  'Return simple string',
  () => {
    expect(escapeHtml('abcd')).toBe('abcd')
  }
)

it(
  'Escape specials characters',
  () => {
    expect(escapeHtml(`<>&"'`)).toBe(`&lt;&gt;&amp;"'`)
  }
)
