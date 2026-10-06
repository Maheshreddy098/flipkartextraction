<template>
  <div class="p-4 sm:p-6">
    <!-- Page header -->
    <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Transfers <span class="text-sm font-normal text-gray-400">(CTR)</span></h1>
        <p class="mt-0.5 text-xs text-gray-500">Move consumable stock between plants</p>
      </div>
      <RouterLink
        to="/transfers/new"
        class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
      >
        + New Transfer
      </RouterLink>
    </div>

    <!-- Status tabs -->
    <div class="mb-4 flex gap-2 overflow-x-auto pb-1">
      <button
        v-for="tab in statusTabs"
        :key="tab.id"
        type="button"
        class="shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm"
        :class="activeTab === tab.id
          ? 'border-teal-600 bg-teal-600 text-white'
          : 'border-gray-300 bg-white text-gray-700 hover:border-teal-400'"
        @click="selectTab(tab.id)"
      >
        {{ tab.label }}
        <span
          v-if="tab.id === 'pending_receipt' && pendingReceiptsUnread > 0"
          class="ml-1 rounded-full px-1.5 text-xs font-semibold"
          :class="activeTab === tab.id ? 'bg-white/25 text-white' : 'bg-amber-100 text-amber-900'"
        >
          {{ pendingReceiptsUnread }}
        </span>
      </button>
    </div>

    <!-- Filters row -->
    <div class="mb-5 flex flex-wrap items-end gap-4">
      <div v-if="authStore.isSuperAdmin">
        <label class="mb-1 block text-xs font-medium text-gray-600">Plant</label>
        <select
          v-model="plantCode"
          class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All plants</option>
          <option v-for="p in authStore.plants" :key="p.plant_code" :value="p.plant_code">
            {{ p.plant_code }} — {{ p.plant_name }}
          </option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs font-medium text-gray-600">From date</label>
        <input v-model="filterFrom" type="date" class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="mb-1 block text-xs font-medium text-gray-600">To date</label>
        <input v-model="filterTo" type="date" class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm" />
      </div>
    </div>

    <!-- Error -->
    <div v-if="transfersStore.error" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {{ transfersStore.error }}
    </div>

    <!-- DataTable -->
    <DataTable
      :columns="columns"
      :rows="displayRows"
      :total="totalForPagination"
      :page="page"
      :page-size="PAGE_SIZE"
      :loading="transfersStore.loading"
      empty-text="No transfer requests match your filters."
      @row-click="goToDetail"
      @page-change="setPage"
    >
      <template #cell-route="{ row }">
        <span class="font-medium text-gray-900">{{ row.from_plant_code || row.from_plant || '—' }}</span>
        <span class="mx-1.5 text-gray-400">→</span>
        <span class="font-medium text-gray-900">{{ row.to_plant_code || row.to_plant || '—' }}</span>
      </template>
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-date="{ row }">
        {{ fmtDate(row) }}
      </template>
      <template #cell-items="{ row }">
        {{ itemCount(row) }}
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useTransfersStore } from '@/stores/transfers.js'
import { StatusBadge, DataTable } from '@/shared/components/index.js'

const PAGE_SIZE = 20

const statusTabs = [
  { id: 'all',              label: 'All',                  apiStatus: null },
  { id: 'pending_approval', label: 'Awaiting Approval',    apiStatus: 'Submitted' },
  { id: 'in_transit',       label: 'In Transit',           apiStatus: 'In Transit' },
  { id: 'pending_receipt',  label: 'Pending Receipt',      apiStatus: null, pendingOnly: true },
  { id: 'completed',        label: 'Completed',            apiStatus: 'Completed' },
  { id: 'rejected',         label: 'Rejected',             apiStatus: 'Rejected' },
]

const columns = [
  { key: 'name',   label: 'Transfer # (CTR)',  cellClass: 'font-mono text-xs' },
  { key: 'route',  label: 'From → To' },
  { key: 'items',  label: 'Items',             cellClass: 'text-center' },
  { key: 'status', label: 'Status' },
  { key: 'date',   label: 'Date',              cellClass: 'text-gray-500' },
]

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const transfersStore = useTransfersStore()

