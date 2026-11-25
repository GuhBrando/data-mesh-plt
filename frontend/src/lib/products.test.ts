import { describe, it, expect } from 'vitest'
import {
  MANAGEMENT_CONTENTS,
  PRODUCT_STATUSES,
  PRODUCT_TYPES,
  isMajorMove,
  newerVersion,
  producersByContract,
  publishOutput,
  removablePort,
  removePort,
  slugify,
  switchInput,
  toInput,
} from './products'
import { makeInput, makeOutput, makeProduct } from '../test/fixtures'
import type { ContractSummary } from '../types'

const v11: ContractSummary = { title: 'Orders', status: 'active', version: '1.1.0', domain: 'Sales' }
const v20: ContractSummary = { ...v11, version: '2.0.0' }

describe('PRODUCT_STATUSES', () => {
  it('are the five ODPS values, in lifecycle order', () => {
    expect(PRODUCT_STATUSES).toEqual(['proposed', 'draft', 'active', 'deprecated', 'retired'])
  })
})

describe('slugify', () => {
  it('turns a title into a port name', () => {
    expect(slugify('Exposição de Crédito')).toBe('exposicao-de-credito')
    expect(slugify('  Orders / EU  ')).toBe('orders-eu')
    expect(slugify('???')).toBe('')
  })
})

describe('toInput', () => {
  it('keeps what the API takes and drops what it computes', () => {
    const product = makeProduct({
      input_ports: [makeInput({ id: 'i1', tags: ['raw'], contract: v11, produced_by: [{ id: 'p9', name: 'X', status: 'active' }] })],
      output_ports: [makeOutput({ id: 'o1', contract: v11, consumed_by: [], sbom: [{ url: 'https://sbom' }] })],
      management_ports: [{ id: 'm1', name: 'metrics', content: 'observability', type: 'rest', url: null, deprecated: false }],
    })
    const input = toInput(product)
    expect(input).toEqual({
      name: product.name,
      description: product.description,
      domain_id: product.domain_id,
      status: product.status,
      version: null,
      type: null,
      tenant: null,
      tags: [],
      synonyms: [],
      context: {},
      team: {},
      support: [],
      custom_properties: [],
      authoritative_definitions: [],
      input_ports: [
        {
          name: 'orders',
          contract_id: 'c1',
          version: '1.0.0',
          deprecated: false,
          authoritative_definitions: [],
          tags: ['raw'],
          custom_properties: [],
        },
      ],
      output_ports: [
        {
          name: 'orders',
          contract_id: 'c1',
          version: '1.0.0',
          type: 'tables',
          description: null,
          deprecated: false,
          authoritative_definitions: [],
          input_contracts: [],
          tags: [],
          custom_properties: [],
          synonyms: [],
          context: {},
          sbom: [{ url: 'https://sbom' }],
        },
      ],
      management_ports: [{ name: 'metrics', content: 'observability', type: 'rest', url: null, deprecated: false }],
    })
  })

  it('carries the ODPS sections it is given', () => {
    const team = { name: 'Risk', members: [{ username: 'ana', name: '', role: 'owner', date_in: '2026-01-01' }] }
    const input = toInput(makeProduct({ version: '${V}', tags: ['risk'], team }))
    expect(input.team).toEqual(team)
    expect([input.version, input.tags]).toEqual(['${V}', ['risk']])
  })
})

describe('ODPS suggestions', () => {
  it('lists the product types and management contents ODPS names', () => {
    expect(PRODUCT_TYPES).toEqual(['sourceAligned', 'aggregate', 'consumerAligned'])
    expect(MANAGEMENT_CONTENTS).toEqual(['discoverability', 'observability', 'control', 'dictionary'])
  })
})

describe('newerVersion', () => {
  it('is the contract version when the port is pinned to an older one', () => {
    expect(newerVersion(makeOutput({ contract: v11 }))).toBe('1.1.0')
  })

  it('is null when the port is current or has no contract', () => {
    expect(newerVersion(makeOutput({ version: '1.1.0', contract: v11 }))).toBeNull()
    expect(newerVersion(makeOutput({ contract_id: null, version: null, contract: null }))).toBeNull()
  })
})

