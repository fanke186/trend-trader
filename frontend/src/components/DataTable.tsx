import { useMemo, useState } from 'react'

export interface Column<T> {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'right'
  render?: (row: T) => React.ReactNode
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  onRowClick?: (row: T) => void
  emptyText?: string
}

export function DataTable<T>({ columns, rows, rowKey, onRowClick, emptyText = '暂无数据' }: Props<T>) {
  const [sort, setSort] = useState<{ key: string; asc: boolean } | null>(null)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find(c => c.key === sort.key)
    return [...rows].sort((a, b) => {
      const aVal = (a as Record<string, unknown>)[sort.key]
      const bVal = (b as Record<string, unknown>)[sort.key]
      if (aVal == null && bVal == null) return 0
      if (aVal == null) return sort.asc ? -1 : 1
      if (bVal == null) return sort.asc ? 1 : -1
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      return sort.asc ? cmp : -cmp
    })
  }, [rows, sort, columns])

  function toggleSort(key: string) {
    setSort(prev => prev?.key === key ? { key, asc: !prev.asc } : { key, asc: true })
  }

  return (
    <div className="overflow-hidden rounded-md border border-base-800 bg-base-900">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-base-850 text-xs text-neutral-500">
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={`px-3 py-2 ${col.align === 'right' ? 'text-right' : 'text-left'} ${col.sortable ? 'cursor-pointer select-none hover:text-neutral-300' : ''}`}
                onClick={() => col.sortable && toggleSort(col.key)}
              >
                {col.label}
                {sort?.key === col.key ? (sort.asc ? ' ↑' : ' ↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-base-800">
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-neutral-500">{emptyText}</td>
            </tr>
          ) : (
            sorted.map(row => (
              <tr
                key={rowKey(row)}
                className={`${onRowClick ? 'cursor-pointer hover:bg-base-850' : ''} transition-colors`}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map(col => (
                  <td key={col.key} className={`px-3 py-2 ${col.align === 'right' ? 'text-right' : 'text-left'}`}>
                    {col.render?.(row) ?? String((row as Record<string, unknown>)[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
