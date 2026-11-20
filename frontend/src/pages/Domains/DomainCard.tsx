import { ContractIcon, UsersIcon } from '../../components/icons'
import { DomainChip } from '../../components/ui/Glyphs'
import Badge from '../../components/ui/Badge'
import type { DomainWithMembers, DomainAccess } from '../../types'

const ACCESS_CARD_CLASSES: Record<DomainAccess, string> = {
  admin: 'border-line bg-panel hover:border-line2 hover:bg-raised',
  owner: 'border-line bg-panel hover:border-line2 hover:bg-raised',
  maintainer: 'border-line bg-panel hover:border-line2 hover:bg-raised',
  member: 'border-line bg-panel hover:border-line2 hover:bg-raised',
  none: 'border-dashed border-line bg-transparent opacity-75 hover:opacity-100',
}

const ACCESS_BADGE_VARIANT: Record<DomainAccess, 'blue' | 'purple' | 'yellow' | 'green' | 'gray'> = {
  admin: 'blue',
  owner: 'purple',
  maintainer: 'yellow',
  member: 'green',
  none: 'gray',
}

const ACCESS_LABELS: Record<DomainAccess, string> = {
  admin: 'Admin',
  owner: 'Owner',
  maintainer: 'Maintainer',
  member: 'Member',
  none: 'No Access',
}

interface DomainCardProps {
  domain: DomainWithMembers
  access: DomainAccess
  isSelected: boolean
  onClick: () => void
}

export default function DomainCard({ domain, access, isSelected, onClick }: DomainCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid="domain-card"
      data-access={access}
      className={`w-full rounded-[10px] border p-3.5 text-left transition-[border-color,background-color,opacity] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-fg ${ACCESS_CARD_CLASSES[access]} ${isSelected ? '!border-accent-fg ring-[3px] ring-accent/20' : ''}`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <DomainChip name={domain.name} className="min-w-0 truncate !text-[13.5px] font-semibold !text-tx" />
        <Badge variant={ACCESS_BADGE_VARIANT[access]} className="shrink-0 !text-[10.5px]">
          {ACCESS_LABELS[access]}
        </Badge>
      </div>
      <p className="mb-3 line-clamp-2 text-xs text-tx2">{domain.description}</p>
      <div className="flex gap-3.5 text-[11.5px] text-tx3">
        <span className="flex items-center gap-1.5" title="Members">
          <UsersIcon size={13} />
          {domain.members.length}
        </span>
        <span className="flex items-center gap-1.5" title="Contracts">
          <ContractIcon size={13} />
          {domain.contract_count}
        </span>
      </div>
    </button>
  )
}
