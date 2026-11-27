import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import InviteStakeholdersModal from './InviteStakeholdersModal'
import { useInviteStakeholders } from '../../hooks/useContractStakeholders'
import { useUsers } from '../../hooks/useUsers'
import { useAllDomains } from '../../hooks/useDomains'
import type { DataContract, Stakeholder } from '../../types'

vi.mock('../../hooks/useContractStakeholders', () => ({ useInviteStakeholders: vi.fn() }))
vi.mock('../../hooks/useUsers', () => ({ useUsers: vi.fn() }))
vi.mock('../../hooks/useDomains', () => ({ useAllDomains: vi.fn() }))

const users = [
  { id: 'u-admin', username: 'admin', email: 'a@x', role: 'PLATFORM_ADMIN' },
  { id: 'u-sam', username: 'sam', email: 's@x', role: 'DATA_STEWARD' },
  { id: 'u-ana', username: 'ana', email: 'an@x', role: 'DATA_CONSUMER' },
  { id: 'u-bob', username: 'bob', email: 'b@x', role: 'DATA_CONSUMER' },
  { id: 'u-zoe', username: 'zoe', email: 'z@x', role: 'DATA_CONSUMER' },
  { id: 'u-ola', username: 'ola', email: 'o@x', role: 'DATA_OWNER' },
]
const domains = [{
  id: 'd1', name: 'commerce', description: '', owner_id: 'u-ola', owner_username: 'ola',
  created_at: '', updated_at: '', contract_count: 1,
  members: [
    { user_id: 'u-sam', username: 'sam', role: 'member' },
    { user_id: 'u-ana', username: 'ana', role: 'member' },
    { user_id: 'u-bob', username: 'bob', role: 'member' },
  ],
}]
const invited: Stakeholder[] = [{
  user_id: 'u-ana', username: 'ana', role: 'DATA_CONSUMER', assigned_by_username: 'sam',
  assigned_at: '2026-01-01T00:00:00Z',
}]
const contract = { id: 'c1', domain: 'commerce', domain_id: 'd1', status: 'draft' } as DataContract

const invite = { mutateAsync: vi.fn(), isPending: false, isError: false, error: null as Error | null }
let onClose = vi.fn()

function renderModal() {
  render(<InviteStakeholdersModal contract={contract} stakeholders={invited} open onClose={onClose} />)
}

function option(name: string) {
  // An option is named after the user, then its reason after a comma.
  return screen.getByRole('option', { name: (n) => n === name || n.startsWith(`${name},`) })
}

beforeEach(() => {
  onClose = vi.fn()
  invite.mutateAsync = vi.fn().mockResolvedValue(undefined)
  invite.isError = false
  invite.error = null
  vi.mocked(useInviteStakeholders).mockReturnValue(invite as never)
  vi.mocked(useUsers).mockReturnValue({ data: users, isLoading: false, isError: false } as never)
  vi.mocked(useAllDomains).mockReturnValue({ data: domains, isLoading: false, isError: false } as never)
})

describe('InviteStakeholdersModal', () => {
  it('lists the domain members first, then everyone else', () => {
    renderModal()
    const members = screen.getByRole('group', { name: 'Members of commerce' })
    const others = screen.getByRole('group', { name: 'Everyone else' })
    expect(within(members).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'anaAlready invited', 'bob', 'samAlready reads drafts of commerce',
    ])
    expect(within(others).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'adminAlready reads drafts of commerce', 'ola', 'zoe',
    ])
  })

  it('disables who already has access and keeps the rest choosable', () => {
    renderModal()
    expect(option('sam')).toBeDisabled()
    expect(option('ana')).toBeDisabled()
    expect(option('admin')).toBeDisabled()
    expect(option('bob')).toBeEnabled()
    // An owner outside the domain cannot read its drafts: they can be invited.
    expect(option('ola')).toBeEnabled()
  })

  it('filters by username', () => {
    renderModal()
    fireEvent.change(screen.getByLabelText('Search users'), { target: { value: 'ZO' } })
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['zoe'])
    expect(screen.queryByRole('group', { name: 'Members of commerce' })).toBeNull()
  })

  it('says when no user matches', () => {
    renderModal()
    fireEvent.change(screen.getByLabelText('Search users'), { target: { value: 'nobody' } })
    expect(screen.getByText('No users found.')).toBeInTheDocument()
  })

  it('invites every selected user and closes', async () => {
    renderModal()
    const inviteButton = screen.getByRole('button', { name: 'Invite' })
    expect(inviteButton).toBeDisabled()
    fireEvent.click(option('bob'))
    fireEvent.click(option('zoe'))
    fireEvent.click(option('ola'))
    fireEvent.click(option('ola'))
    expect(option('bob')).toHaveAttribute('aria-selected', 'true')
    expect(option('ola')).toHaveAttribute('aria-selected', 'false')
    fireEvent.click(inviteButton)
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(invite.mutateAsync).toHaveBeenCalledWith(['u-bob', 'u-zoe'])
  })

  it('keeps the modal open and shows the error when inviting fails', async () => {
    invite.mutateAsync = vi.fn().mockRejectedValue(new Error('boom'))
    invite.isError = true
    invite.error = new Error('Published contracts are readable by everyone.')
    renderModal()
    fireEvent.click(option('bob'))
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }))
    await waitFor(() => expect(invite.mutateAsync).toHaveBeenCalled())
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByText('Published contracts are readable by everyone.')).toBeInTheDocument()
  })

  it('shows the loading and error states of the user list', () => {
    vi.mocked(useUsers).mockReturnValue({ data: undefined, isLoading: true, isError: false } as never)
    const { unmount } = render(
      <InviteStakeholdersModal contract={contract} stakeholders={[]} open onClose={onClose} />)
    expect(screen.getByText('Loading users…')).toBeInTheDocument()
    unmount()
    vi.mocked(useUsers).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never)
    render(<InviteStakeholdersModal contract={contract} stakeholders={[]} open onClose={onClose} />)
    expect(screen.getByText('Failed to load users.')).toBeInTheDocument()
  })
})
