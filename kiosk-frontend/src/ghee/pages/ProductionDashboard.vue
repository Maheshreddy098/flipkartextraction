<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-gray-900">Ghee Production Orders</h2>
        <p class="text-sm text-gray-500 mt-0.5">Reverse production history — all records persist permanently</p>
      </div>
      <router-link
        to="/ghee-production-order/new"
        class="px-4 py-2.5 bg-yellow-500 hover:bg-yellow-600 text-white text-sm font-semibold rounded-lg transition-colors shadow-sm"
      >
        + New Production Order
      </router-link>
    </div>

    <!-- KPI cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div
        v-for="kpi in kpis"
        :key="kpi.label"
        :class="[
          'bg-white rounded-xl border p-4 shadow-sm cursor-pointer transition-all hover:shadow-md',
          activeFilter === kpi.filter
            ? 'border-yellow-400 ring-2 ring-yellow-300'
            : 'border-gray-200'
        ]"
        @click="activeFilter = activeFilter === kpi.filter ? 'all' : kpi.filter"
      >
        <div :class="['text-3xl font-bold', kpi.color]">{{ kpi.count }}</div>
        <div class="text-xs text-gray-500 mt-1 font-medium uppercase tracking-wide">{{ kpi.label }}</div>
      </div>
    </div>

    <!-- Filters & search -->
    <div class="flex gap-3 flex-wrap items-center">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        @click="activeFilter = f.key"
        :class="[
          'px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
          activeFilter === f.key
            ? 'bg-yellow-500 text-white shadow-sm'
            : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
        ]"
      >
        {{ f.label }}
        <span class="ml-1 opacity-60">({{ countFor(f.key) }})</span>
      </button>
      <div class="ml-auto flex items-center gap-2">
        <input
          v-model="search"
          type="text"
          placeholder="Search GPO #, item, doc…"
          class="px-3 py-1.5 border border-gray-300 rounded-lg text-xs focus:outline-none focus:border-yellow-400 w-52"
        />
        <button @click="load" class="px-3 py-1.5 text-xs bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
          Refresh
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20 text-gray-400">
      <svg class="animate-spin w-6 h-6 mr-2" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      Loading…
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center gap-3">
      {{ error }}
      <button @click="load" class="underline text-xs">Retry</button>
    </div>

    <!-- Empty -->
    <div v-else-if="filtered.length === 0" class="text-center py-20 text-gray-400">
      <div class="text-5xl mb-4">📋</div>
      <p class="text-sm font-medium">No production orders found.</p>
      <router-link to="/ghee-production-order/new" class="mt-3 inline-block text-yellow-600 underline text-sm">
        Create the first one
      </router-link>
    </div>

    <!-- Table -->
    <div v-else class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-100 text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">GPO #</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Source Item</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">PO Num</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">GI Doc</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">GR Doc</th>
              <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Cost</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">By</th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Modified</th>
              <th class="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="o in filtered"
              :key="o.name"
              class="hover:bg-yellow-50/40 transition-colors"
            >
              <td class="px-4 py-3 font-mono text-xs font-semibold text-gray-700">{{ o.name }}</td>
              <td class="px-4 py-3 text-xs text-gray-600 whitespace-nowrap">{{ fmtDate(o.doc_date) }}</td>
              <td class="px-4 py-3">
                <span :class="['inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold', statusBadge(o.status).cls]">
                  {{ statusBadge(o.status).icon }} {{ o.status }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-xs font-semibold text-gray-800">{{ o.source_item_code || '—' }}</td>
              <td class="px-4 py-3 font-mono text-xs text-blue-700 font-semibold">{{ o.po_doc_num || '—' }}</td>
              <td class="px-4 py-3 font-mono text-xs text-gray-600">{{ o.goods_issue_doc || '—' }}</td>
              <td class="px-4 py-3 font-mono text-xs text-gray-600">{{ o.goods_receipt_doc || '—' }}</td>
              <td class="px-4 py-3 text-xs text-right font-mono text-gray-700">
                {{ o.total_gi_cost ? '₹' + fmt2(o.total_gi_cost) : '—' }}
              </td>
              <td class="px-4 py-3 text-xs text-gray-400 truncate max-w-[100px]">{{ shortEmail(o.owner) }}</td>
              <td class="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{{ fmtDatetime(o.modified) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center gap-2 justify-end">
                  <router-link
                    v-if="canResume(o)"
                    :to="`/ghee-production-order/new?gpo=${o.name}`"
                    class="px-3 py-1.5 bg-yellow-500 hover:bg-yellow-600 text-white text-xs font-semibold rounded-md transition-colors whitespace-nowrap"
                  >
                    Resume
                  </router-link>
                  <router-link
                    v-if="o.status === 'Completed'"
                    :to="`/ghee-production-order/${o.name}`"
                    class="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-md transition-colors whitespace-nowrap"
                  >
                    View
                  </router-link>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2.5 border-t border-gray-100 text-xs text-gray-400 bg-gray-50">
        Showing {{ filtered.length }} of {{ orders.length }} orders
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { gheeProductionService } from '../services/gheeProductionService.js'

const orders       = ref([])
const loading      = ref(false)
const error        = ref('')
const activeFilter = ref('all')
const search       = ref('')

const FILTERS = [
  { key: 'all',       label: 'All' },
  { key: 'active',    label: 'In Progress' },
  { key: 'Completed', label: 'Completed' },
  { key: 'Failed',    label: 'Failed' },
]

const IN_PROGRESS = ['Draft', 'PO Created', 'GI Done', 'GR Done']

const kpis = computed(() => [
  {
    label: 'Today',
    filter: 'today',
    count: orders.value.filter(o => isToday(o.doc_date)).length,
    color: 'text-blue-600',
  },
  {
    label: 'In Progress',
    filter: 'active',
    count: orders.value.filter(o => IN_PROGRESS.includes(o.status)).length,
    color: 'text-yellow-600',
  },
  {
    label: 'Completed',
    filter: 'Completed',
    count: orders.value.filter(o => o.status === 'Completed').length,
    color: 'text-green-600',
  },
  {
    label: 'Failed',
    filter: 'Failed',
    count: orders.value.filter(o => o.status === 'Failed').length,
    color: 'text-red-500',
  },
])

function isToday(dateStr) {
  if (!dateStr) return false
  return String(dateStr).slice(0, 10) === new Date().toISOString().slice(0, 10)
}

const filtered = computed(() => {
  let list = orders.value

  if (activeFilter.value === 'active') {
    list = list.filter(o => IN_PROGRESS.includes(o.status))
  } else if (activeFilter.value === 'today') {
    list = list.filter(o => isToday(o.doc_date))
  } else if (activeFilter.value !== 'all') {
    list = list.filter(o => o.status === activeFilter.value)
  }

  const q = search.value.trim().toLowerCase()
  if (q) {
    list = list.filter(o =>
      (o.name              || '').toLowerCase().includes(q) ||
      (o.source_item_code  || '').toLowerCase().includes(q) ||
      (o.po_doc_num        || '').toLowerCase().includes(q) ||
      (o.goods_issue_doc   || '').toLowerCase().includes(q) ||
      (o.goods_receipt_doc || '').toLowerCase().includes(q) ||
      (o.owner             || '').toLowerCase().includes(q)
    )
  }

  return list
})

function countFor(key) {
  if (key === 'all')    return orders.value.length
  if (key === 'active') return orders.value.filter(o => IN_PROGRESS.includes(o.status)).length
  return orders.value.filter(o => o.status === key).length
}

function canResume(o) {
  return IN_PROGRESS.includes(o.status) || o.status === 'Failed'
}

function statusBadge(status) {
  return {
    'Draft':      { cls: 'bg-gray-100 text-gray-600',    icon: '○' },
    'PO Created': { cls: 'bg-blue-100 text-blue-700',    icon: '◎' },
    'GI Done':    { cls: 'bg-orange-100 text-orange-700', icon: '◑' },
    'GR Done':    { cls: 'bg-purple-100 text-purple-700', icon: '◕' },
    'Completed':  { cls: 'bg-green-100 text-green-700',  icon: '●' },
    'Failed':     { cls: 'bg-red-100 text-red-700',      icon: '✕' },
  }[status] || { cls: 'bg-gray-100 text-gray-600', icon: '○' }
}

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtDatetime(dt) {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) +
    ' ' + d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function shortEmail(email) {
  return email ? email.split('@')[0] : '—'
}

function fmt2(n) {
  return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

async function load() {
  loading.value = true
  error.value   = ''
  try {
    const res = await gheeProductionService.getAllOrders()
    orders.value = res?.orders || []
  } catch (e) {
    error.value = e.message || 'Failed to load production orders.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
