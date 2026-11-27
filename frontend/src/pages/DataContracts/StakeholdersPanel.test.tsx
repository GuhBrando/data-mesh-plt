import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import StakeholdersPanel from './StakeholdersPanel'
import { useContractStakeholders, useRemoveStakeholder } from '../../hooks/useContractStakeholders'
import type { DataContract, Stakeholder } from '../../types'

vi.mock('../../hooks/useContractStakeholders', () => ({
  useContractStakeholders: vi.fn(),
  useRemoveStakeholder: vi.fn(),
  useInviteStakeholders: vi.fn(),
}))
vi.mock('./InviteStakeholdersModal', () => ({
  default: ({ onClose }: { onClose: () => void }) => (
    <div role="dialog" aria-label="Invite reviewers"><button type="button" onClick={onClose}>close</button></div>
  ),
}))

const ANA: Stakeholder = {
  user_id: 'u-ana', username: 'ana', role: 'DATA_CONSUMER', assigned_by_username: 'joao',
  assigned_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
}

function contract(over: Partial<DataContract> = {}): DataContract {
  return {
    id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
    tier: 4, status: 'draft', models: { fields: [] }, servicelevels: { properties: [] },
    description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    permissions: { edit: true, delete: false, transitions: ['in_review'], manage_stakeholders: true },
    ...over,
  }
}

const remove = { mutate: vi.fn(), isPending: false, isError: false, error: null }

function renderPanel(rows: Stakeholder[], over: Partial<DataContract> = {}) {
  vi.mocked(useContractStakeholders).mockReturnValue({ data: rows, isLoading: false, isError: false } as never)
  return render(<StakeholdersPanel contract={contract(over)} />)
}

beforeEach(() => {
  remove.mutate = vi.fn()
  vi.mocked(useRemoveStakeholder).mockReturnValue(remove as never)
})

describe('StakeholdersPanel', () => {
  it('lists stakeholders with their role and when they were invited', () => {
    renderPanel([ANA])
    expect(screen.getByRole('heading', { name: 'Stakeholders' })).toBeInTheDocument()
    expect(screen.getByText('Can read this draft before it is published.')).toBeInTheDocument()
    expect(screen.getByText('ana')).toBeInTheDocument()
    expect(screen.getByText('Consumer · 3 days ago')).toBeInTheDocument()
  })

  it.each(['active', 'deprecated', 'retired'] as const)('is hidden once the contract is %s', (status) => {
    const { container } = renderPanel([ANA], { status })
    expect(container).toBeEmptyDOMElement()
    expect(useContractStakeholders).toHaveBeenLastCalledWith('c1', false)
  })

  it('offers Add and remove only with manage permission', () => {
    renderPanel([ANA], { permissions: { edit: false, delete: false, transitions: [], manage_stakeholders: false } })
    expect(screen.getByText('ana')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Remove ana' })).toBeNull()
  })

  it('removes a stakeholder at once', () => {
    renderPanel([ANA])
    fireEvent.click(screen.getByRole('button', { name: 'Remove ana' }))
    expect(remove.mutate).toHaveBeenCalledWith('u-ana')
  })

  it('opens the invite modal from Add', () => {
    renderPanel([ANA])
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByRole('dialog', { name: 'Invite reviewers' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'close' }))
    expect(screen.queryByRole('dialog', { name: 'Invite reviewers' })).toBeNull()
  })

  it('invites the first reviewers from the empty state', () => {
    renderPanel([])
    expect(screen.getByText('No one invited yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Invite reviewers' }))
    expect(screen.getByRole('dialog', { name: 'Invite reviewers' })).toBeInTheDocument()
  })

  it('shows the empty state without an invite button when the user cannot manage', () => {
    renderPanel([], { permissions: { edit: false, delete: false, transitions: [], manage_stakeholders: false } })
    expect(screen.getByText('No one invited yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Invite reviewers' })).toBeNull()
  })

  it('says when the list cannot load', () => {
    vi.mocked(useContractStakeholders).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never)
    render(<StakeholdersPanel contract={contract()} />)
    expect(screen.getByText('Could not load the stakeholders.')).toBeInTheDocument()
  })
})
