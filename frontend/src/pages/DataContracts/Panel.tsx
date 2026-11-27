import type { ReactNode } from 'react'

/** A titled card of the contract page's side column. */
export function Panel({ title, icon, aside, children }: { title: string; icon?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-[10px] border border-line bg-panel">
      <header className="flex min-h-[44px] items-center gap-2 border-b border-line px-4 text-tx3">
        {icon}
        <h2 className="text-[13px] font-semibold text-tx">{title}</h2>
        {aside && <span className="ml-auto text-xs text-tx3">{aside}</span>}
      </header>
      {children}
    </section>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-6 text-center text-[13px] text-tx3">{children}</p>
}
