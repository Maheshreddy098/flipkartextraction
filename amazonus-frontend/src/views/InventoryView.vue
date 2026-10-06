<script setup lang="ts">
import { ref } from 'vue'
import { useSession } from '@/stores/session'
import { toast } from '@/stores/toast'
import { useJobPolling } from '@/composables/useJobPolling'
import StatTile from '@/components/StatTile.vue'
import LogPanel from '@/components/LogPanel.vue'

interface InventoryRow {
  seller_sku: string; sap_item_code: string
  sap_qty: number; amazon_qty: number | null; diff: number | null; blocked_qty: number | null
  flags: string[]; remarks: string
}

const session = useSession()
const job = useJobPolling('get_inventory_reconciliation_result')

const rows = ref<InventoryRow[]>([])
const counts = ref<{ missing: number; mismatch: number; inactive: number; blocked: number } | null>(null)
const totalSkus = ref(0)
const filter = ref<'all' | 'missing' | 'mismatch' | 'inactive' | 'blocked'>('all')

function run() {
  job.start('enqueue_inventory_reconciliation', {}).then((r) => {
    if (r.status === 'done') {
      rows.value = r.rows
      counts.value = r.counts
      totalSkus.value = r.total_skus
      toast(
        `Inventory reconciliation done — ${r.total_skus} SKUs, `
        + `${r.counts.missing} missing, ${r.counts.mismatch} mismatched, `
        + `${r.counts.inactive} inactive, ${r.counts.blocked} blocked`,
        'ok', 10000,
      )
    } else if (r.status === 'hana_down') {
      toast(`HANA down — job aborted safely: ${r.message}`, 'error')
    } else {
      toast(r.message || 'Inventory reconciliation failed', 'error')
    }
  })
}

const filtered = () => (filter.value === 'all'
  ? rows.value
  : rows.value.filter((r) => r.flags.map((f) => f.toLowerCase()).includes(filter.value)))

function exportCsv() {
  const cols = ['seller_sku', 'sap_item_code', 'sap_qty', 'amazon_qty', 'diff', 'blocked_qty', 'flags', 'remarks']
  const lines = [cols.join(',')]
  for (const r of filtered()) {
    lines.push(cols.map((c) => {
      const v = (r as any)[c]
      const s = Array.isArray(v) ? v.join('|') : (v ?? '')
      return `"${String(s).replace(/"/g, '""')}"`
    }).join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'amazon_us_inventory_reconciliation.csv'
  a.click()
  URL.revokeObjectURL(url)
}

const flagTone: Record<string, string> = {
  MISSING: 'text-bad border-bad-dim',
  MISMATCH: 'text-money border-money-dim',
  INACTIVE: 'text-bad border-bad-dim',
  BLOCKED: 'text-accent border-accent-dim',
}

function fmt(v: number | null) { return v == null ? '—' : v.toLocaleString() }
</script>

<template>
  <div class="space-y-4">
    <div v-if="!session.canPost" class="card border-money-dim p-3 text-xs text-money">
      View-only access — running a reconciliation needs the "Amazon US Manager" role.
    </div>

    <div class="flex items-center gap-3 flex-wrap">
      <button class="btn-money" :disabled="!session.canPost || job.running.value" @click="run">
        ⇄ Run reconciliation
      </button>
      <button class="btn-ghost" :disabled="!rows.length" @click="exportCsv">⇩ Export CSV</button>
      <div class="ml-auto text-xs text-ink-400 num" v-if="totalSkus">{{ totalSkus.toLocaleString() }} mapped SKUs compared</div>
    </div>

    <p class="text-[11px] text-ink-400">
      Amazon FBA inventory (live) vs SAP OnHand on AMZ-FBA, for every SAP↔Amazon mapped SKU. On-demand only —
      each run is a fresh live comparison, nothing is scheduled or stored.
    </p>

    <div v-if="counts" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatTile label="Missing in Amazon" :value="counts.missing" tone="bad" />
      <StatTile label="Qty mismatch" :value="counts.mismatch" tone="money" />
      <StatTile label="Inactive in SAP" :value="counts.inactive" tone="bad" />
      <StatTile label="Blocked > 20 units" :value="counts.blocked" tone="accent" />
    </div>

    <div v-if="rows.length" class="flex items-center gap-2">
      <button
        v-for="f in ['all', 'missing', 'mismatch', 'inactive', 'blocked'] as const" :key="f"
        class="px-3 py-1.5 text-xs capitalize rounded border"
        :class="filter === f ? 'bg-ink-700 text-ink-100 border-ink-600' : 'text-ink-300 border-ink-700 hover:bg-ink-800'"
        @click="filter = f"
      >{{ f }}</button>
    </div>

    <div v-if="rows.length" class="card overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-left border-b border-ink-700">
            <th class="label px-3 py-2 font-normal">SKU</th>
            <th class="label px-3 py-2 font-normal">SAP Item</th>
            <th class="label px-3 py-2 font-normal text-right">SAP Qty</th>
            <th class="label px-3 py-2 font-normal text-right">Amazon Qty</th>
            <th class="label px-3 py-2 font-normal text-right">Diff</th>
            <th class="label px-3 py-2 font-normal text-right">Blocked</th>
            <th class="label px-3 py-2 font-normal">Flags</th>
            <th class="label px-3 py-2 font-normal">Remarks</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filtered()" :key="r.seller_sku" class="border-b border-ink-700/40 last:border-0">
            <td class="px-3 py-2 font-mono">{{ r.seller_sku }}</td>
            <td class="px-3 py-2 font-mono text-ink-300">{{ r.sap_item_code }}</td>
            <td class="px-3 py-2 num text-right">{{ fmt(r.sap_qty) }}</td>
            <td class="px-3 py-2 num text-right">{{ fmt(r.amazon_qty) }}</td>
            <td class="px-3 py-2 num text-right" :class="{ 'text-money': r.diff }">{{ fmt(r.diff) }}</td>
            <td class="px-3 py-2 num text-right">{{ fmt(r.blocked_qty) }}</td>
            <td class="px-3 py-2">
              <span
                v-for="f in r.flags" :key="f"
                class="inline-block px-1.5 py-0.5 mr-1 rounded border text-[10px] uppercase tracking-wider"
                :class="flagTone[f] || 'text-ink-300 border-ink-600'"
              >{{ f }}</span>
            </td>
            <td class="px-3 py-2 text-ink-300 max-w-xs truncate" :title="r.remarks">{{ r.remarks }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else-if="!job.running.value" class="text-xs text-ink-400 text-center py-6">
      No reconciliation run yet — click "Run reconciliation" above.
    </div>

    <LogPanel v-if="job.running.value || job.log.value.length" :lines="job.log.value" :running="job.running.value" />
  </div>
</template>
