import type { DataContract, QualityDimension, QualityRule, ServiceLevelProperty, ServiceLevels } from '../types'

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

const SLA_UNITS: Partial<Record<string, string>> = { percent: '%', m: 'min' }

// '24h' -> 24 h, '99.9 %' -> 99.9 %, '30m' -> 30 min; anything else stays text.
function splitServiceLevel(text: string): Omit<ServiceLevelProperty, 'property'> | null {
  const unitStart = text.search(/[a-zA-Z%]/)
  const numberPart = (unitStart === -1 ? text : text.slice(0, unitStart)).trim()
  const unitPart = unitStart === -1 ? '' : text.slice(unitStart)
  if (!/^\d+$|^\d+\.\d+$/.test(numberPart)) return null
  if (unitPart && !/^[a-zA-Z%]+$/.test(unitPart)) return null
  return { value: Number(numberPart), unit: unitPart ? (SLA_UNITS[unitPart] ?? unitPart) : null }
}

function normalizeServiceLevels(raw: unknown): ServiceLevels {
  if (typeof raw !== 'object' || raw === null) return { properties: [] }
  if ('properties' in raw) return raw as ServiceLevels
  const properties: ServiceLevelProperty[] = []
  for (const [property, stored] of Object.entries(raw as Record<string, unknown>)) {
    const text = typeof stored === 'string' ? stored.trim() : ''
    if (!text) continue
    properties.push({ property, ...(splitServiceLevel(text) ?? { value: text, unit: null }) })
  }
  return { properties }
}

export function normalizeContract(raw: DataContract): DataContract {
  const quality = ((raw.models.quality ?? []) as unknown[]).map(normalizeRule)
  return {
    ...raw,
    models: { ...raw.models, quality },
    servicelevels: normalizeServiceLevels(raw.servicelevels),
  }
}
