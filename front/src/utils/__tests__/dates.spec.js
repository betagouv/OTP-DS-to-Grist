import { describe, it, expect } from 'vitest'
import { formatDate } from '../dates'

describe('formatDate', () => {
  it(
    'Return an iso 8601 (EU)',
    () => expect(formatDate('2025-10-24')).toBe('24/10/2025')
  )
})
