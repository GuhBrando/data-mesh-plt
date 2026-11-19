import { useState } from 'react'
import EditableRows, { ROW_INPUT_CLASS as INPUT } from './EditableRows'
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

const parseValues = (text: string): string[] => text.split(',').map((v) => v.trim()).filter(Boolean)

function ValidValuesInput({ rule, onChange }: Omit<RowProps, 'fieldNames'>) {
  // The typed text stays local, so the comma being typed is not swallowed, while
  // the rule updates on every keystroke: Enter submits what is on screen.
  const [text, setText] = useState(rule.valid_values.join(', '))
  return (
    <input
      aria-label="Valid values"
      className={`col-span-11 ${INPUT}`}
      placeholder="Valid values, comma separated"
      value={text}
      onChange={(e) => {
        setText(e.target.value)
        onChange({ ...rule, valid_values: parseValues(e.target.value) })
      }}
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
        className={`col-span-2 ${INPUT}`}
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
  return (
    <EditableRows
      rows={rules}
      onChange={onChange}
      emptyRow={emptyRule}
      addLabel="Add rule"
      emptyText="No quality rules yet."
      renderRow={(rule, _index, patch) => (
        <RuleRow rule={rule} fieldNames={fieldNames} onChange={(next) => patch(next)} />
      )}
    />
  )
}
