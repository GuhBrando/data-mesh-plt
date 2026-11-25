import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import { DomainChip, StatusGlyph } from '../../components/ui/Glyphs'
import { ArrowRightIcon, ProductIcon } from '../../components/icons'
import { safeUrl } from '../DataContracts/contractMetadata'
import {
  isMajorMove,
  newerVersion,
  publishOutput,
  removablePort,
  removePort,
  switchInput,
} from '../../lib/products'
import type { DataProduct, DataProductInput, InputPort, OutputPort } from '../../types'

type Move = { kind: 'publish' | 'switch'; index: number; from: string | null; to: string }

function PortList({ label, empty, children }: { label: string; empty: string; children: ReactNode[] }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-tx3">{label}</h3>
      {children.length === 0 && <p className="text-[12.5px] text-tx3">{empty}</p>}
      <ul aria-label={label} className="space-y-2">
        {children}
      </ul>
    </div>
  )
}

function Row({ name, port, children }: { name: string; port: InputPort | OutputPort; children: ReactNode }) {
  return (
    <li className="rounded-lg border border-line bg-raised/40 px-3 py-2.5 text-[12.5px]">
      <div className="flex items-center gap-2">
        <span className="min-w-0 truncate font-mono font-medium text-tx">{name}</span>
        {port.deprecated && <Badge>deprecated</Badge>}
      </div>
      <div className="mt-1 space-y-1 text-tx2">{children}</div>
    </li>
  )
}

function ContractLine({ port }: { port: InputPort | OutputPort }) {
  return (
    <p className="font-mono text-[11.5px]">
      {port.contract?.title ?? port.contract_id} · v{port.version}
    </p>
  )
}

function MoveAction({ to, label, saving, onClick }: { to: string; label: string; saving: boolean; onClick: () => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-accent-fg">v{to} available</span>
      <button
        type="button"
        disabled={saving}
        onClick={onClick}
        className="rounded-md border border-line2 px-2 text-xs font-medium text-tx hover:bg-hover disabled:opacity-50"
      >
        {label}
      </button>
    </div>
  )
}

function RemoveAction({ port, saving, onClick }: { port: InputPort | OutputPort; saving: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={saving}
      onClick={onClick}
      aria-label={`Remove ${port.name} v${port.version}`}
      className="text-xs text-bad hover:underline disabled:opacity-50"
    >
      Remove
    </button>
  )
}

function Producers({ port }: { port: InputPort }) {
  const producers = port.produced_by ?? []
  if (producers.length === 0) return <p className="text-tx3">No producer on the platform</p>
  return (
    <p>
      by{' '}
      {producers.map((p, i) => (
        <span key={p.id}>
          {i > 0 && ', '}
          <Link to={`/data-products/${p.id}`} className="text-tx hover:text-accent-fg hover:underline">
            {p.name}
          </Link>
        </span>
      ))}
    </p>
  )
}

function ContractFlag({ port }: { port: InputPort }) {
  if (port.contract?.status === 'retired') return <Badge variant="red">Contract retired</Badge>
  if (port.contract?.status === 'deprecated') return <Badge variant="yellow">Contract deprecated</Badge>
  return null
}

function External({ port }: { port: InputPort }) {
  // A link a user typed: only http, https and mailto become clickable.
  const url = safeUrl(port.authoritative_definitions[0]?.url ?? '')
  if (!url) return <p className="text-tx3">External source</p>
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="text-tx hover:text-accent-fg hover:underline">
      External source
    </a>
  )
}

function consumers(port: OutputPort): string {
  const n = (port.consumed_by ?? []).length
  return n === 0 ? 'No consumers yet' : `${n} consumer${n === 1 ? '' : 's'}`
}

function ProductNode({ product }: { product: DataProduct }) {
  return (
    <div className="flex items-center gap-3 self-center">
      <ArrowRightIcon size={16} className="hidden text-tx3 lg:block" aria-hidden="true" />
      <div className="rounded-xl border border-accent-fg/40 bg-accent/[0.06] px-4 py-3 text-center">
        <ProductIcon size={18} className="mx-auto mb-1 text-accent-fg" />
        <p className="text-[13px] font-semibold text-tx">{product.name}</p>
        <div className="mt-1.5 flex flex-wrap items-center justify-center gap-2">
          <StatusGlyph status={product.status} className="!text-xs" />
          <DomainChip name={product.domain} className="!text-xs" />
        </div>
      </div>
      <ArrowRightIcon size={16} className="hidden text-tx3 lg:block" aria-hidden="true" />
    </div>
  )
}

