import { useId, useState, type ReactNode } from 'react'
import { Controller, type Control, type FieldErrors, type UseFormRegister } from 'react-hook-form'
import { Input, Textarea } from '../../components/ui/Input'
import EditableRows, { ROW_INPUT_CLASS } from '../../components/rows/EditableRows'
import TeamMembers from '../../components/rows/TeamMembers'
import SupportChannels from '../../components/rows/SupportChannels'
import { MANAGEMENT_CONTENTS, PRODUCT_TYPES } from '../../lib/products'
import type {
  AuthoritativeDefinition,
  ContextConstraint,
  CustomProperty,
  DataProductInput,
  ManagementPort,
  SupportChannel,
  Synonym,
  TeamMember,
  VerifiedStatement,
} from '../../types'

/** Comma-separated tags; the list updates as the user types. */
export function TagsInput({
  value,
  onChange,
  label,
  className = ROW_INPUT_CLASS,
}: {
  value: string[]
  onChange: (tags: string[]) => void
  label: string
  className?: string
}) {
  const [text, setText] = useState(value.join(', '))
  return (
    <input
      aria-label={label}
      placeholder="Tags, comma separated"
      className={className}
      value={text}
      onChange={(e) => {
        setText(e.target.value)
        onChange(
          e.target.value
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean),
        )
      }}
    />
  )
}

/** The first message anywhere in an error tree: a list's own rule, or a row's. */
export function firstMessage(error: unknown): string | undefined {
  if (!error || typeof error !== 'object') return undefined
  const { message } = error as { message?: unknown }
  if (typeof message === 'string' && message) return message
  for (const child of Object.values(error)) {
    const found = firstMessage(child)
    if (found) return found
  }
  return undefined
}

// A text that is empty is left out, as ODPS leaves out what is not set;
// the product's own texts are null then, as the API returns them.
const orAbsent = (value: string) => value || undefined
const orNull = (value: string) => value || null

function Group({ legend, hint, error, children }: { legend: string; hint: string; error?: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3 border-t border-line pt-4 first:border-0 first:pt-0">
      <legend className="text-[13px] font-semibold text-tx">{legend}</legend>
      <p className="text-xs text-tx3">{hint}</p>
      {children}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </fieldset>
  )
}

function Rows<T>({
  rows,
  onChange,
  emptyRow,
  addLabel,
  cells,
}: {
  rows: T[] | undefined
  onChange: (rows: T[]) => void
  emptyRow: () => T
  addLabel: string
  cells: (row: T, patch: (p: Partial<T>) => void) => ReactNode
}) {
  return (
    <EditableRows
      rows={rows ?? []}
      onChange={onChange}
      emptyRow={emptyRow}
      addLabel={addLabel}
      emptyText="None yet."
      renderRow={(row, _index, patch) => <div className="col-span-11 flex flex-wrap gap-2">{cells(row, patch)}</div>}
    />
  )
}