const activeTab   = ref('all')
const plantCode   = ref('')
const filterFrom  = ref('')
const filterTo    = ref('')

const page = computed({
  get: () => transfersStore.filters.page,
  set: (v) => { transfersStore.filters.page = v },
})
const pendingReceiptsUnread = computed(() => {
  try {
    const raw = localStorage.getItem(`storeops_seen_badges:${authStore.user || 'guest'}`)
    const seen = raw ? JSON.parse(raw) : {}
    return Math.max(0, Number(transfersStore.pendingReceiptsCount || 0) - Number(seen.transfer || 0))
  } catch {
    return Number(transfersStore.pendingReceiptsCount || 0)
  }
})

function markTransferNotificationsSeen() {
  try {
    const key = `storeops_seen_badges:${authStore.user || 'guest'}`
    const raw = localStorage.getItem(key)
    const seen = raw ? JSON.parse(raw) : {}
    seen.transfer = Number(transfersStore.pendingReceiptsCount || 0)
    localStorage.setItem(key, JSON.stringify(seen))
  } catch {
    /* ignore */
  }
}

function tabDef() {
  return statusTabs.find((t) => t.id === activeTab.value)
}

const filteredPendingReceipts = computed(() => {
  let rows = transfersStore.pendingReceipts
  if (authStore.isSuperAdmin && plantCode.value) {
    rows = rows.filter((r) => (r.to_plant_code || r.to_plant) === plantCode.value)
  }
  if (filterFrom.value) rows = rows.filter((r) => !rowDateRaw(r) || rowDateRaw(r) >= filterFrom.value)
  if (filterTo.value)   rows = rows.filter((r) => !rowDateRaw(r) || rowDateRaw(r) <= filterTo.value)
  return rows
})

function rowDateRaw(row) {
  return (row.posting_date || row.transaction_date || '').slice(0, 10)
}

const displayRows = computed(() => {
  if (activeTab.value === 'pending_receipt') {
    const start = (page.value - 1) * PAGE_SIZE
    return filteredPendingReceipts.value.slice(start, start + PAGE_SIZE)
  }
  return transfersStore.transfers
})

const totalForPagination = computed(() => {
  if (activeTab.value === 'pending_receipt') return filteredPendingReceipts.value.length
  return transfersStore.totalCount
})

function itemCount(row) {
  return Number(row.items_count ?? row.total_items ?? row.items?.length ?? 0) || 0
}

function fmtDate(row) {
  const d = row.posting_date || row.transaction_date || row.creation || ''
  return d ? String(d).slice(0, 10) : '—'
}

function goToDetail(row) {
  if (row?.name) router.push({ name: 'TransferDetail', params: { name: row.name } })
}

async function fetchMainTable() {
  if (activeTab.value === 'pending_receipt') {
    await transfersStore.fetchPendingReceipts()
    return
  }
  const tab = tabDef()
  await transfersStore.fetchTransfers({
    status:     tab.apiStatus,
    page:       page.value,
    page_size:  PAGE_SIZE,
    from_date:  filterFrom.value || null,
    to_date:    filterTo.value || null,
    plant_code: authStore.isSuperAdmin ? (plantCode.value || null) : null,
  })
}

function selectTab(id) {
  activeTab.value = id
  transfersStore.filters.page = 1
  fetchMainTable()
}

function setPage(p) {
  page.value = p
  if (activeTab.value !== 'pending_receipt') fetchMainTable()
}

watch([plantCode, filterFrom, filterTo], () => {
  transfersStore.filters.page = 1
  if (activeTab.value !== 'pending_receipt') fetchMainTable()
})

watch(() => route.query.tab, (tab) => {
  if (typeof tab === 'string' && statusTabs.some((t) => t.id === tab)) {
    activeTab.value = tab
    transfersStore.filters.page = 1
    fetchMainTable()
  }
})

onMounted(async () => {
  const tab = typeof route.query.tab === 'string' ? route.query.tab : ''
  if (tab && statusTabs.some((t) => t.id === tab)) activeTab.value = tab
  await transfersStore.fetchPendingReceipts()
  markTransferNotificationsSeen()
  await fetchMainTable()
})
</script>
