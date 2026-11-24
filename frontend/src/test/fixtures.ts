import type { DataContract, DataProduct, DomainWithMembers, InputPort, OutputPort, User } from '../types'

// Small builders for the catalog types; each test overrides only what it cares about.

export function makeContract(over: Partial<DataContract> = {}): DataContract {
  return {
    id: 'c1',
    title: 'orders',
    version: '1.0.0',
    owner: 'alice',
    domain: 'Sales',
    domain_id: 'd1',
    tier: 2,
    status: 'active',
    models: { fields: [], quality: [] },
    servicelevels: { properties: [] },
    description: { purpose: '', usage: '', limitations: '' },
    team_members: [],
    support: [],
    servers: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...over,
  }
}

export function makeInput(over: Partial<InputPort> = {}): InputPort {
  return {
    id: 'i1',
    name: 'orders',
    contract_id: 'c1',
    version: '1.0.0',
    deprecated: false,
    authoritative_definitions: [],
    contract: null,
    produced_by: [],
    ...over,
  }
}

export function makeOutput(over: Partial<OutputPort> = {}): OutputPort {
  return {
    id: 'o1',
    name: 'orders',
    contract_id: 'c1',
    version: '1.0.0',
    type: 'tables',
    description: null,
    deprecated: false,
    authoritative_definitions: [],
    input_contracts: [],
    contract: null,
    consumed_by: [],
    ...over,
  }
}

export function makeProduct(over: Partial<DataProduct> = {}): DataProduct {
  return {
    id: 'p1',
    name: 'Orders product',
    description: 'Orders, one row per order line.',
    domain_id: 'd1',
    domain: 'Sales',
    status: 'active',
    deprecated: false,
    input_ports: [],
    output_ports: [makeOutput()],
    repo_url: 'https://github.com/org/orders',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...over,
  }
}

export function makeDomain(over: Partial<DomainWithMembers> = {}): DomainWithMembers {
  return {
    id: 'd1',
    name: 'Sales',
    description: 'Sales domain',
    owner_id: 'u1',
    owner_username: 'alice',
    members: [{ user_id: 'u2', username: 'bob', role: 'maintainer' }],
    contract_count: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...over,
  }
}

export function makeUser(over: Partial<User> = {}): User {
  return { id: 'u1', username: 'alice', email: 'alice@example.com', role: 'admin', ...over }
}
