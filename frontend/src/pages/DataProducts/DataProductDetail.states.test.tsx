import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataProductDetail from './DataProductDetail'
import {
  useDataProduct,
  useUpdateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const mod = await importOriginal<typeof import('react-router-dom')>()
  return { ...mod, useNavigate: () => mockNavigate }
})

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProduct: vi.fn(),
  useUpdateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))

// The detail page joins the product to its contract; these tests cover the product only.
vi.mock('../../hooks/useDataContracts', () => ({
  useDataContract: () => ({ data: undefined, isLoading: false, error: null }),
}))

// The product form lists the contracts the user can pick; these tests cover the page only.
vi.mock('../../hooks/useSelectableContracts', () => ({
  useSelectableContracts: () => ({ contracts: [], isLoading: false, error: null }),
}))

const product = {
  id: 'prod-123',
  name: 'My Product',
  description: 'A test product',
  data_contracts_id: 'contract-abc',
  repo_url: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/data-products/prod-123']}>
      <Routes>
        <Route path="/data-products/:id" element={<DataProductDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

function setMutations(overrides: {
  update?: Record<string, unknown>
  del?: Record<string, unknown>
} = {}) {
  vi.mocked(useUpdateDataProduct).mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.update,
  } as never)
  vi.mocked(useDeleteDataProduct).mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.del,
  } as never)
}

describe('DataProductDetail — states & flows', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    setMutations()
  })

  it('shows a spinner while loading', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never)
    renderDetail()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('shows an error state with a back link', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('not found'),
    } as never)
    renderDetail()
    expect(screen.getByText('not found')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to list' }))
    expect(mockNavigate).toHaveBeenCalledWith('/data-products')
  })

  it('renders product details', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: product,
      isLoading: false,
      error: null,
    } as never)
    renderDetail()
    expect(screen.getByRole('heading', { name: 'My Product' })).toBeInTheDocument()
    expect(screen.getByText('A test product')).toBeInTheDocument()
  })

  it('navigates to the data contract when the contract id is clicked', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: product,
      isLoading: false,
      error: null,
    } as never)
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: 'contract-abc' }))
    expect(mockNavigate).toHaveBeenCalledWith('/data-contracts/contract-abc')
  })

  it('opens the edit modal with prefilled values', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: product,
      isLoading: false,
      error: null,
    } as never)
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /Edit/i }))
    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
  })

  it('opens the delete modal and confirms deletion', async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useDataProduct).mockReturnValue({
      data: product,
      isLoading: false,
      error: null,
    } as never)
    setMutations({ del: { mutateAsync } })
    renderDetail()

    fireEvent.click(screen.getByRole('button', { name: /Delete/i }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith('prod-123'))
    expect(mockNavigate).toHaveBeenCalledWith('/data-products')
  })

  it('renders the update error message inside the edit modal', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: product,
      isLoading: false,
      error: null,
    } as never)
    setMutations({ update: { isError: true, error: new Error('update failed') } })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /Edit/i }))
    expect(screen.getByText('update failed')).toBeInTheDocument()
  })
})
