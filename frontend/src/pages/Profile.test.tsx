import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Profile from './Profile'
import { useAuth } from '../contexts/AuthContext'

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('../hooks/useProfile', () => ({
  useUserDomains: () => ({ data: [], isLoading: false }),
  useChangePassword: () => ({ mutateAsync: vi.fn(), isPending: false, isError: false, error: null }),
}))
vi.mock('../hooks/useDomains', () => ({
  useAllDomains: () => ({ data: [], isLoading: false }),
  useCreateDomain: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateDomain: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteDomain: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('../hooks/useUsers', () => ({ useUsers: () => ({ data: [], isLoading: false }) }))

function renderAs(role: string) {
  vi.mocked(useAuth).mockReturnValue({ user: { id: 'u1', username: 'ana', email: 'ana@x', role } } as never)
  render(<Profile />)
}

describe('Profile role texts follow the contract access layers', () => {
  it('tells a consumer they read every published contract', () => {
    renderAs('DATA_CONSUMER')
    expect(screen.getByText('Reads every published contract; drafts when invited as a stakeholder.')).toBeInTheDocument()
    expect(screen.getByText('View every published data contract')).toBeInTheDocument()
    expect(screen.getByText('View drafts you are invited to review')).toBeInTheDocument()
  })

  it('tells a steward they submit drafts and invite reviewers', () => {
    renderAs('DATA_STEWARD')
    expect(screen.getByText('Submit drafts for review and invite reviewers')).toBeInTheDocument()
    expect(screen.getByText("View published contracts and your domain's drafts")).toBeInTheDocument()
  })

  it('tells an owner they approve, deprecate and retire', () => {
    renderAs('DATA_OWNER')
    expect(screen.getByText('Approve, deprecate, retire and delete contracts in your domain')).toBeInTheDocument()
    expect(screen.getByText("View published contracts and your domain's drafts")).toBeInTheDocument()
  })
})
