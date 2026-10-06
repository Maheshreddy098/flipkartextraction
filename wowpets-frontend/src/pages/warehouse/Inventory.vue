<template>
  <div class="p-6">
    <div class="flex flex-wrap items-center justify-between gap-4 mb-2">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Inventory</h1>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="lastUpdated" class="text-xs text-gray-500">Last fetched: {{ lastUpdated }}</span>
        <button
          type="button"
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
        <button
          type="button"
          @click="handleRefresh"
          :disabled="loading"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 inline-flex items-center gap-2"
        >
          <svg v-if="loading" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div class="flex flex-wrap gap-4 mb-6 items-center">
      <div class="flex items-center gap-2">
        <label for="wh-filter" class="text-sm font-medium text-gray-600 whitespace-nowrap">Warehouse</label>
        <select
          id="wh-filter"
          v-model="warehouseFilter"
          @change="onWarehouseChange"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white min-w-[140px]"
        >
          <option value="">All</option>
          <option value="WO - STR">WO - STR</option>
          <option value="WO -FG">WO -FG</option>
        </select>
      </div>
      <input
        v-model="search"
        @input="debouncedLoad"
        placeholder="Search by item code..."
        class="flex-1 min-w-[200px] max-w-md px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
      />
    </div>

    <DataTable
      :columns="columns"
      :rows="items"
      :total="total"
      :page="page"
      @page-change="p => { page = p; loadInventory() }"
      empty-text="No inventory records"
    >
      <template #cell-available_qty="{ value, row }">
        <span :class="value > 0 ? 'text-green-700 font-medium' : 'text-gray-400'">{{ value }}</span>
      </template>
      <template #cell-allocated_qty="{ value }">
        <span :class="value > 0 ? 'text-purple-700 font-medium' : 'text-gray-400'">{{ value }}</span>
      </template>
      <template #cell-total_qty="{ value }">
        <span class="font-semibold">{{ value }}</span>
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchInventory } from '@/core/api/inventory.js'
import DataTable from '@/components/common/DataTable.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const REFRESH_INTERVAL_MS = 60 * 1000 // 60 seconds – real-time feel without hammering SAP

const notify = useNotificationStore()
const exporting = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const warehouseFilter = ref('') // '' = All, 'WO - STR' | 'WO -FG'
const loading = ref(false)
const lastUpdatedAt = ref(null) // Date of last successful fetch
const lastUpdated = ref('')

const columns = [
  { key: 'item_code', label: 'Item Code' },
  { key: 'item_name', label: 'Item Name' },
  { key: 'warehouse', label: 'Warehouse' },
  { key: 'available_qty', label: 'Available' },
  { key: 'allocated_qty', label: 'Allocated' },
  { key: 'total_qty', label: 'Total' },
]

let debounceTimer = null
let refreshIntervalId = null

async function loadInventory() {
  loading.value = true
  try {
    const params = { page: page.value, search: search.value }
    if (warehouseFilter.value) params.warehouse = warehouseFilter.value
    const res = await fetchInventory(params)
    items.value = res.data || []
    total.value = res.total || 0
    lastUpdatedAt.value = new Date()
    lastUpdated.value = 'just now'
  } catch {
    notify.error('Failed to load inventory')
  } finally {
    loading.value = false
  }
}

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { page.value = 1; loadInventory() }, 300)
}

function handleRefresh() {
  loadInventory()
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999, search: search.value }
    if (warehouseFilter.value) params.warehouse = warehouseFilter.value
    const res = await fetchInventory(params)
    downloadCsv('Inventory', columns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

function onWarehouseChange() {
  page.value = 1
  loadInventory()
}

function updateLastUpdatedLabel() {
  if (!lastUpdatedAt.value) return
  const sec = Math.floor((Date.now() - lastUpdatedAt.value) / 1000)
  if (sec < 10) lastUpdated.value = 'just now'
  else if (sec < 60) lastUpdated.value = `${sec}s ago`
  else lastUpdated.value = `${Math.floor(sec / 60)}m ago`
}

let tickIntervalId = null

onMounted(() => {
  loadInventory()
  refreshIntervalId = setInterval(loadInventory, REFRESH_INTERVAL_MS)
  tickIntervalId = setInterval(updateLastUpdatedLabel, 10000)
})

onUnmounted(() => {
  clearTimeout(debounceTimer)
  if (refreshIntervalId) clearInterval(refreshIntervalId)
  if (tickIntervalId) clearInterval(tickIntervalId)
})
</script>
