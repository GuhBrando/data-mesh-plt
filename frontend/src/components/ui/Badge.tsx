import { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  variant?: 'blue' | 'green' | 'yellow' | 'red' | 'gray' | 'purple'
  className?: string
}

// Variant names are kept for existing callers; they map onto the semantic tokens.
// `badge-<variant>` stays on the element so the variant remains identifiable.
const variantClasses: Record<string, string> = {
  blue: 'bg-accent/10 text-accent-fg border-accent/25',
  green: 'bg-ok/10 text-ok border-ok/25',
  yellow: 'bg-warn/10 text-warn border-warn/25',
  red: 'bg-bad/10 text-bad border-bad/25',
  gray: 'bg-raised text-tx2 border-line',
  purple: 'bg-tx/5 text-tx border-tx/20',
}

export default function Badge({
  children,
  variant = 'gray',
  className = '',
}: BadgeProps) {
  return (
    <span
      className={`badge-${variant} inline-flex h-5 items-center rounded-[5px] border px-1.5 text-[11.5px] font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  )
}
