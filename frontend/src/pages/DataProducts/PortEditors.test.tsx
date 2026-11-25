import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { InputPortsEditor, OutputPortsEditor, emptyOutput } from './PortEditors'
import { makeContract, makeInput, makeOutput } from '../../test/fixtures'
import type { InputPort, OutputPort, ProductRef } from '../../types'

const orders = makeContract({ id: 'c1', title: 'Orders Feed', version: '1.2.0', domain: 'Sales' })
const legacy = makeContract({ id: 'c2', title: 'Legacy', status: 'retired', domain: 'Ops' })
const source = { contracts: [orders, legacy], loading: false, error: null }

function outputs(rows: OutputPort[], inputs: InputPort[] = [], error?: string) {
  const onChange = vi.fn()
  render(<OutputPortsEditor rows={rows} onChange={onChange} inputs={inputs} source={source} error={error} />)
  return onChange
}

function inputs(rows: InputPort[], producers = new Map<string, ProductRef[]>()) {
  const onChange = vi.fn()
  render(<InputPortsEditor rows={rows} onChange={onChange} source={source} producers={producers} />)
  return onChange
}

describe('OutputPortsEditor', () => {
  it('shows that an output without a contract cannot be consumed', () => {
    outputs([emptyOutput()])
    expect(screen.getByText('Not consumable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add a contract' })).toBeInTheDocument()
  })

  it('fills the contract, its current version and a name when one is picked', () => {
    const onChange = outputs([emptyOutput()])
    fireEvent.click(screen.getByRole('button', { name: 'Add a contract' }))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Output contract' })).getByRole('radio', { name: 'Orders Feed' }))
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        name: 'orders-feed',
        contract_id: 'c1',
        version: '1.2.0',
        contract: { title: 'Orders Feed', status: 'active', version: '1.2.0', domain: 'Sales' },
      }),
    ])
  })

  it('keeps a name the user already typed', () => {
    const onChange = outputs([{ ...emptyOutput(), name: 'exposure' }])
    fireEvent.click(screen.getByRole('button', { name: 'Add a contract' }))
    fireEvent.click(screen.getByRole('radio', { name: 'Orders Feed' }))
    expect(onChange.mock.calls[0][0][0].name).toBe('exposure')
  })

  it('closes the picker without a change on Cancel', () => {
    const onChange = outputs([emptyOutput()])
    fireEvent.click(screen.getByRole('button', { name: 'Add a contract' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel picking' }))
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it('shows the contract and version of an output that has one', () => {
    outputs([makeOutput({ contract: { title: 'Orders Feed', status: 'active', version: '1.2.0', domain: 'Sales' } })])
    expect(screen.getByText('Orders Feed · v1.0.0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Change contract' })).toBeInTheDocument()
  })

  it('records which inputs an output is built from', () => {
    const cad = makeInput({ name: 'cad', contract_id: 'c9', version: '2.0.0' })
    const external = makeInput({ name: 'core', contract_id: null, version: null })
    const onChange = outputs([emptyOutput()], [cad, external])
    expect(screen.queryByRole('checkbox', { name: 'core' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', { name: 'cad v2.0.0' }))
    expect(onChange.mock.calls[0][0][0].input_contracts).toEqual([{ contract_id: 'c9', version: '2.0.0' }])
  })

  it('removes an input from what an output is built from', () => {
    const cad = makeInput({ name: 'cad', contract_id: 'c9', version: '2.0.0' })
    const onChange = outputs([{ ...emptyOutput(), input_contracts: [{ contract_id: 'c9', version: '2.0.0' }] }], [cad])
    fireEvent.click(screen.getByRole('checkbox', { name: 'cad v2.0.0' }))
    expect(onChange.mock.calls[0][0][0].input_contracts).toEqual([])
  })

  it('edits the name, type and description', () => {
    const onChange = outputs([emptyOutput()])
    fireEvent.change(screen.getByLabelText('Output name'), { target: { value: 'alerts' } })
    expect(onChange.mock.calls[0][0][0].name).toBe('alerts')
    fireEvent.change(screen.getByLabelText('Output type'), { target: { value: 'topic' } })
    expect(onChange.mock.calls[1][0][0].type).toBe('topic')
    fireEvent.change(screen.getByLabelText('Output description'), { target: { value: 'Limit alerts' } })
    expect(onChange.mock.calls[2][0][0].description).toBe('Limit alerts')
  })

  it('adds an empty output', () => {
    const onChange = outputs([])
    fireEvent.click(screen.getByRole('button', { name: 'Add output' }))
    expect(onChange).toHaveBeenCalledWith([emptyOutput()])
    expect(emptyOutput().type).toBe('tables')
  })

  it('marks the older row of a port in a version move', () => {
    outputs([makeOutput({ version: '2.0.0' }), makeOutput({ version: '1.0.0' })])
    expect(screen.getAllByText('older version')).toHaveLength(1)
  })

  it('shows the section error', () => {
    outputs([], [], 'A data product needs at least one output')
    expect(screen.getByRole('alert')).toHaveTextContent('A data product needs at least one output')
  })
})

describe('InputPortsEditor', () => {
  it('adds an input from any contract, named after it, at its current version', () => {
    const producers = new Map([['c1', [{ id: 'p1', name: 'Sales Hub', status: 'active' as const }]]])
    const onChange = inputs([], producers)
    fireEvent.click(screen.getByRole('button', { name: 'From a contract' }))
    const picker = screen.getByRole('radiogroup', { name: 'Input contract' })
    expect(within(picker).getByRole('radio', { name: 'Orders Feed' })).toHaveAccessibleDescription(/Produced by Sales Hub/)
    fireEvent.click(within(picker).getByRole('radio', { name: 'Orders Feed' }))
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ name: 'orders-feed', contract_id: 'c1', version: '1.2.0' }),
    ])
  })

  it('says who produces a contract input, or that no one does', () => {
    const producers = new Map([['c1', [{ id: 'p1', name: 'Sales Hub', status: 'active' as const }]]])
    inputs([makeInput({ name: 'a' }), makeInput({ name: 'b', contract_id: 'c3' })], producers)
    expect(screen.getByText('Produced by Sales Hub')).toBeInTheDocument()
    expect(screen.getByText('No producer on the platform')).toBeInTheDocument()
  })

  it('flags an input whose contract is deprecated or retired', () => {
    inputs([
      makeInput({ name: 'old', contract: { title: 'Legacy', status: 'retired', version: '1.0.0', domain: 'Ops' } }),
      makeInput({ name: 'dep', contract: { title: 'Dep', status: 'deprecated', version: '1.0.0', domain: 'Ops' } }),
    ])
    expect(screen.getByText('Retired contract')).toBeInTheDocument()
    expect(screen.getByText('Deprecated contract')).toBeInTheDocument()
  })

  it('adds an external source with a name and a link', () => {
    const onChange = inputs([])
    fireEvent.click(screen.getByRole('button', { name: 'External source' }))
    expect(onChange).toHaveBeenCalledWith([
      { name: '', contract_id: null, version: null, deprecated: false, authoritative_definitions: [] },
    ])
  })

  it('stores the link of an external source as an implementation definition', () => {
    const external = makeInput({ name: 'core', contract_id: null, version: null })
    const onChange = inputs([external])
    fireEvent.change(screen.getByLabelText('Source link'), { target: { value: 'https://wiki/core' } })
    expect(onChange.mock.calls[0][0][0].authoritative_definitions).toEqual([
      { type: 'implementation', url: 'https://wiki/core' },
    ])
  })

  it('drops the definition when the link is cleared', () => {
    const external = makeInput({
      name: 'core',
      contract_id: null,
      version: null,
      authoritative_definitions: [{ type: 'implementation', url: 'https://wiki/core' }],
    })
    const onChange = inputs([external])
    expect(screen.getByLabelText('Source link')).toHaveValue('https://wiki/core')
    fireEvent.change(screen.getByLabelText('Source link'), { target: { value: '' } })
    expect(onChange.mock.calls[0][0][0].authoritative_definitions).toEqual([])
  })

  it('renames an input', () => {
    const onChange = inputs([makeInput()])
    fireEvent.change(screen.getByLabelText('Input name'), { target: { value: 'orders_eu' } })
    expect(onChange.mock.calls[0][0][0].name).toBe('orders_eu')
  })
})
