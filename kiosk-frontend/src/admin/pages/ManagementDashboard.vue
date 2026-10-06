<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Management Dashboard</h1>
      <button
        @click="refreshAll"
        :disabled="isLoading"
        class="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ isLoading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>
    <p class="text-gray-600 mb-6">High-level KPIs and interactive charts for sales, inventory, and operations.</p>

    <div v-if="errorMessage" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ errorMessage }}</p>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4 mb-8">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">SKUs with Stock</p>
        <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(inventoryMetrics.total_skus_with_stock) }}</p>
        <p class="text-xs text-gray-500 mt-1">Inventory</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">On-Hand Qty</p>
        <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(inventoryMetrics.total_onhand_qty) }}</p>
        <p class="text-xs text-gray-500 mt-1">Inventory</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Stock Value</p>
        <p class="mt-2 text-2xl font-bold text-emerald-700">{{ formatCurrency(inventoryMetrics.total_stock_value) }}</p>
        <p class="text-xs text-gray-500 mt-1">Inventory</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Sales Orders</p>
        <p class="mt-2 text-2xl font-bold text-blue-700">{{ formatInt(salesCount) }}</p>
        <p class="text-xs text-gray-500 mt-1">Sales (period)</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Sales Value</p>
        <p class="mt-2 text-2xl font-bold text-blue-700">{{ formatCurrency(salesTotal) }}</p>
        <p class="text-xs text-gray-500 mt-1">Sales (period)</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Open SO (Value)</p>
        <p class="mt-2 text-2xl font-bold text-amber-700">{{ formatCurrency(openSalesTotal) }}</p>
        <p class="text-xs text-gray-500 mt-1">Sales</p>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Stock Value by Warehouse</h3>
        <div class="relative h-72">
          <canvas ref="warehouseValueChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Click legend to toggle warehouses. Hover for values.</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Warehouse Comparison (SKUs vs Value)</h3>
        <div class="relative h-72">
          <canvas ref="warehouseComparisonChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Dual axis: SKU count and stock value by warehouse.</p>
      </div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">On-Hand Quantity by Warehouse</h3>
        <div class="relative h-72">
          <canvas ref="warehouseQtyChartEl"></canvas>
        </div>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Sales vs Open Orders (Value)</h3>
        <div class="relative h-72">
          <canvas ref="salesVsOpenChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Period: last 30 days. Sales = closed orders; Open = open SO value.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { createResource } from 'frappe-ui'
import { Chart, registerables } from 'chart.js'
import { APP_CONFIG } from '@/config/constants.js'

Chart.register(...registerables)

function unwrapFrappeResponse(data) {
  if (data?.message) return data.message
  if (data?.data?.message) return data.data.message
  if (data?.data) return data.data
  return data
}

function defaultDateRange() {
  const end = new Date()
  const start = new Date(end)
  start.setDate(start.getDate() - 30)
  return {
    from_date: start.toISOString().slice(0, 10),
    to_date: end.toISOString().slice(0, 10)
  }
}

const range = defaultDateRange()

const inventorySummaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.MANAGEMENT_DASHBOARD.GET_INVENTORY_SUMMARY,
  method: 'GET',
  makeParams: () => ({ filters: JSON.stringify({}) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const warehouseRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.MANAGEMENT_DASHBOARD.GET_WAREHOUSE_BREAKDOWN,
  method: 'GET',
  makeParams: () => ({ filters: JSON.stringify({}) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const salesCountRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.MANAGEMENT_DASHBOARD.SALES_ORDER_COUNT,
  method: 'GET',
  makeParams: () => ({ from_date: range.from_date, to_date: range.to_date }),
  auto: false,
  transform: unwrapFrappeResponse
})

const salesTotalRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.MANAGEMENT_DASHBOARD.TOTAL_SALES_ORDER,
  method: 'GET',
  makeParams: () => ({ from_date: range.from_date, to_date: range.to_date }),
  auto: false,
  transform: unwrapFrappeResponse
})

const openSalesCountRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.MANAGEMENT_DASHBOARD.OPEN_SALES_ORDER,
  method: 'GET',
  makeParams: () => ({ from_date: range.from_date, to_date: range.to_date }),
  auto: false,
  transform: unwrapFrappeResponse
})

const openSalesTotalRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.MANAGEMENT_DASHBOARD.TOTAL_SALES_ORDER_OPEN,
  method: 'GET',
  makeParams: () => ({ from_date: range.from_date, to_date: range.to_date }),
  auto: false,
  transform: unwrapFrappeResponse
})

