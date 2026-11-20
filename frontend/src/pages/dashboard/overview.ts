import type { ContractStatus } from '../../lib/contracts'
import type { DataContract, DataProduct, DomainWithMembers } from '../../types'

// Pure builders for the Overview page; the data comes from useOverview.

export type StatusCounts = Record<ContractStatus, number>

export function countStatuses(contracts: DataContract[]): StatusCounts {
  const counts: StatusCounts = { active: 0, in_review: 0, draft: 0, deprecated: 0, retired: 0 }
  for (const c of contracts) counts[c.status] += 1
  return counts
}

export function countTiers(contracts: DataContract[]): Record<number, number> {
  const counts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0 }
  for (const c of contracts) counts[c.tier] = (counts[c.tier] ?? 0) + 1
  return counts
}

export function pct(part: number, total: number): number {
  return total === 0 ? 0 : (part / total) * 100
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

export function hasMaintainer(domain: DomainWithMembers): boolean {
  return (domain.members ?? []).some((m) => m.role === 'maintainer')
}

export interface AttentionItem {
  key: 'review' | 'repo' | 'quality' | 'maintainer'
  to: string
  warn: boolean
  title: string
  detail: string
}

function reviewItem(contracts: DataContract[]): AttentionItem | null {
  const inReview = contracts.filter((c) => c.status === 'in_review')
  if (inReview.length === 0) return null
  return {
    key: 'review',
    to: '/data-contracts',
    warn: true,
    title: `${plural(inReview.length, 'contract')} waiting for review`,
    detail: inReview.slice(0, 3).map((c) => c.title).join(' · '),
  }
}

function repoItem(products: DataProduct[]): AttentionItem | null {
  const missing = products.filter((p) => !p.repo_url)
  if (missing.length === 0) return null
  return {
    key: 'repo',
    to: '/data-products',
    warn: false,
    title: `${plural(missing.length, 'product')} without a repository`,
    detail: `Provisioning pending · ${missing.slice(0, 2).map((p) => p.name).join(', ')}`,
  }
}

function qualityItem(contracts: DataContract[]): AttentionItem | null {
  const missing = contracts.filter((c) => !c.models?.quality?.length)
  if (missing.length === 0) return null
  const tierOne = missing.filter((c) => c.tier === 1).length
  return {
    key: 'quality',
    to: '/data-contracts',
    warn: tierOne > 0,
    title: `${plural(missing.length, 'contract')} without quality rules`,
    detail: tierOne > 0
      ? `Includes ${plural(tierOne, 'Tier 1 contract')}`
      : missing.slice(0, 3).map((c) => c.title).join(' · '),
  }
}

function maintainerItem(domains: DomainWithMembers[]): AttentionItem | null {
  const missing = domains.filter((d) => !hasMaintainer(d))
  if (missing.length === 0) return null
  return {
    key: 'maintainer',
    to: '/domains',
    warn: false,
    title: missing.length === 1 ? `${missing[0].name} has no maintainer` : `${missing.length} domains have no maintainer`,
    detail: 'Only the owner can approve their contracts',
  }
}

export function buildAttention(
  contracts: DataContract[],
  products: DataProduct[],
  domains: DomainWithMembers[],
): AttentionItem[] {
  return [reviewItem(contracts), repoItem(products), qualityItem(contracts), maintainerItem(domains)].filter(
    (item): item is AttentionItem => item !== null,
  )
}

export interface RecentRow {
  key: string
  kind: 'contract' | 'product'
  name: string
  to: string
  contract?: DataContract
  updatedAt: string
}

export function buildRecent(contracts: DataContract[], products: DataProduct[]): RecentRow[] {
  const byId = new Map(contracts.map((c) => [c.id, c]))
  const rows: RecentRow[] = [
    ...contracts.map((c) => ({
      key: `c-${c.id}`,
      kind: 'contract' as const,
      name: c.title,
      to: `/data-contracts/${c.id}`,
      contract: c,
      updatedAt: c.updated_at,
    })),
    ...products.map((p) => ({
      key: `p-${p.id}`,
      kind: 'product' as const,
      name: p.name,
      to: `/data-products/${p.id}`,
      contract: byId.get(p.data_contracts_id),
      updatedAt: p.updated_at,
    })),
  ]
  return rows.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
}

export interface DomainCard {
  domain: DomainWithMembers
  contracts: number
  products: number
  members: number
  counts: StatusCounts
  noMaintainer: boolean
}

export function buildDomainCards(
  domains: DomainWithMembers[],
  contracts: DataContract[],
  products: DataProduct[],
): DomainCard[] {
  return domains.map((d) => {
    const own = contracts.filter((c) => c.domain_id === d.id)
    const ownIds = new Set(own.map((c) => c.id))
    return {
      domain: d,
      contracts: own.length,
      products: products.filter((p) => ownIds.has(p.data_contracts_id)).length,
      members: (d.members ?? []).length,
      counts: countStatuses(own),
      noMaintainer: !hasMaintainer(d),
    }
  })
}
