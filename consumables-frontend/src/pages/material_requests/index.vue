<template>
  <div class="p-4 sm:p-6">
    <!-- Header -->
    <div class="mb-4 flex items-center justify-between sm:mb-5">
      <div>
        <h1 class="text-xl font-bold text-gray-900 sm:text-2xl">Material Requests <span class="text-sm font-normal text-gray-400">(CMR)</span></h1>
        <p class="mt-0.5 text-xs text-gray-500">Request consumable items from store or procurement</p>
      </div>
      <RouterLink
        to="/material-requests/new"
        class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
      >
        + New Request
      </RouterLink>
    </div>

    <!-- Search -->
    <div class="mb-3">
      <input
        v-model="searchQuery"
        type="search"
        placeholder="Search by request ID, plant, or requester…"
        class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
      />
    </div>

    <!-- View tabs -->
    <div class="mb-3 flex gap-1.5 overflow-x-auto pb-1">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors sm:text-sm"
        :class="
          activeTab === tab.id
            ? 'border-teal-600 bg-teal-600 text-white'
            : 'border-gray-300 bg-white text-gray-700 hover:border-teal-400'
        "
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
        <span
          v-if="tab.id === 'decision' && decisionCountUnread > 0"
          class="ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold"
          :class="activeTab === tab.id ? 'bg-white/30 text-white' : 'bg-blue-100 text-blue-800'"
        >
          {{ decisionCountUnread }}
        </span>
      </button>
    </div>

    <!-- Status filter pills -->
    <div class="mb-4 flex gap-1.5 overflow-x-auto pb-1">
      <button
        v-for="s in statusOptions"
        :key="s"
        type="button"
        class="shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors sm:text-xs"
        :class="
          activeStatus === s
            ? 'border-gray-800 bg-gray-800 text-white'
            : 'border-gray-200 bg-white text-gray-600 hover:border-gray-400'
        "
        @click="activeStatus = s"
      >
        {{ s === '' ? 'All Statuses' : s }}
      </button>
    </div>

    <!-- Result count -->
    <p v-if="!materialRequestsStore.loading" class="mb-3 text-xs text-gray-500">
      {{ displayRows.length }} {{ displayRows.length === 1 ? 'request' : 'requests' }} found
    </p>

    <div v-if="materialRequestsStore.loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="h-20 rounded-xl bg-gray-100 animate-pulse" />
    </div>

    <div v-else-if="materialRequestsStore.error" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {{ materialRequestsStore.error }}
    </div>

    <div v-else-if="!displayRows.length" class="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500">
      <p class="font-medium">{{ emptyMessage }}</p>
      <RouterLink v-if="activeTab === 'my'" to="/material-requests/new" class="mt-2 inline-block text-sm text-teal-700 underline">
        Create your first request
      </RouterLink>
    </div>

    <!-- Card list -->
    <div v-else class="space-y-2.5">
      <RouterLink
        v-for="row in displayRows"
        :key="row.name"
        :to="`/material-requests/${row.name}`"
        class="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 transition-all hover:border-teal-300 hover:shadow-sm"
      >
        <!-- Left: urgency indicator -->
        <span
          class="h-8 w-1 shrink-0 rounded-full"
          :class="urgencyColor(row.urgency)"
        />

        <!-- Middle: info -->
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <p class="font-mono text-sm font-semibold text-gray-900">{{ row.name }}</p>
            <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">{{ row.plant_code || row.plant || '—' }}</span>
            <span v-if="row.urgency && row.urgency !== 'Normal'" class="rounded px-1.5 py-0.5 text-[10px] font-semibold" :class="urgencyBg(row.urgency)">
              {{ row.urgency }}
            </span>
          </div>
          <p class="mt-0.5 text-xs text-gray-500">
            by {{ row.requested_by || row.owner || '—' }} ·
            {{ fmtDate(row.requested_on || row.transaction_date || row.creation) }}
            <span v-if="row.items_count || (row.line_items && row.line_items.length)" class="ml-1 text-gray-400">
              · {{ row.items_count || row.line_items?.length || 0 }} item(s)
            </span>
          </p>
        </div>

        <!-- Right: status -->
        <StatusBadge :status="row.status || 'Submitted'" size="sm" />
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useMaterialRequestsStore } from '@/stores/material_requests.js'
import { StatusBadge } from '@/shared/components/index.js'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const materialRequestsStore = useMaterialRequestsStore()

