<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { call } from '@/api/client'
import StageBadge from '@/components/StageBadge.vue'

const props = withDefaults(defineProps<{ orderName: string; autoLoadCn?: boolean }>(), {
  autoLoadCn: false,
})
defineEmits<{ close: [] }>()

interface OrderItem {
  seller_sku: string; sap_item_code: string | null; is_mapped: number
  asin: string; title: string; quantity: number
  item_price_amount: number; item_tax_amount: number
  shipping_price_amount: number; shipping_tax_amount: number
  shipping_discount_amount: number; promotion_discount_amount: number
  cod_fee: number; unit_price: number
}
interface SettlementLine { settlement_name: string; settlement_id: string; deposit_date: string | null; principal_amount: number }
interface Order { [key: string]: any }
interface CnLine { [key: string]: any }

const loading = ref(false)
const notFound = ref(false)
const order = ref<Order | null>(null)
const items = ref<OrderItem[]>([])
const settlementLines = ref<SettlementLine[]>([])
const showRaw = ref(false)

const cnLoading = ref(false)
const cnLines = ref<CnLine[] | null>(null)
const cnError = ref('')

async function load() {
  loading.value = true
  notFound.value = false
  order.value = null
  cnLines.value = null
  cnError.value = ''
  try {
    const res = await call<{ status: string; message?: string; order?: Order; items?: OrderItem[]; settlement_lines?: SettlementLine[] }>(
      'get_order_detail', { order_name: props.orderName },
    )
    if (res.status !== 'ok') {
      notFound.value = true
      return
    }
    order.value = res.order ?? null
    items.value = res.items ?? []
    settlementLines.value = res.settlement_lines ?? []
    if (props.autoLoadCn && order.value?.cn_doc_num) await loadCn()
  } finally {
    loading.value = false
  }
}

async function loadCn() {
  cnLoading.value = true
  cnError.value = ''
  try {
    const res = await call<{ status: string; message?: string; lines?: CnLine[] }>(
      'get_credit_note_detail', { order_name: props.orderName },
    )
    if (res.status === 'ok') cnLines.value = res.lines ?? []
    else cnError.value = res.message || 'Failed to load credit note detail'
  } finally {
    cnLoading.value = false
  }
}

