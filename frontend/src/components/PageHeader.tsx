import { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRightIcon } from './icons'

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  backTo?: string
}

export default function PageHeader({
  title,
  subtitle,
  actions,
  backTo,
}: PageHeaderProps) {
  const navigate = useNavigate()

  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div className="flex items-start gap-3">
        {backTo && (
          <button
            onClick={() => navigate(backTo)}
            className="mt-0.5 grid h-8 w-8 place-items-center rounded-lg text-tx3 transition-colors hover:bg-hover hover:text-tx"
            aria-label="Go back"
          >
            <ChevronRightIcon className="rotate-180" />
          </button>
        )}
        <div>
          <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-tx">{title}</h1>
          {subtitle && <p className="mt-1.5 text-[13px] text-tx2">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
