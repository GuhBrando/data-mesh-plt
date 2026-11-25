import { useId, useState, type ReactNode } from 'react'
import EditableRows, { ROW_INPUT_CLASS } from '../../components/rows/EditableRows'
import ContractPicker from './ContractPicker'
import Badge from '../../components/ui/Badge'
import { PlusIcon } from '../../components/icons'
import { slugify } from '../../lib/products'
import type { ContractSummary, DataContract, InputPort, OutputPort, ProductRef } from '../../types'

/** The contracts a picker offers, with their loading state. */
export interface ContractSource {
  contracts: DataContract[]
  loading: boolean
  error: string | null
}

// ODPS suggests these output types; any other value is allowed.
const OUTPUT_TYPES = ['tables', 'topic', 'files', 'api']

export function emptyOutput(): OutputPort {
  return {
    name: '',
    contract_id: null,
    version: null,
    type: 'tables',
    description: null,
    deprecated: false,
    authoritative_definitions: [],
    input_contracts: [],
    tags: [],
    custom_properties: [],
    synonyms: [],
    context: {},
    sbom: [],
  }
}

function emptyInput(): InputPort {
  return {
    name: '',
    contract_id: null,
    version: null,
    deprecated: false,
    authoritative_definitions: [],
    tags: [],
    custom_properties: [],
  }
}

function summaryOf(c: DataContract): ContractSummary {
  return { title: c.title, status: c.status, version: c.version, domain: c.domain }
}

/** A port on a picked contract: its current version, and its name unless one was typed. */
function onContract<T extends InputPort | OutputPort>(row: T, c: DataContract): T {
  return { ...row, name: row.name || slugify(c.title), contract_id: c.id, version: c.version, contract: summaryOf(c) }
}

function titleOf(port: InputPort | OutputPort, source: ContractSource): string {
  return port.contract?.title ?? source.contracts.find((c) => c.id === port.contract_id)?.title ?? port.contract_id ?? ''
}

function producedBy(producers: Map<string, ProductRef[]>, contractId: string): string {
  const names = (producers.get(contractId) ?? []).map((p) => p.name)
  return names.length ? `Produced by ${names.join(', ')}` : 'No producer on the platform'
}

/** Rows that repeat the name of an earlier row: the older side of a version move. */
function isOlder(rows: { name: string }[], index: number): boolean {
  return rows.slice(0, index).some((r) => r.name === rows[index].name)
}

function Section({ legend, hint, error, children }: { legend: string; hint: string; error?: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-2">
      <legend className="form-label">{legend}</legend>
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

function PickerPanel({
  label,
  source,
  value,
  detail,
  emptyHint,
  onPick,
  onCancel,
}: {
  label: string
  source: ContractSource
  value: string
  detail?: (c: DataContract) => ReactNode
  emptyHint?: string
  onPick: (c: DataContract) => void
  onCancel: () => void
}) {
  return (
    <div className="space-y-2 rounded-lg border border-line2 p-3">
      <ContractPicker
        label={label}
        contracts={source.contracts}
        value={value}
        loading={source.loading}
        loadError={source.error}
        detail={detail}
        emptyHint={emptyHint}
        onChange={(id) => {
          const contract = source.contracts.find((c) => c.id === id)
          if (contract) onPick(contract)
        }}
      />
      <button type="button" aria-label="Cancel picking" onClick={onCancel} className="text-xs text-tx2 hover:text-tx">
        Cancel
      </button>
    </div>
  )
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="flex items-center gap-1 text-sm text-accent-fg hover:underline">
      <PlusIcon size={14} />
      {label}
    </button>
  )
}

function BuiltFrom({ row, inputs, patch }: { row: OutputPort; inputs: InputPort[]; patch: (p: Partial<OutputPort>) => void }) {
  const cited = inputs.filter((i): i is InputPort & { contract_id: string; version: string } => !!i.contract_id && !!i.version)
  if (cited.length === 0) return null
  const has = (i: { contract_id: string; version: string }) =>
    row.input_contracts.some((r) => r.contract_id === i.contract_id && r.version === i.version)
  const toggle = (i: { contract_id: string; version: string }) =>
    patch({
      input_contracts: has(i)
        ? row.input_contracts.filter((r) => !(r.contract_id === i.contract_id && r.version === i.version))
        : [...row.input_contracts, { contract_id: i.contract_id, version: i.version }],
    })
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-tx2">
      <span className="text-tx3">Built from</span>
      {cited.map((i) => (
        <label key={`${i.name}-${i.version}`} className="inline-flex items-center gap-1">
          <input type="checkbox" checked={has(i)} onChange={() => toggle(i)} />
          {i.name} v{i.version}
        </label>
      ))}
    </div>
  )
}