function fmt(d: string | null | undefined) { return d ? String(d).slice(0, 10) : '—' }
function fmtDt(d: string | null | undefined) { return d ? String(d).slice(0, 19) : '—' }
function money(v: number | null | undefined) {
  return v == null ? '—' : `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

onMounted(load)
watch(() => props.orderName, load)
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-40 flex justify-end bg-black/50" @click.self="$emit('close')">
      <div class="w-[36rem] h-full bg-ink-900 border-l border-ink-700 p-5 overflow-auto">
        <div class="flex items-center justify-between">
          <div class="font-mono text-sm">{{ orderName }}</div>
          <button class="btn-ghost" @click="$emit('close')">✕</button>
        </div>

        <div v-if="loading" class="mt-6 text-xs text-ink-400 text-center">Loading…</div>
        <div v-else-if="notFound" class="mt-6 text-xs text-bad text-center">Order not found.</div>

        <div v-else-if="order" class="mt-4 space-y-5">
          <!-- Header -->
          <div class="flex items-center gap-2">
            <StageBadge :stage="order.stage" />
            <span class="text-[11px] text-ink-400">{{ order.order_status }}</span>
          </div>

          <!-- Buyer & shipping -->
          <div>
            <div class="label mb-1.5">Buyer & shipping</div>
            <div class="grid grid-cols-2 gap-3 text-xs">
              <div><div class="label">Buyer</div><div class="mt-1">{{ order.buyer_name || '—' }}</div></div>
              <div><div class="label">Email</div><div class="mt-1 truncate">{{ order.buyer_email || '—' }}</div></div>
              <div><div class="label">City / State</div><div class="mt-1">{{ order.ship_city || '—' }}, {{ order.ship_state_or_region || '—' }}</div></div>
              <div><div class="label">Postal / Country</div><div class="mt-1 num">{{ order.ship_postal_code || '—' }} {{ order.ship_country || '' }}</div></div>
            </div>
          </div>

          <!-- Flags & channel -->
          <div>
            <div class="label mb-1.5">Flags & channel</div>
            <div class="flex flex-wrap gap-1.5">
              <span v-if="order.is_prime" class="px-1.5 py-0.5 rounded border border-accent-dim text-accent text-[10px]">Prime</span>
              <span v-if="order.is_business_order" class="px-1.5 py-0.5 rounded border border-ink-600 text-ink-300 text-[10px]">Business</span>
              <span v-if="order.is_replacement_order" class="px-1.5 py-0.5 rounded border border-money-dim text-money text-[10px]">Replacement</span>
              <span class="px-1.5 py-0.5 rounded border border-ink-600 text-ink-300 text-[10px]">{{ order.fulfillment_channel || '—' }}</span>
              <span class="px-1.5 py-0.5 rounded border border-ink-600 text-ink-300 text-[10px]">{{ order.sales_channel || '—' }}</span>
              <span class="px-1.5 py-0.5 rounded border border-ink-600 text-ink-300 text-[10px]">{{ order.ship_service_level || '—' }}</span>
            </div>
          </div>

          <!-- Dates -->
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div><div class="label">Purchased</div><div class="mt-1 num">{{ fmtDt(order.purchase_date) }}</div></div>
            <div><div class="label">Shipped</div><div class="mt-1 num">{{ fmt(order.actual_ship_date) }}</div></div>
            <div><div class="label">Posted at</div><div class="mt-1 num">{{ fmtDt(order.posted_at) }}</div></div>
            <div><div class="label">SAP DocNum</div><div class="mt-1 num text-ok">{{ order.sap_doc_num || '—' }}</div></div>
          </div>

          <!-- Line items -->
          <div>
            <div class="label mb-1.5">Line items ({{ items.length }})</div>
            <div class="space-y-2">
              <div v-for="(it, i) in items" :key="i" class="card p-2.5 text-xs">
                <div class="flex items-center justify-between">
                  <div class="font-mono">{{ it.seller_sku }}</div>
                  <div class="flex items-center gap-1.5">
                    <span v-if="!it.is_mapped" class="text-[10px] text-bad border border-bad-dim rounded px-1">unmapped</span>
                    <span class="text-[10px] text-ink-400">{{ it.sap_item_code || '—' }}</span>
                  </div>
                </div>
                <div class="text-ink-300 mt-0.5 truncate" :title="it.title">{{ it.title }}</div>
                <div class="grid grid-cols-4 gap-1.5 mt-2 num text-[11px]">
                  <div><div class="label">Qty</div>{{ it.quantity }}</div>
                  <div><div class="label">Unit price</div>{{ money(it.unit_price) }}</div>
                  <div><div class="label">Item tax</div>{{ money(it.item_tax_amount) }}</div>
                  <div><div class="label">Promo</div>{{ money(it.promotion_discount_amount) }}</div>
                  <div><div class="label">Shipping</div>{{ money(it.shipping_price_amount) }}</div>
                  <div><div class="label">Ship tax</div>{{ money(it.shipping_tax_amount) }}</div>
                  <div><div class="label">Ship discount</div>{{ money(it.shipping_discount_amount) }}</div>
                  <div><div class="label">COD fee</div>{{ money(it.cod_fee) }}</div>
                </div>
              </div>
            </div>
            <div class="mt-2 text-right text-xs">
              <span class="label">Order total</span>
              <span class="ml-2 num font-semibold">{{ money(order.order_total_amount) }} {{ order.order_total_currency }}</span>
            </div>
          </div>

          <!-- Credit note -->
          <div v-if="order.cn_doc_num">
            <div class="label mb-1.5">Credit note</div>
            <div class="text-xs mb-2">
              CN DocNum <span class="num text-money">{{ order.cn_doc_num }}</span> ·
              refunded <span class="num">{{ fmtDt(order.refunded_at) }}</span>
            </div>
            <button v-if="!cnLines && !cnLoading" class="btn-ghost" @click="loadCn">Load refund detail</button>
            <div v-if="cnLoading" class="text-xs text-ink-400">Loading from SAP…</div>
            <div v-if="cnError" class="text-xs text-bad">{{ cnError }}</div>
            <table v-if="cnLines" class="w-full text-xs mt-2">
              <thead>
                <tr class="text-left border-b border-ink-700">
                  <th class="label px-1 py-1 font-normal">Item</th>
                  <th class="label px-1 py-1 font-normal text-right">Qty</th>
                  <th class="label px-1 py-1 font-normal text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(l, i) in cnLines" :key="i" class="border-b border-ink-700/40 last:border-0">
                  <td class="px-1 py-1 font-mono">{{ l.ItemCode }}</td>
                  <td class="px-1 py-1 num text-right">{{ l.Quantity ?? '—' }}</td>
                  <td class="px-1 py-1 num text-right text-money">{{ money(l.LineTotal ?? l.UnitPrice) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Settlement linkage -->
          <div v-if="settlementLines.length">
            <div class="label mb-1.5">Settlement linkage</div>
            <table class="w-full text-xs">
              <tbody>
                <tr v-for="sl in settlementLines" :key="sl.settlement_name" class="border-b border-ink-700/40 last:border-0">
                  <td class="py-1 font-mono">{{ sl.settlement_id }}</td>
                  <td class="py-1 num text-ink-300">{{ fmt(sl.deposit_date) }}</td>
                  <td class="py-1 num text-right text-ok">{{ money(sl.principal_amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Errors -->
          <div v-if="order.last_error">
            <div class="label mb-1">Last error <span class="text-ink-400 normal-case">(attempt {{ order.attempt_count || 0 }})</span></div>
            <pre class="text-[11px] text-bad whitespace-pre-wrap bg-ink-900/70 rounded p-2 border border-bad-dim">{{ order.last_error }}</pre>
          </div>

          <!-- Raw JSON -->
          <div>
            <button class="label" @click="showRaw = !showRaw">{{ showRaw ? '▾' : '▸' }} Raw JSON</button>
            <pre v-if="showRaw" class="mt-1 text-[10px] text-ink-300 whitespace-pre-wrap bg-ink-900/70 rounded p-2 border border-ink-700 max-h-64 overflow-auto">{{ JSON.stringify({ order, items }, null, 1) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
