import EditableRows, { ROW_INPUT_CLASS } from './EditableRows'
import type { TeamMember } from '../../types'

interface TeamMembersProps {
  rows: TeamMember[]
  onChange: (rows: TeamMember[]) => void
}

const emptyMember = (): TeamMember => ({ username: '', name: '', role: '' })

export default function TeamMembers({ rows, onChange }: TeamMembersProps) {
  return (
    <EditableRows
      rows={rows}
      onChange={onChange}
      emptyRow={emptyMember}
      addLabel="Add team member"
      emptyText="No team members yet."
      renderRow={(row, _index, patch) => (
        <>
          <input
            className={`col-span-4 ${ROW_INPUT_CLASS}`}
            placeholder="Username"
            value={row.username}
            onChange={(e) => patch({ username: e.target.value })}
          />
          <input
            className={`col-span-4 ${ROW_INPUT_CLASS}`}
            placeholder="Name"
            value={row.name}
            onChange={(e) => patch({ name: e.target.value })}
          />
          <input
            className={`col-span-3 ${ROW_INPUT_CLASS}`}
            placeholder="Role"
            value={row.role}
            onChange={(e) => patch({ role: e.target.value })}
          />
        </>
      )}
    />
  )
}
