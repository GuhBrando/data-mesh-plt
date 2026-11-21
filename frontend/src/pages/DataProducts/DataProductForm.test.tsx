import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import DataProductForm from './DataProductForm'
import { useSelectableContracts } from '../../hooks/useSelectableContracts'
import { makeContract } from '../../test/fixtures'
import type { DataContract, DataProduct } from '../../types'

vi.mock('../../hooks/useSelectableContracts', () => ({ useSelectableContracts: vi.fn() }))

const existing: DataProduct = {
  id: 'prod-1',
  name: 'Existing Product',
  description: 'An existing data product description',
  data_contracts_id: 'c2',
  repo_url: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const contracts = [
  makeContract({
    id: 'c1',
    title: 'orders_contract',
    domain: 'Sales',
    version: '2.0.1',
    tier: 1,
    owner: 'alice',
    description: { purpose: 'One row per order line', usage: '', limitations: '' },
  }),
  makeContract({ id: 'c2', title: 'exposure_contract', domain: 'Risk', status: 'in_review', owner: 'carla' }),
]

function selectable(over: Partial<{ contracts: DataContract[]; isLoading: boolean; error: Error | null }> = {}) {
  vi.mocked(useSelectableContracts).mockReturnValue({ contracts, isLoading: false, error: null, ...over })
}

function renderForm(props: Partial<Parameters<typeof DataProductForm>[0]> = {}) {
  const onSubmit = vi.fn()
  render(<DataProductForm onSubmit={onSubmit} onCancel={vi.fn()} isSubmitting={false} {...props} />)
  return { onSubmit }
}

function fillNameAndDescription() {
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Valid Name' } })
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'A sufficiently long description' } })
}

beforeEach(() => selectable())

describe('DataProductForm', () => {
  it('renders the create button label without defaultValues', () => {
    renderForm()
    expect(screen.getByRole('button', { name: 'Create Product' })).toBeInTheDocument()
  })

  it('renders the save label and prefilled values in edit mode', () => {
    renderForm({ defaultValues: existing })
    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('Existing Product')
    expect(screen.getByRole('radio', { name: 'exposure_contract' })).toBeChecked()
    expect(useSelectableContracts).toHaveBeenCalledWith('c2')
  })

  it('calls onCancel when Cancel is clicked', () => {
    const onCancel = vi.fn()
    renderForm({ onCancel })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('lists the selectable contracts with their summary, instead of a UUID field', () => {
    renderForm()
    expect(screen.queryByLabelText('Data Contract ID')).not.toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Data contract' })).toBeInTheDocument()
    const orders = screen.getByRole('radio', { name: 'orders_contract' })
    expect(orders).toHaveAccessibleDescription(/Sales.*v2\.0\.1.*Active.*alice/)
    expect(screen.getByText('One row per order line')).toBeInTheDocument()
    expect(screen.getByText('2 available')).toBeInTheDocument()
  })

  it('shows validation errors and does not submit invalid data', async () => {
    const { onSubmit } = renderForm()
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    expect(await screen.findByText('Name must be at least 3 characters')).toBeInTheDocument()
    expect(screen.getByText('Select a data contract')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits the picked contract id when the form is valid', async () => {
    const { onSubmit } = renderForm()
    fillNameAndDescription()
    fireEvent.click(screen.getByRole('radio', { name: 'orders_contract' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: 'Valid Name',
      description: 'A sufficiently long description',
      data_contracts_id: 'c1',
    })
  })

  it('submits a changed contract in edit mode', async () => {
    const { onSubmit } = renderForm({ defaultValues: existing })
    fireEvent.click(screen.getByRole('radio', { name: 'orders_contract' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ data_contracts_id: 'c1' })
  })
})

describe('DataProductForm — contract picker states', () => {
  it('shows a spinner while the contracts load', () => {
    selectable({ contracts: [], isLoading: true })
    renderForm()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
  })

  it('shows why the list is empty when no contract is reachable', () => {
    selectable({ contracts: [] })
    renderForm()
    expect(screen.getByText('No data contracts available to you')).toBeInTheDocument()
    expect(screen.getByText(/only use a contract from a domain you belong to/)).toBeInTheDocument()
  })

  it('shows a load error', () => {
    selectable({ contracts: [], error: new Error('boom') })
    renderForm()
    expect(screen.getByText('Could not load data contracts: boom')).toBeInTheDocument()
  })

  it('hides the filter for a short list', () => {
    renderForm()
    expect(screen.queryByRole('textbox', { name: 'Filter data contracts' })).not.toBeInTheDocument()
  })

  it('filters a long list by title, domain, owner or purpose', () => {
    const many = [
      ...contracts,
      ...['a', 'b', 'c', 'd'].map((x) => makeContract({ id: `x${x}`, title: `misc_${x}`, domain: 'Ops', owner: 'zed' })),
    ]
    selectable({ contracts: many })
    renderForm()
    const filter = screen.getByRole('textbox', { name: 'Filter data contracts' })

    fireEvent.change(filter, { target: { value: 'risk' } })
    expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-label'))).toEqual(['exposure_contract'])
    expect(screen.getByText('1 of 6 available')).toBeInTheDocument()

    fireEvent.change(filter, { target: { value: 'ORDER LINE' } })
    expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-label'))).toEqual(['orders_contract'])

    fireEvent.change(filter, { target: { value: 'zed' } })
    expect(screen.getAllByRole('radio')).toHaveLength(4)

    fireEvent.change(filter, { target: { value: 'nothing' } })
    expect(screen.getByText('No contracts match this filter.')).toBeInTheDocument()
  })
})
