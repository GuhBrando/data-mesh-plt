import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import DataProductsList from './index'
import { useDataProducts, useCreateDataProduct, useDeleteDataProduct } from '../../hooks/useDataProducts'
import { makeInput, makeOutput, makeProduct, makeProductInput } from '../../test/fixtures'
import type { DataProductInput } from '../../types'

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProducts: vi.fn(),
  useCreateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))

const CREATED: DataProductInput = makeProductInput({
  name: 'New',
  description: { purpose: 'A new product', usage: '', limitations: '' },
  status: 'draft',
})

// The form has its own tests; here it only hands the page a value.
vi.mock('./DataProductForm', () => ({
  default: ({ onSubmit }: { onSubmit: (v: DataProductInput) => void }) => (
    <button type="button" onClick={() => onSubmit(CREATED)}>
      Submit form
    </button>
  ),
}))

const cadastro = { title: 'Cadastro PF', status: 'active' as const, version: '1.0.0', domain: 'Clientes' }
const products = [
  makeProduct({ id: 'p1', name: 'Orders', domain: 'Sales', status: 'active', updated_at: '2026-01-03T00:00:00Z' }),
  makeProduct({
    id: 'p2',
    name: 'Exposure',
    domain: 'Risk',
    status: 'draft',
    repo_url: null,
    updated_at: '2026-01-02T00:00:00Z',
    output_ports: [makeOutput({ name: 'exposure' })],
    input_ports: [makeInput({ name: 'cad', contract: cadastro }), makeInput({ name: 'core', contract_id: null, version: null })],
  }),
  makeProduct({
    id: 'p3',
    name: 'Ledger',
    domain: 'Sales',
    status: 'deprecated',
    output_ports: [makeOutput({ name: 'ledger', contract_id: null, version: null })],
  }),
]

function renderAt(path = '/data-products') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <DataProductsList />
    </MemoryRouter>,
  )
}

const mutation = (over = {}) => ({ mutateAsync: vi.fn(), isPending: false, isError: false, error: null, ...over }) as never

beforeEach(() => {
  vi.mocked(useDataProducts).mockReturnValue({ data: products, isLoading: false, error: null } as never)
  vi.mocked(useCreateDataProduct).mockReturnValue(mutation())
  vi.mocked(useDeleteDataProduct).mockReturnValue(mutation())
})

const cardNames = () => screen.queryAllByRole('heading', { level: 3 }).map((h) => h.textContent)

describe('Marketplace', () => {
  it('shows each product with its own domain, status and ports', () => {
    renderAt()
    expect(screen.getByText('3 data products from 2 domains.')).toBeInTheDocument()
    const exposure = screen.getByRole('heading', { level: 3, name: 'Exposure' }).closest('article') as HTMLElement
    expect(within(exposure).getByText('Risk')).toBeInTheDocument()
    expect(within(exposure).getByText('Draft')).toBeInTheDocument()
    expect(within(exposure).getByText('1 output · 2 inputs')).toBeInTheDocument()
    expect(within(exposure).getByText('Provisioning')).toBeInTheDocument()
    expect(cardNames()).toEqual(['Orders', 'Exposure', 'Ledger'])
  })

  it('filters by domain', () => {
    renderAt()
    fireEvent.click(within(screen.getByRole('group', { name: 'Filter by domain' })).getByRole('button', { name: /^Risk/ }))
    expect(cardNames()).toEqual(['Exposure'])
    fireEvent.click(screen.getByRole('button', { name: /^All domains/ }))
    expect(cardNames()).toHaveLength(3)
  })

  it('filters by status, together with the domain', () => {
    renderAt()
    const statuses = screen.getByRole('group', { name: 'Filter by status' })
    expect(within(statuses).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'All statuses3',
      'Draft1',
      'Active1',
      'Deprecated1',
    ])
    fireEvent.click(within(statuses).getByRole('button', { name: /^Deprecated/ }))
    expect(cardNames()).toEqual(['Ledger'])
    fireEvent.click(within(screen.getByRole('group', { name: 'Filter by domain' })).getByRole('button', { name: /^Risk/ }))
    expect(screen.getByText('No data products match this filter.')).toBeInTheDocument()
  })

  it('filters by text, including port names and their contracts', () => {
    renderAt('/data-products?q=cadastro')
    expect(cardNames()).toEqual(['Exposure'])
    fireEvent.change(screen.getByRole('textbox', { name: 'Filter data products' }), { target: { value: 'ledger' } })
    expect(cardNames()).toEqual(['Ledger'])
    fireEvent.change(screen.getByRole('textbox', { name: 'Filter data products' }), { target: { value: 'nothing matches' } })
    expect(screen.getByText('No data products match this filter.')).toBeInTheDocument()
  })

  it('switches to a list', () => {
    renderAt()
    fireEvent.click(screen.getByRole('button', { name: 'List view' }))
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(
      expect.arrayContaining(['Domain', 'Status', 'Ports', 'Repository']),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Grid view' }))
    expect(cardNames()).toHaveLength(3)
  })

  it('opens the create dialog from ?new=1', () => {
    renderAt('/data-products?new=1')
    expect(screen.getByRole('dialog')).toHaveTextContent('New Data Product')
  })

  it('creates a product and shows the warnings the platform returned', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ ...products[0], warnings: ['Contract Orders is already published by Billing'] })
    vi.mocked(useCreateDataProduct).mockReturnValue(mutation({ mutateAsync }))
    renderAt('/data-products?new=1')
    fireEvent.click(screen.getByRole('button', { name: 'Submit form' }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(CREATED))
    expect(await screen.findByRole('status')).toHaveTextContent('already published by Billing')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
