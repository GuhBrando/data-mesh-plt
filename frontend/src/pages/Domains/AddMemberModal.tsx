import { useState, useMemo } from 'react'
import { useUsers } from '../../hooks/useUsers'
import { useAddDomainMember } from '../../hooks/useDomainMembers'
import type { DomainWithMembers } from '../../types'
import Modal from '../../components/ui/Modal'
import Button from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

interface AddMemberModalProps {
  domain: DomainWithMembers
  open: boolean
  onClose: () => void
}

export default function AddMemberModal({ domain, open, onClose }: AddMemberModalProps) {
  const [search, setSearch] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [role, setRole] = useState<'member' | 'maintainer'>('member')

  const { data: users = [], isLoading: usersLoading, isError: usersError } = useUsers()
  const addMember = useAddDomainMember(domain.id)

  const existingIds = useMemo(
    () => new Set([domain.owner_id, ...domain.members.map((m) => m.user_id)]),
    [domain],
  )

  const filtered = useMemo(
    () =>
      users.filter(
        (u) =>
          !existingIds.has(u.id) &&
          u.username.toLowerCase().includes(search.toLowerCase()),
      ),
    [users, existingIds, search],
  )

  function handleClose() {
    setSearch('')
    setSelectedUserId(null)
    setRole('member')
    onClose()
  }

  async function handleSubmit() {
    if (!selectedUserId) return
    try {
      await addMember.mutateAsync({ user_id: selectedUserId, role })
      handleClose()
    } catch {
      // error surfaced via addMember.error
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Add Member" size="sm">
      <div className="space-y-4">
        <Input
          label="Search users"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setSelectedUserId(null)
          }}
          placeholder="Type a username…"
        />

        <div
          role="listbox"
          aria-label="Available users"
          className="max-h-40 overflow-y-auto border border-line rounded-lg divide-y divide-line"
        >
          {usersLoading ? (
            <p className="text-sm text-tx3 text-center py-6">Loading users…</p>
          ) : usersError ? (
            <p className="text-sm text-bad text-center py-6">Failed to load users.</p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-tx3 text-center py-6">No users found.</p>
          ) : (
            filtered.map((u) => (
              <button
                key={u.id}
                type="button"
                role="option"
                aria-selected={selectedUserId === u.id}
                onClick={() => setSelectedUserId(u.id)}
                className={`w-full text-left px-3 py-2.5 text-sm transition-colors ${
                  selectedUserId === u.id
                    ? 'bg-accent text-accent-ink'
                    : 'text-tx2 hover:bg-hover'
                }`}
              >
                {u.username}
              </button>
            ))
          )}
        </div>

        <div>
          <p className="text-xs font-medium text-tx2 mb-1.5">Role</p>
          <div className="flex gap-2">
            {(['member', 'maintainer'] as const).map((r) => (
              <button
                key={r}
                type="button"
                aria-pressed={role === r}
                onClick={() => setRole(r)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-colors ${
                  role === r
                    ? 'bg-accent text-accent-ink border-accent'
                    : 'border-line text-tx2 hover:bg-hover'
                }`}
              >
                {r.charAt(0).toUpperCase() + r.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {addMember.error && (
          <p className="text-xs text-bad">
            {addMember.error.message}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="secondary" onClick={handleClose} className="flex-1">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!selectedUserId}
            loading={addMember.isPending}
            className="flex-1"
          >
            Add Member
          </Button>
        </div>
      </div>
    </Modal>
  )
}
