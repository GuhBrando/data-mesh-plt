import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ContractPicker from './ContractPicker'
import { makeContract } from '../../test/fixtures'
import type { DataContract } from '../../types'

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

function renderPicker(props: Partial<Parameters<typeof ContractPicker>[0]> = {}) {
  const onChange = vi.fn()
  render(<ContractPicker contracts={contracts} value="" onChange={onChange} {...props} />)
  return { onChange }
}

describe('ContractPicker', () => {
  it('lists the contracts with their summary', () => {
    renderPicker()
    expect(screen.getByRole('radiogroup', { name: 'Data contract' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'orders_contract' })).toHaveAccessibleDescription(/Sales.*v2\.0\.1.*Active.*alice/)
    expect(screen.getByText('One row per order line')).toBeInTheDocument()
    expect(screen.getByText('2 available')).toBeInTheDocument()
  })

  it('takes a label and an extra detail per contract', () => {
    renderPicker({ label: 'Input contract', detail: (c: DataContract) => `produced by ${c.owner}` })
    expect(screen.getByRole('radiogroup', { name: 'Input contract' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'exposure_contract' })).toHaveAccessibleDescription(/produced by carla/)
  })

  it('reports the picked contract', () => {
    const { onChange } = renderPicker()
    fireEvent.click(screen.getByRole('radio', { name: 'orders_contract' }))
    expect(onChange).toHaveBeenCalledWith('c1')
  })

  it('shows a spinner while the contracts load', () => {
    renderPicker({ contracts: [], loading: true })
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
  })

  it('explains an empty list, with the default or a given hint', () => {
    renderPicker({ contracts: [] })
    expect(screen.getByText('No data contracts available to you')).toBeInTheDocument()
    expect(screen.getByText(/only use a contract from a domain you belong to/)).toBeInTheDocument()
  })

  it('takes another hint for an empty list', () => {
    renderPicker({ contracts: [], emptyHint: 'No contract exists yet.' })
    expect(screen.getByText('No contract exists yet.')).toBeInTheDocument()
  })

  it('shows a load error', () => {
    renderPicker({ contracts: [], loadError: 'boom' })
    expect(screen.getByText('Could not load data contracts: boom')).toBeInTheDocument()
  })

  it('hides the filter for a short list', () => {
    renderPicker()
    expect(screen.queryByRole('textbox', { name: 'Filter data contracts' })).not.toBeInTheDocument()
  })

  it('filters a long list by title, domain, owner or purpose', () => {
    const many = [
      ...contracts,
      ...['a', 'b', 'c', 'd'].map((x) => makeContract({ id: `x${x}`, title: `misc_${x}`, domain: 'Ops', owner: 'zed' })),
    ]
    renderPicker({ contracts: many })
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
