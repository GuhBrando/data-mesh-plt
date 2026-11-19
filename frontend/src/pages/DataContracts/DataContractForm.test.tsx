import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DataContractForm from './DataContractForm'
import { emptyServer } from './contractMetadata'
import type { DataContract } from '../../types'

vi.mock('../../hooks/useDomains', () => ({
  useAllDomains: () => ({ data: [{ id: 'd1', name: 'commerce', owner_id: 'u1', members: [] }], isLoading: false }),
}))
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u1', role: 'PLATFORM_ADMIN' } }) }))

const contract: DataContract = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { freshness: '', availability: '', retention: '', latency: '' },
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

const change = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } })

describe('DataContractForm metadata', () => {
  it('shows every section at tier 4, submits an edited description and keeps the other sections', async () => {
    const onSubmit = renderForm()
    for (const label of ['Description', 'Team Members', 'Support', 'Servers']) {
      expect(screen.getByRole('heading', { name: label })).toBeInTheDocument()
    }
    change(screen.getByLabelText('Usage'), 'reporting')
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      description: { purpose: 'p', usage: 'reporting', limitations: '' },
      team_members: contract.team_members, support: contract.support, servers: contract.servers,
    })
  })

  it('blocks submit and names the row when a server is incomplete', async () => {
    const onSubmit = renderForm({ ...contract, servers: [{ ...emptyServer(), server: 'prod' }] })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('Server 1 (databricks) needs Catalog, Schema')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('DataContractForm tiers', () => {
  it('classifies the tier with the wizard and enforces tier 1 on create', async () => {
    const onSubmit = vi.fn()
    const onCancel = vi.fn()
    render(<DataContractForm showWizard onSubmit={onSubmit} onCancel={onCancel} isSubmitting={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()

    for (let i = 0; i < 3; i++) fireEvent.click(screen.getByRole('button', { name: 'No' }))
    change(screen.getByDisplayValue('Tier 4 — Experimental / Sandbox'), '2')
    expect(screen.getByText('Tier 2 — Business Important', { selector: 'span' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Restart' }))
    fireEvent.click(screen.getByRole('button', { name: 'Yes' }))

    change(screen.getByLabelText('Title'), 'Orders')
    change(screen.getByLabelText('Owner'), 'alice')
    change(screen.getByDisplayValue('Select a domain'), 'd1')
    change(screen.getByLabelText('Freshness *'), 'soon')
    change(screen.getByLabelText('Availability *'), '99')
    fireEvent.click(screen.getByRole('button', { name: 'Create Contract' }))
    expect(await screen.findByText('Use a duration like 24h, 7d, 30m')).toBeInTheDocument()
    expect(screen.getByText('Use a percentage like 99.9%')).toBeInTheDocument()
    expect(screen.getAllByText('Required for Tier 1')).toHaveLength(2)

    change(screen.getByLabelText('Freshness *'), '24h')
    change(screen.getByLabelText('Availability *'), '99.9%')
    change(screen.getByLabelText('Retention *'), '365d')
    change(screen.getByLabelText('Latency *'), '1h')
    fireEvent.click(screen.getByRole('button', { name: 'Create Contract' }))
    expect(await screen.findByText('At least one schema field is required for Tier 1')).toBeInTheDocument()
    expect(screen.getByText('At least one quality rule is required for Tier 1')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('requires freshness and availability at tier 2', async () => {
    renderForm()
    change(screen.getByDisplayValue('Tier 4 — Experimental / Sandbox'), '2')
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findAllByText('Required for Tier 2')).toHaveLength(2)
  })
})
