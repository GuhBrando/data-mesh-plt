import type { ReactNode } from 'react'
import Button from '../../components/ui/Button'
import { AlertIcon, LockIcon, PendingIcon } from '../../components/icons'
import type { DataContract } from '../../types'

type Status = DataContract['status']

interface Move {
  to: Status
  label: string
  primary?: boolean
}

interface Bar {
  text: (domain: string) => string
  icon: ReactNode
  tone: string
  // Offered in this order, each only when the user may make it.
  moves: (allowed: Status[]) => Move[]
}

const WARN = 'border-warn/30 bg-warn/10'

const BARS: Partial<Record<Status, Bar>> = {
  draft: {
    text: (domain) => `Draft · only ${domain} and invited reviewers can see it.`,
    icon: <LockIcon className="text-tx3" />,
    tone: 'border-line bg-raised',
    moves: () => [{ to: 'in_review', label: 'Submit for review', primary: true }],
  },
  in_review: {
    text: (domain) => `Awaiting review by the ${domain} owner.`,
    icon: <PendingIcon className="text-warn" />,
    tone: WARN,
    // The owner approves or sends back; the steward who submitted can withdraw.
    moves: (allowed) =>
      allowed.includes('active')
        ? [{ to: 'active', label: 'Approve', primary: true }, { to: 'draft', label: 'Request changes' }]
        : [{ to: 'draft', label: 'Withdraw' }],
  },
  deprecated: {
    text: () => 'Deprecated · consumers should move to a newer contract.',
    icon: <AlertIcon className="text-warn" />,
    tone: WARN,
    moves: () => [{ to: 'active', label: 'Reactivate' }, { to: 'retired', label: 'Retire' }],
  },
}

/** Where the contract is in its review, and the moves the user may make next. */
export default function StatusBar({
  contract,
  pending,
  error,
  onMove,
}: {
  contract: DataContract
  pending: boolean
  error: string | null
  onMove: (to: Status) => void
}) {
  const bar = BARS[contract.status]
  if (!bar) return null
  const allowed = contract.permissions?.transitions ?? []
  const moves = bar.moves(allowed).filter((m) => allowed.includes(m.to))
  return (
    <div className={`flex animate-enter flex-wrap items-center gap-3 rounded-[10px] border px-4 py-3 [animation-delay:0.06s] ${bar.tone}`}>
      {bar.icon}
      <p className="flex-1 text-[13px] text-tx">{bar.text(contract.domain)}</p>
      {moves.map((m) => (
        <Button key={m.to} size="sm" variant={m.primary ? 'primary' : 'secondary'} disabled={pending} onClick={() => onMove(m.to)}>
          {m.label}
        </Button>
      ))}
      {error && <p className="w-full text-[12px] text-bad">{error}</p>}
    </div>
  )
}
