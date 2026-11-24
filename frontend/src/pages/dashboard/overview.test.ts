import { describe, expect, it } from 'vitest'
import {
  buildAttention,
  buildDomainCards,
  buildRecent,
  countStatuses,
  countTiers,
  hasMaintainer,
  pct,
  plural,
} from './overview'
import { makeContract, makeDomain, makeProduct } from '../../test/fixtures'
import type { QualityRule } from '../../types'

const rule = { type: 'library', dimension: 'completeness', column: 'id' } as QualityRule

describe('counting', () => {
  it('counts contracts per status, keeping empty ones at zero', () => {
    const counts = countStatuses([
      makeContract({ status: 'active' }),
      makeContract({ status: 'active' }),
      makeContract({ status: 'in_review' }),
    ])
    expect(counts).toEqual({ active: 2, in_review: 1, draft: 0, deprecated: 0, retired: 0 })
  })

  it('counts contracts per tier', () => {
    expect(countTiers([makeContract({ tier: 1 }), makeContract({ tier: 1 }), makeContract({ tier: 4 })])).toEqual({
      1: 2, 2: 0, 3: 0, 4: 1,
    })
  })

  it('computes percentages without dividing by zero', () => {
    expect(pct(1, 4)).toBe(25)
    expect(pct(3, 0)).toBe(0)
  })

  it('pluralises', () => {
    expect(plural(1, 'contract')).toBe('1 contract')
    expect(plural(2, 'contract')).toBe('2 contracts')
  })

  it('knows when a domain has a maintainer', () => {
    expect(hasMaintainer(makeDomain())).toBe(true)
    expect(hasMaintainer(makeDomain({ members: [{ user_id: 'u3', username: 'carl', role: 'member' }] }))).toBe(false)
  })
})

describe('buildAttention', () => {
  it('is empty when everything is in order', () => {
    const contracts = [makeContract({ models: { fields: [], quality: [rule] } })]
    expect(buildAttention(contracts, [makeProduct()], [makeDomain()])).toEqual([])
  })

  it('lists review, repository, quality and maintainer issues in that order', () => {
    const items = buildAttention(
      [
        makeContract({ id: 'a', title: 'pix', status: 'in_review', tier: 1 }),
        makeContract({ id: 'b', title: 'ledger', models: { fields: [], quality: [rule] } }),
      ],
      [makeProduct({ name: 'Pix analytics', repo_url: null })],
      [makeDomain({ name: 'Payments', members: [] })],
    )
    expect(items.map((i) => i.key)).toEqual(['review', 'repo', 'quality', 'maintainer'])
    expect(items[0]).toMatchObject({ title: '1 contract waiting for review', detail: 'pix', warn: true })
    expect(items[1]).toMatchObject({ title: '1 product without a repository', warn: false })
    expect(items[1].detail).toContain('Pix analytics')
    expect(items[2]).toMatchObject({ title: '1 contract without quality rules', detail: 'Includes 1 Tier 1 contract', warn: true })
    expect(items[3]).toMatchObject({ title: 'Payments has no maintainer' })
  })

  it('names the contracts when none of the ones without rules is Tier 1', () => {
    const [item] = buildAttention([makeContract({ title: 'orders', tier: 3 })], [], [])
    expect(item).toMatchObject({ key: 'quality', warn: false, detail: 'orders' })
  })

  it('counts several domains without a maintainer', () => {
    const [item] = buildAttention([], [], [makeDomain({ id: 'a', members: [] }), makeDomain({ id: 'b', members: [] })])
    expect(item.title).toBe('2 domains have no maintainer')
  })
})

describe('buildRecent', () => {
  it('merges contracts and products, newest first, each with its own domain and status', () => {
    const contract = makeContract({ id: 'c1', domain: 'Sales', status: 'draft', tier: 1, owner: 'alice', updated_at: '2026-01-02T00:00:00Z' })
    const rows = buildRecent(
      [contract],
      [
        makeProduct({ id: 'p1', domain: 'Risk', status: 'proposed', updated_at: '2026-01-03T00:00:00Z' }),
        makeProduct({ id: 'p2', updated_at: '2026-01-01T00:00:00Z' }),
      ],
    )
    expect(rows.map((r) => r.key)).toEqual(['p-p1', 'c-c1', 'p-p2'])
    expect(rows[0]).toEqual({
      key: 'p-p1',
      kind: 'product',
      name: 'Orders product',
      to: '/data-products/p1',
      domain: 'Risk',
      status: 'proposed',
      updatedAt: '2026-01-03T00:00:00Z',
    })
    expect(rows[1]).toMatchObject({ kind: 'contract', to: '/data-contracts/c1', domain: 'Sales', status: 'draft', tier: 1, owner: 'alice' })
  })
})

describe('buildDomainCards', () => {
  it('counts contracts, products and members per domain', () => {
    const contracts = [
      makeContract({ id: 'c1', domain_id: 'd1', status: 'active' }),
      makeContract({ id: 'c2', domain_id: 'd1', status: 'draft' }),
      makeContract({ id: 'c3', domain_id: 'd2' }),
    ]
    const products = [makeProduct({ id: 'p1', domain_id: 'd1' }), makeProduct({ id: 'p2', domain_id: 'd2' })]
    const [card] = buildDomainCards([makeDomain({ id: 'd1', members: [] })], contracts, products)
    expect(card).toMatchObject({ contracts: 2, products: 1, members: 0, noMaintainer: true })
    expect(card.counts).toMatchObject({ active: 1, draft: 1 })
  })
})
