<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { call } from '@/api/client'
import { usePeriod } from '@/stores/period'
import { useSession } from '@/stores/session'
import { toast } from '@/stores/toast'
import StageBadge from '@/components/StageBadge.vue'
import OrderDetailDrawer from '@/components/OrderDetailDrawer.vue'

interface OrderRow {
  name: string; amazon_order_id: string; order_status: string; stage: string
  purchase_date: string; actual_ship_date: string | null
  sap_doc_entry: string | null; sap_doc_num: string | null
  posted_at: string | null; last_error: string | null; item_count: number
  cn_doc_num: string | null; refunded_at: string | null
}

const period = usePeriod()
const session = useSession()

const stage = ref('all')
const page = ref(1)
const rows = ref<OrderRow[]>([])
const total = ref(0)
const pageSize = 50
const loading = ref(false)
const detailName = ref<string | null>(null)
const search = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined

const stages = ['all', 'fetched', 'ready', 'posting', 'posted', 'failed']

async function load() {
  loading.value = true
  try {
    const res = await call<{ orders: OrderRow[]; total: number }>('get_orders', {
      from_date: period.from, to_date: period.to, stage: stage.value, page: page.value, page_size: pageSize,
      search: search.value.trim() || undefined,
    })
    rows.value = res.orders
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; load() }, 300)
}
onBeforeUnmount(() => clearTimeout(searchTimer))

async function retry(r: OrderRow) {
  const res = await call<{ status: string; message?: string; doc_num?: string }>('retry_order', { amazon_order_id: r.amazon_order_id })
  if (res.status === 'success') toast(`Posted ${r.amazon_order_id} → DocNum ${res.doc_num}`, 'ok')
  else toast(res.message || 'Retry failed', 'error')
  await load()
}

async function postOne(r: OrderRow) {
  const res = await call<{ status: string; message?: string; doc_num?: string }>('post_single', { amazon_order_id: r.amazon_order_id })
  if (res.status === 'success') toast(`Posted ${r.amazon_order_id} → DocNum ${res.doc_num}`, 'ok')
  else toast(res.message || 'Post failed', 'error')
  await load()
}

function exportCsv() {
  const params = new URLSearchParams({
    from_date: period.from, to_date: period.to, stage: stage.value,
  })
  if (search.value.trim()) params.set('search', search.value.trim())
  window.open(`/api/method/khanal_tech_integrations.amazon_us.api.ops.export_orders_csv?${params}`, '_blank')
}

function fmt(d: string | null) { return d ? String(d).slice(0, 10) : '—' }

onMounted(load)
watch([() => period.key, stage], () => { page.value = 1; load() })
watch(page, load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-3 flex-wrap">
      <div class="flex rounded-md overflow-hidden border border-ink-600">
        <button
          v-for="s in stages" :key="s"
          class="px-3 py-1.5 text-xs capitalize"
          :class="stage === s ? 'bg-ink-700 text-ink-100' : 'text-ink-300 hover:bg-ink-800'"
          @click="stage = s"
        >{{ s }}</button>
      </div>
      <input v-model="search" @input="onSearchInput" placeholder="search order id, buyer, SKU…" class="input w-64 font-mono" />
      <button class="btn-ghost" @click="exportCsv">⇩ Export CSV</button>
      <div class="ml-auto text-xs text-ink-400 num">{{ total.toLocaleString() }} orders</div>
    </div>

    <div class="card overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-left border-b border-ink-700">
            <th class="label px-3 py-2 font-normal">Order</th>
            <th class="label px-3 py-2 font-normal">Stage</th>
            <th class="label px-3 py-2 font-normal">Shipped</th>
            <th class="label px-3 py-2 font-normal">Purchased</th>
            <th class="label px-3 py-2 font-normal">SAP Doc</th>
            <th class="label px-3 py-2 font-normal">CN</th>
            <th class="label px-3 py-2 font-normal">Items</th>
            <th class="label px-3 py-2 font-normal"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="8" class="px-3 py-6 text-center text-ink-400">Loading…</td></tr>
          <tr
            v-for="r in rows" v-else :key="r.name"
            class="border-b border-ink-700/40 last:border-0 hover:bg-ink-700/20 cursor-pointer"
            @click="detailName = r.name"
          >
            <td class="px-3 py-2 font-mono">{{ r.amazon_order_id }}</td>
            <td class="px-3 py-2"><StageBadge :stage="r.stage" /></td>
            <td class="px-3 py-2 num">{{ fmt(r.actual_ship_date) }}</td>
            <td class="px-3 py-2 num text-ink-300">{{ fmt(r.purchase_date) }}</td>
            <td class="px-3 py-2 num text-ok">{{ r.sap_doc_num || '—' }}</td>
            <td class="px-3 py-2 num text-money">{{ r.cn_doc_num || '—' }}</td>
            <td class="px-3 py-2 num">{{ r.item_count }}</td>
            <td class="px-3 py-2 text-right" @click.stop>
              <button v-if="session.canPost && r.stage === 'failed'" class="btn-danger !py-0.5" @click="retry(r)">Retry</button>
              <button v-else-if="session.canPost && r.stage === 'ready'" class="btn-money !py-0.5" @click="postOne(r)">Post</button>
            </td>
          </tr>
          <tr v-if="!loading && !rows.length"><td colspan="8" class="px-3 py-6 text-center text-ink-400">No orders.</td></tr>
        </tbody>
      </table>
    </div>

    <div class="flex items-center gap-2 justify-end text-xs">
      <button class="btn-ghost" :disabled="page <= 1" @click="page--">‹ Prev</button>
      <span class="num text-ink-300">page {{ page }} / {{ Math.max(1, Math.ceil(total / pageSize)) }}</span>
      <button class="btn-ghost" :disabled="page >= Math.ceil(total / pageSize)" @click="page++">Next ›</button>
    </div>

    <OrderDetailDrawer v-if="detailName" :order-name="detailName" @close="detailName = null" />
  </div>
</template>
