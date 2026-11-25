import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataProductDetail from './DataProductDetail'
import { useDataProduct, useDeleteDataProduct, useUpdateDataProduct } from '../../hooks/useDataProducts'
import { makeProduct } from '../../test/fixtures'
import type { DataProduct } from '../../types'

vi.mock('../../hooks/useDataProducts', () => ({
  useDataProduct: vi.fn(),
  useUpdateDataProduct: vi.fn(),
  useDeleteDataProduct: vi.fn(),
}))

const mutation = { mutateAsync: vi.fn(), isPending: false, isError: false, error: null } as never

beforeEach(() => {
  vi.mocked(useUpdateDataProduct).mockReturnValue(mutation)
  vi.mocked(useDeleteDataProduct).mockReturnValue(mutation)
})

function renderProduct(product: DataProduct) {
  vi.mocked(useDataProduct).mockReturnValue({ data: product, isLoading: false, error: null } as never)
  render(
    <MemoryRouter initialEntries={[`/data-products/${product.id}`]}>
      <Routes>
        <Route path="/data-products/:id" element={<DataProductDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

function panel(name: string) {
  return screen.getByRole('heading', { name }).closest('section') as HTMLElement
}

describe('DataProductDetail — ODPS sections', () => {
  it('shows the purpose, and usage and limitations when given', () => {
    renderProduct(makeProduct({ description: { purpose: 'Credit exposure', usage: 'Daily batch', limitations: 'No intraday' } }))
    const about = panel('About')
    expect(within(about).getByText('Credit exposure')).toBeInTheDocument()
    expect(within(about).getByText('Daily batch')).toBeInTheDocument()
    expect(within(about).getByText('No intraday')).toBeInTheDocument()
  })

  it('leaves out usage and limitations when empty', () => {
    renderProduct(makeProduct())
    expect(within(panel('About')).queryByText('Usage')).not.toBeInTheDocument()
  })

  it('lists the ODPS sections that are filled', () => {
    renderProduct(
      makeProduct({
        version: '1.2.0',
        type: 'consumerAligned',
        tenant: 'acme',
        tags: ['risk', 'credit'],
        team: { name: 'Risk', members: [{ username: 'ana' }, { username: 'bo' }] },
        support: [
          { channel: '#risk', url: 'https://chat/risk' },
          { channel: 'oncall', url: '${ONCALL_URL}' },
        ],
        management_ports: [{ name: 'metrics', content: 'observability', type: 'rest', deprecated: false }],
      }),
    )
    const details = panel('ODPS')
    for (const text of ['1.2.0', 'consumerAligned', 'acme', 'risk', 'credit', 'Risk', 'ana, bo', 'metrics']) {
      expect(within(details).getByText(text)).toBeInTheDocument()
    }
    expect(within(details).getByRole('link', { name: '#risk' })).toHaveAttribute('href', 'https://chat/risk')
    expect(within(details).queryByRole('link', { name: 'oncall' })).not.toBeInTheDocument()
    expect(within(details).getByText('oncall')).toBeInTheDocument()
    expect(within(details).getByText('observability · rest')).toBeInTheDocument()
  })

  it('has no ODPS panel when nothing is filled', () => {
    renderProduct(makeProduct())
    expect(screen.queryByRole('heading', { name: 'ODPS' })).not.toBeInTheDocument()
  })
})