describe('isMajorMove', () => {
  it('compares the major part of two semver versions', () => {
    expect(isMajorMove('1.2.0', '2.0.0')).toBe(true)
    expect(isMajorMove('1.2.0', '1.3.0')).toBe(false)
  })

  it('is false when either version is not semver', () => {
    expect(isMajorMove('1.0', '2.0.0')).toBe(false)
    expect(isMajorMove(null, '2.0.0')).toBe(false)
  })
})

describe('publishOutput', () => {
  const old = makeOutput({ id: 'o1', contract: v11, description: 'd', input_contracts: [{ contract_id: 'c9', version: '3.0.0' }] })

  it('adds the new version right after the old row, built from the same inputs', () => {
    const product = makeProduct({ output_ports: [old, makeOutput({ name: 'alert', contract_id: null, version: null })] })
    const { output_ports } = publishOutput(product, 0, { deprecateOld: false })
    expect(output_ports.map((p) => [p.name, p.version, p.deprecated])).toEqual([
      ['orders', '1.0.0', false],
      ['orders', '1.1.0', false],
      ['alert', null, false],
    ])
    expect(output_ports[1]).toMatchObject({ type: 'tables', description: 'd', input_contracts: old.input_contracts })
  })

  it('marks the old row deprecated when asked', () => {
    const { output_ports } = publishOutput(makeProduct({ output_ports: [old] }), 0, { deprecateOld: true })
    expect(output_ports.map((p) => p.deprecated)).toEqual([true, false])
  })
})

describe('switchInput', () => {
  it('adds the new version of the same contract after the old input', () => {
    const product = makeProduct({ input_ports: [makeInput({ contract: v20 })] })
    const { input_ports } = switchInput(product, 0)
    expect(input_ports.map((p) => [p.name, p.contract_id, p.version])).toEqual([
      ['orders', 'c1', '1.0.0'],
      ['orders', 'c1', '2.0.0'],
    ])
  })
})

describe('removablePort', () => {
  it('offers an old output once no product consumes it', () => {
    const product = makeProduct({
      output_ports: [makeOutput(), makeOutput({ version: '1.1.0' })],
    })
    expect(removablePort(product, 'output', 0)).toBe(true)
  })

  it('keeps an output that still has consumers', () => {
    const product = makeProduct({
      output_ports: [makeOutput({ consumed_by: [{ id: 'p2', name: 'B', status: 'active' }] }), makeOutput({ version: '1.1.0' })],
    })
    expect(removablePort(product, 'output', 0)).toBe(false)
  })

  it('never offers a port that is not in a version move', () => {
    expect(removablePort(makeProduct(), 'output', 0)).toBe(false)
    expect(removablePort(makeProduct({ input_ports: [makeInput()] }), 'input', 0)).toBe(false)
  })

  it('keeps an input that an output is built from', () => {
    const inputs = [makeInput(), makeInput({ version: '2.0.0' })]
    const cited = makeProduct({
      input_ports: inputs,
      output_ports: [makeOutput({ input_contracts: [{ contract_id: 'c1', version: '1.0.0' }] })],
    })
    expect(removablePort(cited, 'input', 0)).toBe(false)
    expect(removablePort(cited, 'input', 1)).toBe(true)
  })
})

describe('removePort', () => {
  it('drops one row of one role', () => {
    const product = makeProduct({ input_ports: [makeInput(), makeInput({ version: '2.0.0' })] })
    const input = removePort(product, 'input', 0)
    expect(input.input_ports.map((p) => p.version)).toEqual(['2.0.0'])
    expect(input.output_ports).toHaveLength(1)
  })
})

describe('producersByContract', () => {
  it('lists each producing product once per contract', () => {
    const a = makeProduct({ id: 'pa', name: 'A', output_ports: [makeOutput(), makeOutput({ version: '1.1.0' })] })
    const b = makeProduct({ id: 'pb', name: 'B', status: 'draft', output_ports: [makeOutput({ contract_id: null, version: null })] })
    const producers = producersByContract([a, b])
    expect(producers.get('c1')).toEqual([{ id: 'pa', name: 'A', status: 'active' }])
    expect([...producers.keys()]).toEqual(['c1'])
  })
})
