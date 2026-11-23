import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import DataProductsList from './index'
import { useDataProducts, useCreateDataProduct, useDeleteDataProduct } from '../../hooks/useDataProducts'
import { useDataContracts } from '../../hooks/useDataContracts'
import { makeContract, makeProduct } from '../../test/fixtures'

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProducts: vi.fn(),
  useCreateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))
vi.mock('../../hooks/useDataContracts', () => ({ useDataContracts: vi.fn() }))

// The product form lists the contracts the user can pick; these tests cover the page only.
vi.mock('../../hooks/useSelectableContracts', () => ({
  useSelectableContracts: () => ({ contracts: [], isLoading: false, error: null }),
}))

const contracts = [
  makeContract({ id: 'c1', title: 'orders_contract', domain: 'Sales', version: '2.0.1', tier: 1 }),
  makeContract({ id: 'c2', title: 'exposure_contract', domain: 'Risk', status: 'in_review', owner: 'carla' }),
]
const products = [
  makeProduct({ id: 'p1', name: 'Orders', data_contracts_id: 'c1', updated_at: '2026-01-02T00:00:00Z' }),
  makeProduct({ id: 'p2', name: 'Exposure', data_contracts_id: 'c2', repo_url: null }),
  makeProduct({ id: 'p3', name: 'Orphan', data_contracts_id: 'gone', description: 'No contract here' }),
]

function renderAt(path = '/data-products') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <DataProductsList />
    </MemoryRouter>,
  )
}

const mutation = { mutateAsync: vi.fn(), isPending: false, isError: false, error: null } as never

beforeEach(() => {
  vi.mocked(useDataProducts).mockReturnValue({ data: products, isLoading: false, error: null } as never)
  vi.mocked(useDataContracts).mockReturnValue({ data: contracts } as never)
  vi.mocked(useCreateDataProduct).mockReturnValue(mutation)
  vi.mocked(useDeleteDataProduct).mockReturnValue(mutation)
})

const cardNames = () => screen.queryAllByRole('heading', { level: 3 }).map((h) => h.textContent)

describe('Marketplace', () => {
  it('joins each product to its contract', () => {
    renderAt()
    expect(screen.getByText('3 data products from 2 domains. Each one ships with a data contract.')).toBeInTheDocument()
    expect(screen.getByText('v2.0.1')).toBeInTheDocument()
    expect(screen.getByText('No contract found')).toBeInTheDocument()
    expect(screen.getByText('Provisioning')).toBeInTheDocument()
  })

  it('filters by domain', () => {
    renderAt()
    fireEvent.click(screen.getByRole('button', { name: /^Risk/ }))
    expect(cardNames()).toEqual(['Exposure'])
    fireEvent.click(screen.getByRole('button', { name: /^All domains/ }))
    expect(cardNames()).toHaveLength(3)
  })

  it('filters by text, including the contract and its owner', () => {
    renderAt('/data-products?q=carla')
    expect(cardNames()).toEqual(['Exposure'])
    fireEvent.change(screen.getByRole('textbox', { name: 'Filter data products' }), { target: { value: 'nothing matches' } })
    expect(screen.getByText('No data products match this filter.')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('textbox', { name: 'Filter data products' }), { target: { value: '' } })
    expect(cardNames()).toHaveLength(3)
  })

  it('switches to a list', () => {
    renderAt()
    fireEvent.click(screen.getByRole('button', { name: 'List view' }))
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toContain('Repository')
    fireEvent.click(screen.getByRole('button', { name: 'Grid view' }))
    expect(cardNames()).toHaveLength(3)
  })

  it('opens the create dialog from ?new=1', () => {
    renderAt('/data-products?new=1')
    expect(screen.getByRole('dialog')).toHaveTextContent('New Data Product')
  })
})
