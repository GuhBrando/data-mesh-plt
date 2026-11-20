import { useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useCountUp } from '../hooks/useCountUp'
import Spinner from '../components/ui/Spinner'
import { Avatar, DomainChip, StatusGlyph, TierGlyph } from '../components/ui/Glyphs'
import {
  AlertIcon,
  ArrowRightIcon,
  ChevronRightIcon,
  ContractIcon,
  DomainIcon,
  NewContractIcon,
  PlusIcon,
  ProductIcon,
  RepoIcon,
  ShieldAlertIcon,
  UserPlusIcon,
  UsersIcon,
} from '../components/icons'
import { STATUS_ORDER, TIER_NAMES, domainColor, type ContractStatus } from '../lib/contracts'
import { relativeTime } from '../lib/format'
import {
  buildAttention,
  buildDomainCards,
  buildRecent,
  countStatuses,
  countTiers,
  hasMaintainer,
  pct,
  plural,
  useOverview,
  type AttentionItem,
  type DomainCard,
  type Overview,
  type RecentRow,
  type StatusCounts,
} from './dashboard/overview'

const STATUS_BG: Record<ContractStatus, string> = {
  active: 'bg-ok',
  in_review: 'bg-warn',
  draft: 'bg-mute',
  deprecated: 'bg-dep',
  retired: 'bg-line2',
}

const ATTENTION_ICON: Record<AttentionItem['key'], ReactNode> = {
  review: <AlertIcon size={15} />,
  repo: <RepoIcon size={15} />,
  quality: <ShieldAlertIcon size={15} />,
  maintainer: <UserPlusIcon size={15} />,
}

const delay = (s: number): CSSProperties => ({ animationDelay: `${s}s` })

// ─── Small pieces ─────────────────────────────────────────────────────────────

function StatusBar({ counts, total, className = '' }: { counts: StatusCounts; total: number; className?: string }) {
  if (total === 0) {
    return (
      <span className={`flex ${className}`}>
        <span className="h-full w-full rounded-[2px] bg-line" />
      </span>
    )
  }
  return (
    <span className={`flex gap-[2px] ${className}`}>
      {STATUS_ORDER.filter((s) => counts[s] > 0).map((s) => (
        <span key={s} className={`h-full rounded-[2px] ${STATUS_BG[s]}`} style={{ width: `${pct(counts[s], total)}%` }} />
      ))}
    </span>
  )
}

function PanelHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="flex min-h-[46px] items-center gap-2 border-b border-line px-4">
      <h2 className="text-[13px] font-semibold text-tx">{title}</h2>
      {children}
    </header>
  )
}

function TextLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="group ml-auto inline-flex items-center gap-1 text-xs text-tx2 transition-colors duration-150 hover:text-tx"
    >
      {children}
      <ArrowRightIcon size={12} className="transition-transform duration-150 group-hover:translate-x-0.5" />
    </Link>
  )
}

function Dash() {
  return <span className="text-tx3">—</span>
}

// ─── Header ───────────────────────────────────────────────────────────────────

function Header({ syncedAt }: { syncedAt: number }) {
  return (
    <div className="flex animate-enter flex-wrap items-end justify-between gap-4" style={delay(0.04)}>
      <div>
        <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-tx">Overview</h1>
        <p className="mt-1.5 text-[13px] text-tx2">Health of domains, contracts and data products.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {syncedAt > 0 && (
          <span className="mr-1.5 inline-flex items-center gap-[7px] text-xs text-tx3">
            <span className="h-1.5 w-1.5 rounded-full bg-ok shadow-[0_0_0_3px_rgb(var(--ok)/0.18)]" />
            Synced {relativeTime(new Date(syncedAt).toISOString()).toLowerCase()}
          </span>
        )}
        <Link to="/data-contracts/new" className="btn-secondary">
          <NewContractIcon size={15} />
          New contract
        </Link>
        <Link to="/data-products?new=1" className="btn-primary">
          <PlusIcon size={15} />
          New data product
        </Link>
      </div>
    </div>
  )
}

// ─── KPIs ─────────────────────────────────────────────────────────────────────

function Kpi({
  to,
  icon,
  label,
  value,
  ready,
  children,
}: {
  to: string
  icon: ReactNode
  label: string
  value: number
  ready: boolean
  children: ReactNode
}) {
  const shown = useCountUp(ready ? value : 0)
  return (
    <Link
      to={to}
      className="flex min-w-0 flex-col gap-1.5 px-[18px] py-4 transition-colors duration-150 hover:bg-hover [&+&]:border-l [&+&]:border-line max-lg:[&:nth-child(3)]:border-l-0 max-lg:[&:nth-child(n+3)]:border-t"
    >
      <span className="flex items-center gap-[7px] text-xs text-tx2">
        {icon}
        {label}
      </span>
      <span className="text-[30px] font-semibold leading-[1.1] tracking-[-0.03em] tabular-nums text-tx">
        {ready ? shown : '—'}
      </span>
      <span className="flex min-h-5 items-center gap-2.5 text-xs text-tx3">{children}</span>
    </Link>
  )
}

