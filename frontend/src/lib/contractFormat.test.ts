import { describe, it, expect } from 'vitest'
import { normalizeContract } from './contractFormat'
import { emptyRule } from './qualityRules'
import type { DataContract } from '../types'

const base = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 2, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { freshness: '', availability: '', retention: '', latency: '' },
  description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

const withRules = (quality: unknown[]) =>
  normalizeContract({ ...base, models: { fields: [], quality } } as unknown as DataContract)

describe('normalizeContract', () => {
  it('shows an old rule as a text rule that keeps its values', () => {
    const [rule] = withRules([
      { dimension: 'completeness', column: 'email', operator: '>=', threshold: '99%', description: 'Emails' },
    ]).models.quality!
    expect(rule).toMatchObject({ type: 'text', dimension: 'completeness', column: '', metric: null, value: null })
    expect(rule.description).toBe(
      'Emails [legacy rule: dimension=completeness column=email operator=>= threshold=99%]',
    )
  })

  it('maps old dimensions to ODCS', () =>
    expect(
      withRules([{ dimension: 'freshness', column: '', operator: '<=', threshold: '24h' }]).models.quality![0]
        .dimension,
    ).toBe('timeliness'))

  it('leaves a rule already in the new shape alone', () => {
    const rule = { ...emptyRule(), column: 'email' }
    expect(withRules([rule]).models.quality).toEqual([rule])
  })

  it('wraps an unreadable rule in a text rule', () =>
    expect(withRules(['free text']).models.quality![0].description).toBe('[legacy rule: "free text"]'))
})
