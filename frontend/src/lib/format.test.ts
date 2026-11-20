import { describe, expect, it } from 'vitest'
import { formatDate, relativeTime } from './format'

const NOW = new Date('2026-06-15T12:00:00Z').getTime()
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString()

describe('relativeTime', () => {
  it.each([
    [30, 'Just now'],
    [18 * 60, '18 min ago'],
    [3 * 3600, '3 h ago'],
    [26 * 3600, 'Yesterday'],
    [4 * 86400, '4 days ago'],
    [14 * 86400, '2 wk ago'],
  ])('%i seconds ago reads "%s"', (seconds, expected) => {
    expect(relativeTime(ago(seconds), NOW)).toBe(expected)
  })

  it('falls back to a date after a month', () => {
    expect(relativeTime('2026-04-01T12:00:00Z', NOW)).toBe(formatDate('2026-04-01T12:00:00Z'))
  })
})

describe('formatDate', () => {
  it('formats as a short US date', () => {
    expect(formatDate('2026-03-05T12:00:00Z')).toBe('Mar 5, 2026')
  })
})
