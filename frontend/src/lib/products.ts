import type {
  DataProduct,
  DataProductInput,
  InputPort,
  OutputPort,
  ProductRef,
  ProductStatus,
} from '../types'

// The ODPS product lifecycle, in order.
export const PRODUCT_STATUSES: ProductStatus[] = ['proposed', 'draft', 'active', 'deprecated', 'retired']

type Role = 'input' | 'output'

/** Lowercase ASCII words joined by hyphens, as the backend names ports and repos. */
export function slugify(text: string): string {
  return text
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function inputOf({ name, contract_id, version, deprecated, authoritative_definitions }: InputPort): InputPort {
  return { name, contract_id, version, deprecated, authoritative_definitions }
}

function outputOf(port: OutputPort): OutputPort {
  const { name, contract_id, version, type, description, deprecated, authoritative_definitions, input_contracts } = port
  return { name, contract_id, version, type, description, deprecated, authoritative_definitions, input_contracts }
}

/** What the API takes back: ids, lineage and contract summaries are computed by it. */
export function toInput(p: DataProduct): DataProductInput {
  return {
    name: p.name,
    description: p.description,
    domain_id: p.domain_id,
    status: p.status,
    input_ports: p.input_ports.map(inputOf),
    output_ports: p.output_ports.map(outputOf),
  }
}

/** The contract's current version when the port is pinned to another one. */
export function newerVersion(port: InputPort | OutputPort): string | null {
  const current = port.contract?.version
  return current && current !== port.version ? current : null
}

const SEMVER = /^(\d+)\.\d+\.\d+$/

/** A move across a MAJOR version, which may break whoever reads the port. */
export function isMajorMove(from: string | null, to: string): boolean {
  const a = from?.match(SEMVER)
  const b = to.match(SEMVER)
  return !!a && !!b && a[1] !== b[1]
}

function insertAfter<T>(rows: T[], index: number, row: T): T[] {
  return [...rows.slice(0, index + 1), row, ...rows.slice(index + 1)]
}

/**
 * Publish the contract's new version from an output: a new row next to the old
 * one, built from the same inputs. The old row stays until no one consumes it.
 */
export function publishOutput(p: DataProduct, index: number, { deprecateOld }: { deprecateOld: boolean }): DataProductInput {
  const input = toInput(p)
  const old = input.output_ports[index]
  const fresh = { ...old, version: newerVersion(p.output_ports[index]), deprecated: false }
  const rows = input.output_ports.map((row, i) => (i === index && deprecateOld ? { ...row, deprecated: true } : row))
  return { ...input, output_ports: insertAfter(rows, index, fresh) }
}

/** Read the contract's new version: a new input row next to the old one. */
export function switchInput(p: DataProduct, index: number): DataProductInput {
  const input = toInput(p)
  const fresh = { ...input.input_ports[index], version: newerVersion(p.input_ports[index]) }
  return { ...input, input_ports: insertAfter(input.input_ports, index, fresh) }
}

/**
 * Whether a row left behind by a version move can go: another row of the same
 * name remains, and nothing uses this one (no consumer for an output, no output
 * built from it for an input).
 */
export function removablePort(p: DataProduct, role: Role, index: number): boolean {
  const ports: (InputPort | OutputPort)[] = role === 'input' ? p.input_ports : p.output_ports
  const port = ports[index]
  if (!ports.some((other, i) => i !== index && other.name === port.name)) return false
  if (role === 'output') return ((port as OutputPort).consumed_by ?? []).length === 0
  return !p.output_ports.some((o) =>
    o.input_contracts.some((ref) => ref.contract_id === port.contract_id && ref.version === port.version),
  )
}

export function removePort(p: DataProduct, role: Role, index: number): DataProductInput {
  const input = toInput(p)
  const key = role === 'input' ? 'input_ports' : 'output_ports'
  return { ...input, [key]: input[key].filter((_, i) => i !== index) }
}

/** For each contract, the products that publish it, each listed once. */
export function producersByContract(products: DataProduct[]): Map<string, ProductRef[]> {
  const producers = new Map<string, ProductRef[]>()
  for (const p of products) {
    const ids = new Set(p.output_ports.map((o) => o.contract_id).filter((id): id is string => !!id))
    for (const id of ids) {
      producers.set(id, [...(producers.get(id) ?? []), { id: p.id, name: p.name, status: p.status }])
    }
  }
  return producers
}
