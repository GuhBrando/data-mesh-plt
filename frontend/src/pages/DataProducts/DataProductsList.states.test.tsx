import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import DataProductsList from './index'
import {
  useDataProducts,
  useCreateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'
import { makeProduct } from '../../test/fixtures'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const mod = await importOriginal<typeof import('react-router-dom')>()
  return { ...mod, useNavigate: () => mockNavigate }
})

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProducts: vi.fn(),
  useCreateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))

// The form has its own tests; these cover the page only.
vi.mock('./DataProductForm', () => ({
  default: () => <button type="button">Create Product</button>,
}))

const product = makeProduct({
  id: 'prod-1',
  name: 'Sales Product',
  description: 'A'.repeat(120), // long description -> exercises truncation branch
  repo_url: null,
})

function renderList() {
  return render(
    <MemoryRouter>
      <DataProductsList />
    </MemoryRouter>,
  )
}

function setMutations(overrides: {
  create?: Record<string, unknown>
  del?: Record<string, unknown>
} = {}) {
  vi.mocked(useCreateDataProduct).mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.create,
  } as never)
  vi.mocked(useDeleteDataProduct).mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.del,
  } as never)
}

describe('DataProductsList — states & flows', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    setMutations()
  })

  it('shows a spinner while loading', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never)
    renderList()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('shows an error message when the query fails', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('boom'),
    } as never)
    renderList()
    expect(screen.getByText('boom')).toBeInTheDocument()
  })

  it('shows the empty state when there are no products', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as never)
    renderList()
    expect(screen.getByText('No data products yet')).toBeInTheDocument()
  })

  it('opens the create modal from the header button', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [product],
      isLoading: false,
      error: null,
    } as never)
    renderList()
    fireEvent.click(screen.getByRole('button', { name: /New Data Product/i }))
    expect(screen.getByRole('button', { name: 'Create Product' })).toBeInTheDocument()
  })

  it('navigates to the detail page when a row is clicked', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [product],
      isLoading: false,
      error: null,
    } as never)
    renderList()
    fireEvent.click(screen.getAllByText('Sales Product')[0])
    expect(mockNavigate).toHaveBeenCalledWith('/data-products/prod-1')
  })

  it('opens the delete modal and confirms deletion', async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useDataProducts).mockReturnValue({
      data: [product],
      isLoading: false,
      error: null,
    } as never)
    setMutations({ del: { mutateAsync } })
    renderList()

    fireEvent.click(screen.getAllByTitle('Delete')[0])
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith('prod-1'))
  })

  it('renders the create error message when the mutation fails', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [product],
      isLoading: false,
      error: null,
    } as never)
    setMutations({ create: { isError: true, error: new Error('create failed') } })
    renderList()
    fireEvent.click(screen.getByRole('button', { name: /New Data Product/i }))
    expect(screen.getByText('create failed')).toBeInTheDocument()
  })
})
