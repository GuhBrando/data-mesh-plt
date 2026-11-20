import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { makeContract, makeDomain, makeProduct, makeUser } from '../test/fixtures'

const toggle = vi.fn()
const logout = vi.fn()
let theme: 'light' | 'dark' = 'dark'

vi.mock('../contexts/ThemeContext', () => ({ useTheme: () => ({ theme, toggle }) }))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: makeUser({ username: 'ana.ribeiro' }), logout }) }))
vi.mock('../lib/api', () => ({ post: vi.fn().mockResolvedValue(undefined) }))
vi.mock('../lib/auth', () => ({ getRefreshToken: () => 'refresh' }))
vi.mock('../hooks/useDataProducts', () => ({ useDataProducts: () => ({ data: [makeProduct(), makeProduct({ id: 'p2' })] }) }))
vi.mock('../hooks/useDataContracts', () => ({ useDataContracts: () => ({ data: [makeContract()] }) }))
vi.mock('../hooks/useDomains', () => ({ useAllDomains: () => ({ data: [makeDomain()] }) }))
vi.mock('../hooks/useUsers', () => ({ useUsers: () => ({ data: undefined }) }))

function Where() {
  const { pathname, search } = useLocation()
  return <p data-testid="where">{pathname + search}</p>
}

function renderSidebar(path = '/dashboard') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <Sidebar />
              <Where />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  theme = 'dark'
  toggle.mockClear()
  logout.mockClear()
})

describe('Sidebar', () => {
  it('links every section with its count, and none for a query without data', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: /^Marketplace\s*2$/ })).toHaveAttribute('href', '/data-products')
    expect(screen.getByRole('link', { name: /^Data contracts\s*1$/ })).toHaveAttribute('href', '/data-contracts')
    expect(screen.getByRole('link', { name: /^Domains\s*1$/ })).toHaveAttribute('href', '/domains')
    expect(screen.getByRole('link', { name: 'Users' })).toHaveAttribute('href', '/users')
  })

  it('marks the current section', () => {
    renderSidebar('/data-products')
    expect(screen.getByRole('link', { name: /^Marketplace\s*2$/ })).toHaveAttribute('aria-current', 'page')
  })

  it('creates a contract or a product from the New menu', () => {
    renderSidebar()
    fireEvent.click(screen.getByRole('button', { name: 'New' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Data contract' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/data-contracts/new')

    fireEvent.click(screen.getByRole('button', { name: 'New' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Data product' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/data-products?new=1')
  })

  it('closes the New menu on Escape and on an outside click', () => {
    renderSidebar()
    fireEvent.click(screen.getByRole('button', { name: 'New' }))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'New' }))
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('shows the signed-in user and toggles the theme', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: /ana\.ribeiro/ })).toHaveAttribute('href', '/profile')
    fireEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
    expect(toggle).toHaveBeenCalledOnce()
  })

  it('offers dark mode from the light theme', () => {
    theme = 'light'
    renderSidebar()
    expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toBeInTheDocument()
  })

  it('signs out', async () => {
    renderSidebar()
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    await waitFor(() => expect(logout).toHaveBeenCalledOnce())
  })
})
