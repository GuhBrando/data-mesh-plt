import { useState, useMemo } from 'react'
import { DomainIcon } from '../../components/icons'
import { useAllDomains } from '../../hooks/useDomains'
import { useAuth } from '../../contexts/AuthContext'
import { getDomainAccess } from '../../lib/domains'
import type { DomainAccess } from '../../types'
import DomainCard from './DomainCard'
import DomainPanel from './DomainPanel'

type FilterTab = 'all' | Exclude<DomainAccess, 'none'>

const FILTER_LABELS: Record<FilterTab, string> = {
  all: 'All',
  admin: 'Admin',
  owner: 'Owner',
  maintainer: 'Maintainer',
  member: 'Member',
}

export default function DomainsList() {
  const { user } = useAuth()
  const { data: domains = [], isLoading, error, refetch } = useAllDomains()
  const [filter, setFilter] = useState<FilterTab>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const domainsWithAccess = useMemo(
    () =>
      domains.map((d) => ({
        domain: d,
        access: user ? getDomainAccess(d, user.id, user.role) : ('none' as DomainAccess),
      })),
    [domains, user],
  )

  const counts = useMemo(
    () =>
      domainsWithAccess.reduce(
        (acc, { access }) => {
          acc[access] = (acc[access] ?? 0) + 1
          return acc
        },
        {} as Record<DomainAccess, number>,
      ),
    [domainsWithAccess],
  )

  const filterTabs = useMemo(
    () => [
      { id: 'all' as FilterTab, label: 'All', count: domains.length },
      { id: 'admin' as FilterTab, label: 'Admin', count: counts.admin ?? 0 },
      { id: 'owner' as FilterTab, label: 'Owner', count: counts.owner ?? 0 },
      { id: 'maintainer' as FilterTab, label: 'Maintainer', count: counts.maintainer ?? 0 },
      { id: 'member' as FilterTab, label: 'Member', count: counts.member ?? 0 },
    ],
    [counts, domains.length],
  )

  const filtered = useMemo(
    () =>
      filter === 'all'
        ? domainsWithAccess
        : domainsWithAccess.filter(({ access }) => access === filter),
    [domainsWithAccess, filter],
  )

  const selectedEntry = useMemo(
    () => domainsWithAccess.find(({ domain }) => domain.id === selectedId) ?? null,
    [domainsWithAccess, selectedId],
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500 dark:text-slate-400 text-sm">
        Loading domains…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3">
        <p className="text-sm text-red-600 dark:text-red-400">
          Failed to load domains. {(error as Error).message}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs text-accent-fg underline"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <div className="mb-5 animate-enter">
        <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-tx">Domains</h1>
        <p className="mt-1.5 text-[13px] text-tx2">Browse all domains and manage your access.</p>
      </div>

      {/* Filter chips (mobile) / tabs (desktop) */}
      <div className="mb-4">
        {/* Mobile: scrollable pill chips */}
        <div className="flex gap-2 overflow-x-auto pb-1 md:hidden">
          {filterTabs.filter((t) => t.count > 0 || t.id === 'all').map((tab) => (
            <button
              key={tab.id}
              type="button"
              aria-pressed={filter === tab.id}
              onClick={() => { setFilter(tab.id); setSelectedId(null) }}
              className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === tab.id
                  ? 'border-tx3 bg-raised text-tx'
                  : 'border-line text-tx2'
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>

        {/* Desktop: underline tabs */}
        <div className="hidden gap-0.5 border-b border-line md:flex">
          {filterTabs.filter((t) => t.count > 0 || t.id === 'all').map((tab) => (
            <button
              key={tab.id}
              type="button"
              aria-pressed={filter === tab.id}
              onClick={() => { setFilter(tab.id); setSelectedId(null) }}
              className={`relative h-10 px-3 text-[13px] font-medium transition-colors duration-150 after:absolute after:inset-x-2.5 after:-bottom-px after:h-0.5 after:rounded-full after:bg-accent-fg after:transition-transform after:duration-300 ${
                filter === tab.id ? 'text-tx after:scale-x-100' : 'text-tx3 after:scale-x-0 hover:text-tx'
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>
      </div>

      {/* Content area */}
      <div className="flex flex-1 min-h-0">
        {/* Card grid */}
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-[10px] border border-dashed border-line2 text-tx3">
              <DomainIcon size={24} />
              <p className="text-sm">
                {filter === 'all' ? 'No domains exist yet.' : `No domains with "${FILTER_LABELS[filter]}" access.`}
              </p>
            </div>
          ) : (
            <div className="grid animate-enter grid-cols-1 gap-3 [animation-delay:0.06s] sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map(({ domain, access }) => (
                <DomainCard
                  key={domain.id}
                  domain={domain}
                  access={access}
                  isSelected={domain.id === selectedId}
                  onClick={() =>
                    setSelectedId((prev) => (prev === domain.id ? null : domain.id))
                  }
                />
              ))}
            </div>
          )}
        </div>

        {/* DomainPanel renders once. Desktop: `hidden md:flex` side panel participates
            in flex layout as a sibling. Mobile: `md:hidden fixed` bottom sheet uses
            fixed positioning so DOM location doesn't matter — renders as overlay. */}
        {selectedEntry && (
          <DomainPanel
            domain={selectedEntry.domain}
            access={selectedEntry.access}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  )
}
