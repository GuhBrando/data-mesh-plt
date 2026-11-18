import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DataContractForm from './DataContractForm'
import { emptyServer } from './contractMetadata'
import { emptyRule } from '../../lib/qualityRules'
import type { DataContract } from '../../types'

vi.mock('../../hooks/useDomains', () => ({
  useAllDomains: () => ({ data: [{ id: 'd1', name: 'commerce', owner_id: 'u1', members: [] }], isLoading: false }),
}))
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u1', role: 'PLATFORM_ADMIN' } }) }))

const contract: DataContract = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { properties: [] },
  description: { purpose: 'p', usage: '', limitations: '' },
  team_members: [{ username: 'alice', name: '', role: 'owner' }],
  support: [{ channel: '#c', url: '', tool: 'slack', scope: '' }],
  servers: [{ ...emptyServer(), server: 'prod', catalog: 'c', schema_name: 's' }],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

const renderForm = (value = contract) => {
  const onSubmit = vi.fn()
  render(<DataContractForm defaultValues={value} onSubmit={onSubmit} onCancel={vi.fn()} isSubmitting={false} />)
  return onSubmit
}

describe('DataContractForm metadata', () => {
  it('shows every section at tier 4 and keeps stored metadata on an untouched save', async () => {
    const onSubmit = renderForm()
    for (const label of ['Description', 'Team Members', 'Support', 'Servers']) {
      expect(screen.getByRole('heading', { name: label })).toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      description: contract.description, team_members: contract.team_members,
      support: contract.support, servers: contract.servers,
    })
  })

  it('submits an edited description', async () => {
    const onSubmit = renderForm()
    fireEvent.change(screen.getByLabelText('Usage'), { target: { value: 'reporting' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0].description).toEqual({ purpose: 'p', usage: 'reporting', limitations: '' })
  })

  it('blocks submit and names the row when a server is incomplete', async () => {
    const onSubmit = renderForm({ ...contract, servers: [{ ...emptyServer(), server: 'prod' }] })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('Server 1 (databricks) needs Catalog, Schema')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('DataContractForm quality rules', () => {
  it('blocks saving a rule whose column was removed', async () => {
    const email = {
      name: 'email', type: 'string' as const, description: '', nullable: true, primary_key: false,
      classification: '' as const, unique: false, physical_type: '',
    }
    const onSubmit = renderForm({
      ...contract,
      tier: 3,
      models: { fields: [email], quality: [{ ...emptyRule(), column: 'gone' }] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText("Rule 1: column 'gone' is not a schema field")).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('DataContractForm service levels', () => {
  const email = {
    name: 'email', type: 'string' as const, description: '', nullable: true, primary_key: false,
    classification: '' as const, unique: false, physical_type: '',
  }
  const tier2 = {
    ...contract,
    tier: 2 as const,
    models: { fields: [email], quality: [] },
    servicelevels: { properties: [
      { property: 'freshness', value: 24, unit: 'h' },
      { property: 'availability', value: 99.9, unit: '%' },
      { property: 'frequency', value: 1, unit: 'd' },
    ] },
  }

  it('submits structured service levels and keeps hidden ones', async () => {
    const onSubmit = renderForm(tier2)
    fireEvent.change(screen.getByLabelText('Freshness *'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0].servicelevels.properties).toEqual([
      { property: 'freshness', value: 12, unit: 'h' },
      { property: 'availability', value: 99.9, unit: '%' },
      { property: 'frequency', value: 1, unit: 'd' },
    ])
  })

  it('rejects a number without a unit', async () => {
    const onSubmit = renderForm(tier2)
    fireEvent.change(screen.getByLabelText('Freshness unit'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('Pick a unit')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('clears the shown levels at tier 4 but keeps hidden ones', async () => {
    const onSubmit = renderForm({ ...tier2, tier: 4 })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0].servicelevels.properties).toEqual([
      { property: 'frequency', value: 1, unit: 'd' },
    ])
  })
})

describe('DataContractForm status', () => {
  it('offers Retired only when editing', () => {
    const props = { onSubmit: vi.fn(), onCancel: vi.fn(), isSubmitting: false }
    const { unmount } = render(<DataContractForm defaultValues={contract} {...props} />)
    expect(screen.getByRole('option', { name: 'Retired' })).toBeInTheDocument()
    unmount()
    render(<DataContractForm {...props} />)
    expect(screen.queryByRole('option', { name: 'Retired' })).not.toBeInTheDocument()
  })
})
