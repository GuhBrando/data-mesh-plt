import type { ContractServer, ServerType, SupportChannel, TeamMember } from '../../types'

export type ServerKey =
  | 'host'
  | 'catalog'
  | 'schema_name'
  | 'port'
  | 'database'
  | 'location'
  | 'format'
  | 'path'

// Mirrors SERVER_RULES in backend/domain/contract_metadata.py, which stays authoritative:
// ODCS rejects a server that carries a key its type does not take.
export const SERVER_TYPE_KEYS: Record<ServerType, { required: ServerKey[]; optional: ServerKey[] }> = {
  databricks: { required: ['catalog', 'schema_name'], optional: ['host'] },
  postgres: { required: ['host', 'port', 'database', 'schema_name'], optional: [] },
  azure: { required: ['location', 'format'], optional: [] },
  local: { required: ['path', 'format'], optional: [] },
}

export const SERVER_KEY_LABELS: Record<ServerKey, string> = {
  host: 'Host',
  catalog: 'Catalog',
  schema_name: 'Schema',
  port: 'Port',
  database: 'Database',
  location: 'Location',
  format: 'Format',
  path: 'Path',
}

const SERVER_KEYS = Object.keys(SERVER_KEY_LABELS) as ServerKey[]

export const emptyServer = (): ContractServer => ({
  server: '',
  type: 'databricks',
  environment: '',
  host: '',
  catalog: '',
  schema_name: '',
  port: null,
  database: '',
  location: '',
  format: '',
  path: '',
})

const isBlank = (value: string | number | null): boolean =>
  value === null || String(value).trim() === ''

export function withServerType(server: ContractServer, type: ServerType): ContractServer {
  const { required, optional } = SERVER_TYPE_KEYS[type]
  const cleared: Partial<ContractServer> = {}
  for (const key of SERVER_KEYS) {
    if (required.includes(key) || optional.includes(key)) continue
    if (key === 'port') cleared.port = null
    else cleared[key] = ''
  }
  return { ...server, ...cleared, type }
}

function serverError(server: ContractServer, position: number): string | null {
  if (isBlank(server.server)) return `Server ${position} needs a name`
  const missing = SERVER_TYPE_KEYS[server.type].required.filter((key) => isBlank(server[key]))
  if (missing.length === 0) return null
  const labels = missing.map((key) => SERVER_KEY_LABELS[key]).join(', ')
  return `Server ${position} (${server.type}) needs ${labels}`
}

function firstError<T>(rows: T[], check: (row: T, position: number) => string | null): string | null {
  for (const [index, row] of rows.entries()) {
    const error = check(row, index + 1)
    if (error) return error
  }
  return null
}

export function metadataError(
  members: TeamMember[],
  support: SupportChannel[],
  servers: ContractServer[],
): string | null {
  return (
    firstError(members, (m, n) => (isBlank(m.username) ? `Team member ${n} needs a username` : null)) ??
    firstError(support, (s, n) => (isBlank(s.channel) ? `Support channel ${n} needs a channel` : null)) ??
    firstError(servers, serverError)
  )
}
