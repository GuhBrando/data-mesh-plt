import { useState } from 'react'
import Button from '../../components/ui/Button'
import Spinner from '../../components/ui/Spinner'
import { Avatar } from '../../components/ui/Glyphs'
import { CloseIcon, UserPlusIcon, UsersIcon } from '../../components/icons'
import { useContractStakeholders, useRemoveStakeholder } from '../../hooks/useContractStakeholders'
import { relativeTime } from '../../lib/format'
import type { DataContract, Stakeholder } from '../../types'
import InviteStakeholdersModal from './InviteStakeholdersModal'
import { Empty, Panel } from './Panel'

// Published contracts are read by everyone: no one needs an invitation.
const PUBLISHED: ReadonlySet<DataContract['status']> = new Set(['active', 'deprecated', 'retired'])

const ROLE_LABELS: Record<string, string> = {
  PLATFORM_ADMIN: 'Admin',
  DATA_OWNER: 'Owner',
  DATA_STEWARD: 'Steward',
  DATA_CONSUMER: 'Consumer',
}

function StakeholderRow({ s, onRemove }: { s: Stakeholder; onRemove?: () => void }) {
  const by = s.assigned_by_username ? `Invited by ${s.assigned_by_username}` : undefined
  return (
    <li className="flex h-[38px] items-center gap-2.5 text-[12.5px]">
      <Avatar name={s.username} />
      <span className="min-w-0 truncate text-tx">{s.username}</span>
      <span className="ml-auto shrink-0 text-xs text-tx3" title={by}>
        {ROLE_LABELS[s.role] ?? s.role} · {relativeTime(s.assigned_at).toLowerCase()}
      </span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${s.username}`}
          className="shrink-0 text-tx3 transition-colors hover:text-bad"
        >
          <CloseIcon size={12} />
        </button>
      )}
    </li>
  )
}

/** Who may read this draft before it is published, and inviting more. */
export default function StakeholdersPanel({ contract }: { contract: DataContract }) {
  const visible = !PUBLISHED.has(contract.status)
  const { data: rows = [], isLoading, isError } = useContractStakeholders(contract.id, visible)
  const remove = useRemoveStakeholder(contract.id)
  const [inviteOpen, setInviteOpen] = useState(false)
  if (!visible) return null

  const canManage = !!contract.permissions?.manage_stakeholders
  const add = canManage && rows.length > 0 && (
    <button
      type="button"
      onClick={() => setInviteOpen(true)}
      className="inline-flex items-center gap-1 font-medium text-accent-fg transition-colors hover:text-tx"
    >
      <UserPlusIcon size={12} />
      Add
    </button>
  )

  return (
    <Panel
      title="Stakeholders"
      icon={<UsersIcon size={15} />}
      aside={<span className="inline-flex items-center gap-2.5">{rows.length > 0 && rows.length}{add}</span>}
    >
      <p className="px-4 pt-3 text-xs text-tx3">Can read this draft before it is published.</p>
      {isLoading ? (
        <div className="flex justify-center py-5"><Spinner size="sm" /></div>
      ) : isError ? (
        <p className="px-4 py-5 text-center text-[13px] text-bad">Could not load the stakeholders.</p>
      ) : rows.length === 0 ? (
        <>
          <Empty>No one invited yet.</Empty>
          {canManage && (
            <div className="flex justify-center px-4 pb-4">
              <Button size="sm" variant="secondary" onClick={() => setInviteOpen(true)}>
                <UserPlusIcon size={12} />
                Invite reviewers
              </Button>
            </div>
          )}
        </>
      ) : (
        <ul className="px-4 py-1.5">
          {rows.map((s) => (
            <StakeholderRow
              key={s.user_id}
              s={s}
              onRemove={canManage && !remove.isPending ? () => remove.mutate(s.user_id) : undefined}
            />
          ))}
        </ul>
      )}
      {remove.isError && <p className="px-4 pb-3 text-xs text-bad">{remove.error.message}</p>}
      {inviteOpen && (
        <InviteStakeholdersModal
          contract={contract}
          stakeholders={rows}
          open
          onClose={() => setInviteOpen(false)}
        />
      )}
    </Panel>
  )
}
