import { describe, it, expect } from 'vitest'
import { describeCheck, emptyRule, qualityProblem, withMetric, withType } from './qualityRules'

describe('withMetric', () => {
  it('clears the column when the metric becomes rowCount', () =>
    expect(withMetric({ ...emptyRule(), column: 'email' }, 'rowCount').column).toBe(''))

  it('falls back to rows when percent cannot run', () =>
    expect(withMetric({ ...emptyRule(), unit: 'percent' }, 'duplicateValues').unit).toBe('rows'))

  it('keeps percent where it runs', () =>
    expect(withMetric({ ...emptyRule(), unit: 'percent' }, 'missingValues').unit).toBe('percent'))

  it('drops valid values when the metric is not invalidValues', () =>
    expect(
      withMetric({ ...emptyRule(), metric: 'invalidValues', valid_values: ['a'] }, 'nullValues').valid_values,
    ).toEqual([]))
})

describe('withType', () => {
  it('clears the check of a text rule and keeps what it shares', () => {
    const rule = withType({ ...emptyRule(), column: 'email', description: 'd' }, 'text')
    expect(rule).toMatchObject({
      type: 'text', column: 'email', description: 'd',
      metric: null, operator: null, value: null, unit: null, valid_values: [],
    })
  })

  it('gives a library rule a default check', () =>
    expect(withType(withType(emptyRule(), 'text'), 'library')).toMatchObject({
      type: 'library', metric: 'nullValues', operator: 'mustBe', value: 0, unit: 'rows',
    }))
})

describe('qualityProblem', () => {
  it('accepts a runnable rule', () =>
    expect(qualityProblem([{ ...emptyRule(), column: 'email' }], ['email'])).toBeNull())

  it('reports a rule whose column is no longer a field', () =>
    expect(qualityProblem([{ ...emptyRule(), column: 'mail' }], ['email'])).toBe(
      "Rule 1: column 'mail' is not a schema field",
    ))

  it('reports the second rule on the same metric and column', () =>
    expect(
      qualityProblem([{ ...emptyRule(), column: 'email' }, { ...emptyRule(), column: 'email' }], ['email']),
    ).toBe('Rule 2: email already has a nullValues rule'))

  it('requires valid values for invalidValues', () =>
    expect(qualityProblem([{ ...emptyRule(), column: 'email', metric: 'invalidValues' }], ['email'])).toBe(
      'Rule 1: invalidValues needs valid values',
    ))

  it('requires a description on a text rule', () =>
    expect(qualityProblem([withType(emptyRule(), 'text')], [])).toBe('Rule 1: a text rule needs a description'))

  it('requires a column for a column metric', () =>
    expect(qualityProblem([emptyRule()], ['email'])).toBe('Rule 1: nullValues needs a column'))

  it('refuses a column on rowCount', () =>
    expect(qualityProblem([{ ...emptyRule(), metric: 'rowCount', column: 'email' }], ['email'])).toBe(
      'Rule 1: rowCount applies to the whole table',
    ))

  it('refuses percent above 100', () =>
    expect(
      qualityProblem([{ ...emptyRule(), column: 'email', unit: 'percent', value: 120 }], ['email']),
    ).toBe('Rule 1: a percent value cannot exceed 100'))

  it('needs a value on a library rule', () =>
    expect(qualityProblem([{ ...emptyRule(), column: 'email', value: null }], ['email'])).toBe(
      'Rule 1: a library rule needs a value',
    ))
})

describe('describeCheck', () => {
  it('describes a check', () =>
    expect(describeCheck({ ...emptyRule(), operator: 'mustBeLessOrEqualTo', value: 1, unit: 'percent' })).toBe(
      'nullValues ≤ 1 percent',
    ))

  it('lists valid values', () =>
    expect(describeCheck({ ...emptyRule(), metric: 'invalidValues', valid_values: ['open', 'paid'] })).toBe(
      'invalidValues = 0 rows (valid: open, paid)',
    ))

  it('omits a missing unit', () =>
    expect(
      describeCheck({ ...emptyRule(), metric: 'rowCount', operator: 'mustBeGreaterOrEqualTo', value: 5, unit: null }),
    ).toBe('rowCount ≥ 5'))

  it('shows a dash for a text rule', () => expect(describeCheck(withType(emptyRule(), 'text'))).toBe('—'))
})
