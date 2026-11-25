import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import type { ReactElement } from 'react'
import ContractFields from './ContractFields'
import ContractServers from './ContractServers'
import QualityRules from './QualityRules'
import SupportChannels from '../../components/rows/SupportChannels'
import TeamMembers from '../../components/rows/TeamMembers'
import { emptyServer } from './contractMetadata'
import { emptyRule } from '../../lib/qualityRules'

type Editor = (rows: never[], onChange: (rows: unknown[]) => void) => ReactElement

// Every row editor shares one contract: each control patches its row, the
// trash button drops it, the add button appends an empty one.
const EDITORS: [string, Editor, object, string][] = [
  ['TeamMembers', (rows, onChange) => <TeamMembers rows={rows} onChange={onChange} />,
    { username: 'a', name: '', role: '' }, 'No team members yet.'],
  ['SupportChannels', (rows, onChange) => <SupportChannels rows={rows} onChange={onChange} />,
    { channel: 'c', url: '', tool: '', scope: '' }, 'No support channels yet.'],
  ['ContractServers', (rows, onChange) => <ContractServers rows={rows} onChange={onChange} />,
    { ...emptyServer(), server: 'prod' }, 'No servers yet.'],
  ['QualityRules', (rows, onChange) => <QualityRules rules={rows} fieldNames={['email']} onChange={onChange} />,
    emptyRule(), 'No quality rules yet.'],
  ['ContractFields', (rows, onChange) => <ContractFields fields={rows} onChange={onChange} />,
    { name: 'a', type: 'string', description: '', nullable: true, primary_key: false,
      classification: '', unique: false, physical_type: '' }, 'No fields yet.'],
]

function changeControl(control: Element) {
  if (control instanceof HTMLSelectElement) {
    fireEvent.change(control, { target: { value: control.options[control.options.length - 1].value } })
  } else if ((control as HTMLInputElement).type === 'checkbox') {
    fireEvent.click(control)
  } else {
    fireEvent.change(control, { target: { value: 'x' } })
  }
}

describe.each(EDITORS)('%s', (_name, editor, row, emptyText) => {
  it('patches the row from every control', () => {
    const onChange = vi.fn()
    const { container } = render(editor([row as never], onChange))
    for (const control of container.querySelectorAll('input, select')) {
      onChange.mockClear()
      changeControl(control)
      expect(onChange).toHaveBeenCalledOnce()
      expect(onChange.mock.lastCall![0][0]).not.toEqual(row)
    }
  })

  it('removes a row, shows the empty text and adds a row', () => {
    const onChange = vi.fn()
    const { rerender } = render(editor([row as never], onChange))
    fireEvent.click(screen.getByTitle(/remove/i))
    expect(onChange).toHaveBeenLastCalledWith([])
    rerender(editor([], onChange))
    expect(screen.getByText(emptyText)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /add/i }))
    expect(onChange.mock.lastCall![0]).toHaveLength(1)
  })
})
