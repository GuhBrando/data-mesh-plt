import { useRef } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import {
  DIMENSIONS,
  METRICS,
  OPERATORS,
  PERCENT_METRICS,
  emptyRule,
  withMetric,
  withType,
} from '../../lib/qualityRules'
import type { QualityDimension, QualityMetric, QualityOperator, QualityRule } from '../../types'

const INPUT =
  'text-sm border border-gray-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-200'

interface QualityRulesProps {
  rules: QualityRule[]
  fieldNames: string[]
  onChange: (rules: QualityRule[]) => void
}

interface RowProps {
  rule: QualityRule
  fieldNames: string[]
  onChange: (rule: QualityRule) => void
}

function ColumnSelect({ rule, fieldNames, onChange }: RowProps) {
  // A column whose field was renamed or removed stays visible, so the form can name it.
  const options = rule.column && !fieldNames.includes(rule.column) ? [...fieldNames, rule.column] : fieldNames
  return (
    <select
      aria-label="Column"
      className={`col-span-3 ${INPUT}`}
      value={rule.column}
      disabled={rule.metric === 'rowCount'}
      onChange={(e) => onChange({ ...rule, column: e.target.value })}
    >
      <option value="">{rule.metric === 'rowCount' ? 'whole table' : '— column —'}</option>
      {options.map((name) => (
        <option key={name} value={name}>{name}</option>
      ))}
    </select>
  )
}

function ValidValuesInput({ rule, onChange }: Omit<RowProps, 'fieldNames'>) {
  // Uncontrolled: parsing on every keystroke would swallow the comma being typed.
  return (
    <input
      aria-label="Valid values"
      className={`col-span-12 ${INPUT}`}
      placeholder="Valid values, comma separated"
      defaultValue={rule.valid_values.join(', ')}
      onBlur={(e) =>
        onChange({
          ...rule,
          valid_values: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
        })
      }
    />
  )
}

function LibraryInputs({ rule, onChange }: Omit<RowProps, 'fieldNames'>) {
  const metric = rule.metric ?? 'nullValues'
  return (
    <>
      <select
        aria-label="Metric"
        className={`col-span-3 ${INPUT}`}
        value={metric}
        onChange={(e) => onChange(withMetric(rule, e.target.value as QualityMetric))}
      >
        {METRICS.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>
      <select
        aria-label="Operator"
        className={`col-span-4 ${INPUT}`}
        value={rule.operator ?? 'mustBe'}
        onChange={(e) => onChange({ ...rule, operator: e.target.value as QualityOperator })}
      >
        {OPERATORS.map((op) => (
          <option key={op} value={op}>{op}</option>
        ))}
      </select>
      <input
        aria-label="Value"
        type="number"
        min={0}
        className={`col-span-2 ${INPUT}`}
        value={rule.value ?? ''}
        onChange={(e) => onChange({ ...rule, value: e.target.value === '' ? null : Number(e.target.value) })}
      />
      <select
        aria-label="Unit"
        className={`col-span-3 ${INPUT}`}
        value={rule.unit ?? ''}
        onChange={(e) => onChange({ ...rule, unit: (e.target.value || null) as QualityRule['unit'] })}
      >
        <option value="">—</option>
        <option value="rows">rows</option>
        <option value="percent" disabled={!PERCENT_METRICS.includes(metric)}>percent</option>
      </select>
      {metric === 'invalidValues' && <ValidValuesInput rule={rule} onChange={onChange} />}
    </>
  )
}

function RuleRow({ rule, fieldNames, onChange }: RowProps) {
  return (
    <>
      <select
        aria-label="Rule type"
        className={`col-span-2 ${INPUT}`}
        value={rule.type}
        onChange={(e) => onChange(withType(rule, e.target.value as QualityRule['type']))}
      >
        <option value="library">library</option>
        <option value="text">text</option>
      </select>
      <select
        aria-label="Dimension"
        className={`col-span-3 ${INPUT}`}
        value={rule.dimension ?? ''}
        onChange={(e) => onChange({ ...rule, dimension: (e.target.value || null) as QualityDimension | null })}
      >
        <option value="">— dimension —</option>
        {DIMENSIONS.map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
      <ColumnSelect rule={rule} fieldNames={fieldNames} onChange={onChange} />
      <input
        aria-label="Description"
        className={`col-span-3 ${INPUT}`}
        placeholder={rule.type === 'text' ? 'Description (required)' : 'Description (optional)'}
        value={rule.description}
        onChange={(e) => onChange({ ...rule, description: e.target.value })}
      />
      {rule.type === 'library' && <LibraryInputs rule={rule} onChange={onChange} />}
    </>
  )
}

export default function QualityRules({ rules, fieldNames, onChange }: QualityRulesProps) {
  const idsRef = useRef<string[]>([])
  const getKey = (index: number): string => {
    while (idsRef.current.length <= index) idsRef.current.push(crypto.randomUUID())
    return idsRef.current[index]
  }

  const update = (index: number, rule: QualityRule) => {
    onChange(rules.map((r, i) => (i === index ? rule : r)))
  }

  const remove = (index: number) => {
    idsRef.current.splice(index, 1)
    onChange(rules.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      {rules.length === 0 && (
        <p className="text-sm text-gray-400 dark:text-slate-500 italic">No quality rules yet.</p>
      )}
      {rules.map((rule, i) => (
        <div
          key={getKey(i)}
          className="grid grid-cols-12 gap-2 items-center rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900"
        >
          <RuleRow rule={rule} fieldNames={fieldNames} onChange={(next) => update(i, next)} />
          <button
            type="button"
            onClick={() => remove(i)}
            className="col-span-1 flex items-center justify-center text-red-400 hover:text-red-600"
            title="Remove rule"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...rules, emptyRule()])}
        className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"
      >
        <Plus size={14} />
        Add rule
      </button>
    </div>
  )
}
