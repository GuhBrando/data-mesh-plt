import type { QualityDimension, QualityMetric, QualityOperator, QualityRule } from '../types'

// Mirrors backend/domain/quality_rules.py, which stays authoritative: the API
// refuses any rule datacontract-cli 1.2.9 cannot run. These checks only let the
// form name the problem before saving.

export const DIMENSIONS: readonly QualityDimension[] = [
  'accuracy',
  'completeness',
  'conformity',
  'consistency',
  'coverage',
  'timeliness',
  'uniqueness',
]
export const METRICS: readonly QualityMetric[] = [
  'nullValues',
  'missingValues',
  'invalidValues',
  'duplicateValues',
  'rowCount',
]
export const OPERATORS: readonly QualityOperator[] = [
  'mustBe',
  'mustNotBe',
  'mustBeGreaterThan',
  'mustBeGreaterOrEqualTo',
  'mustBeLessThan',
  'mustBeLessOrEqualTo',
]
// The tool only runs unit percent on these.
export const PERCENT_METRICS: readonly QualityMetric[] = ['nullValues', 'missingValues', 'invalidValues']

const OPERATOR_SYMBOLS: Record<QualityOperator, string> = {
  mustBe: '=',
  mustNotBe: '≠',
  mustBeGreaterThan: '>',
  mustBeGreaterOrEqualTo: '≥',
  mustBeLessThan: '<',
  mustBeLessOrEqualTo: '≤',
}

export function emptyRule(): QualityRule {
  return {
    type: 'library',
    dimension: 'completeness',
    column: '',
    metric: 'nullValues',
    operator: 'mustBe',
    value: 0,
    unit: 'rows',
    valid_values: [],
    description: '',
  }
}

export function withMetric(rule: QualityRule, metric: QualityMetric): QualityRule {
  return {
    ...rule,
    metric,
    column: metric === 'rowCount' ? '' : rule.column,
    unit: rule.unit === 'percent' && !PERCENT_METRICS.includes(metric) ? 'rows' : rule.unit,
    valid_values: metric === 'invalidValues' ? rule.valid_values : [],
  }
}

export function withType(rule: QualityRule, type: QualityRule['type']): QualityRule {
  if (type === 'text') {
    return { ...rule, type, metric: null, operator: null, value: null, unit: null, valid_values: [] }
  }
  const { metric, operator, value, unit } = emptyRule()
  return { ...rule, type, metric, operator, value, unit }
}

function textProblem(rule: QualityRule): string | null {
  return rule.description.trim() ? null : 'a text rule needs a description'
}

function valueProblem(rule: QualityRule): string | null {
  if (rule.value === null || !Number.isFinite(rule.value)) return 'a library rule needs a value'
  if (rule.value < 0) return 'value cannot be negative'
  if (rule.unit === 'percent' && rule.value > 100) return 'a percent value cannot exceed 100'
  return null
}

function libraryProblem(rule: QualityRule): string | null {
  const metric = rule.metric ?? 'nullValues'
  const problem = valueProblem(rule)
  if (problem) return problem
  if (metric === 'rowCount' && rule.column) return 'rowCount applies to the whole table'
  if (metric !== 'rowCount' && !rule.column) return `${metric} needs a column`
  if (rule.unit === 'percent' && !PERCENT_METRICS.includes(metric)) {
    return `unit percent only runs with ${PERCENT_METRICS.join(', ')}`
  }
  if (metric === 'invalidValues' && rule.valid_values.length === 0) return 'invalidValues needs valid values'
  return null
}

function ruleProblem(rule: QualityRule, fieldNames: string[]): string | null {
  const shape = rule.type === 'text' ? textProblem(rule) : libraryProblem(rule)
  if (shape) return shape
  if (rule.column && !fieldNames.includes(rule.column)) return `column '${rule.column}' is not a schema field`
  return null
}

export function qualityProblem(rules: QualityRule[], fieldNames: string[]): string | null {
  const seen = new Set<string>()
  for (const [index, rule] of rules.entries()) {
    const problem = ruleProblem(rule, fieldNames)
    if (problem) return `Rule ${index + 1}: ${problem}`
    if (rule.type !== 'library') continue
    // The tool cannot run two rules on one metric and column.
    const key = `${rule.metric}\u0000${rule.column}`
    if (seen.has(key)) {
      return `Rule ${index + 1}: ${rule.column || 'the table'} already has a ${rule.metric} rule`
    }
    seen.add(key)
  }
  return null
}

export function describeCheck(rule: QualityRule): string {
  if (rule.type === 'text' || !rule.metric || !rule.operator) return '—'
  const unit = rule.unit ? ` ${rule.unit}` : ''
  const valid = rule.metric === 'invalidValues' ? ` (valid: ${rule.valid_values.join(', ')})` : ''
  return `${rule.metric} ${OPERATOR_SYMBOLS[rule.operator]} ${rule.value}${unit}${valid}`
}
