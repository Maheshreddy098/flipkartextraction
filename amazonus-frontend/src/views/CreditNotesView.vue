<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { call } from '@/api/client'
import { usePeriod } from '@/stores/period'
import OrderDetailDrawer from '@/components/OrderDetailDrawer.vue'

interface CnRow {
  name: string; amazon_order_id: string; cn_doc_num: string; sap_doc_num: string
  refunded_at: string; actual_ship_date: string | null
}

const period = usePeriod()
const rows = ref<CnRow[]>([])
const loading = ref(false)
const detailName = ref<string | null>(null)

// Credit-noted orders in the window (refund recorded on the staged order).
async function load() {
  loading.value = true
  try {
    const res = await call<{ orders: any[]; total: number }>('get_orders', {
      from_date: period.from, to_date: period.to, stage: 'all', page: 1, page_size: 500,
    })
    rows.value = res.orders.filter((o: any) => o.cn_doc_num || o.refunded_at)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => period.key, load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="text-xs text-ink-400">
        Credit-noted orders in {{ period.label }} · run CN jobs from the
        <RouterLink to="/actions" class="text-accent hover:underline">Actions</RouterLink> tab
      </div>
      <div class="text-xs text-ink-400 num">{{ rows.length }} orders</div>
    </div>

    <div class="card overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-left border-b border-ink-700">
            <th class="label px-3 py-2 font-normal">Order</th>
            <th class="label px-3 py-2 font-normal">Invoice DocNum</th>
            <th class="label px-3 py-2 font-normal">CN DocNum</th>
            <th class="label px-3 py-2 font-normal">Refunded at</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="4" class="px-3 py-6 text-center text-ink-400">Loading…</td></tr>
          <tr
            v-for="r in rows" v-else :key="r.amazon_order_id"
            class="border-b border-ink-700/40 last:border-0 hover:bg-ink-700/20 cursor-pointer"
            @click="detailName = r.name"
          >
            <td class="px-3 py-2 font-mono">{{ r.amazon_order_id }}</td>
            <td class="px-3 py-2 num text-ok">{{ r.sap_doc_num || '—' }}</td>
            <td class="px-3 py-2 num text-money">{{ r.cn_doc_num || '—' }}</td>
            <td class="px-3 py-2 num text-ink-300">{{ r.refunded_at || '—' }}</td>
          </tr>
          <tr v-if="!loading && !rows.length"><td colspan="4" class="px-3 py-6 text-center text-ink-400">No credit notes in this window.</td></tr>
        </tbody>
      </table>
    </div>
    <p class="text-[11px] text-ink-400">
      CNs reverse item value, product tax, shipping and shipping tax (EXP000003 / EXP000004) —
      matching the refund the buyer actually received. Pre-fix CNs carry a separate “-SHIP” supplement CN.
      Click a row for the full refund line breakdown.
    </p>

    <OrderDetailDrawer v-if="detailName" :order-name="detailName" :auto-load-cn="true" @close="detailName = null" />
  </div>
</template>
