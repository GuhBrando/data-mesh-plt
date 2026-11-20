import { describe, it, expect } from 'vitest'
import {
  SLA_KEYS,
  formatServiceLevel,
  readSlaInputs,
  slaInputProblem,
  toServiceLevels,
} from './serviceLevels'
import type { SlaInput, SlaKey } from './serviceLevels'
import type { ServiceLevels } from '../types'

const blank = Object.fromEntries(SLA_KEYS.map((k) => [k, { value: '', unit: '' }])) as Record<SlaKey, SlaInput>

describe('readSlaInputs', () => {
  it('reads stored properties into inputs', () =>
    expect(readSlaInputs({ properties: [{ property: 'freshness', value: 24, unit: 'h' }] }).freshness).toEqual({
      value: '24',
      unit: 'h',
    }))

  it('gives missing keys their default unit', () =>
    expect(readSlaInputs(undefined)).toEqual({
      freshness: { value: '', unit: 'h' },
      availability: { value: '', unit: '%' },
      retention: { value: '', unit: 'd' },
      latency: { value: '', unit: 'h' },
    }))

  it('reads text as text with no unit', () =>
    expect(
      readSlaInputs({ properties: [{ property: 'retention', value: 'P1D', unit: null }] }).retention,
    ).toEqual({ value: 'P1D', unit: '' }))

  it('reads an unmigrated row as empty inputs', () =>
    expect(readSlaInputs({ freshness: '24h' } as unknown as ServiceLevels).freshness.value).toBe(''))
})

describe('toServiceLevels', () => {
  it('writes numbers with units and text without, dropping blanks', () =>
    expect(
      toServiceLevels(
        { ...blank, freshness: { value: '12', unit: 'h' }, retention: { value: 'P1D', unit: '' } },
        undefined,
      ),
    ).toEqual({
      properties: [
        { property: 'freshness', value: 12, unit: 'h' },
        { property: 'retention', value: 'P1D', unit: null },
      ],
    }))

  it('keeps properties the form does not show', () =>
    expect(toServiceLevels(blank, { properties: [{ property: 'frequency', value: 1, unit: 'd' }] }).properties).toEqual(
      [{ property: 'frequency', value: 1, unit: 'd' }],
    ))

  it('replaces a shown property instead of keeping the stored copy', () =>
    expect(
      toServiceLevels({ ...blank, latency: { value: '2', unit: 'h' } }, {
        properties: [{ property: 'latency', value: 1, unit: 'h' }],
      }).properties,
    ).toEqual([{ property: 'latency', value: 2, unit: 'h' }]))
})

describe('slaInputProblem', () => {
  it('asks for a unit on a number', () => expect(slaInputProblem({ value: '24', unit: '' })).toBe('Pick a unit'))
  it('accepts text without a unit', () => expect(slaInputProblem({ value: 'best effort', unit: '' })).toBeNull())
  it('refuses text with a unit', () =>
    expect(slaInputProblem({ value: 'soon', unit: 'h' })).toBe('Use a number, or clear the unit to keep text'))
  it('accepts an empty value', () => expect(slaInputProblem({ value: '', unit: 'h' })).toBeNull())
})

describe('formatServiceLevel', () => {
  it('joins value and unit', () => expect(formatServiceLevel({ property: 'f', value: 24, unit: 'h' })).toBe('24 h'))
  it('shows text alone', () => expect(formatServiceLevel({ property: 'r', value: 'P1D', unit: null })).toBe('P1D'))
})
