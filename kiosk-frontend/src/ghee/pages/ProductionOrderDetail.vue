<template>
  <div class="p-6 max-w-5xl mx-auto space-y-6">

    <!-- Back link -->
    <router-link
      to="/ghee-production-order"
      class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
    >
      ← Back to Dashboard
    </router-link>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20 text-gray-400">
      <svg class="animate-spin w-6 h-6 mr-2" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      Loading…
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
      {{ error }}
      <button @click="load" class="ml-2 underline text-xs">Retry</button>
    </div>

    <template v-else-if="order">

      <!-- Summary card -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h1 class="text-xl font-bold text-gray-900 font-mono">{{ order.name }}</h1>
            <p class="text-sm text-gray-500 mt-0.5">Ghee Reverse Production Order</p>
          </div>
          <span :class="['inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold', badge.cls]">
            {{ badge.icon }} {{ order.status }}
          </span>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-gray-100">
          <div class="px-6 py-4">
            <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">Date</div>
            <div class="text-sm font-semibold text-gray-800">{{ fmtDate(order.doc_date) }}</div>
          </div>
          <div class="px-6 py-4">
            <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">Source Item</div>
            <div class="text-sm font-mono font-semibold text-gray-800">{{ order.source_item_code || '—' }}</div>
          </div>
          <div class="px-6 py-4">
            <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">Output Item</div>
            <div class="text-sm font-mono font-semibold text-gray-800">{{ order.new_item_code || '—' }}</div>
          </div>
          <div class="px-6 py-4">
            <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">Created By</div>
            <div class="text-sm text-gray-700">{{ shortEmail(order.owner) }}</div>
          </div>
        </div>

        <div v-if="order.remarks" class="px-6 py-3 border-t border-gray-100 bg-gray-50">
          <span class="text-xs text-gray-400 font-medium">Remarks: </span>
          <span class="text-xs text-gray-600">{{ order.remarks }}</span>
        </div>
      </div>

      <!-- SAP Documents -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-2">Production Order</div>
          <div class="font-mono text-lg font-bold text-blue-700">{{ order.po_doc_num || '—' }}</div>
          <div class="text-xs text-gray-400 mt-0.5">DocEntry: {{ order.po_entry || '—' }}</div>
          <div v-if="order.po_created_at" class="text-xs text-gray-400 mt-1">{{ fmtDatetime(order.po_created_at) }}</div>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-2">Goods Issue</div>
          <div class="font-mono text-lg font-bold text-orange-700">{{ order.goods_issue_doc || '—' }}</div>
          <div v-if="order.gi_done_at" class="text-xs text-gray-400 mt-1">{{ fmtDatetime(order.gi_done_at) }}</div>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <div class="text-xs text-gray-400 uppercase tracking-wide font-medium mb-2">Goods Receipt</div>
          <div class="font-mono text-lg font-bold text-green-700">{{ order.goods_receipt_doc || '—' }}</div>
          <div v-if="order.gr_done_at" class="text-xs text-gray-400 mt-1">{{ fmtDatetime(order.gr_done_at) }}</div>
          <div v-if="order.po_closed" class="mt-1">
            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">PO Closed</span>
          </div>
        </div>
      </div>

      <!-- Cost Summary -->
      <div v-if="order.status === 'Completed'" class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Cost Summary</h3>
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div>
            <div class="text-xs text-gray-400 mb-1">Total GI Cost</div>
            <div class="text-base font-bold text-gray-800">₹{{ fmt2(order.total_gi_cost) }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400 mb-1">Jar Cost</div>
            <div class="text-base font-bold text-gray-800">₹{{ fmt2(order.jar_cost) }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400 mb-1">Scrap Cost</div>
            <div class="text-base font-bold text-gray-800">₹{{ fmt2(order.scrap_cost) }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400 mb-1">FG Residual</div>
            <div class="text-base font-bold text-gray-800">₹{{ fmt2(order.fg_residual) }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400 mb-1">Total GR Cost</div>
            <div class="text-base font-bold text-gray-800">₹{{ fmt2(order.total_gr_cost) }}</div>
          </div>
        </div>
      </div>

      <!-- Cost Breakdown (items child table) -->
      <div v-if="order.items && order.items.length" class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-sm font-semibold text-gray-700">Cost Breakdown</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-100 text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Item Code</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Batch</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Warehouse</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Qty</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Unit Price</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Line Cost</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Source</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="it in order.items" :key="it.name || it.item_code" class="hover:bg-gray-50">
                <td class="px-4 py-2.5 font-mono text-xs font-semibold text-gray-800">{{ it.item_code }}</td>
                <td class="px-4 py-2.5 font-mono text-xs text-gray-600">{{ it.batch_no || '—' }}</td>
                <td class="px-4 py-2.5 text-xs text-gray-600">{{ it.warehouse || '—' }}</td>
                <td class="px-4 py-2.5 text-xs text-right font-mono text-gray-700">{{ fmt4(it.quantity) }}</td>
                <td class="px-4 py-2.5 text-xs text-right font-mono text-gray-700">₹{{ fmt2(it.unit_price) }}</td>
                <td class="px-4 py-2.5 text-xs text-right font-mono font-semibold text-gray-800">₹{{ fmt2(it.line_cost) }}</td>
                <td class="px-4 py-2.5 text-xs text-gray-400">{{ it.cost_source || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- State timeline -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-5">Audit Trail</h3>
        <div class="space-y-4">
          <div v-for="step in timeline" :key="step.label" class="flex items-start gap-3">
            <div :class="['flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm', step.done ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400']">
              {{ step.done ? '✓' : '○' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium" :class="step.done ? 'text-gray-800' : 'text-gray-400'">{{ step.label }}</div>
              <div v-if="step.ts" class="text-xs text-gray-400 mt-0.5">{{ fmtDatetime(step.ts) }}</div>
              <div v-if="step.doc" class="text-xs text-gray-500 font-mono mt-0.5">{{ step.doc }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error panel for Failed orders with Resume link -->
      <div v-if="order.status === 'Failed' && order.error_message" class="bg-red-50 border border-red-200 rounded-xl p-5">
        <div class="text-sm font-semibold text-red-700 mb-2">Last Error</div>
        <pre class="text-xs text-red-600 whitespace-pre-wrap font-mono">{{ order.error_message }}</pre>
        <div class="mt-4">
          <router-link
            :to="`/ghee-production-order/new?gpo=${order.name}`"
            class="inline-flex items-center px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            Retry — Resume from last good state
          </router-link>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { gheeProductionService } from '../services/gheeProductionService.js'

const route   = useRoute()
const order   = ref(null)
const loading = ref(false)
const error   = ref('')

const badge = computed(() => ({
  'Draft':      { cls: 'bg-gray-100 text-gray-600',    icon: '○' },
  'PO Created': { cls: 'bg-blue-100 text-blue-700',    icon: '◎' },
  'GI Done':    { cls: 'bg-orange-100 text-orange-700', icon: '◑' },
  'GR Done':    { cls: 'bg-purple-100 text-purple-700', icon: '◕' },
  'Completed':  { cls: 'bg-green-100 text-green-700',  icon: '●' },
  'Failed':     { cls: 'bg-red-100 text-red-700',      icon: '✕' },
}[order.value?.status] || { cls: 'bg-gray-100 text-gray-600', icon: '○' }))

const timeline = computed(() => {
  if (!order.value) return []
  const o = order.value
  return [
    { label: 'Order Created',       done: true,                            ts: o.creation,       doc: o.name },
    { label: 'Production Order (SAP)', done: !!o.po_entry,                ts: o.po_created_at,  doc: o.po_doc_num ? `PO# ${o.po_doc_num}` : '' },
    { label: 'Goods Issue Posted',  done: !!o.goods_issue_doc,            ts: o.gi_done_at,     doc: o.goods_issue_doc ? `GI# ${o.goods_issue_doc}` : '' },
    { label: 'Goods Receipt Posted', done: !!o.goods_receipt_doc,         ts: o.gr_done_at,     doc: o.goods_receipt_doc ? `GR# ${o.goods_receipt_doc}` : '' },
    { label: 'Completed & PO Closed', done: o.status === 'Completed',     ts: o.completed_at,   doc: '' },
  ]
})

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtDatetime(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function shortEmail(email) {
  return email ? email.split('@')[0] : '—'
}

function fmt2(n) {
  return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

function fmt4(n) {
  return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 4 })
}

async function load() {
  loading.value = true
  error.value   = ''
  try {
    order.value = await gheeProductionService.getOrder(route.params.name)
  } catch (e) {
    error.value = e.message || 'Failed to load production order.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
