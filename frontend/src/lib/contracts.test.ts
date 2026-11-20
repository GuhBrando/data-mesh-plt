import { describe, expect, it } from 'vitest'
import { STATUS_LABELS, STATUS_ORDER, domainColor, initials } from './contracts'

describe('domainColor', () => {
  it('gives a domain the same colour every time', () => {
    expect(domainColor('Riscos')).toBe(domainColor('Riscos'))
  })

  it('returns a hex colour from the palette', () => {
    for (const name of ['Sales', 'Finance', 'Riscos', 'Crédito', '']) {
      expect(domainColor(name)).toMatch(/^#[0-9A-F]{6}$/)
    }
  })
})

describe('initials', () => {
  it.each([
    ['ana.ribeiro', 'AR'],
    ['Platform Admin', 'PA'],
    ['bruno_costa', 'BC'],
    ['alice', 'AL'],
  ])('%s → %s', (name, expected) => {
    expect(initials(name)).toBe(expected)
  })
})

describe('status labels', () => {
  it('has a label for every status in display order', () => {
    expect(STATUS_ORDER.map((s) => STATUS_LABELS[s])).toEqual(['Active', 'In review', 'Draft', 'Deprecated', 'Retired'])
  })
})
