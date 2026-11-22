import { useId, useState, type ReactNode } from 'react'
import Spinner from '../../components/ui/Spinner'
import { DomainChip, StatusGlyph, TierGlyph } from '../../components/ui/Glyphs'
import { ContractIcon, FilterIcon } from '../../components/icons'
import type { DataContract } from '../../types'

// Below this many contracts the whole list fits at a glance; no filter needed.
const FILTER_FROM = 6

interface ContractPickerProps {
  contracts: DataContract[]
  value: string
  onChange: (id: string) => void
  loading?: boolean
  loadError?: string | null
  error?: string
}

function matches(c: DataContract, needle: string): boolean {
  return [c.title, c.domain, c.owner, c.description?.purpose].some(
    (v) => typeof v === 'string' && v.toLowerCase().includes(needle),
  )
}

function Notice({ tone = 'muted', children }: { tone?: 'muted' | 'bad'; children: ReactNode }) {
  const toneClass = tone === 'bad' ? 'border-bad/40 text-bad' : 'border-dashed border-line2 text-tx3'
  return <div className={`rounded-lg border px-4 py-6 text-center text-[13px] ${toneClass}`}>{children}</div>
}

function ContractOption({
  contract: c,
  name,
  checked,
  onSelect,
}: {
  contract: DataContract
  name: string
  checked: boolean
  onSelect: () => void
}) {
  const detailsId = `${name}-${c.id}-details`
  return (
    <label className="group flex cursor-pointer gap-3 px-3 py-2.5 transition-colors duration-150 hover:bg-hover has-[:checked]:bg-accent/[0.07] has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-inset has-[:focus-visible]:ring-accent-fg/50">
      <input
        type="radio"
        name={name}
        value={c.id}
        checked={checked}
        onChange={onSelect}
        aria-label={c.title}
        aria-describedby={detailsId}
        className="sr-only"
      />
      <span
        aria-hidden="true"
        className="mt-[3px] grid h-4 w-4 shrink-0 place-items-center rounded-full border border-line2 transition-colors group-has-[:checked]:border-accent-fg"
      >
        <i className="h-2 w-2 scale-0 rounded-full bg-accent-fg transition-transform duration-150 group-has-[:checked]:scale-100" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate font-mono text-[12.5px] font-medium text-tx">{c.title}</span>
          <TierGlyph tier={c.tier} />
        </span>
        <span id={detailsId} className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <DomainChip name={c.domain} className="!text-xs" />
          <span className="font-mono text-[11.5px] text-tx2">v{c.version}</span>
          <StatusGlyph status={c.status} className="!text-xs" />
          {c.owner && <span className="text-xs text-tx3">{c.owner}</span>}
        </span>
        {c.description?.purpose && (
          <span className="mt-1 block truncate text-xs text-tx3" title={c.description.purpose}>
            {c.description.purpose}
          </span>
        )}
      </span>
    </label>
  )
}

function FilterInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="mb-2 flex h-8 items-center gap-2 rounded-lg border border-line2 bg-panel px-2.5 text-tx3 transition-shadow focus-within:border-accent-fg focus-within:ring-[3px] focus-within:ring-accent/20">
      <FilterIcon size={15} />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Filter by title, domain or owner"
        aria-label="Filter data contracts"
        className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-tx outline-none placeholder:text-tx3"
      />
    </label>
  )
}

function ContractList({
  contracts,
  name,
  labelId,
  errorId,
  value,
  onChange,
  error,
}: {
  contracts: DataContract[]
  name: string
  labelId: string
  errorId: string
  value: string
  onChange: (id: string) => void
  error?: string
}) {
  if (contracts.length === 0) return <Notice>No contracts match this filter.</Notice>
  return (
    <div
      role="radiogroup"
      aria-labelledby={labelId}
      aria-invalid={!!error}
      aria-describedby={error ? errorId : undefined}
      className={`max-h-[264px] divide-y divide-line overflow-y-auto rounded-lg border ${error ? 'border-bad' : 'border-line2'}`}
    >
      {contracts.map((c) => (
        <ContractOption key={c.id} contract={c} name={name} checked={value === c.id} onSelect={() => onChange(c.id)} />
      ))}
    </div>
  )
}

function Unavailable({ loading, loadError }: { loading: boolean; loadError: string | null }) {
  if (loading) {
    return (
      <Notice>
        <Spinner size="sm" className="mx-auto" />
      </Notice>
    )
  }
  if (loadError) return <Notice tone="bad">Could not load data contracts: {loadError}</Notice>
  return (
    <Notice>
      <ContractIcon size={18} className="mx-auto mb-2 text-tx3" />
      <p className="font-medium text-tx2">No data contracts available to you</p>
      <p className="mt-1 text-xs">A data product can only use a contract from a domain you belong to.</p>
    </Notice>
  )
}

/**
 * Pick the data contract a product is built on, from the contracts the user
 * can reach, each with the few facts that tell them apart.
 */
export default function ContractPicker({
  contracts,
  value,
  onChange,
  loading = false,
  loadError = null,
  error,
}: ContractPickerProps) {
  const name = useId()
  const labelId = `${name}-label`
  const errorId = `${name}-error`
  const [query, setQuery] = useState('')
  const needle = query.trim().toLowerCase()
  const shown = needle ? contracts.filter((c) => matches(c, needle)) : contracts
  const ready = !loading && !loadError && contracts.length > 0

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span id={labelId} className="form-label !mb-0">
          Data contract
        </span>
        {ready && (
          <span className="text-[11.5px] tabular-nums text-tx3">
            {needle ? `${shown.length} of ${contracts.length}` : contracts.length} available
          </span>
        )}
      </div>
      {!ready && <Unavailable loading={loading} loadError={loadError} />}
      {ready && contracts.length >= FILTER_FROM && <FilterInput value={query} onChange={setQuery} />}
      {ready && (
        <ContractList
          contracts={shown}
          name={name}
          labelId={labelId}
          errorId={errorId}
          value={value}
          onChange={onChange}
          error={error}
        />
      )}
      {error && (
        <p id={errorId} className="form-error">
          {error}
        </p>
      )}
    </div>
  )
}
