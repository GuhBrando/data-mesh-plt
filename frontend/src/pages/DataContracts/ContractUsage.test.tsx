import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ContractUsage from './ContractUsage'
import { useContractPorts } from '../../hooks/useDataContracts'
import { makeContract } from '../../test/fixtures'
import type { PortUsage } from '../../types'

vi.mock('../../hooks/useDataContracts', () => ({ useContractPorts: vi.fn() }))

const contract = makeContract({ id: 'c1', version: '1.0.0' })

function usage(over: Partial<PortUsage>): PortUsage {
  return { product_id: 'p1', product_name: 'Risco', domain: 'Risco', status: 'active', role: 'output', port_name: 'exposicao', version: '1.0.0', ...over }
}

function renderUsage(query: object) {
  vi.mocked(useContractPorts).mockReturnValue({ data: undefined, isLoading: false, isError: false, ...query } as never)
  render(
    <MemoryRouter>
      <ContractUsage contract={contract} />
    </MemoryRouter>,
  )
}

beforeEach(() => vi.mocked(useContractPorts).mockReset())

describe('ContractUsage', () => {
  it('lists who produces and who consumes the contract', () => {
    renderUsage({
      data: [
        usage({}),
        usage({ product_id: 'p2', product_name: 'Cobrança', role: 'input', port_name: 'exposicao' }),
        usage({ product_id: 'p3', product_name: 'Provisões', role: 'input', version: '0.9.0' }),
      ],
    })
    const produced = screen.getByRole('list', { name: 'Produced by' })
    expect(within(produced).getByRole('link', { name: 'Risco' })).toHaveAttribute('href', '/data-products/p1')
    expect(within(produced).getByText('exposicao · v1.0.0')).toBeInTheDocument()
    const consumed = screen.getByRole('list', { name: 'Consumed by' })
    expect(within(consumed).getAllByRole('listitem')).toHaveLength(2)
    expect(within(consumed).getByText('pinned to an older version')).toBeInTheDocument()
    expect(useContractPorts).toHaveBeenCalledWith('c1')
  })

  it('says when no product uses the contract', () => {
    renderUsage({ data: [] })
    expect(screen.getByText('No data product uses this contract yet.')).toBeInTheDocument()
  })

  it('says when nobody consumes what is produced', () => {
    renderUsage({ data: [usage({})] })
    expect(screen.getByText('No consumers yet')).toBeInTheDocument()
  })

  it('shows loading and errors', () => {
    renderUsage({ isLoading: true })
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('shows an error', () => {
    renderUsage({ isError: true })
    expect(screen.getByText('Could not load the usage.')).toBeInTheDocument()
  })
})
