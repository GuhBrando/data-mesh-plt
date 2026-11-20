import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataContractDetail from './DataContractDetail'
import { emptyServer } from './contractMetadata'
import {
  useDataContract, useDataContractYaml, useDeleteDataContract, useUpdateDataContract,
} from '../../hooks/useDataContracts'

vi.mock('../../hooks/useDataContracts', () => ({
  useDataContract: vi.fn(), useDataContractYaml: vi.fn(), useDeleteDataContract: vi.fn(), useUpdateDataContract: vi.fn(),
}))
vi.mock('./DataContractForm', () => ({
  default: ({ onSubmit }: { onSubmit: (input: object) => void }) => (
    <button type="button" onClick={() => onSubmit({ title: 'New' })}>Submit form</button>
  ),
}))

const base = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { freshness: '', availability: '', retention: '', latency: '' },
  description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

const mutationOf = (over = {}) => ({
  mutate: vi.fn(), mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false, isError: false, error: null, ...over,
})
let mutation = mutationOf()

function renderDetail(contract: object, query: object = {}) {
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
})