function cell(label: string, value: string | null | undefined, onChange: (v: string) => void, placeholder = label) {
  return (
    <input
      aria-label={label}
      placeholder={placeholder}
      className={`min-w-0 flex-1 ${ROW_INPUT_CLASS}`}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

const SECTION_FIELDS = [
  'version',
  'type',
  'tenant',
  'tags',
  'synonyms',
  'context',
  'team',
  'support',
  'custom_properties',
  'authoritative_definitions',
  'management_ports',
] as const

interface MoreFieldsProps {
  control: Control<DataProductInput>
  register: UseFormRegister<DataProductInput>
  errors: FieldErrors<DataProductInput>
}

/**
 * Every ODPS field beyond the short path, grouped by what it is for, closed
 * until asked for — or until one of its fields needs fixing.
 */
export default function MoreFields({ control, register, errors }: MoreFieldsProps) {
  const [open, setOpen] = useState(false)
  const typesId = useId()
  const contentsId = useId()
  const invalid =
    SECTION_FIELDS.some((field) => errors[field]) || !!errors.description?.usage || !!errors.description?.limitations
  const shown = open || invalid
  const text = (value: string | null | undefined) => value ?? ''

  return (
    <div className="rounded-lg border border-line">
      <button
        type="button"
        aria-expanded={shown}
        onClick={() => setOpen(!shown)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-[13px] font-medium text-tx"
      >
        <span>More ODPS fields</span>
        <span className="text-xs font-normal text-tx3">version, type, team, support, tags, context, …</span>
      </button>
      {shown && (
        <div className="space-y-5 border-t border-line px-4 py-4">
          <datalist id={typesId}>
            {PRODUCT_TYPES.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <datalist id={contentsId}>
            {MANAGEMENT_CONTENTS.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>

          <Group legend="About" hint="What the product is, how to use it and the names people search it by.">
            <div className="grid gap-3 sm:grid-cols-3">
              <Input label="Version" placeholder="1.0.0" {...register('version', { setValueAs: orNull })} />
              <Input label="Type" placeholder="consumerAligned" list={typesId} {...register('type', { setValueAs: orNull })} />
              <Input label="Tenant" {...register('tenant', { setValueAs: orNull })} />
            </div>
            <Textarea label="Usage" rows={2} className="!font-sans !text-sm" {...register('description.usage')} />
            <Textarea label="Limitations" rows={2} className="!font-sans !text-sm" {...register('description.limitations')} />
            <Controller
              name="tags"
              control={control}
              render={({ field }) => <TagsInput label="Tags" value={field.value} onChange={field.onChange} className="form-input" />}
            />
            <Controller
              name="synonyms"
              control={control}
              render={({ field }) => (
                <Rows<Synonym>
                  rows={field.value}
                  onChange={field.onChange}
                  emptyRow={() => ({ synonym: '' })}
                  addLabel="Add synonym"
                  cells={(row, patch) => (
                    <>
                      {cell('Synonym', row.synonym, (v) => patch({ synonym: v }))}
                      {cell('Synonym status', row.status, (v) => patch({ status: orAbsent(v) }), 'Status')}
                      {cell('Synonym source', row.source, (v) => patch({ source: orAbsent(v) }), 'Source')}
                    </>
                  )}
                />
              )}
            />
          </Group>

          <Group
            legend="People"
            hint="Who builds the product and where consumers ask for help."
            error={firstMessage(errors.team) ?? firstMessage(errors.support)}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Team name" {...register('team.name', { setValueAs: orAbsent })} />
              <Input label="Team description" {...register('team.description', { setValueAs: orAbsent })} />
            </div>
            <Controller
              name="team.members"
              control={control}
              render={({ field }) => (
                <TeamMembers rows={(field.value ?? []) as TeamMember[]} onChange={field.onChange} />
              )}
            />
            <Controller
              name="support"
              control={control}
              render={({ field }) => (
                <SupportChannels rows={field.value as SupportChannel[]} onChange={field.onChange} />
              )}
            />
          </Group>

          <Group
            legend="For AI agents"
            hint="Guidance for AI agents and BI tools: how to use the product, what never to do, and questions with known answers."
            error={firstMessage(errors.context)}
          >
            <Textarea
              label="Instructions"
              rows={3}
              className="!font-sans !text-sm"
              {...register('context.instructions', { setValueAs: orAbsent })}
            />
            <Controller
              name="context.constraints"
              control={control}
              render={({ field }) => (
                <Rows<ContextConstraint>
                  rows={field.value}
                  onChange={field.onChange}
                  emptyRow={() => ({ constraint: '' })}
                  addLabel="Add constraint"
                  cells={(row, patch) => cell('Constraint', row.constraint, (v) => patch({ constraint: v }))}
                />
              )}
            />
            <Controller
              name="context.verified_statements"
              control={control}
              render={({ field }) => (
                <Rows<VerifiedStatement>
                  rows={field.value}
                  onChange={field.onChange}
                  emptyRow={() => ({ question: '' })}
                  addLabel="Add verified statement"
                  cells={(row, patch) => (
                    <>
                      {cell('Question', row.question, (v) => patch({ question: v }))}
                      {cell('Answer', row.answer, (v) => patch({ answer: orAbsent(v) }))}
                    </>
                  )}
                />
              )}
            />
          </Group>

          <Group
            legend="Links"
            hint="Where the product is defined or documented, and any extra properties your organization tracks."
            error={firstMessage(errors.authoritative_definitions) ?? firstMessage(errors.custom_properties)}
          >
            <Controller
              name="authoritative_definitions"
              control={control}
              render={({ field }) => (
                <Rows<AuthoritativeDefinition>
                  rows={field.value}
                  onChange={field.onChange}
                  emptyRow={() => ({ type: '', url: '' })}
                  addLabel="Add definition"
                  cells={(row, patch) => (
                    <>
                      {cell('Definition type', row.type, (v) => patch({ type: v }), 'Type (businessDefinition, …)')}
                      {cell('Definition URL', row.url, (v) => patch({ url: v }), 'URL')}
                    </>
                  )}
                />
              )}
            />
            <Controller
              name="custom_properties"
              control={control}
              render={({ field }) => (
                <Rows<CustomProperty>
                  rows={field.value}
                  onChange={field.onChange}
                  emptyRow={() => ({ property: '', value: '' })}
                  addLabel="Add custom property"
                  cells={(row, patch) => (
                    <>
                      {cell('Property', row.property, (v) => patch({ property: v }))}
                      {cell(
                        'Value',
                        typeof row.value === 'string' ? row.value : JSON.stringify(row.value),
                        (v) => patch({ value: v }),
                      )}
                    </>
                  )}
                />
              )}
            />
          </Group>

          <Group
            legend="Management ports"
            hint="Endpoints that observe or control the product: metrics, health, a data dictionary, a control topic."
            error={firstMessage(errors.management_ports)}
          >
            <Controller
              name="management_ports"
              control={control}
              render={({ field }) => (
                <Rows<ManagementPort>
                  rows={field.value}
                  onChange={field.onChange}
                  emptyRow={() => ({ name: '', content: '', type: 'rest', deprecated: false })}
                  addLabel="Add management port"
                  cells={(row, patch) => (
                    <>
                      {cell('Management port name', row.name, (v) => patch({ name: v }), 'Name')}
                      <input
                        aria-label="Content"
                        placeholder="Content (observability, …)"
                        list={contentsId}
                        className={`min-w-0 flex-1 ${ROW_INPUT_CLASS}`}
                        value={row.content}
                        onChange={(e) => patch({ content: e.target.value })}
                      />
                      <select
                        aria-label="Management port type"
                        className={ROW_INPUT_CLASS}
                        value={row.type}
                        onChange={(e) => patch({ type: e.target.value })}
                      >
                        <option value="rest">rest</option>
                        <option value="topic">topic</option>
                      </select>
                      {cell('Management port URL', text(row.url), (v) => patch({ url: orAbsent(v) }), 'URL')}
                      {cell('Management port channel', text(row.channel), (v) => patch({ channel: orAbsent(v) }), 'Channel')}
                    </>
                  )}
                />
              )}
            />
          </Group>
        </div>
      )}
    </div>
  )
}
