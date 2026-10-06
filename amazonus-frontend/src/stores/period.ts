import { defineStore } from 'pinia'

function monthBounds(ym: string): { from: string; to: string } {
  const [y, m] = ym.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  const mm = String(m).padStart(2, '0')
  return { from: `${y}-${mm}-01`, to: `${y}-${mm}-${String(last).padStart(2, '0')}` }
}

function currentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

/**
 * Shared reporting window. Ship date decides the MTR month, so every view and
 * every posting action driven from here agrees with the MTR report.
 * Two modes: whole month (default, steppable) or a custom from/to range.
 */
export const usePeriod = defineStore('period', {
  state: () => ({
    mode: 'month' as 'month' | 'range',
    month: currentMonth(),
    rangeFrom: monthBounds(currentMonth()).from,
    rangeTo: monthBounds(currentMonth()).to,
  }),
  getters: {
    from: (s) => (s.mode === 'month' ? monthBounds(s.month).from : s.rangeFrom),
    to: (s) => (s.mode === 'month' ? monthBounds(s.month).to : s.rangeTo),
    /** Views watch this single key to reload on any window change. */
    key(): string {
      return `${this.from}:${this.to}`
    },
    label(): string {
      if (this.mode === 'month') {
        const [y, m] = this.month.split('-').map(Number)
        return new Date(y, m - 1, 1).toLocaleString('en', { month: 'long', year: 'numeric' })
      }
      return 'Custom range'
    },
  },
  actions: {
    stepMonth(delta: number) {
      const [y, m] = this.month.split('-').map(Number)
      const d = new Date(y, m - 1 + delta, 1)
      this.month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      this.mode = 'month'
    },
    setMonth(ym: string) {
      this.month = ym
      this.mode = 'month'
    },
    setRange(from: string, to: string) {
      if (!from || !to || from > to) return
      this.rangeFrom = from
      this.rangeTo = to
      this.mode = 'range'
    },
  },
})
