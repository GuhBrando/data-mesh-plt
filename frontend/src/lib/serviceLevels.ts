import type { ServiceLevelProperty, ServiceLevels } from '../types'

// The form shows four service levels. A contract may hold more (a synced file
// can carry frequency or support time), and saving the form keeps those.

export const SLA_KEYS = ['freshness', 'availability', 'retention', 'latency'] as const
export type SlaKey = (typeof SLA_KEYS)[number]

// ODCS units: min for minutes, because datacontract-cli reads m as months.
export const DURATION_UNITS = ['s', 'min', 'h', 'd', 'w', 'y'] as const
export const UNITS: Record<SlaKey, readonly string[]> = {
  freshness: DURATION_UNITS,
  availability: ['%'],
  retention: DURATION_UNITS,
  latency: DURATION_UNITS,
}
const DEFAULT_UNITS: Record<SlaKey, string> = { freshness: 'h', availability: '%', retention: 'd', latency: 'h' }

export interface SlaInput {
  value: string
  unit: string
}

const isNumber = (value: string): boolean => value.trim() !== '' && Number.isFinite(Number(value))

function storedProperties(sl: ServiceLevels | undefined): ServiceLevelProperty[] {
  // An unmigrated row has no properties key; it reads as empty instead of crashing.
  return Array.isArray(sl?.properties) ? sl.properties : []
}

export function readSlaInputs(sl: ServiceLevels | undefined): Record<SlaKey, SlaInput> {
  const stored = storedProperties(sl)
  const inputs = {} as Record<SlaKey, SlaInput>
  for (const key of SLA_KEYS) {
    const found = stored.find((p) => p.property === key)
    inputs[key] = found
      ? { value: String(found.value), unit: found.unit ?? '' }
      : { value: '', unit: DEFAULT_UNITS[key] }
  }
  return inputs
}

export function slaInputProblem(input: SlaInput): string | null {
  const value = input.value.trim()
  if (!value) return null
  if (isNumber(value) && !input.unit) return 'Pick a unit'
  if (!isNumber(value) && input.unit) return 'Use a number, or clear the unit to keep text'
  return null
}

export function toServiceLevels(
  inputs: Record<SlaKey, SlaInput>,
  previous: ServiceLevels | undefined,
): ServiceLevels {
  const shown: ServiceLevelProperty[] = []
  for (const key of SLA_KEYS) {
    const value = inputs[key].value.trim()
    if (!value) continue
    shown.push(
      isNumber(value)
        ? { property: key, value: Number(value), unit: inputs[key].unit || null }
        : { property: key, value, unit: null },
    )
  }
  const hidden = storedProperties(previous).filter((p) => !(SLA_KEYS as readonly string[]).includes(p.property))
  return { properties: [...shown, ...hidden] }
}

export function formatServiceLevel(p: ServiceLevelProperty): string {
  return p.unit ? `${p.value} ${p.unit}` : String(p.value)
}