export function OutputPortsEditor({
  rows,
  onChange,
  inputs,
  source,
  error,
}: {
  rows: OutputPort[]
  onChange: (rows: OutputPort[]) => void
  inputs: InputPort[]
  source: ContractSource
  error?: string
}) {
  const typesId = useId()
  const [picking, setPicking] = useState<number | null>(null)
  return (
    <Section
      legend="Outputs · at least one"
      hint="What this product publishes. An output with a contract can be read by other products."
      error={error}
    >
      <datalist id={typesId}>
        {OUTPUT_TYPES.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <EditableRows
        rows={rows}
        onChange={onChange}
        emptyRow={emptyOutput}
        addLabel="Add output"
        emptyText="No outputs yet."
        renderRow={(row, index, patch) => (
          <div className="col-span-11 space-y-2">
            <div className="grid grid-cols-12 items-center gap-2">
              <input
                aria-label="Output name"
                placeholder="Name"
                className={`col-span-5 ${ROW_INPUT_CLASS}`}
                value={row.name}
                onChange={(e) => patch({ name: e.target.value })}
              />
              <input
                aria-label="Output type"
                placeholder="Type"
                list={typesId}
                className={`col-span-3 ${ROW_INPUT_CLASS}`}
                value={row.type ?? ''}
                onChange={(e) => patch({ type: e.target.value || null })}
              />
              <div className="col-span-4 flex flex-wrap items-center gap-2 text-xs">
                {row.contract_id ? (
                  <>
                    <span className="font-mono text-tx2">
                      {titleOf(row, source)} · v{row.version}
                    </span>
                    <button type="button" onClick={() => setPicking(index)} className="text-accent-fg hover:underline">
                      Change contract
                    </button>
                  </>
                ) : (
                  <>
                    <Badge variant="yellow">Not consumable</Badge>
                    <button type="button" onClick={() => setPicking(index)} className="text-accent-fg hover:underline">
                      Add a contract
                    </button>
                  </>
                )}
              </div>
            </div>
            <input
              aria-label="Output description"
              placeholder="Description (optional)"
              className={`w-full ${ROW_INPUT_CLASS}`}
              value={row.description ?? ''}
              onChange={(e) => patch({ description: e.target.value || null })}
            />
            <BuiltFrom row={row} inputs={inputs} patch={patch} />
            {isOlder(rows, index) && <span className="text-xs text-tx3">older version</span>}
          </div>
        )}
      />
      {picking !== null && rows[picking] && (
        <PickerPanel
          label="Output contract"
          source={source}
          value={rows[picking].contract_id ?? ''}
          onCancel={() => setPicking(null)}
          onPick={(c) => {
            onChange(rows.map((r, i) => (i === picking ? onContract(r, c) : r)))
            setPicking(null)
          }}
        />
      )}
    </Section>
  )
}

function ContractInput({ row, source, producers }: { row: InputPort; source: ContractSource; producers: Map<string, ProductRef[]> }) {
  const status = row.contract?.status ?? source.contracts.find((c) => c.id === row.contract_id)?.status
  return (
    <div className="col-span-7 flex flex-wrap items-center gap-2 text-xs">
      <span className="font-mono text-tx2">
        {titleOf(row, source)} · v{row.version}
      </span>
      <span className="text-tx3">{producedBy(producers, row.contract_id ?? '')}</span>
      {status === 'retired' && <Badge variant="red">Retired contract</Badge>}
      {status === 'deprecated' && <Badge variant="yellow">Deprecated contract</Badge>}
    </div>
  )
}

export function InputPortsEditor({
  rows,
  onChange,
  source,
  producers,
  error,
}: {
  rows: InputPort[]
  onChange: (rows: InputPort[]) => void
  source: ContractSource
  producers: Map<string, ProductRef[]>
  error?: string
}) {
  const [picking, setPicking] = useState(false)
  return (
    <Section
      legend="Inputs"
      hint="What this product reads: another product's contract, or an external source such as a core system or a partner file."
      error={error}
    >
      <EditableRows
        rows={rows}
        onChange={onChange}
        emptyRow={emptyInput}
        addLabel="Add input"
        emptyText="No inputs yet."
        addActions={
          <div className="flex flex-wrap gap-4">
            <AddButton label="From a contract" onClick={() => setPicking(true)} />
            <AddButton label="External source" onClick={() => onChange([...rows, emptyInput()])} />
          </div>
        }
        renderRow={(row, index, patch) => (
          <div className="col-span-11 grid grid-cols-12 items-center gap-2">
            <input
              aria-label="Input name"
              placeholder="Name"
              className={`col-span-4 ${ROW_INPUT_CLASS}`}
              value={row.name}
              onChange={(e) => patch({ name: e.target.value })}
            />
            {row.contract_id ? (
              <ContractInput row={row} source={source} producers={producers} />
            ) : (
              <>
                <input
                  aria-label="Source link"
                  placeholder="Link (wiki, catalog, API docs)"
                  className={`col-span-5 ${ROW_INPUT_CLASS}`}
                  value={row.authoritative_definitions[0]?.url ?? ''}
                  onChange={(e) =>
                    patch({
                      authoritative_definitions: e.target.value ? [{ type: 'implementation', url: e.target.value }] : [],
                    })
                  }
                />
                <span className="col-span-2 text-xs text-tx3">External source</span>
              </>
            )}
            {isOlder(rows, index) && <span className="col-span-12 text-xs text-tx3">older version</span>}
          </div>
        )}
      />
      {picking && (
        <PickerPanel
          label="Input contract"
          source={source}
          value=""
          detail={(c) => producedBy(producers, c.id)}
          emptyHint="No data contract exists yet."
          onCancel={() => setPicking(false)}
          onPick={(c) => {
            onChange([...rows, onContract(emptyInput(), c)])
            setPicking(false)
          }}
        />
      )}
    </Section>
  )
}
