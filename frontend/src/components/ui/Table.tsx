import { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  className?: string
  mobileHidden?: boolean
}

interface MobileCardConfig {
  titleKey: string
  badgeKey?: string
}

interface TableProps<T> {
  columns: Column<T>[]
  data: T[]
  onRowClick?: (row: T) => void
  keyExtractor: (row: T) => string
  emptyMessage?: string
  mobileCardConfig?: MobileCardConfig
}

export default function Table<T>({
  columns,
  data,
  onRowClick,
  keyExtractor,
  emptyMessage = 'No records found.',
  mobileCardConfig,
}: TableProps<T>) {
  const tableNode = (
    <div className="overflow-x-auto rounded-[10px] border border-line bg-panel">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-line">
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={`whitespace-nowrap px-4 py-2.5 text-left text-[11.5px] font-medium text-tx3 ${col.className ?? ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-12 text-center text-[13px] text-tx3"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={keyExtractor(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`transition-colors ${
                  onRowClick
                    ? 'cursor-pointer hover:bg-hover'
                    : 'hover:bg-hover'
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`h-11 px-4 py-2 text-[13px] text-tx2 ${col.className ?? ''}`}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )

  if (!mobileCardConfig) return tableNode

  const titleCol = columns.find((c) => c.key === mobileCardConfig.titleKey)
  if (import.meta.env.DEV && !titleCol) {
    console.warn(`[Table] mobileCardConfig.titleKey "${mobileCardConfig.titleKey}" does not match any column key`)
  }
  const badgeCol = mobileCardConfig.badgeKey
    ? columns.find((c) => c.key === mobileCardConfig.badgeKey)
    : undefined
  const bodyColumns = columns.filter(
    (c) =>
      c.key !== mobileCardConfig.titleKey &&
      c.key !== mobileCardConfig.badgeKey &&
      c.header !== '' &&
      !c.mobileHidden,
  )
  const actionColumns = columns.filter(
    (c) => c.header === '' && c.key !== mobileCardConfig.badgeKey && !c.mobileHidden,
  )

  const cardListNode = (
    <div className="md:hidden space-y-3">
      {data.length === 0 ? (
        <p className="py-12 text-center text-[13px] text-tx3">
          {emptyMessage}
        </p>
      ) : (
        data.map((row) => (
          <div
            key={keyExtractor(row)}
            data-testid="mobile-card"
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            role={onRowClick ? 'button' : undefined}
            tabIndex={onRowClick ? 0 : undefined}
            onKeyDown={onRowClick ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onRowClick(row)
              }
            } : undefined}
            className={`bg-panel border border-line rounded-[10px] p-4 transition-colors ${
              onRowClick
                ? 'cursor-pointer hover:bg-hover'
                : ''
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-3">
              <div className="font-medium text-tx min-w-0">
                {titleCol?.render(row)}
              </div>
              {badgeCol && <div className="shrink-0">{badgeCol.render(row)}</div>}
            </div>
            {bodyColumns.length > 0 && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                {bodyColumns.map((col) => (
                  <div key={col.key}>
                    <div className="text-[11.5px] font-medium text-tx3 mb-0.5">
                      {col.header}
                    </div>
                    <div className="text-[13px] text-tx2">
                      {col.render(row)}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {actionColumns.map((col) => (
              <div
                key={col.key}
                className="mt-3 pt-3 border-t border-line flex justify-end"
              >
                {col.render(row)}
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  )

  return (
    <>
      <div className="hidden md:block">{tableNode}</div>
      {cardListNode}
    </>
  )
}
