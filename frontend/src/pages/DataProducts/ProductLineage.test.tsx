import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ProductLineage from './ProductLineage'
import { makeInput, makeOutput, makeProduct } from '../../test/fixtures'
import type { ContractSummary, DataProduct } from '../../types'

const cadastro: ContractSummary = { title: 'Cadastro', status: 'active', version: '2.1.0', domain: 'Clientes' }
const exposicao: ContractSummary = { title: 'Exposição', status: 'active', version: '1.0.0', domain: 'Risco' }

function renderLineage(product: DataProduct, saving = false) {
  const onChange = vi.fn()
  render(
    <MemoryRouter>
      <ProductLineage product={product} onChange={onChange} saving={saving} />
    </MemoryRouter>,
  )
  return onChange
}

const product = makeProduct({
  name: 'Risco de Crédito',
  input_ports: [
    makeInput({ name: 'cadastro', version: '2.1.0', contract: cadastro, produced_by: [{ id: 'pf', name: 'Cadastro PF', status: 'active' }] }),
    makeInput({
      name: 'core-bancario',
      contract_id: null,
      version: null,
      authoritative_definitions: [{ type: 'implementation', url: 'https://wiki/core' }],
    }),
  ],
  output_ports: [
    makeOutput({
      name: 'exposicao',
      contract: exposicao,
      consumed_by: [
        { id: 'a', name: 'Cobrança', status: 'active' },
        { id: 'b', name: 'Provisões', status: 'active' },
      ],
    }),
    makeOutput({ name: 'alerta-limite', contract_id: null, version: null, type: 'topic' }),
  ],
})

describe('ProductLineage', () => {
  it('shows inputs, the product and outputs', () => {
    renderLineage(product)
    const inputs = screen.getByRole('list', { name: 'Inputs' })
    expect(within(inputs).getByText('cadastro')).toBeInTheDocument()
    expect(within(inputs).getByText('Cadastro · v2.1.0')).toBeInTheDocument()
    expect(within(inputs).getByRole('link', { name: 'Cadastro PF' })).toHaveAttribute('href', '/data-products/pf')
    expect(within(inputs).getByRole('link', { name: 'External source' })).toHaveAttribute('href', 'https://wiki/core')
    expect(screen.getByText('Risco de Crédito')).toBeInTheDocument()
    const outputs = screen.getByRole('list', { name: 'Outputs' })
    expect(within(outputs).getByText('2 consumers')).toBeInTheDocument()
    expect(within(outputs).getByText('No contract — not consumable')).toBeInTheDocument()
  })

  it('never turns an unsafe source link into a clickable link', () => {
    renderLineage(
      makeProduct({
        input_ports: [
          makeInput({
            name: 'core',
            contract_id: null,
            version: null,
            authoritative_definitions: [{ type: 'implementation', url: 'javascript:alert(1)' }],
          }),
        ],
      }),
    )
    expect(screen.queryByRole('link', { name: 'External source' })).not.toBeInTheDocument()
    expect(screen.getByText('External source')).toBeInTheDocument()
  })

  it('says when an input has no producer on the platform', () => {
    renderLineage(makeProduct({ input_ports: [makeInput({ contract: cadastro, version: '2.1.0' })] }))
    expect(screen.getByText('No producer on the platform')).toBeInTheDocument()
  })

  it('flags an input whose contract is deprecated or retired', () => {
    renderLineage(
      makeProduct({
        input_ports: [
          makeInput({ name: 'a', contract: { ...cadastro, status: 'deprecated', version: '1.0.0' } }),
          makeInput({ name: 'b', contract: { ...cadastro, status: 'retired', version: '1.0.0' } }),
        ],
      }),
    )
    expect(screen.getByText('Contract deprecated')).toBeInTheDocument()
    expect(screen.getByText('Contract retired')).toBeInTheDocument()
  })

  it('publishes a new output version and offers to deprecate the old one', () => {
    const behind = makeProduct({ output_ports: [makeOutput({ contract: { ...exposicao, version: '1.1.0' } })] })
    const onChange = renderLineage(behind)
    expect(screen.getByText('v1.1.0 available')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Publish' }))
    const dialog = screen.getByRole('dialog', { name: 'Publish v1.1.0' })
    expect(within(dialog).getByRole('checkbox', { name: 'Mark v1.0.0 deprecated' })).toBeChecked()
    expect(within(dialog).queryByText(/MAJOR/)).not.toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Publish v1.1.0' }))
    const sent = onChange.mock.calls[0][0]
    expect(sent.output_ports.map((p: { version: string; deprecated: boolean }) => [p.version, p.deprecated])).toEqual([
      ['1.0.0', true],
      ['1.1.0', false],
    ])
  })

  it('can publish without deprecating the old output', () => {
    const behind = makeProduct({ output_ports: [makeOutput({ contract: { ...exposicao, version: '1.1.0' } })] })
    const onChange = renderLineage(behind)
    fireEvent.click(screen.getByRole('button', { name: 'Publish' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark v1.0.0 deprecated' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Publish v1.1.0' }))
    expect(onChange.mock.calls[0][0].output_ports[0].deprecated).toBe(false)
  })

  it('warns about a MAJOR output version before publishing', () => {
    const behind = makeProduct({ output_ports: [makeOutput({ contract: { ...exposicao, version: '2.0.0' } })] })
    renderLineage(behind)
    fireEvent.click(screen.getByRole('button', { name: 'Publish' }))
    expect(within(screen.getByRole('dialog')).getByText(/MAJOR version/)).toBeInTheDocument()
  })

  it('switches an input to a new MINOR version at once', () => {
    const behind = makeProduct({ input_ports: [makeInput({ contract: { ...cadastro, version: '1.1.0' } })] })
    const onChange = renderLineage(behind)
    fireEvent.click(screen.getByRole('button', { name: 'Switch' }))
    expect(onChange.mock.calls[0][0].input_ports.map((p: { version: string }) => p.version)).toEqual(['1.0.0', '1.1.0'])
  })

  it('asks before switching an input to a MAJOR version', () => {
    const behind = makeProduct({ input_ports: [makeInput({ contract: { ...cadastro, version: '2.0.0' } })] })
    const onChange = renderLineage(behind)
    fireEvent.click(screen.getByRole('button', { name: 'Switch' }))
    expect(onChange).not.toHaveBeenCalled()
    const dialog = screen.getByRole('dialog', { name: 'Switch to v2.0.0' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Switch to v2.0.0' }))
    expect(onChange).toHaveBeenCalledOnce()
  })

  it('offers to remove an old row nothing uses any more', () => {
    const moved = makeProduct({
      output_ports: [makeOutput({ version: '1.0.0' }), makeOutput({ id: 'o2', version: '1.1.0', consumed_by: [{ id: 'c', name: 'C', status: 'active' }] })],
    })
    const onChange = renderLineage(moved)
    const removes = screen.getAllByRole('button', { name: /Remove/ })
    expect(removes).toHaveLength(1)
    fireEvent.click(removes[0])
    expect(onChange.mock.calls[0][0].output_ports.map((p: { version: string }) => p.version)).toEqual(['1.1.0'])
  })

  it('disables the actions while saving', () => {
    const behind = makeProduct({ input_ports: [makeInput({ contract: { ...cadastro, version: '1.1.0' } })] })
    renderLineage(behind, true)
    expect(screen.getByRole('button', { name: 'Switch' })).toBeDisabled()
  })
})
