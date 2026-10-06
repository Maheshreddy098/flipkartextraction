<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { call } from '@/api/client'
import { useSession } from '@/stores/session'
import { toast } from '@/stores/toast'
import { useJobPolling } from '@/composables/useJobPolling'
import LogPanel from '@/components/LogPanel.vue'
import OrderDetailDrawer from '@/components/OrderDetailDrawer.vue'

interface Settlement {
  name: string; settlement_id: string; status: string; currency: string
  settlement_start_date: string; settlement_end_date: string; deposit_date: string
  total_amount: number; gross_revenue: number; total_fees: number
  total_refunds: number; total_reimbursements: number
}
interface ReconOrderLine {
  order_id: string; settlement_principal: number; order_total: number | null
  sap_doc_entry: string | null; sap_doc_num: string | null; match_status: string
}

const session = useSession()
const rows = ref<Settlement[]>([])
const total = ref(0)
const page = ref(1)
const recon = ref<{ status: string; order_lines: ReconOrderLine[]; summary: Record<string, number> } | null>(null)
const reconFor = ref('')
const detailName = ref<string | null>(null)

const matchTone: Record<string, string> = {
  posted: 'text-ok', pending_post: 'text-money', failed: 'text-bad', unmatched: 'text-ink-400',
}

const job = useJobPolling('get_settlement_result')

async function load() {
  const res = await call<{ settlements: Settlement[]; total: number }>('get_settlements', { page: page.value, page_size: 20 })
  rows.value = res.settlements
  total.value = res.total
}

function sync() {
  job.start('enqueue_settlement_sync', {}).then((r) => {
    toast(`Settlement sync ${r.status}`, r.status === 'done' ? 'ok' : 'error')
    load()
  })
}

async function openRecon(s: Settlement) {
  reconFor.value = s.settlement_id
  recon.value = await call('get_settlement_reconciliation', { settlement_id: s.name })
}

function money(v: number | null, cur = '$') { return v == null ? '—' : `${cur}${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` }

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="text-xs text-ink-400 num">{{ total }} settlement periods</div>
      <button class="btn-safe" :disabled="!session.canPost || job.running.value" @click="sync">⇄ Sync settlement reports</button>
    </div>

    <div class="card overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-left border-b border-ink-700">
            <th class="label px-3 py-2 font-normal">Settlement</th>
            <th class="label px-3 py-2 font-normal">Period</th>
            <th class="label px-3 py-2 font-normal">Deposit</th>
            <th class="label px-3 py-2 font-normal text-right">Gross</th>
            <th class="label px-3 py-2 font-normal text-right">Fees</th>
            <th class="label px-3 py-2 font-normal text-right">Refunds</th>
            <th class="label px-3 py-2 font-normal text-right">Net payout</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in rows" :key="s.name"
            class="border-b border-ink-700/40 last:border-0 hover:bg-ink-700/20 cursor-pointer"
            @click="openRecon(s)"
          >
            <td class="px-3 py-2 font-mono">{{ s.settlement_id }}</td>
            <td class="px-3 py-2 num text-ink-300">{{ String(s.settlement_start_date).slice(0, 10) }} → {{ String(s.settlement_end_date).slice(0, 10) }}</td>
            <td class="px-3 py-2 num">{{ String(s.deposit_date || '').slice(0, 10) || '—' }}</td>
            <td class="px-3 py-2 num text-right text-ok">{{ money(s.gross_revenue) }}</td>
            <td class="px-3 py-2 num text-right text-bad">{{ money(s.total_fees) }}</td>
            <td class="px-3 py-2 num text-right text-money">{{ money(s.total_refunds) }}</td>
            <td class="px-3 py-2 num text-right font-semibold">{{ money(s.total_amount) }}</td>
          </tr>
          <tr v-if="!rows.length"><td colspan="7" class="px-3 py-6 text-center text-ink-400">No settlements synced yet.</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="job.running.value || job.log.value.length" class="mt-2">
      <LogPanel :lines="job.log.value" :running="job.running.value" />
    </div>

    <!-- Reconciliation drawer -->
    <Teleport to="body">
      <div v-if="recon" class="fixed inset-0 z-40 flex justify-end bg-black/50" @click.self="recon = null">
        <div class="w-[34rem] h-full bg-ink-900 border-l border-ink-700 p-5 overflow-auto">
          <div class="flex items-center justify-between">
            <div class="text-sm">Reconciliation · <span class="font-mono">{{ reconFor }}</span></div>
            <button class="btn-ghost" @click="recon = null">✕</button>
          </div>
          <div v-if="recon.summary" class="mt-3 flex flex-wrap gap-3 text-xs">
            <span v-for="(v, k) in recon.summary" :key="k" class="px-2 py-1 rounded border border-ink-600 text-ink-300">
              {{ k }}: <span class="num">{{ v }}</span>
            </span>
          </div>
          <table class="w-full text-xs mt-4">
            <thead>
              <tr class="text-left border-b border-ink-700">
                <th class="label px-2 py-1.5 font-normal">Order</th>
                <th class="label px-2 py-1.5 font-normal text-right">Settlement</th>
                <th class="label px-2 py-1.5 font-normal text-right">Order total</th>
                <th class="label px-2 py-1.5 font-normal">SAP Doc</th>
                <th class="label px-2 py-1.5 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="ol in recon.order_lines" :key="ol.order_id"
                class="border-b border-ink-700/40 last:border-0 hover:bg-ink-700/20 cursor-pointer"
                @click="detailName = ol.order_id"
              >
                <td class="px-2 py-1.5 font-mono">{{ ol.order_id }}</td>
                <td class="px-2 py-1.5 num text-right">{{ ol.settlement_principal }}</td>
                <td class="px-2 py-1.5 num text-right text-ink-300">{{ ol.order_total ?? '—' }}</td>
                <td class="px-2 py-1.5 num text-ok">{{ ol.sap_doc_num || '—' }}</td>
                <td class="px-2 py-1.5" :class="matchTone[ol.match_status] || 'text-ink-400'">{{ ol.match_status }}</td>
              </tr>
              <tr v-if="!recon.order_lines?.length"><td colspan="5" class="px-2 py-6 text-center text-ink-400">No order lines.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </Teleport>

    <OrderDetailDrawer v-if="detailName" :order-name="detailName" @close="detailName = null" />
  </div>
</template>
