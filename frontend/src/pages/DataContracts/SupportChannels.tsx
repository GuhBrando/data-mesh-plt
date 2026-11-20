import EditableRows, { ROW_INPUT_CLASS } from './EditableRows'
import type { SupportChannel } from '../../types'

interface SupportChannelsProps {
  rows: SupportChannel[]
  onChange: (rows: SupportChannel[]) => void
}

const emptyChannel = (): SupportChannel => ({ channel: '', url: '', tool: '', scope: '' })

// Tool and scope are free text: ODCS gives its values as examples, not a closed list.
export default function SupportChannels({ rows, onChange }: SupportChannelsProps) {
  return (
    <EditableRows
      rows={rows}
      onChange={onChange}
      emptyRow={emptyChannel}
      addLabel="Add support channel"
      emptyText="No support channels yet."
      renderRow={(row, _index, patch) => (
        <>
          <input
            className={`col-span-3 ${ROW_INPUT_CLASS}`}
            placeholder="Channel"
            value={row.channel}
            onChange={(e) => patch({ channel: e.target.value })}
          />
          <input
            className={`col-span-3 ${ROW_INPUT_CLASS}`}
            placeholder="URL"
            value={row.url}
            onChange={(e) => patch({ url: e.target.value })}
          />
          <input
            className={`col-span-3 ${ROW_INPUT_CLASS}`}
            placeholder="Tool (slack, teams, email...)"
            value={row.tool}
            onChange={(e) => patch({ tool: e.target.value })}
          />
          <input
            className={`col-span-2 ${ROW_INPUT_CLASS}`}
            placeholder="Scope (interactive, issues...)"
            value={row.scope}
            onChange={(e) => patch({ scope: e.target.value })}
          />
        </>
      )}
    />
  )
}
