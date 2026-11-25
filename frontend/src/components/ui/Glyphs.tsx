import type { CSSProperties } from 'react'
import { STATUS_LABELS, TIER_NAMES, domainColor, initials, type GlyphStatus } from '../../lib/contracts'

export function StatusGlyph({ status, className = '' }: { status: GlyphStatus; className?: string }) {
  return <span className={`st st-${status} ${className}`}>{STATUS_LABELS[status] ?? status}</span>
}

export function TierGlyph({
  tier,
  showName = false,
  className = '',
}: {
  tier: number
  showName?: boolean
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[11.5px] font-medium text-tx2 whitespace-nowrap ${className}`}
      title={`Tier ${tier} · ${TIER_NAMES[tier] ?? ''}`}
    >
      <span className={`tier tier-${tier}`} aria-hidden="true">
        <i />
        <i />
        <i />
        <i />
      </span>
      T{tier}
      {showName && TIER_NAMES[tier] ? ` · ${TIER_NAMES[tier]}` : ''}
    </span>
  )
}

export function DomainChip({ name, className = '' }: { name: string; className?: string }) {
  return (
    <span className={`dom ${className}`} style={{ '--dc': domainColor(name) } as CSSProperties}>
      {name}
    </span>
  )
}

export function Avatar({ name, size = 22, className = '' }: { name: string; size?: number; className?: string }) {
  return (
    <span
      className={`inline-grid place-items-center shrink-0 rounded-full border border-line2 bg-raised font-semibold text-tx2 ${className}`}
      style={{ width: size, height: size, fontSize: Math.max(7.5, size * 0.4) }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}
