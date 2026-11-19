import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import QualityRules from './QualityRules'
import { emptyRule, withType } from '../../lib/qualityRules'

describe('QualityRules', () => {
  it('offers only schema fields as columns', () => {
    render(<QualityRules rules={[emptyRule()]} fieldNames={['email', 'id']} onChange={vi.fn()} />)
    const options = within(screen.getByLabelText('Column')).getAllByRole('option')
    expect(options.map((o) => (o as HTMLOptionElement).value)).toEqual(['', 'email', 'id'])
  })

  it('keeps a typed comma on screen and updates the rule on every keystroke', () => {
    const onChange = vi.fn()
    const rule = { ...emptyRule(), column: 'email', metric: 'invalidValues' as const }
    render(<QualityRules rules={[rule]} fieldNames={['email']} onChange={onChange} />)
    const input = screen.getByLabelText('Valid values') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'open,' } })
    expect(input.value).toBe('open,')
    expect(onChange.mock.lastCall![0][0].valid_values).toEqual(['open'])
    fireEvent.change(input, { target: { value: 'open, paid' } })
    expect(onChange.mock.lastCall![0][0].valid_values).toEqual(['open', 'paid'])
  })

  it('shows the stale column of a rule whose field was removed', () => {
    render(<QualityRules rules={[{ ...emptyRule(), column: 'mail' }]} fieldNames={['email']} onChange={vi.fn()} />)
    expect((screen.getByLabelText('Column') as HTMLSelectElement).value).toBe('mail')
  })

  it('hides metric inputs for a text rule', () => {
    render(<QualityRules rules={[withType(emptyRule(), 'text')]} fieldNames={[]} onChange={vi.fn()} />)
    expect(screen.queryByLabelText('Metric')).toBeNull()
    expect(screen.queryByLabelText('Value')).toBeNull()
  })

  it('disables percent where the tool cannot run it', () => {
    const rule = { ...emptyRule(), column: 'email', metric: 'duplicateValues' as const }
    render(<QualityRules rules={[rule]} fieldNames={['email']} onChange={vi.fn()} />)
    const percent = within(screen.getByLabelText('Unit')).getByRole('option', { name: 'percent' })
    expect((percent as HTMLOptionElement).disabled).toBe(true)
  })

  it('switching the metric to rowCount clears the column', () => {
    const onChange = vi.fn()
    render(<QualityRules rules={[{ ...emptyRule(), column: 'email' }]} fieldNames={['email']} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Metric'), { target: { value: 'rowCount' } })
    expect(onChange.mock.lastCall![0][0]).toMatchObject({ metric: 'rowCount', column: '' })
  })
})