const activeTab = ref('my')
const activeStatus = ref('')
const searchQuery = ref('')

const tabs = [
  { id: 'my', label: 'My Requests' },
  { id: 'decision', label: 'Awaiting Decision' },
]

const DECISION_STATUSES = ['submitted', 'under review']

const decisionCount = computed(() =>
  materialRequestsStore.list.filter(r =>
    DECISION_STATUSES.includes((r.status || '').toLowerCase()),
  ).length,
)
const decisionCountUnread = computed(() => {
  try {
    const raw = localStorage.getItem(`storeops_seen_badges:${authStore.user || 'guest'}`)
    const seen = raw ? JSON.parse(raw) : {}
    return Math.max(0, Number(decisionCount.value || 0) - Number(seen.request || 0))
  } catch {
    return Number(decisionCount.value || 0)
  }
})

const statusOptions = computed(() => {
  const statuses = new Set([''])
  for (const row of materialRequestsStore.list) {
    const s = (row.status || 'Submitted').trim()
    statuses.add(s)
  }
  return [...statuses]
})

const filteredRows = computed(() => {
  let rows = [...materialRequestsStore.list]
  if (activeTab.value === 'my') {
    rows = rows.filter(r => (r.requested_by || r.owner || '') === authStore.user)
  } else if (activeTab.value === 'decision') {
    rows = rows.filter(r => DECISION_STATUSES.includes((r.status || '').toLowerCase()))
  }
  if (activeStatus.value) {
    rows = rows.filter(r => (r.status || 'Submitted') === activeStatus.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    rows = rows.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.plant_code || r.plant || '').toLowerCase().includes(q) ||
      (r.requested_by || r.owner || '').toLowerCase().includes(q) ||
      (r.reason || '').toLowerCase().includes(q),
    )
  }
  return rows
})

const displayRows = computed(() => {
  return [...filteredRows.value].sort((a, b) => {
    const at = new Date(a.requested_on || a.transaction_date || a.creation || 0).getTime()
    const bt = new Date(b.requested_on || b.transaction_date || b.creation || 0).getTime()
    return bt - at
  })
})

const emptyMessage = computed(() => {
  if (activeTab.value === 'my') return 'No requests created by you yet.'
  if (activeTab.value === 'decision') return 'No requests need a decision right now.'
  return 'No material requests found.'
})

function fmtDate(val) {
  if (!val) return ''
  return new Date(val).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function urgencyColor(u) {
  if (u === 'Critical') return 'bg-red-500'
  if (u === 'Urgent') return 'bg-amber-400'
  return 'bg-gray-200'
}

function urgencyTextColor(u) {
  if (u === 'Critical') return 'text-red-600'
  if (u === 'Urgent') return 'text-amber-600'
  return 'text-gray-500'
}

function urgencyBg(u) {
  if (u === 'Critical') return 'bg-red-100 text-red-700'
  if (u === 'Urgent') return 'bg-amber-100 text-amber-700'
  return 'bg-gray-100 text-gray-600'
}

onMounted(() => {
  if (typeof route.query.tab === 'string' && tabs.some(t => t.id === route.query.tab)) {
    activeTab.value = route.query.tab
  }
  materialRequestsStore.fetchList({ page: 1, page_size: 200 })
})

watch(
  () => route.query.tab,
  tab => {
    if (typeof tab === 'string' && tabs.some(t => t.id === tab)) activeTab.value = tab
  },
)
</script>
