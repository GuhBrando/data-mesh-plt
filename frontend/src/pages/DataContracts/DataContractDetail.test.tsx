import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataContractDetail from './DataContractDetail'
import { emptyServer } from './contractMetadata'
import { emptyRule, withType } from '../../lib/qualityRules'
import {
  useContractVersionYaml, useContractVersions,
  useDataContract, useDataContractYaml, useDeleteDataContract, useUpdateDataContract,
} from '../../hooks/useDataContracts'
import type { ContractVersion } from '../../types'

vi.mock('../../hooks/useDataContracts', () => ({
  useDataContract: vi.fn(), useDataContractYaml: vi.fn(), useDeleteDataContract: vi.fn(), useUpdateDataContract: vi.fn(),
  useContractVersions: vi.fn(), useContractVersionYaml: vi.fn(),
}))
vi.mock('./DataContractForm', () => ({
  default: ({ onSubmit }: { onSubmit: (input: object) => void }) => (
    <button type="button" onClick={() => onSubmit({ title: 'New' })}>Submit form</button>
  ),
}))

const base = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { properties: [] },
  description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

function mockVersions(rows: ContractVersion[]) {
  vi.mocked(useContractVersions).mockReturnValue({ data: rows, isLoading: false, isError: false } as never)
  vi.mocked(useContractVersionYaml).mockReturnValue({ data: undefined, isFetching: false } as never)
}

const mutationOf = (over = {}) => ({
  mutate: vi.fn(), mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false, isError: false, error: null, ...over,
})
let mutation = mutationOf()

function renderDetail(contract: object = {}, query: object = {}) {
  vi.mocked(useDataContract).mockReturnValue(
    { data: { ...base, ...contract }, isLoading: false, error: null, ...query } as never,
  )
  render(
    <MemoryRouter initialEntries={['/data-contracts/c1']}>
      <Routes>
        <Route path="/data-contracts/:id" element={<DataContractDetail />} />
        <Route path="/data-contracts" element={<p>contract list</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mutation = mutationOf()
  vi.mocked(useUpdateDataContract).mockReturnValue(mutation as never)
  vi.mocked(useDeleteDataContract).mockReturnValue(mutation as never)
  vi.mocked(useDataContractYaml).mockReturnValue({ data: 'apiVersion: v3.2.0', isFetching: false } as never)
  mockVersions([])
})

describe('DataContractDetail states and actions', () => {
  it('shows a spinner while loading', () => {
    renderDetail({}, { data: undefined, isLoading: true })
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('shows the load error and goes back to the list', async () => {
    renderDetail({}, { data: undefined, error: new Error('Contract gone') })
    expect(screen.getByText('Contract gone')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to list' }))
    expect(await screen.findByText('contract list')).toBeInTheDocument()
  })

  it('approves or requests changes on a contract in review', () => {
    renderDetail({ status: 'in_review' })
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(mutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'active' })
    fireEvent.click(screen.getByRole('button', { name: 'Request Changes' }))
    expect(mutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'draft' })
  })

  it('opens the YAML, saves an edit and shows the mutation error', async () => {
    mutation = mutationOf({ isError: true, error: new Error('Save failed') })
    vi.mocked(useUpdateDataContract).mockReturnValue(mutation as never)
    renderDetail({})
    fireEvent.click(screen.getByRole('button', { name: /view yaml/i }))
    expect(screen.getByText('apiVersion: v3.2.0')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close modal' }))
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.getByText('Save failed')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Submit form' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Submit form' })).toBeNull())
    expect(mutation.mutateAsync).toHaveBeenCalledWith({ id: 'c1', title: 'New' })
  })

  it('deletes after confirmation and returns to the list', async () => {
    renderDetail({})
    fireEvent.click(screen.getByRole('button', { name: /delete/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.click(screen.getByRole('button', { name: /delete/i }))
    fireEvent.click(screen.getAllByRole('button', { name: /delete/i })[1])
    expect(await screen.findByText('contract list')).toBeInTheDocument()
    expect(mutation.mutateAsync).toHaveBeenCalledWith('c1')
  })
})

describe('DataContractDetail metadata', () => {
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

const T1 = '2026-01-01T10:00:00Z'
const T2 = '2026-02-01T10:00:00Z'

describe('DataContractDetail version history', () => {
  it('lists versions in the order the API returns and marks the current one', () => {
    mockVersions([{ version: '1.1.0', created_by: null, created_at: T2 },
                  { version: '1.0.0', created_by: null, created_at: T1 }])
    renderDetail({ version: '1.1.0' })
    const rows = screen.getAllByTestId('version-row')
    expect(rows[0]).toHaveTextContent('1.1.0')
    expect(rows[0]).toHaveTextContent('current')
    expect(rows[1]).toHaveTextContent('1.0.0')
    expect(rows[1]).not.toHaveTextContent('current')
  })

  it('empty history shows the empty state', () => {
    renderDetail()
    expect(screen.getByText('No history yet. It starts at the next version change.')).toBeInTheDocument()
  })

  it('shows a message when the history cannot load', () => {
    vi.mocked(useContractVersions).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never)
    renderDetail()
    expect(screen.getByText('Could not load version history.')).toBeInTheDocument()
  })

  it('opens the YAML of the chosen version', async () => {
    mockVersions([{ version: '1.0.0', created_by: null, created_at: T1 }])
    vi.mocked(useContractVersionYaml).mockReturnValue({ data: 'version: 1.0.0', isFetching: false } as never)
    renderDetail()
    await userEvent.click(screen.getByRole('button', { name: 'View YAML for version 1.0.0' }))
    expect(vi.mocked(useContractVersionYaml)).toHaveBeenLastCalledWith('c1', '1.0.0')
    expect(screen.getByText('version: 1.0.0')).toBeInTheDocument()
  })

  it('hides Edit on a retired contract, keeps Delete and tells it from a draft', () => {
    renderDetail({ status: 'retired' })
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    expect(screen.getAllByText('retired').some((el) => el.className.includes('purple'))).toBe(true)
  })
})
