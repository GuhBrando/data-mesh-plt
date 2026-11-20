import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from './Dashboard'
import { useDataContracts } from '../hooks/useDataContracts'
import { useDataProducts } from '../hooks/useDataProducts'
import { useAllDomains } from '../hooks/useDomains'
import { useUsers } from '../hooks/useUsers'
import { makeContract, makeDomain, makeProduct, makeUser } from '../test/fixtures'
import type { QualityRule } from '../types'

vi.mock('../hooks/useDataContracts', () => ({ useDataContracts: vi.fn() }))
vi.mock('../hooks/useDataProducts', () => ({ useDataProducts: vi.fn() }))
vi.mock('../hooks/useDomains', () => ({ useAllDomains: vi.fn() }))
vi.mock('../hooks/useUsers', () => ({ useUsers: vi.fn() }))
// Numbers render at their final value; the count-up has its own test.
vi.mock('../hooks/useCountUp', () => ({ useCountUp: (value: number) => value }))

const rule = { type: 'library', dimension: 'completeness', column: 'id' } as QualityRule

function query<T>(data: T, over: object = {}) {
  return { data, isLoading: false, isError: false, dataUpdatedAt: 0, ...over } as never
}

function setData({
  contracts = [makeContract({ models: { fields: [], quality: [rule] } })],
  products = [makeProduct()],
  domains = [makeDomain()],
  users = [makeUser(), makeUser({ id: 'u2', username: 'bob', role: 'user' })],
  contractsQuery = {},
}: {
  contracts?: ReturnType<typeof makeContract>[]
  products?: ReturnType<typeof makeProduct>[]
  domains?: ReturnType<typeof makeDomain>[]
  users?: ReturnType<typeof makeUser>[]
  contractsQuery?: object
} = {}) {
  vi.mocked(useDataContracts).mockReturnValue(query(contracts, contractsQuery))
  vi.mocked(useDataProducts).mockReturnValue(query(products))
  vi.mocked(useAllDomains).mockReturnValue(query(domains))
  vi.mocked(useUsers).mockReturnValue(query(users))
}

function renderDashboard() {
  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )
}

beforeEach(() => setData())

describe('Dashboard', () => {
  it('shows the key figures', () => {
    renderDashboard()
    const kpis = within(screen.getByRole('region', { name: 'Key figures' }))
    expect(kpis.getByRole('link', { name: /Data products\s*1/ })).toHaveAttribute('href', '/data-products')
    expect(kpis.getByText('1 of 1 with a repository')).toBeInTheDocument()
    expect(kpis.getByText('All with a maintainer')).toBeInTheDocument()
    expect(kpis.getByText('1 admin')).toBeInTheDocument()
  })

  it('shows a dash for a figure whose query failed', () => {
    vi.mocked(useUsers).mockReturnValue(query(undefined, { isError: true }))
    renderDashboard()
    expect(within(screen.getByRole('link', { name: /Users/ })).getByText('—')).toBeInTheDocument()
  })

  it('is all clear when nothing needs attention', () => {
    renderDashboard()
    expect(screen.getByText('All clear')).toBeInTheDocument()
  })

  it('lists what needs attention', () => {
    setData({
      contracts: [makeContract({ title: 'pix', status: 'in_review', tier: 1 })],
      products: [makeProduct({ repo_url: null })],
      domains: [makeDomain({ name: 'Payments', members: [] })],
    })
    renderDashboard()
    expect(screen.getByText('1 contract waiting for review')).toBeInTheDocument()
    expect(screen.getByText('1 product without a repository')).toBeInTheDocument()
    expect(screen.getByText('1 contract without quality rules')).toBeInTheDocument()
    expect(screen.getByText('Payments has no maintainer')).toBeInTheDocument()
  })

  it('breaks contracts down by status and tier', () => {
    setData({
      contracts: [
        makeContract({ id: 'a', status: 'active', tier: 1 }),
        makeContract({ id: 'b', status: 'draft', tier: 1 }),
      ],
    })
    renderDashboard()
    expect(screen.getByText('2 contracts')).toBeInTheDocument()
    expect(screen.getAllByText('50%')).toHaveLength(2)
  })

  it('shows a spinner while contracts load', () => {
    setData({ contracts: [], contractsQuery: { data: undefined, isLoading: true } })
    renderDashboard()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('filters recent updates by type', () => {
    setData({
      contracts: [makeContract({ id: 'c1', title: 'orders_contract', models: { fields: [], quality: [rule] } })],
      products: [makeProduct({ name: 'Orders product' })],
    })
    renderDashboard()
    expect(screen.getByRole('link', { name: /orders_contract/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Orders product/ })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^Products/ }))
    expect(screen.queryByRole('link', { name: /orders_contract/ })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /^Contracts/ }))
    expect(screen.queryByRole('link', { name: /Orders product/ })).toBeNull()
  })

  it('shows an empty state when there is nothing recent', () => {
    setData({ contracts: [], products: [] })
    renderDashboard()
    expect(screen.getByText('Nothing here yet.')).toBeInTheDocument()
  })

  it('shows a card per domain and flags a missing maintainer', () => {
    setData({ domains: [makeDomain({ name: 'Sales' }), makeDomain({ id: 'd2', name: 'Risk', members: [] })] })
    renderDashboard()
    expect(screen.getByRole('heading', { name: 'Domains' })).toBeInTheDocument()
    expect(screen.getByText('No maintainer')).toBeInTheDocument()
  })

  it('says when it last synced', () => {
    setData({ contractsQuery: { dataUpdatedAt: Date.now() } })
    renderDashboard()
    expect(screen.getByText('Synced just now')).toBeInTheDocument()
  })
})
