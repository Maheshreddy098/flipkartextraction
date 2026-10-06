/**
 * Converts rows + column definitions to a CSV file and triggers a browser download.
 * @param {string} filename  Base name (no extension, no date — added automatically)
 * @param {Array<{key: string, label: string}>} columns
 * @param {Array<Object>} rows
 */
export function downloadCsv(filename, columns, rows) {
  const escape = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'

  const header = columns.map((c) => escape(c.label || c.key)).join(',')
  const body = rows.map((row) => columns.map((c) => escape(row[c.key])).join(',')).join('\r\n')

  // BOM ensures Excel opens UTF-8 CSV correctly
  const csv = '﻿' + header + '\r\n' + body
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
