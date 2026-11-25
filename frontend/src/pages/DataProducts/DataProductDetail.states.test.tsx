import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataProductDetail from './DataProductDetail'
import { useDataProduct, useUpdateDataProduct, useDeleteDataProduct } from '../../hooks/useDataProducts'
import { makeInput, makeProduct, makeProductInput } from '../../test/fixtures'
import type { DataProductInput } from '../../types'

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

const EDITED: DataProductInput = makeProductInput({
  name: 'Edited',
  description: { purpose: 'Edited description', usage: '', limitations: '' },
  status: 'active',
})

// The form has its own tests; here it only hands the page a value.
vi.mock('./DataProductForm', () => ({
  default: ({ onSubmit }: { onSubmit: (v: DataProductInput) => void }) => (
    <button type="button" onClick={() => onSubmit(EDITED)}>
      Submit form
    </button>
  ),
}))

const product = makeProduct({
  id: 'prod-123',
  name: 'My Product',
  description: { purpose: 'A test product', usage: '', limitations: '' },
  domain: 'Risco',
  status: 'deprecated',
  repo_url: null,
  input_ports: [makeInput({ contract: { title: 'Cadastro', status: 'active', version: '1.1.0', domain: 'Clientes' } })],
})

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/data-products/prod-123']}>
      <Routes>
        <Route path="/data-products/:id" element={<DataProductDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

function mutation(over: Record<string, unknown> = {}) {
  return {
    mutateAsync: vi.fn().mockResolvedValue({ ...product, warnings: [] }),
    isPending: false,
    isError: false,
    error: null,
    ...over,
  }
}

function setMutations({ update = {}, del = {} }: { update?: Record<string, unknown>; del?: Record<string, unknown> } = {}) {
  const updating = mutation(update)
  vi.mocked(useUpdateDataProduct).mockReturnValue(updating as never)
  vi.mocked(useDeleteDataProduct).mockReturnValue(mutation(del) as never)
  return updating
}

function showProduct() {
  vi.mocked(useDataProduct).mockReturnValue({ data: product, isLoading: false, error: null } as never)
}

describe('DataProductDetail — states & flows', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    setMutations()
  })

  it('shows a spinner while loading', () => {
    vi.mocked(useDataProduct).mockReturnValue({ data: undefined, isLoading: true, error: null } as never)
    renderDetail()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('shows an error state with a back link', () => {
    vi.mocked(useDataProduct).mockReturnValue({ data: undefined, isLoading: false, error: new Error('not found') } as never)
    renderDetail()
    expect(screen.getByText('not found')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to list' }))
    expect(mockNavigate).toHaveBeenCalledWith('/data-products')
  })

  it('shows the product with its own domain, status and lineage', () => {
    showProduct()
    renderDetail()
    const heading = screen.getByRole('heading', { name: 'My Product' })
    const header = heading.parentElement as HTMLElement
    expect(within(header).getByText('Risco')).toBeInTheDocument()
    expect(within(header).getByText('Deprecated')).toBeInTheDocument()
    expect(screen.getByText('A test product')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Inputs' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Outputs' })).toBeInTheDocument()
  })

  it('saves a version move from the lineage and shows its warnings', async () => {
    showProduct()
    const updating = setMutations({
      update: {
        mutateAsync: vi.fn().mockResolvedValue({
          ...product,
          warnings: ['Input orders uses contract Cadastro, which is deprecated'],
        }),
      },
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: 'Switch' }))
    await waitFor(() => expect(updating.mutateAsync).toHaveBeenCalledOnce())
    const sent = updating.mutateAsync.mock.calls[0][0]
    expect(sent.id).toBe('prod-123')
    expect(sent.input_ports.map((p: { version: string }) => p.version)).toEqual(['1.0.0', '1.1.0'])
    expect(await screen.findByRole('status')).toHaveTextContent('which is deprecated')
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows why a lineage save failed', async () => {
    showProduct()
    setMutations({
      update: {
        mutateAsync: vi.fn().mockRejectedValue(new Error('Contract retired')),
        isError: true,
        error: new Error('Contract retired'),
      },
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: 'Switch' }))
    expect(await screen.findByText('Contract retired')).toBeInTheDocument()
  })

  it('saves the edit form, closes it and shows the warnings', async () => {
    showProduct()
    const updating = setMutations({
      update: { mutateAsync: vi.fn().mockResolvedValue({ ...product, warnings: ['Contract X belongs to domain Y'] }) },
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /Edit/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Submit form' }))
    await waitFor(() => expect(updating.mutateAsync).toHaveBeenCalledWith({ id: 'prod-123', ...EDITED }))
    expect(await screen.findByRole('status')).toHaveTextContent('Contract X belongs to domain Y')
    expect(screen.queryByRole('button', { name: 'Submit form' })).not.toBeInTheDocument()
  })

  it('opens the delete modal and confirms deletion', async () => {
    showProduct()
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    setMutations({ del: { mutateAsync } })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith('prod-123'))
    expect(mockNavigate).toHaveBeenCalledWith('/data-products')
  })

  it('renders the update error message inside the edit modal', () => {
    showProduct()
    setMutations({ update: { isError: true, error: new Error('update failed') } })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /Edit/i }))
    expect(within(screen.getByRole('dialog')).getByText('update failed')).toBeInTheDocument()
  })
})