function MoveDialog({
  move,
  onConfirm,
  onClose,
}: {
  move: Move | null
  onConfirm: (deprecateOld: boolean) => void
  onClose: () => void
}) {
  const [deprecateOld, setDeprecateOld] = useState(true)
  if (!move) return null
  const title = move.kind === 'publish' ? `Publish v${move.to}` : `Switch to v${move.to}`
  const major = isMajorMove(move.from, move.to)
  return (
    <Modal open onClose={onClose} title={title} size="sm">
      <div className="space-y-3 text-[13px] text-tx2">
        {move.kind === 'publish' ? (
          <p>A new output row carries v{move.to}; v{move.from} stays until no product reads it.</p>
        ) : (
          <p>A new input row reads v{move.to}; v{move.from} stays until no output is built from it.</p>
        )}
        {major && (
          <p className="text-warn">
            This is a MAJOR version: {move.kind === 'publish' ? 'consumers' : 'outputs built'} on v{move.from} may break.
          </p>
        )}
        {move.kind === 'publish' && (
          <label className="flex items-center gap-2 text-tx">
            <input type="checkbox" checked={deprecateOld} onChange={(e) => setDeprecateOld(e.target.checked)} />
            Mark v{move.from} deprecated
          </label>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => onConfirm(deprecateOld)}>{title}</Button>
        </div>
      </div>
    </Modal>
  )
}

/**
 * Inputs → product → outputs, with the version moves a contract change calls
 * for. Each action is one save of the whole product.
 */
export default function ProductLineage({
  product,
  onChange,
  saving = false,
}: {
  product: DataProduct
  onChange: (input: DataProductInput) => void
  saving?: boolean
}) {
  const [move, setMove] = useState<Move | null>(null)

  const confirm = (deprecateOld: boolean) => {
    if (!move) return
    onChange(move.kind === 'publish' ? publishOutput(product, move.index, { deprecateOld }) : switchInput(product, move.index))
    setMove(null)
  }

  const switchTo = (port: InputPort, index: number, to: string) => {
    if (isMajorMove(port.version, to)) setMove({ kind: 'switch', index, from: port.version, to })
    else onChange(switchInput(product, index))
  }

  return (
    <div className="grid items-start gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
      <PortList label="Inputs" empty="This product declares no inputs.">
        {product.input_ports.map((port, index) => {
          const to = newerVersion(port)
          return (
            <Row key={port.id ?? `${port.name}-${port.version}`} name={port.name} port={port}>
              {port.contract_id ? (
                <>
                  <ContractLine port={port} />
                  <Producers port={port} />
                  <ContractFlag port={port} />
                  {to && <MoveAction to={to} label="Switch" saving={saving} onClick={() => switchTo(port, index, to)} />}
                </>
              ) : (
                <External port={port} />
              )}
              {removablePort(product, 'input', index) && (
                <RemoveAction port={port} saving={saving} onClick={() => onChange(removePort(product, 'input', index))} />
              )}
            </Row>
          )
        })}
      </PortList>
      <ProductNode product={product} />
      <PortList label="Outputs" empty="This product publishes nothing yet.">
        {product.output_ports.map((port, index) => {
          const to = newerVersion(port)
          return (
            <Row key={port.id ?? `${port.name}-${port.version}`} name={port.name} port={port}>
              {port.contract_id ? (
                <>
                  <ContractLine port={port} />
                  <p>{consumers(port)}</p>
                  {to && (
                    <MoveAction
                      to={to}
                      label="Publish"
                      saving={saving}
                      onClick={() => setMove({ kind: 'publish', index, from: port.version, to })}
                    />
                  )}
                </>
              ) : (
                <p className="text-tx3">No contract — not consumable</p>
              )}
              {removablePort(product, 'output', index) && (
                <RemoveAction port={port} saving={saving} onClick={() => onChange(removePort(product, 'output', index))} />
              )}
            </Row>
          )
        })}
      </PortList>
      <MoveDialog key={move ? `${move.kind}-${move.index}` : 'none'} move={move} onConfirm={confirm} onClose={() => setMove(null)} />
    </div>
  )
}
