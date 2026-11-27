import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StatusBar from './StatusBar'
import type { DataContract } from '../../types'

type Status = DataContract['status']

function contract(status: Status, transitions: Status[]): DataContract {
  return {
    id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
    tier: 4, status, models: { fields: [] }, servicelevels: { properties: [] },
    description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    permissions: { edit: false, delete: false, transitions, manage_stakeholders: false },
  }
}

function renderBar(status: Status, transitions: Status[], over: { error?: string | null; pending?: boolean } = {}) {
  const onMove = vi.fn()
  const { container } = render(
    <StatusBar contract={contract(status, transitions)} pending={over.pending ?? false} error={over.error ?? null} onMove={onMove} />,
  )
  return { onMove, container }
}

describe('StatusBar', () => {
  it.each<[Status, Status[], string, string[]]>([
    ['draft', ['in_review'], 'Draft · only commerce and invited reviewers can see it.', ['Submit for review']],
    ['draft', [], 'Draft · only commerce and invited reviewers can see it.', []],
    ['in_review', ['draft', 'active'], 'Awaiting review by the commerce owner.', ['Approve', 'Request changes']],
    ['in_review', ['draft'], 'Awaiting review by the commerce owner.', ['Withdraw']],
    ['in_review', [], 'Awaiting review by the commerce owner.', []],
    ['deprecated', ['active', 'retired'], 'Deprecated · consumers should move to a newer contract.', ['Reactivate', 'Retire']],
    ['deprecated', [], 'Deprecated · consumers should move to a newer contract.', []],
  ])('for %s with %j', (status, transitions, text, buttons) => {
    renderBar(status, transitions)
    expect(screen.getByText(text)).toBeInTheDocument()
    expect(screen.queryAllByRole('button').map((b) => b.textContent)).toEqual(buttons)
  })

  it.each<Status>(['active', 'retired'])('shows nothing for %s', (status) => {
    const { container } = renderBar(status, ['deprecated', 'retired'])
    expect(container).toBeEmptyDOMElement()
  })

  it.each<[Status, Status[], string, Status]>([
    ['draft', ['in_review'], 'Submit for review', 'in_review'],
    ['in_review', ['draft', 'active'], 'Approve', 'active'],
    ['in_review', ['draft', 'active'], 'Request changes', 'draft'],
    ['in_review', ['draft'], 'Withdraw', 'draft'],
    ['deprecated', ['active', 'retired'], 'Reactivate', 'active'],
    ['deprecated', ['active', 'retired'], 'Retire', 'retired'],
  ])('%s: %s moves to the chosen status', (status, transitions, button, target) => {
    const { onMove } = renderBar(status, transitions)
    fireEvent.click(screen.getByRole('button', { name: button }))
    expect(onMove).toHaveBeenCalledWith(target)
  })

  it('shows the error of the last move', () => {
    renderBar('in_review', ['draft', 'active'], { error: 'The contract is now draft. Reload and try again.' })
    expect(screen.getByText('The contract is now draft. Reload and try again.')).toBeInTheDocument()
  })

  it('disables its buttons while a move runs', () => {
    renderBar('in_review', ['draft', 'active'], { pending: true })
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
  })
})
