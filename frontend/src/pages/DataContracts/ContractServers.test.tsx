import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ContractServers from './ContractServers'
import { emptyServer } from './contractMetadata'

const row = (over = {}) => ({ ...emptyServer(), server: 'prod', ...over })

describe('ContractServers', () => {
  it('shows only the keys of the selected type', () => {
    render(<ContractServers rows={[row({ type: 'azure' })]} onChange={vi.fn()} />)
    expect(screen.getByPlaceholderText('Location')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Format')).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Host')).toBeNull()
    expect(screen.queryByPlaceholderText('Schema')).toBeNull()
  })

  it('clears keys the new type does not take', () => {
    const onChange = vi.fn()
    render(<ContractServers rows={[row({ host: 'h', catalog: 'c', schema_name: 's' })]} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Server type'), { target: { value: 'azure' } })
    expect(onChange.mock.lastCall![0][0]).toMatchObject({ type: 'azure', host: '', catalog: '', schema_name: '' })
  })

  it('stores port as a number and blank as null', () => {
    const onChange = vi.fn()
    render(<ContractServers rows={[row({ type: 'postgres', port: 5432 })]} onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('Port'), { target: { value: '6543' } })
    expect(onChange.mock.lastCall![0][0].port).toBe(6543)
    fireEvent.change(screen.getByPlaceholderText('Port'), { target: { value: '' } })
    expect(onChange.mock.lastCall![0][0].port).toBeNull()
  })
})