const isLoading = computed(() =>
  inventorySummaryRes.loading ||
  warehouseRes.loading ||
  salesCountRes.loading ||
  salesTotalRes.loading ||
  openSalesCountRes.loading ||
  openSalesTotalRes.loading
)

const errorMessage = computed(() => {
  const err =
    inventorySummaryRes.error || inventorySummaryRes.data?.error ||
    warehouseRes.error || warehouseRes.data?.error ||
    salesCountRes.error || salesCountRes.data?.error ||
    salesTotalRes.error || salesTotalRes.data?.error ||
    openSalesCountRes.error || openSalesCountRes.data?.error ||
    openSalesTotalRes.error || openSalesTotalRes.data?.error
  return err ? String(err?.message || err) : ''
})

const inventoryMetrics = computed(() => inventorySummaryRes.data?.metrics || {})

const warehouses = computed(() => warehouseRes.data?.warehouses || [])

const salesCount = computed(() => salesCountRes.data?.value ?? 0)
const salesTotal = computed(() => salesTotalRes.data?.value ?? 0)
const openSalesTotal = computed(() => openSalesTotalRes.data?.value ?? 0)

const warehouseValueChartEl = ref(null)
const warehouseComparisonChartEl = ref(null)
const warehouseQtyChartEl = ref(null)
const salesVsOpenChartEl = ref(null)
let chartInstances = []

const numberFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })
const intFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const currencyFmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })

function formatNumber(v) {
  return numberFmt.format(Number(v || 0))
}
function formatInt(v) {
  return intFmt.format(Number(v || 0))
}
function formatCurrency(v) {
  return currencyFmt.format(Number(v || 0))
}

function destroyCharts() {
  chartInstances.forEach(ch => { if (ch) ch.destroy() })
  chartInstances = []
}

function buildCharts() {
  destroyCharts()
  const whs = warehouses.value
  if (!whs.length && !salesCountRes.data) return

  if (warehouseValueChartEl.value && whs.length) {
    const ctx = warehouseValueChartEl.value.getContext('2d')
    const colors = whs.map((_, i) => {
      const hue = (i * 47) % 360
      return `hsla(${hue}, 70%, 55%, 0.85)`
    })
    const ch = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: whs.map(w => w.whscode),
        datasets: [{ data: whs.map(w => w.stock_value || 0), backgroundColor: colors, borderWidth: 2 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
      }
    })
    chartInstances.push(ch)
  }

  if (warehouseComparisonChartEl.value && whs.length) {
    const ctx = warehouseComparisonChartEl.value.getContext('2d')
    const ch = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: whs.map(w => w.whscode),
        datasets: [
          { label: 'SKU Count', data: whs.map(w => w.sku_count || 0), backgroundColor: 'rgba(59, 130, 246, 0.7)', yAxisID: 'y' },
          { label: 'Stock Value (₹)', data: whs.map(w => w.stock_value || 0), backgroundColor: 'rgba(34, 197, 94, 0.7)', yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: {
          y: { type: 'linear', position: 'left', beginAtZero: true },
          y1: { type: 'linear', position: 'right', beginAtZero: true, grid: { drawOnChartArea: false } }
        }
      }
    })
    chartInstances.push(ch)
  }

  if (warehouseQtyChartEl.value && whs.length) {
    const ctx = warehouseQtyChartEl.value.getContext('2d')
    const ch = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: whs.map(w => w.whscode),
        datasets: [{ label: 'On-Hand Qty', data: whs.map(w => w.onhand_qty || 0), backgroundColor: 'rgba(99, 102, 241, 0.7)' }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    })
    chartInstances.push(ch)
  }

  if (salesVsOpenChartEl.value) {
    const ctx = salesVsOpenChartEl.value.getContext('2d')
    const ch = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Sales (Closed)', 'Open SO'],
        datasets: [{
          label: 'Value (₹)',
          data: [Number(salesTotalRes.data?.value || 0), Number(openSalesTotalRes.data?.value || 0)],
          backgroundColor: ['rgba(34, 197, 94, 0.8)', 'rgba(245, 158, 11, 0.8)']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    })
    chartInstances.push(ch)
  }
}

async function refreshAll() {
  await Promise.all([
    inventorySummaryRes.fetch(),
    warehouseRes.fetch(),
    salesCountRes.fetch(),
    salesTotalRes.fetch(),
    openSalesCountRes.fetch(),
    openSalesTotalRes.fetch()
  ])
  await nextTick()
  buildCharts()
}

onMounted(() => {
  refreshAll()
})
</script>
