import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataProductDetail from './DataProductDetail'
import {
  useDataProduct,
  useUpdateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'
import { makeProduct } from '../../test/fixtures'

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProduct: vi.fn(),
  useUpdateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))

const baseProduct = makeProduct({ id: 'prod-123', name: 'My Product', description: 'A test product', repo_url: null })

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/data-products/prod-123']}>
      <Routes>
        <Route path="/data-products/:id" element={<DataProductDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('DataProductDetail — GitHub button', () => {
  beforeEach(() => {
    vi.mocked(useUpdateDataProduct).mockReturnValue({
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

  it('renders a GitHub link when repo_url is a non-empty string', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: { ...baseProduct, repo_url: 'https://github.com/org/dp-test' },
      isLoading: false,
      error: null,
    } as never)

    renderDetail()

    const link = screen.getByRole('link', { name: /github/i })
    expect(link).toHaveAttribute('href', 'https://github.com/org/dp-test')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('does not render a GitHub link when repo_url is null', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: { ...baseProduct, repo_url: null },
      isLoading: false,
      error: null,
    } as never)

    renderDetail()

    expect(screen.queryByRole('link', { name: /github/i })).not.toBeInTheDocument()
  })

  it('does not render a GitHub link when repo_url is undefined', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: { ...baseProduct },
      isLoading: false,
      error: null,
    } as never)

    renderDetail()

    expect(screen.queryByRole('link', { name: /github/i })).not.toBeInTheDocument()
  })

  it('does not render a GitHub link when repo_url is an empty string', () => {
    vi.mocked(useDataProduct).mockReturnValue({
      data: { ...baseProduct, repo_url: '' },
      isLoading: false,
      error: null,
    } as never)

    renderDetail()

    expect(screen.queryByRole('link', { name: /github/i })).not.toBeInTheDocument()
  })
})
