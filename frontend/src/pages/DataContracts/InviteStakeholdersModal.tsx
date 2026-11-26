import { useMemo, useState } from 'react'
import Modal from '../../components/ui/Modal'
import Button from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { useInviteStakeholders } from '../../hooks/useContractStakeholders'
import { useUsers } from '../../hooks/useUsers'
import { useAllDomains } from '../../hooks/useDomains'
import type { DataContract, Stakeholder, User } from '../../types'

interface Candidate {
  user: User
  // Why they cannot be chosen; null when they can.
  reason: string | null
}

// Display only: the API decides who reads drafts. These users already do.
function alreadyReads(user: User, isMember: boolean): boolean {
  if (user.role === 'PLATFORM_ADMIN') return true
  return isMember && (user.role === 'DATA_OWNER' || user.role === 'DATA_STEWARD')
}

function OptionRow({ c, selected, onToggle }: { c: Candidate; selected: boolean; onToggle: () => void }) {
  const disabled = c.reason !== null
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      aria-label={c.reason ? `${c.user.username}, ${c.reason}` : c.user.username}
      disabled={disabled}
      onClick={onToggle}
      className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm transition-colors ${
        selected ? 'bg-accent text-accent-ink' : disabled ? 'cursor-not-allowed text-tx3' : 'text-tx2 hover:bg-hover'
      }`}
    >
      {c.user.username}
      {c.reason && <span className="text-xs text-tx3">{c.reason}</span>}
    </button>
  )
}

function Group({ id, label, candidates, selected, onToggle }: {
  id: string
  label: string
  candidates: Candidate[]
  selected: string[]
  onToggle: (userId: string) => void
}) {
  if (candidates.length === 0) return null
  return (
    <div role="group" aria-labelledby={id}>
      <p id={id} className="bg-raised px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-tx3">
        {label}
      </p>
      <div className="divide-y divide-line">
        {candidates.map((c) => (
          <OptionRow key={c.user.id} c={c} selected={selected.includes(c.user.id)} onToggle={() => onToggle(c.user.id)} />
        ))}
      </div>
    </div>
  )
}

/** Choose people to invite to read a draft: the contract's domain first. */
export default function InviteStakeholdersModal({
  contract,
  stakeholders,
  open,
  onClose,
}: {
  contract: DataContract
  stakeholders: Stakeholder[]
  open: boolean
  onClose: () => void
}) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const { data: users = [], isLoading, isError } = useUsers()
  const { data: domains = [] } = useAllDomains()
  const invite = useInviteStakeholders(contract.id)

  const { members, others } = useMemo(() => {
    const memberIds = new Set(domains.find((d) => d.id === contract.domain_id)?.members.map((m) => m.user_id) ?? [])
    const invited = new Set(stakeholders.map((s) => s.user_id))
    const needle = search.trim().toLowerCase()
    const candidates = users
      .filter((u) => u.username.toLowerCase().includes(needle))
      .sort((a, b) => a.username.localeCompare(b.username))
      .map((user): Candidate & { member: boolean } => {
        const member = memberIds.has(user.id)
        const reason = invited.has(user.id)
          ? 'Already invited'
          : alreadyReads(user, member)
            ? `Already reads drafts of ${contract.domain}`
            : null
        return { user, reason, member }
      })
    return { members: candidates.filter((c) => c.member), others: candidates.filter((c) => !c.member) }
  }, [users, domains, stakeholders, search, contract.domain_id, contract.domain])

  const toggle = (userId: string) =>
    setSelected((current) => (current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId]))

  async function handleInvite() {
    try {
      await invite.mutateAsync(selected)
      onClose()
    } catch {
      // The error shows below; the choice stays so the user can retry.
    }
  }

  const empty = members.length === 0 && others.length === 0
  return (
    <Modal open={open} onClose={onClose} title="Invite reviewers" size="sm">
      <div className="space-y-4">
        <Input
          label="Search users"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Type a username…"
        />
        <div
          role="listbox"
          aria-label="Users"
          aria-multiselectable="true"
          className="max-h-60 overflow-y-auto rounded-lg border border-line"
        >
          {isLoading ? (
            <p className="py-6 text-center text-sm text-tx3">Loading users…</p>
          ) : isError ? (
            <p className="py-6 text-center text-sm text-bad">Failed to load users.</p>
          ) : empty ? (
            <p className="py-6 text-center text-sm text-tx3">No users found.</p>
          ) : (
            <>
              <Group id="invite-members" label={`Members of ${contract.domain}`} candidates={members} selected={selected} onToggle={toggle} />
              <Group id="invite-others" label="Everyone else" candidates={others} selected={selected} onToggle={toggle} />
            </>
          )}
        </div>
        {invite.isError && <p className="text-sm text-bad">{invite.error?.message}</p>}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={selected.length === 0} loading={invite.isPending} onClick={handleInvite}>
            Invite
          </Button>
        </div>
      </div>
    </Modal>
  )
}
