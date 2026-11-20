import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import DataProductsList from './index'
import {
  useDataProducts,
  useCreateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'

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

// The marketplace joins each product to its contract for domain, tier and status.
vi.mock('../../hooks/useDataContracts', () => ({
  useDataContracts: () => ({ data: [], isLoading: false, error: null }),
}))

const productWithRepo = {
  id: 'prod-1',
  name: 'Product With Repo',
  description: 'Has a GitHub repo',
  data_contracts_id: 'contract-1',
  repo_url: 'https://github.com/org/dp-test',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const productWithoutRepo = {
  id: 'prod-2',
  name: 'Product Without Repo',
  description: 'No GitHub repo yet',
  data_contracts_id: 'contract-2',
  repo_url: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

function renderList() {
  return render(
    <MemoryRouter>
      <DataProductsList />
    </MemoryRouter>
  )
}

describe('DataProductsList — GitHub button', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    vi.mocked(useCreateDataProduct).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    } as never)
    vi.mocked(useDeleteDataProduct).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    } as never)
  })

  it('renders a GitHub link for a row that has repo_url', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [productWithRepo],
      isLoading: false,
      error: null,
    } as never)

    renderList()

    const link = screen.getByTitle('Open GitHub repo')
    expect(link).toHaveAttribute('href', 'https://github.com/org/dp-test')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('does not render a GitHub link for a row without repo_url', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [productWithoutRepo],
      isLoading: false,
      error: null,
    } as never)

    renderList()

    expect(screen.queryByTitle('Open GitHub repo')).not.toBeInTheDocument()
  })

  it('renders GitHub links only for rows that have repo_url when the list is mixed', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [productWithRepo, productWithoutRepo],
      isLoading: false,
      error: null,
    } as never)

    renderList()

    expect(screen.getAllByTitle('Open GitHub repo')).toHaveLength(1)
  })

  it('clicking the GitHub link does not trigger row navigation', () => {
    vi.mocked(useDataProducts).mockReturnValue({
      data: [productWithRepo],
      isLoading: false,
      error: null,
    } as never)

    renderList()

    fireEvent.click(screen.getByTitle('Open GitHub repo'))

    expect(mockNavigate).not.toHaveBeenCalled()
  })
})
