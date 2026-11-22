import { describe, it, expect } from 'vitest'
import { getDomainAccess, selectableContracts } from './domains'
import { makeContract, makeDomain } from '../test/fixtures'
import type { DomainWithMembers } from '../types'

const domain: DomainWithMembers = {
  id: '1',
  name: 'Analytics',
  description: 'Core analytics',
  owner_id: 'user-alice',
  owner_username: 'alice',
  members: [
    { user_id: 'user-bob', username: 'bob', role: 'maintainer' },
    { user_id: 'user-carol', username: 'carol', role: 'member' },
  ],
  contract_count: 2,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

describe('getDomainAccess', () => {
  it('returns "owner" for the domain owner', () => {
    expect(getDomainAccess(domain, 'user-alice')).toBe('owner')
  })

  it('returns "maintainer" for a maintainer member', () => {
    expect(getDomainAccess(domain, 'user-bob')).toBe('maintainer')
  })

  it('returns "member" for a regular member', () => {
    expect(getDomainAccess(domain, 'user-carol')).toBe('member')
  })

  it('returns "none" for a user not in the domain', () => {
    expect(getDomainAccess(domain, 'user-dave')).toBe('none')
  })

  it('owner check takes precedence even if owner is also listed as a member', () => {
    const d: DomainWithMembers = {
      ...domain,
      members: [
        ...domain.members,
        { user_id: 'user-alice', username: 'alice', role: 'member' },
      ],
    }
    expect(getDomainAccess(d, 'user-alice')).toBe('owner')
  })

  it('returns "admin" for a PLATFORM_ADMIN regardless of domain membership', () => {
    expect(getDomainAccess(domain, 'user-dave', 'PLATFORM_ADMIN')).toBe('admin')
  })

  it('returns "admin" for a PLATFORM_ADMIN even when they are the domain owner', () => {
    expect(getDomainAccess(domain, 'user-alice', 'PLATFORM_ADMIN')).toBe('admin')
  })

  it('returns "owner" without userRole argument (backward-compatible)', () => {
    expect(getDomainAccess(domain, 'user-alice')).toBe('owner')
  })
})

describe('selectableContracts', () => {
  const sales = makeDomain({ id: 'd-sales', name: 'Sales', owner_id: 'u-owner', members: [{ user_id: 'u-member', username: 'm', role: 'member' }] })
  const risk = makeDomain({ id: 'd-risk', name: 'Risk', owner_id: 'u-other', members: [] })
  const contracts = [
    makeContract({ id: 'c-retired', title: 'a_retired', domain_id: 'd-sales', status: 'retired' }),
    makeContract({ id: 'c-draft', title: 'b_draft', domain_id: 'd-sales', status: 'draft' }),
    makeContract({ id: 'c-active', title: 'c_active', domain_id: 'd-sales', status: 'active' }),
    makeContract({ id: 'c-risk', title: 'risk', domain_id: 'd-risk', status: 'active' }),
  ]
  const ids = (cs: { id: string }[]) => cs.map((c) => c.id)

  it('returns nothing without a signed-in user', () => {
    expect(selectableContracts(contracts, [sales, risk], null)).toEqual([])
  })

  it('keeps only contracts of domains the user owns or belongs to, active first', () => {
    const owner = { id: 'u-owner', role: 'DATA_OWNER' }
    const member = { id: 'u-member', role: 'DATA_STEWARD' }
    expect(ids(selectableContracts(contracts, [sales, risk], owner))).toEqual(['c-active', 'c-draft', 'c-retired'])
    expect(ids(selectableContracts(contracts, [sales, risk], member))).toEqual(['c-active', 'c-draft', 'c-retired'])
  })

  it('returns nothing to a user outside every domain', () => {
    expect(selectableContracts(contracts, [sales, risk], { id: 'u-nobody', role: 'DATA_CONSUMER' })).toEqual([])
  })

  it('gives a platform admin every contract, even before domains load', () => {
    const admin = { id: 'u-admin', role: 'PLATFORM_ADMIN' }
    expect(ids(selectableContracts(contracts, [], admin))).toEqual(['c-active', 'c-risk', 'c-draft', 'c-retired'])
  })

  it('keeps the current contract, at the top, even outside the user domains', () => {
    const owner = { id: 'u-owner', role: 'DATA_OWNER' }
    expect(ids(selectableContracts(contracts, [sales, risk], owner, 'c-risk'))).toEqual([
      'c-risk',
      'c-active',
      'c-draft',
      'c-retired',
    ])
  })

  it('does not mutate its input', () => {
    const before = ids(contracts)
    selectableContracts(contracts, [sales, risk], { id: 'u-admin', role: 'PLATFORM_ADMIN' })
    expect(ids(contracts)).toEqual(before)
  })
})
