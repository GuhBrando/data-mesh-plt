import type { DataContract, QualityDimension, QualityRule } from '../types'

// Temporary read shim: a row the data migration has not converted yet still
// holds pre-ODCS rules. Showing them as text rules keeps every old value visible
// and lets the form save. Deleted once the old shapes are removed.

interface LegacyRule {
  dimension?: string
  column?: string
  operator?: string
  threshold?: string
  description?: string
}

const LEGACY_DIMENSIONS: Partial<Record<string, QualityDimension>> = {
  completeness: 'completeness',
  uniqueness: 'uniqueness',
  freshness: 'timeliness',
  validity: 'conformity',
  integrity: 'consistency',
}

function textRule(dimension: QualityDimension | null, description: string): QualityRule {
  return {
    type: 'text',
    dimension,
    column: '',
    metric: null,
    operator: null,
    value: null,
    unit: null,
    valid_values: [],
    description,
  }
}

function normalizeRule(raw: unknown): QualityRule {
  if (typeof raw !== 'object' || raw === null) return textRule(null, `[legacy rule: ${JSON.stringify(raw)}]`)
  if ('type' in raw) return raw as QualityRule
  const old = raw as LegacyRule
  const values = `dimension=${old.dimension ?? ''} column=${old.column ?? ''} operator=${old.operator ?? ''} threshold=${old.threshold ?? ''}`
  const description = `${old.description ?? ''} [legacy rule: ${values}]`.trim()
  return textRule(LEGACY_DIMENSIONS[old.dimension ?? ''] ?? null, description)
}

export function normalizeContract(raw: DataContract): DataContract {
  const quality = ((raw.models.quality ?? []) as unknown[]).map(normalizeRule)
  return { ...raw, models: { ...raw.models, quality } }
}
