import { render, screen } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataContractDetail from './DataContractDetail'
import { emptyServer } from './contractMetadata'
import { emptyRule, withType } from '../../lib/qualityRules'
import {
  useDataContract, useDataContractYaml, useDeleteDataContract, useUpdateDataContract,
} from '../../hooks/useDataContracts'

vi.mock('../../hooks/useDataContracts', () => ({
  useDataContract: vi.fn(), useDataContractYaml: vi.fn(), useDeleteDataContract: vi.fn(), useUpdateDataContract: vi.fn(),
}))
vi.mock('./DataContractForm', () => ({ default: () => null }))

const base = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { properties: [] },
  description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

function renderDetail(contract: object) {
  vi.mocked(useDataContract).mockReturnValue({ data: { ...base, ...contract }, isLoading: false, error: null } as never)
  render(
    <MemoryRouter initialEntries={['/data-contracts/c1']}>
      <Routes><Route path="/data-contracts/:id" element={<DataContractDetail />} /></Routes>
    </MemoryRouter>,
  )
}

describe('DataContractDetail metadata', () => {
  beforeEach(() => {
    const mutation = { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, isError: false, error: null }
    vi.mocked(useUpdateDataContract).mockReturnValue(mutation as never)
    vi.mocked(useDeleteDataContract).mockReturnValue(mutation as never)
    vi.mocked(useDataContractYaml).mockReturnValue({ data: undefined, isFetching: false } as never)
  })

  it('shows description, team, support and servers', () => {
    renderDetail({
      description: { purpose: 'Orders placed', usage: '', limitations: '' },
      team_members: [{ username: 'alice@example.com', name: 'Alice', role: 'owner' }],
      support: [{ channel: '#commerce', url: 'https://example.com/c', tool: 'slack', scope: 'issues' }],
      servers: [{ ...emptyServer(), server: 'prod', environment: 'prod', catalog: 'dmplt', schema_name: 'sales' }],
    })
    expect(screen.getByText('Orders placed')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://example.com/c' })).toHaveAttribute('href', 'https://example.com/c')
    expect(screen.getByText('dmplt.sales')).toBeInTheDocument()
  })

  it('hides sections the contract does not have', () => {
    renderDetail({})
    for (const heading of ['Description', 'Team Members', 'Support', 'Servers']) {
      expect(screen.queryByRole('heading', { name: heading })).toBeNull()
    }
  })

  it('shows a javascript: support url as text, not a link', () => {
    renderDetail({ support: [{ channel: 'c', url: 'javascript:alert(1)', tool: '', scope: '' }] })
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /javascript/ })).toBeNull()
  })

  it('shows field attributes, and renders a stored field without them', () => {
    renderDetail({ models: { fields: [
      { name: 'email', type: 'string', description: '', nullable: true, primary_key: false,
        classification: 'restricted', unique: true, physical_type: 'VARCHAR(255)' },
      { name: 'legacy', type: 'string', description: '', nullable: true, primary_key: false },
    ] } })
    expect(screen.getByText('restricted')).toBeInTheDocument()
    expect(screen.getByText('VARCHAR(255)')).toBeInTheDocument()
    expect(screen.getByText('legacy')).toBeInTheDocument()
  })

  it('lists library and text rules', () => {
    renderDetail({ models: { fields: [], quality: [
      { ...emptyRule(), column: 'email', operator: 'mustBeLessOrEqualTo', value: 1, unit: 'percent' },
      { ...withType(emptyRule(), 'text'), description: 'Totals reconcile with the ledger.' },
    ] } })
    expect(screen.getByText('nullValues ≤ 1 percent')).toBeInTheDocument()
    expect(screen.getByText('Totals reconcile with the ledger.')).toBeInTheDocument()
  })

  it('renders service levels', () => {
    renderDetail({ servicelevels: { properties: [
      { property: 'freshness', value: 24, unit: 'h' },
      { property: 'availability', value: 99.9, unit: '%' },
    ] } })
    expect(screen.getByText('24 h')).toBeInTheDocument()
    expect(screen.getByText('99.9 %')).toBeInTheDocument()
  })

  it('survives an unmigrated row', () => {
    renderDetail({ servicelevels: { freshness: '24h' } })
    expect(screen.getByText('No service levels')).toBeInTheDocument()
  })
})