function KpiStrip({ o, counts }: { o: Overview; counts: StatusCounts }) {
  const withRepo = o.products.filter((p) => p.repo_url).length
  const missingMaintainer = o.domains.filter((d) => !hasMaintainer(d)).length
  const admins = o.users.filter((u) => u.role === 'admin').length
  return (
    <section
      aria-label="Key figures"
      className="grid animate-enter grid-cols-2 overflow-hidden rounded-[10px] border border-line bg-panel lg:grid-cols-4"
      style={delay(0.1)}
    >
      <Kpi to="/data-products" icon={<ProductIcon size={14} className="text-tx3" />} label="Data products" value={o.products.length} ready={o.ready.products}>
        <span className="h-1 w-14 shrink-0 overflow-hidden rounded-sm bg-line">
          <span className="block h-full origin-left animate-grow rounded-sm bg-tx2" style={{ width: `${pct(withRepo, o.products.length)}%` }} />
        </span>
        {withRepo} of {o.products.length} with a repository
      </Kpi>
      <Kpi to="/data-contracts" icon={<ContractIcon size={14} className="text-tx3" />} label="Data contracts" value={o.contracts.length} ready={o.ready.contracts}>
        <StatusBar counts={counts} total={o.contracts.length} className="h-1 w-14 shrink-0 origin-left animate-grow" />
        {counts.in_review} waiting for review
      </Kpi>
      <Kpi to="/domains" icon={<DomainIcon size={14} className="text-tx3" />} label="Domains" value={o.domains.length} ready={o.ready.domains}>
        <span className="flex shrink-0 gap-[3px]">
          {o.domains.slice(0, 6).map((d) => (
            <span key={d.id} className="h-2 w-2 rounded-sm" style={{ background: domainColor(d.name) }} />
          ))}
        </span>
        {missingMaintainer === 0 ? 'All with a maintainer' : `${missingMaintainer} without a maintainer`}
      </Kpi>
      <Kpi to="/users" icon={<UsersIcon size={14} className="text-tx3" />} label="Users" value={o.users.length} ready={o.ready.users}>
        <span className="flex shrink-0">
          {o.users.slice(0, 4).map((u, i) => (
            <Avatar key={u.id} name={u.username} size={20} className={`shadow-[0_0_0_2px_rgb(var(--panel))] ${i ? '-ml-[5px]' : ''}`} />
          ))}
        </span>
        {plural(admins, 'admin')}
      </Kpi>
    </section>
  )
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────

function StatusLegend({ counts, total }: { counts: StatusCounts; total: number }) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
      {STATUS_ORDER.map((s) => (
        <div key={s} className="flex min-w-0 flex-col gap-1">
          <StatusGlyph status={s} />
          <span className="flex items-baseline gap-1.5">
            <b className={`text-xl font-semibold tracking-[-0.02em] tabular-nums ${counts[s] ? 'text-tx' : 'text-tx3'}`}>
              {counts[s]}
            </b>
            <span className="text-[11.5px] text-tx3">{counts[s] ? `${Math.round(pct(counts[s], total))}%` : '—'}</span>
          </span>
        </div>
      ))}
    </div>
  )
}

function TierBreakdown({ tiers }: { tiers: Record<number, number> }) {
  const max = Math.max(1, ...Object.values(tiers))
  return (
    <div className="border-t border-line px-4 pb-4 pt-3.5">
      <p className="mb-2.5 text-xs font-medium text-tx2">By tier</p>
      <div className="grid gap-x-7 gap-y-1.5 sm:grid-cols-2">
        {[1, 2, 3, 4].map((t) => (
          <div key={t} className="grid h-[26px] grid-cols-[36px_minmax(0,1fr)_64px_18px] items-center gap-2.5 text-[12.5px]">
            <TierGlyph tier={t} />
            <span className="truncate text-tx2">{TIER_NAMES[t]}</span>
            <span className="h-1 overflow-hidden rounded-sm bg-line">
              <span className="block h-full origin-left animate-grow rounded-sm bg-tx2" style={{ width: `${pct(tiers[t], max)}%` }} />
            </span>
            <b className="text-right font-medium tabular-nums text-tx">{tiers[t]}</b>
          </div>
        ))}
      </div>
    </div>
  )
}

