import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataContractDetail from './DataContractDetail'
import { emptyServer } from './contractMetadata'
import { emptyRule, withType } from '../../lib/qualityRules'
import {
  useChangeContractStatus, useContractVersionYaml, useContractVersions,
  useDataContract, useDataContractYaml, useDeleteDataContract, useUpdateDataContract,
} from '../../hooks/useDataContracts'
import type { ContractVersion } from '../../types'

vi.mock('../../hooks/useDataContracts', () => ({
  useDataContract: vi.fn(), useDataContractYaml: vi.fn(), useDeleteDataContract: vi.fn(), useUpdateDataContract: vi.fn(),
  useContractVersions: vi.fn(), useContractVersionYaml: vi.fn(), useChangeContractStatus: vi.fn(),
  useContractPorts: () => ({ data: [], isLoading: false, isError: false }),
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
  permissions: { edit: true, delete: true, transitions: [], manage_stakeholders: false },
}
const NONE = { edit: false, delete: false, transitions: [], manage_stakeholders: false }

function mockVersions(rows: ContractVersion[]) {
  vi.mocked(useContractVersions).mockReturnValue({ data: rows, isLoading: false, isError: false } as never)
  vi.mocked(useContractVersionYaml).mockReturnValue({ data: undefined, isFetching: false } as never)
}

const mutationOf = (over = {}) => ({
  mutate: vi.fn(), mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false, isError: false, error: null, ...over,
})
let mutation = mutationOf()
let statusMutation = mutationOf()

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
  statusMutation = mutationOf()
  vi.mocked(useUpdateDataContract).mockReturnValue(mutation as never)
  vi.mocked(useChangeContractStatus).mockReturnValue(statusMutation as never)
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
    renderDetail({ status: 'in_review', permissions: { ...NONE, delete: true, transitions: ['draft', 'active'] } })
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(statusMutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'active' })
    fireEvent.click(screen.getByRole('button', { name: 'Request changes' }))
    expect(statusMutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'draft' })
  })

  it('submits a draft for review', () => {
    renderDetail({ status: 'draft', permissions: { ...NONE, edit: true, transitions: ['in_review'] } })
    expect(screen.getByText('Draft · only commerce and invited reviewers can see it.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Submit for review' }))
    expect(statusMutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'in_review' })
  })

  it('shows the error of a refused move in the bar', () => {
    statusMutation = mutationOf({ isError: true, error: new Error('The contract is now draft. Reload and try again.') })
    vi.mocked(useChangeContractStatus).mockReturnValue(statusMutation as never)
    renderDetail({ status: 'in_review', permissions: { ...NONE, transitions: ['draft', 'active'] } })
    expect(screen.getByText('The contract is now draft. Reload and try again.')).toBeInTheDocument()
  })

  it('shows only View YAML without permissions', () => {
    renderDetail({ status: 'active', permissions: NONE })
    expect(screen.getByRole('button', { name: /view yaml/i })).toBeInTheDocument()
    for (const name of [/^edit$/i, /^delete$/i, /deprecate/i, /retire/i]) {
      expect(screen.queryByRole('button', { name })).toBeNull()
    }
  })

  it('shows only View YAML when the contract comes without permissions', () => {
    renderDetail({ status: 'active', permissions: undefined })
    expect(screen.queryByRole('button', { name: /^edit$/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /^delete$/i })).toBeNull()
  })

  it('lets the owner deprecate an active contract from the header', () => {
    renderDetail({ status: 'active', permissions: { ...NONE, delete: true, transitions: ['deprecated', 'retired'] } })
    fireEvent.click(screen.getByRole('button', { name: 'Deprecate' }))
    expect(statusMutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'deprecated' })
  })

  it('retires only after confirmation', () => {
    renderDetail({ status: 'active', permissions: { ...NONE, transitions: ['deprecated', 'retired'] } })
    fireEvent.click(screen.getByRole('button', { name: 'Retire' }))
    expect(statusMutation.mutate).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: 'Retire contract' })).toHaveTextContent(
      'Retiring is permanent: the contract can no longer be edited or reactivated.')
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog', { name: 'Retire contract' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retire' }))
    const dialog = screen.getByRole('dialog', { name: 'Retire contract' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Retire' }))
    expect(statusMutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'retired' }, expect.anything())
  })

  it('retires a deprecated contract from the bar after confirmation', () => {
    renderDetail({ status: 'deprecated', permissions: { ...NONE, transitions: ['active', 'retired'] } })
    fireEvent.click(screen.getByRole('button', { name: 'Retire' }))
    const dialog = screen.getByRole('dialog', { name: 'Retire contract' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Retire' }))
    expect(statusMutation.mutate).toHaveBeenLastCalledWith({ id: 'c1', status: 'retired' }, expect.anything())
  })

  it('shows the draft message when the API refuses to read the contract', () => {
    const message = 'This contract is a draft. Only its domain and invited reviewers can read it.'
    renderDetail({}, { data: undefined, error: new Error(message) })
    expect(screen.getByText(message)).toBeInTheDocument()
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
    fireEvent.click(screen.getByRole('tab', { name: /quality/i }))
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
    fireEvent.click(screen.getByRole('tab', { name: /versions/i }))
    const rows = screen.getAllByTestId('version-row')
    expect(rows[0]).toHaveTextContent('1.1.0')
    expect(rows[0]).toHaveTextContent('current')
    expect(rows[1]).toHaveTextContent('1.0.0')
    expect(rows[1]).not.toHaveTextContent('current')
  })

  it('empty history shows the empty state', () => {
    renderDetail()
    fireEvent.click(screen.getByRole('tab', { name: /versions/i }))
    expect(screen.getByText('No history yet. It starts at the next version change.')).toBeInTheDocument()
  })

  it('shows a message when the history cannot load', () => {
    vi.mocked(useContractVersions).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never)
    renderDetail()
    fireEvent.click(screen.getByRole('tab', { name: /versions/i }))
    expect(screen.getByText('Could not load version history.')).toBeInTheDocument()
  })

  it('opens the YAML of the chosen version', async () => {
    mockVersions([{ version: '1.0.0', created_by: null, created_at: T1 }])
    vi.mocked(useContractVersionYaml).mockReturnValue({ data: 'version: 1.0.0', isFetching: false } as never)
    renderDetail()
    await userEvent.click(screen.getByRole('tab', { name: /versions/i }))
    await userEvent.click(screen.getByRole('button', { name: 'View YAML for version 1.0.0' }))
    expect(vi.mocked(useContractVersionYaml)).toHaveBeenLastCalledWith('c1', '1.0.0')
    expect(screen.getByText('version: 1.0.0')).toBeInTheDocument()
  })

  it('hides Edit on a retired contract, keeps Delete and tells it from a draft', () => {
    // What the API sends a domain owner for a retired contract.
    renderDetail({ status: 'retired', permissions: { ...NONE, delete: true } })
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    expect(screen.getAllByText('retired').some((el) => el.className.includes('purple'))).toBe(true)
  })
})

describe('DataContractDetail usage', () => {
  it('shows which data products produce and consume the contract', () => {
    renderDetail()
    expect(screen.getByRole('heading', { name: 'Usage' })).toBeInTheDocument()
    expect(screen.getByText('No data product uses this contract yet.')).toBeInTheDocument()
  })
})
