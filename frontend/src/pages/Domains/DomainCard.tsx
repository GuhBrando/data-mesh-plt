import { Users, FileText } from 'lucide-react'
import Badge from '../../components/ui/Badge'
import type { DomainWithMembers, DomainAccess } from '../../types'

const ACCESS_CARD_CLASSES: Record<DomainAccess, string> = {
  admin:
    'border-[1.5px] border-accent-fg bg-accent/10 dark:bg-accent/10 dark:border-accent-fg',
  owner:
    'border-[1.5px] border-accent-fg bg-accent/10 dark:bg-accent/10 dark:border-accent-fg',
  maintainer:
    'border-[1.5px] border-amber-400 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-400',
  member:
    'border-[1.5px] border-green-500 bg-green-50 dark:bg-green-900/20 dark:border-green-400',
  none: 'border border-slate-200 bg-slate-50 dark:bg-slate-800/50 dark:border-slate-700 opacity-65',
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
      className={`w-full text-left rounded-xl p-3 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-fg ring-offset-2 ${ACCESS_CARD_CLASSES[access]} ${isSelected ? 'ring-2 ring-accent-fg' : ''}`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="font-semibold text-sm text-slate-900 dark:text-white truncate">
          {domain.name}
        </span>
        <Badge variant={ACCESS_BADGE_VARIANT[access]} className="shrink-0 text-[10px]">
          {ACCESS_LABELS[access]}
        </Badge>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mb-2">
        {domain.description}
      </p>
      <div className="flex gap-3 text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <Users size={10} aria-hidden="true" />
          {domain.members.length}
        </span>
        <span className="flex items-center gap-1">
          <FileText size={10} aria-hidden="true" />
          {domain.contract_count}
        </span>
      </div>
    </button>
  )
}