function LifecyclePanel({ o, counts }: { o: Overview; counts: StatusCounts }) {
  const tiers = useMemo(() => countTiers(o.contracts), [o.contracts])
  const total = o.contracts.length
  return (
    <section className="min-w-0 animate-enter rounded-[10px] border border-line bg-panel" style={delay(0.16)}>
      <PanelHeader title="Contract lifecycle">
        <span className="text-xs text-tx3">{plural(total, 'contract')}</span>
        <TextLink to="/data-contracts">Open contracts</TextLink>
      </PanelHeader>
      {o.contractsLoading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : (
        <>
          <div className="px-4 py-[18px]">
            <StatusBar counts={counts} total={total} className="h-2.5 origin-left animate-grow [&>span]:rounded-[3px]" />
            <StatusLegend counts={counts} total={total} />
          </div>
          <TierBreakdown tiers={tiers} />
        </>
      )}
    </section>
  )
}

// ─── Needs attention ──────────────────────────────────────────────────────────

function AttentionPanel({ items }: { items: AttentionItem[] }) {
  return (
    <section className="min-w-0 animate-enter rounded-[10px] border border-line bg-panel" style={delay(0.22)}>
      <PanelHeader title="Needs attention">
        {items.length > 0 && (
          <span className="rounded-full border border-line bg-raised px-[7px] font-mono text-[11px] font-medium leading-[18px] text-tx2">
            {items.length}
          </span>
        )}
      </PanelHeader>
      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-1 px-4 py-12 text-center">
          <p className="text-[13px] font-medium text-tx">All clear</p>
          <p className="text-xs text-tx3">Nothing is waiting on review, repositories or owners.</p>
        </div>
      ) : (
        <ul className="p-1.5">
          {items.map((a) => (
            <li key={a.key}>
              <Link to={a.to} className="group flex items-center gap-3 rounded-lg p-2.5 transition-colors duration-150 hover:bg-hover">
                <span
                  className={`grid h-[30px] w-[30px] shrink-0 place-items-center rounded-lg border ${
                    a.warn ? 'border-warn/25 bg-warn/10 text-warn' : 'border-line bg-raised text-tx2'
                  }`}
                >
                  {ATTENTION_ICON[a.key]}
                </span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <b className="text-[13px] font-medium text-tx">{a.title}</b>
                  <span className="truncate text-[11.5px] text-tx3">{a.detail}</span>
                </span>
                <ChevronRightIcon size={14} className="ml-auto text-tx3 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-tx" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// ─── Recently updated ─────────────────────────────────────────────────────────

type RecentKind = 'all' | 'contract' | 'product'

function RecentRowView({ r, index }: { r: RecentRow; index: number }) {
  const c = r.contract
  const KindIcon = r.kind === 'product' ? ProductIcon : ContractIcon
  return (
    <tr className="animate-swap transition-colors duration-150 hover:bg-hover" style={delay(index * 0.03)}>
      <td className="h-[46px] border-b border-line px-4">
        <Link to={r.to} className="group/name flex min-w-0 items-center gap-2.5">
          <KindIcon className="text-tx3" role="img" aria-hidden={undefined} aria-label={r.kind === 'product' ? 'Data product' : 'Data contract'} />
          <span className="truncate font-medium text-tx group-hover/name:underline group-hover/name:decoration-line2 group-hover/name:underline-offset-[3px]">
            {r.name}
          </span>
        </Link>
      </td>
      <td className="border-b border-line px-4">{c ? <DomainChip name={c.domain} /> : <Dash />}</td>
      <td className="border-b border-line px-4">{c ? <StatusGlyph status={c.status} /> : <Dash />}</td>
      <td className="border-b border-line px-4">{c ? <TierGlyph tier={c.tier} /> : <Dash />}</td>
      <td className="border-b border-line px-4">
        {c?.owner ? (
          <span className="inline-flex items-center gap-2 text-[12.5px] text-tx2">
            <Avatar name={c.owner} size={20} />
            {c.owner}
          </span>
        ) : (
          <Dash />
        )}
      </td>
      <td className="border-b border-line px-4 text-right text-[12.5px] text-tx3">{relativeTime(r.updatedAt)}</td>
    </tr>
  )
}

function RecentPanel({ o }: { o: Overview }) {
  const [kind, setKind] = useState<RecentKind>('all')
  const recent = useMemo(() => buildRecent(o.contracts, o.products), [o.contracts, o.products])
  const shown = recent.filter((r) => kind === 'all' || r.kind === kind).slice(0, 8)
  const tabs: [RecentKind, string, number][] = [
    ['all', 'All', recent.length],
    ['contract', 'Contracts', o.contracts.length],
    ['product', 'Products', o.products.length],
  ]
  return (
    <section className="reveal rounded-[10px] border border-line bg-panel">
      <PanelHeader title="Recently updated">
        <div className="ml-auto flex gap-0.5 rounded-lg border border-line bg-raised p-0.5" aria-label="Filter by type">
          {tabs.map(([k, label, n]) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              aria-pressed={kind === k}
              className={`inline-flex h-6 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors duration-150 ${
                kind === k ? 'bg-panel text-tx shadow-[0_0_0_1px_rgb(var(--line))]' : 'text-tx3 hover:text-tx'
              }`}
            >
              {label}
              <span className="font-mono text-[10.5px] text-tx3">{n}</span>
            </button>
          ))}
        </div>
      </PanelHeader>
      {shown.length === 0 ? (
        <p className="px-4 py-12 text-center text-[13px] text-tx3">Nothing here yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse">
            <thead>
              <tr className="text-left text-[11.5px] text-tx3">
                <th className="border-b border-line px-4 py-2.5 font-medium">Name</th>
                <th className="border-b border-line px-4 py-2.5 font-medium">Domain</th>
                <th className="border-b border-line px-4 py-2.5 font-medium">Contract status</th>
                <th className="border-b border-line px-4 py-2.5 font-medium">Tier</th>
                <th className="border-b border-line px-4 py-2.5 font-medium">Owner</th>
                <th className="border-b border-line px-4 py-2.5 text-right font-medium">Updated</th>
              </tr>
            </thead>
            <tbody key={kind}>
              {shown.map((r, i) => (
                <RecentRowView key={r.key} r={r} index={i} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// ─── Domains ──────────────────────────────────────────────────────────────────

function DomainCardView({ d }: { d: DomainCard }) {
  return (
    <Link
      to="/domains"
      className="flex flex-col gap-3 rounded-[10px] border border-line bg-panel px-4 py-3.5 transition-[border-color,background-color,transform] duration-150 hover:-translate-y-px hover:border-line2 hover:bg-raised"
    >
      <span className="flex items-center justify-between gap-2">
        <DomainChip name={d.domain.name} className="!text-[13.5px] font-semibold !text-tx" />
        {d.noMaintainer && (
          <span className="inline-flex items-center gap-1.5 text-[11px] text-warn">
            <span className="h-[5px] w-[5px] rounded-full bg-warn" />
            No maintainer
          </span>
        )}
      </span>
      <span className="inline-flex items-center gap-2 text-xs text-tx2">
        <Avatar name={d.domain.owner_username} size={18} />
        {d.domain.owner_username}
      </span>
      <StatusBar counts={d.counts} total={d.contracts} className="h-1 w-full" />
      <span className="flex gap-3.5 text-xs text-tx3">
        <span>
          <b className="mr-0.5 font-medium tabular-nums text-tx">{d.contracts}</b> contracts
        </span>
        <span>
          <b className="mr-0.5 font-medium tabular-nums text-tx">{d.products}</b> products
        </span>
        <span>
          <b className="mr-0.5 font-medium tabular-nums text-tx">{d.members}</b> members
        </span>
      </span>
    </Link>
  )
}

function DomainsSection({ o }: { o: Overview }) {
  const cards = useMemo(() => buildDomainCards(o.domains, o.contracts, o.products), [o.domains, o.contracts, o.products])
  if (cards.length === 0) return null
  return (
    <section className="reveal flex flex-col gap-3">
      <div className="flex items-center gap-2 px-0.5">
        <h2 className="text-[13px] font-semibold text-tx">Domains</h2>
        <span className="text-xs text-tx3">{cards.length}</span>
        <TextLink to="/domains">Manage domains</TextLink>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-3">
        {cards.map((d) => (
          <DomainCardView key={d.domain.id} d={d} />
        ))}
      </div>
    </section>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const o = useOverview()
  const counts = useMemo(() => countStatuses(o.contracts), [o.contracts])
  const attention = useMemo(() => buildAttention(o.contracts, o.products, o.domains), [o.contracts, o.products, o.domains])

  return (
    <div className="flex flex-col gap-5">
      <Header syncedAt={o.syncedAt} />
      <KpiStrip o={o} counts={counts} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        <LifecyclePanel o={o} counts={counts} />
        <AttentionPanel items={attention} />
      </div>
      <RecentPanel o={o} />
      <DomainsSection o={o} />
    </div>
  )
}
