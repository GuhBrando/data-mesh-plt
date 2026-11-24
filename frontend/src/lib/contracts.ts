import type { DataContract, ProductStatus } from '../types'

export type ContractStatus = DataContract['status']
// The status glyph shows contracts and products; products add `proposed`.
export type GlyphStatus = ContractStatus | ProductStatus

export const STATUS_ORDER: ContractStatus[] = ['active', 'in_review', 'draft', 'deprecated', 'retired']

export const STATUS_LABELS: Record<GlyphStatus, string> = {
  proposed: 'Proposed',
  active: 'Active',
  in_review: 'In review',
  draft: 'Draft',
  deprecated: 'Deprecated',
  retired: 'Retired',
}

export const TIER_NAMES: Record<number, string> = {
  1: 'Critical / Regulated',
  2: 'Business Important',
  3: 'Operational / Internal',
  4: 'Experimental / Sandbox',
}

// Domain markers: picked by name so a domain keeps its colour everywhere.
const DOMAIN_COLORS = ['#F08A6C', '#6FA8F2', '#B591F2', '#4FC4BD', '#E2B556', '#E57FB0', '#8FC46A', '#9AA3B5']

export function domainColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  return DOMAIN_COLORS[hash % DOMAIN_COLORS.length]
}

export function initials(name: string): string {
  const parts = name.split(/[\s._-]+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2)
  return letters.toUpperCase()
}
