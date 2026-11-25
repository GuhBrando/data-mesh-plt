import EditableRows, { ROW_INPUT_CLASS } from '../../components/rows/EditableRows'
import {
  SERVER_KEY_LABELS,
  SERVER_TYPE_KEYS,
  emptyServer,
  withServerType,
} from './contractMetadata'
import type { ServerKey } from './contractMetadata'
import type { ContractServer, ServerType } from '../../types'

const SERVER_TYPES = Object.keys(SERVER_TYPE_KEYS) as ServerType[]

interface ContractServersProps {
  rows: ContractServer[]
  onChange: (rows: ContractServer[]) => void
}

function ServerKeyInput({
  row,
  serverKey,
  patch,
}: {
  row: ContractServer
  serverKey: ServerKey
  patch: (p: Partial<ContractServer>) => void
}) {
  const className = `col-span-3 ${ROW_INPUT_CLASS}`
  if (serverKey === 'port') {
    return (
      <input
        type="number"
        className={className}
        placeholder={SERVER_KEY_LABELS.port}
        value={row.port ?? ''}
        onChange={(e) => patch({ port: e.target.value === '' ? null : Number(e.target.value) })}
      />
    )
  }
  return (
    <input
      className={className}
      placeholder={SERVER_KEY_LABELS[serverKey]}
      value={row[serverKey]}
      onChange={(e) => patch({ [serverKey]: e.target.value })}
    />
  )
}

// Servers hold coordinates only. Credentials never belong in a contract.
export default function ContractServers({ rows, onChange }: ContractServersProps) {
  return (
    <EditableRows
      rows={rows}
      onChange={onChange}
      emptyRow={emptyServer}
      addLabel="Add server"
      emptyText="No servers yet."
      renderRow={(row, _index, patch) => {
        const { required, optional } = SERVER_TYPE_KEYS[row.type]
        return (
          <>
            <input
              className={`col-span-4 ${ROW_INPUT_CLASS}`}
              placeholder="Server name"
              value={row.server}
              onChange={(e) => patch({ server: e.target.value })}
            />
            <input
              className={`col-span-3 ${ROW_INPUT_CLASS}`}
              placeholder="Environment"
              value={row.environment}
              onChange={(e) => patch({ environment: e.target.value })}
            />
            <select
              aria-label="Server type"
              className={`col-span-4 ${ROW_INPUT_CLASS}`}
              value={row.type}
              // Keys the new type does not take are cleared, or the API rejects the row.
              onChange={(e) => patch(withServerType(row, e.target.value as ServerType))}
            >
              {SERVER_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            {[...required, ...optional].map((key) => (
              <ServerKeyInput key={key} row={row} serverKey={key} patch={patch} />
            ))}
          </>
        )
      }}
    />
  )
}
