import { useState } from 'react'
import { X, UserPlus, Pencil } from 'lucide-react'
import { useRemoveDomainMember } from '../../hooks/useDomainMembers'
import { useUpdateDomain } from '../../hooks/useDomains'
import type { DomainWithMembers, DomainAccess } from '../../types'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import { Input, Textarea } from '../../components/ui/Input'
import AddMemberModal from './AddMemberModal'
import { Avatar } from '../../components/ui/Glyphs'

const MEMBER_ROLE_VARIANT = {
  maintainer: 'yellow',
  member: 'green',
} as const

interface DomainPanelProps {
  domain: DomainWithMembers
  access: DomainAccess
  onClose: () => void
}

function EditDomainModal({
  domain,
  open,
  onClose,
}: {
  domain: DomainWithMembers
  open: boolean
  onClose: () => void
}) {
  const [name, setName] = useState(domain.name)
  const [description, setDescription] = useState(domain.description)
  const update = useUpdateDomain()

  function handleClose() {
    setName(domain.name)
    setDescription(domain.description)
    onClose()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await update.mutateAsync({ id: domain.id, name, description })
      onClose()
    } catch {
      // error surfaced via update.error
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Edit Domain" size="sm">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Textarea
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          required
        />
        {update.error && (
          <p className="text-xs text-red-600 dark:text-red-400">
            {update.error.message}
          </p>
        )}
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" onClick={handleClose} className="flex-1">
            Cancel
          </Button>
          <Button type="submit" loading={update.isPending} className="flex-1">
            Save
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function PanelContent({
  domain,
  access,
  onClose,
}: DomainPanelProps) {
  const [addOpen, setAddOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const removeMember = useRemoveDomainMember(domain.id)

  const isOwner = access === 'owner' || access === 'admin'
  const canSeeMembers = access !== 'none'

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <h2 className="font-bold text-base text-slate-900 dark:text-white truncate">
            {domain.name}
          </h2>
          <Badge
            variant={
              access === 'admin'
                ? 'blue'
                : access === 'owner'
                  ? 'purple'
                  : access === 'maintainer'
                    ? 'yellow'
                    : access === 'member'
                      ? 'green'
                      : 'gray'
            }
            className="mt-1 text-[10px]"
          >
            {access === 'admin'
              ? 'Admin'
              : access === 'owner'
                ? 'Owner'
                : access === 'maintainer'
                  ? 'Maintainer'
                  : access === 'member'
                    ? 'Member'
                    : 'No Access'}
          </Badge>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shrink-0"
          aria-label="Close panel"
        >
          <X size={15} />
        </button>
      </div>

      {/* Description */}
      <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
        {domain.description}
      </p>

      {/* Owner */}
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Owner
        </p>
        <div className="flex items-center gap-2">
          <Avatar name={domain.owner_username} size={20} />
          <span className="text-xs text-slate-700 dark:text-slate-300">
            {domain.owner_username}
          </span>
        </div>
      </div>

      {/* Members */}
      {canSeeMembers && (
        <div className="flex-1 min-h-0">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Members ({domain.members.length})
            </p>
            {isOwner && (
              <button
                type="button"
                onClick={() => setAddOpen(true)}
                className="flex items-center gap-1 text-[10px] font-medium text-accent-fg hover:text-tx dark:text-accent-fg"
              >
                <UserPlus size={11} />
                Add
              </button>
            )}
          </div>
          <div className="space-y-2 overflow-y-auto max-h-48">
            {domain.members.length === 0 ? (
              <p className="text-xs text-slate-400">No members yet.</p>
            ) : (
              domain.members.map((m) => (
                <div key={m.user_id} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Avatar name={m.username} size={20} />
                    <span className="text-xs text-slate-700 dark:text-slate-300 truncate">
                      {m.username}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Badge variant={MEMBER_ROLE_VARIANT[m.role]} className="text-[9px]">
                      {m.role.charAt(0).toUpperCase() + m.role.slice(1)}
                    </Badge>
                    {isOwner && (
                      <button
                        type="button"
                        onClick={() => removeMember.mutate(m.user_id)}
                        className="text-slate-300 hover:text-red-500 dark:text-slate-600 dark:hover:text-red-400 transition-colors text-xs leading-none"
                        aria-label={`Remove ${m.username}`}
                      >
                        <X size={12} />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Owner: edit button */}
      {isOwner && (
        <div className="border-t border-slate-100 dark:border-slate-700 pt-3 mt-auto">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setEditOpen(true)}
            className="w-full flex items-center justify-center gap-1.5"
          >
            <Pencil size={12} />
            Edit Domain Info
          </Button>
        </div>
      )}

      <AddMemberModal domain={domain} open={addOpen} onClose={() => setAddOpen(false)} />
      <EditDomainModal key={domain.id} domain={domain} open={editOpen} onClose={() => setEditOpen(false)} />
    </div>
  )
}

export default function DomainPanel(props: DomainPanelProps) {
  return (
    <>
      {/* Desktop: side panel */}
      <div className="hidden md:flex flex-col w-72 shrink-0 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 overflow-y-auto">
        <PanelContent {...props} />
      </div>

      {/* Mobile: bottom sheet overlay */}
      <div className="md:hidden fixed inset-0 z-40">
        <div
          className="absolute inset-0 bg-black/40"
          onClick={props.onClose}
          aria-hidden="true"
        />
        <div className="absolute bottom-0 left-0 right-0 bg-white dark:bg-slate-800 rounded-t-2xl max-h-[75vh] flex flex-col p-4 pb-8">
          <div className="w-8 h-1 bg-slate-300 dark:bg-slate-600 rounded-full mx-auto mb-4 shrink-0" />
          <div className="flex-1 overflow-y-auto">
            <PanelContent {...props} />
          </div>
        </div>
      </div>
    </>
  )
}
