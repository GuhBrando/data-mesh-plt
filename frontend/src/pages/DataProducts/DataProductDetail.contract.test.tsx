import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataProductDetail from './DataProductDetail'
import { useDataProduct, useDeleteDataProduct, useUpdateDataProduct } from '../../hooks/useDataProducts'
import { useDataContract } from '../../hooks/useDataContracts'
import { makeContract, makeProduct } from '../../test/fixtures'
import type { SchemaField } from '../../types'

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProduct: vi.fn(),
  useUpdateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))
vi.mock('../../hooks/useDataContracts', () => ({ useDataContract: vi.fn() }))

const field = (name: string, primary_key = false) =>
  ({ name, type: 'string', primary_key, nullable: false, description: '', classification: '', unique: false, physical_type: '' }) as SchemaField

const mutation = { mutateAsync: vi.fn(), isPending: false, isError: false, error: null } as never

function renderDetail() {
  render(
    <MemoryRouter initialEntries={['/data-products/p1']}>
      <Routes>
        <Route path="/data-products/:id" element={<DataProductDetail />} />
        <Route path="/data-contracts/:id" element={<p>contract page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(useUpdateDataProduct).mockReturnValue(mutation)
  vi.mocked(useDeleteDataProduct).mockReturnValue(mutation)
})

describe('DataProductDetail with its contract', () => {
  it('shows the contract, its owner and a preview of the schema', () => {
    vi.mocked(useDataProduct).mockReturnValue({ data: makeProduct(), isLoading: false, error: null } as never)
    vi.mocked(useDataContract).mockReturnValue({
      data: makeContract({
        title: 'orders_contract',
        owner: 'carla',
        status: 'in_review',
        models: { fields: ['id', 'a', 'b', 'c', 'd', 'e', 'f'].map((n, i) => field(n, i === 0)), quality: [] },
      }),
    } as never)
    renderDetail()

    expect(screen.getByText('Sales')).toBeInTheDocument()
    expect(screen.getAllByText('In review')).toHaveLength(2)
    expect(screen.getByText('carla')).toBeInTheDocument()
    expect(screen.getByText('Schema · 7 fields')).toBeInTheDocument()
    expect(screen.getByText('PK')).toBeInTheDocument()
    expect(screen.queryByText('f')).toBeNull()
    expect(screen.getByRole('link', { name: 'Open repository' })).toHaveAttribute('href', 'https://github.com/org/orders')

    fireEvent.click(screen.getByRole('button', { name: 'Open the data contract' }))
    expect(screen.getByText('contract page')).toBeInTheDocument()
  })

  it('says the repository is still being provisioned', () => {
    vi.mocked(useDataProduct).mockReturnValue({ data: makeProduct({ repo_url: null }), isLoading: false, error: null } as never)
    vi.mocked(useDataContract).mockReturnValue({ data: makeContract({ models: { fields: [field('id')], quality: [] } }) } as never)
    renderDetail()

    expect(screen.getByText('Provisioning in progress')).toBeInTheDocument()
    expect(screen.getByText('Schema · 1 field')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'orders' }))
    expect(screen.getByText('contract page')).toBeInTheDocument()
  })
})
