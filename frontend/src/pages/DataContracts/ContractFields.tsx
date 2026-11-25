import EditableRows, { ROW_INPUT_CLASS } from '../../components/rows/EditableRows'
import type { FieldClassification, SchemaField } from '../../types'

const FIELD_TYPES = ['string', 'integer', 'float', 'boolean', 'date', 'timestamp'] as const
const CLASSIFICATIONS = ['public', 'internal', 'confidential', 'restricted'] as const

interface ContractFieldsProps {
  fields: SchemaField[]
  onChange: (fields: SchemaField[]) => void
}

const emptyField = (): SchemaField => ({
  name: '',
  type: 'string',
  description: '',
  nullable: true,
  primary_key: false,
  classification: '',
  unique: false,
  physical_type: '',
})

// A field stored before classification, unique and physical type existed lacks them.
export function withFieldDefaults(field: SchemaField): SchemaField {
  return { ...emptyField(), ...field }
}

const CHECKBOX_CLASS = 'flex items-center gap-1 text-xs text-gray-500 dark:text-slate-400 cursor-pointer'

export default function ContractFields({ fields, onChange }: ContractFieldsProps) {
  return (
    <EditableRows
      rows={fields}
      onChange={onChange}
      emptyRow={emptyField}
      addLabel="Add field"
      emptyText="No fields yet."
      renderRow={(field, _index, patch) => (
        <>
          <input
            className={`col-span-3 ${ROW_INPUT_CLASS}`}
            placeholder="field_name"
            value={field.name}
            onChange={(e) => patch({ name: e.target.value })}
          />
          <select
            className={`col-span-2 ${ROW_INPUT_CLASS}`}
            value={field.type}
            onChange={(e) => patch({ type: e.target.value as SchemaField['type'] })}
          >
            {FIELD_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <input
            className={`col-span-4 ${ROW_INPUT_CLASS}`}
            placeholder="Description"
            value={field.description}
            onChange={(e) => patch({ description: e.target.value })}
          />
          <label className={`col-span-1 ${CHECKBOX_CLASS}`}>
            <input
              type="checkbox"
              checked={field.nullable}
              onChange={(e) => patch({ nullable: e.target.checked })}
            />
            Null
          </label>
          <label className={`col-span-2 ${CHECKBOX_CLASS}`}>
            <input
              type="checkbox"
              checked={field.primary_key}
              onChange={(e) => patch({ primary_key: e.target.checked })}
            />
            PK
          </label>
          <input
            className={`col-span-5 ${ROW_INPUT_CLASS}`}
            placeholder="Physical type"
            value={field.physical_type}
            onChange={(e) => patch({ physical_type: e.target.value })}
          />
          <select
            aria-label="Classification"
            className={`col-span-4 ${ROW_INPUT_CLASS}`}
            value={field.classification}
            onChange={(e) => patch({ classification: e.target.value as FieldClassification })}
          >
            <option value="">unclassified</option>
            {CLASSIFICATIONS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <label className={`col-span-2 ${CHECKBOX_CLASS}`}>
            <input
              type="checkbox"
              checked={field.unique}
              onChange={(e) => patch({ unique: e.target.checked })}
            />
            Unique
          </label>
        </>
      )}
    />
  )
}
