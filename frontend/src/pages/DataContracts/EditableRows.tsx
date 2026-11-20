import { useRef } from 'react'
import type { ReactNode } from 'react'
import { Plus, Trash2 } from 'lucide-react'

export const ROW_INPUT_CLASS =
  'text-sm border border-gray-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-200'

interface EditableRowsProps<T> {
  rows: T[]
  onChange: (rows: T[]) => void
  emptyRow: () => T
  addLabel: string
  emptyText: string
  /** Cells of one row, laid out on an 11-column span; the remove button takes the 12th. */
  renderRow: (row: T, index: number, patch: (p: Partial<T>) => void) => ReactNode
}

export default function EditableRows<T>({
  rows,
  onChange,
  emptyRow,
  addLabel,
  emptyText,
  renderRow,
}: EditableRowsProps<T>) {
  const idsRef = useRef<string[]>([])
  const getKey = (index: number): string => {
    while (idsRef.current.length <= index) idsRef.current.push(crypto.randomUUID())
    return idsRef.current[index]
  }

  const update = (index: number, patch: Partial<T>) => {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }

  const remove = (index: number) => {
    idsRef.current.splice(index, 1)
    onChange(rows.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      {rows.length === 0 && (
        <p className="text-sm text-gray-400 dark:text-slate-500 italic">{emptyText}</p>
      )}
      {rows.map((row, i) => (
        <div
          key={getKey(i)}
          className="grid grid-cols-12 gap-2 items-center rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900"
        >
          {renderRow(row, i, (p) => update(i, p))}
          <button
            type="button"
            onClick={() => remove(i)}
            className="col-span-1 flex items-center justify-center text-red-400 hover:text-red-600"
            title="Remove"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...rows, emptyRow()])}
        className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"
      >
        <Plus size={14} />
        {addLabel}
      </button>
    </div>
  )
}
