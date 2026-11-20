import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ContractFields, { withFieldDefaults } from './ContractFields'
import type { SchemaField } from '../../types'

const field: SchemaField = {
  name: 'order_id', type: 'string', description: '', nullable: false, primary_key: true,
  classification: '', unique: false, physical_type: '',
}

describe('ContractFields', () => {
  it('reports physical type, classification and unique changes', () => {
    const onChange = vi.fn()
    render(<ContractFields fields={[field]} onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('Physical type'), { target: { value: 'VARCHAR(36)' } })
    expect(onChange.mock.lastCall![0][0].physical_type).toBe('VARCHAR(36)')
    fireEvent.change(screen.getByLabelText('Classification'), { target: { value: 'restricted' } })
    expect(onChange.mock.lastCall![0][0].classification).toBe('restricted')
    fireEvent.click(screen.getByLabelText('Unique'))
    expect(onChange.mock.lastCall![0][0].unique).toBe(true)
  })

  it('offers the four classifications plus empty', () => {
    render(<ContractFields fields={[field]} onChange={vi.fn()} />)
    const options = within(screen.getByLabelText('Classification')).getAllByRole('option')
    expect(options.map((o) => (o as HTMLOptionElement).value)).toEqual(
      ['', 'public', 'internal', 'confidential', 'restricted'],
    )
  })

  it('gives added and stored fields empty attributes', () => {
    const onChange = vi.fn()
    render(<ContractFields fields={[]} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add field/i }))
    expect(onChange.mock.lastCall![0][0]).toMatchObject({ classification: '', unique: false, physical_type: '' })
    const stored = { name: 'a', type: 'string', description: '', nullable: true, primary_key: false } as SchemaField
    expect(withFieldDefaults(stored)).toMatchObject({ name: 'a', classification: '', unique: false, physical_type: '' })
  })
})
