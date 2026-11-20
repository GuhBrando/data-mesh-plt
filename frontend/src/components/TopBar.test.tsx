import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import TopBar from './TopBar'

vi.mock('../hooks/useDataContracts', () => ({
  useDataContract: (id: string) => ({ data: id ? { title: 'orders_contract' } : undefined }),
}))
vi.mock('../hooks/useDataProducts', () => ({
  useDataProduct: (id: string) => ({ data: id ? { name: 'Orders product' } : undefined }),
}))

function Where() {
  const { pathname, search } = useLocation()
  return <p data-testid="where">{pathname + search}</p>
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <TopBar />
              <Where />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TopBar breadcrumbs', () => {
  it('names the section', () => {
    renderAt('/dashboard')
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Overview')
  })

  it('adds the contract title on a contract page', () => {
    renderAt('/data-contracts/c1')
    expect(screen.getByRole('link', { name: 'Data contracts' })).toHaveAttribute('href', '/data-contracts')
    expect(screen.getByText('orders_contract')).toHaveAttribute('aria-current', 'page')
  })

  it('reads "New contract" on the create page', () => {
    renderAt('/data-contracts/new')
    expect(screen.getByText('New contract')).toBeInTheDocument()
  })

  it('adds the product name on a product page', () => {
    renderAt('/data-products/p1')
    expect(screen.getByRole('link', { name: 'Marketplace' })).toBeInTheDocument()
    expect(screen.getByText('Orders product')).toBeInTheDocument()
  })
})

describe('TopBar search', () => {
  it('searches the marketplace', () => {
    renderAt('/dashboard')
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search data products' }), { target: { value: 'pix sales' } })
    fireEvent.submit(screen.getByRole('search'))
    expect(screen.getByTestId('where')).toHaveTextContent('/data-products?q=pix%20sales')
  })

  it('opens the marketplace when the search is empty', () => {
    renderAt('/dashboard')
    fireEvent.submit(screen.getByRole('search'))
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/data-products$/)
  })

  it('focuses the search on Ctrl+K', () => {
    renderAt('/dashboard')
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(screen.getByRole('searchbox')).toHaveFocus()
  })
})
