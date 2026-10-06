<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Sales Dashboard</h1>
      <button
        @click="refreshAll"
        :disabled="isLoading"
        class="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ isLoading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>
    <p class="text-gray-600 mb-6">KPIs, interactive charts, and customer-wise sales table. Use filters and click Apply.</p>

    <!-- Filters -->
    <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
      <h3 class="text-sm font-semibold text-gray-900 mb-3">Date range & customer group</h3>
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label class="block text-xs font-semibold text-gray-600 mb-1">From date</label>
          <input
            v-model="fromDate"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 mb-1">To date</label>
          <input
            v-model="toDate"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 mb-1">Customer group</label>
          <select
            v-model="custGroup"
            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="Domestic E-com Customer">Domestic E-com Customer</option>
            <option value="Export HN Customer">Export HN Customer</option>
          </select>
        </div>
        <div class="flex items-end">
          <button
            @click="refreshAll"
            :disabled="isLoading"
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Apply
          </button>
        </div>
      </div>
    </div>

    <div v-if="errorMessage" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ errorMessage }}</p>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">No. of Sales Orders</p>
        <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(salesCount) }}</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Sales</p>
        <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatCurrency(salesTotal) }}</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Open SO</p>
        <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(openSalesCount) }}</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-500 font-semibold">Open SO (Value)</p>
        <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatCurrency(openSalesTotal) }}</p>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Top 10 Customers by Revenue (Inv − CN)</h3>
        <div class="relative h-72">
          <canvas ref="topCustomersRevenueChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Hover for values. Revenue = Invoice Total − Credit Notes.</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Revenue vs Collections vs Outstanding</h3>
        <div class="relative h-72">
          <canvas ref="revenueMixChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Click legend to toggle segments.</p>
      </div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Top 10 Customers by Closing Balance</h3>
        <div class="relative h-72">
          <canvas ref="topCustomersBalanceChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Highest outstanding dues.</p>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <h3 class="text-base font-semibold text-gray-900 mb-3">Invoice Total vs Collections (Top 8)</h3>
        <div class="relative h-72">
          <canvas ref="invoiceVsCollectionsChartEl"></canvas>
        </div>
        <p class="text-xs text-gray-500 mt-2">Billed vs collected.</p>
      </div>
    </div>

    <!-- Customer table -->
    <div class="bg-white border rounded-lg shadow-sm p-4">
      <h3 class="text-base font-semibold text-gray-900 mb-3">Customer-wise Sales</h3>
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Customer</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Opening Bal.</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Invoice Total</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Returns</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Revenue</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Collections</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Deductions</th>
              <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Closing Bal.</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="r in salesTableData" :key="r.sap_customer_code || r.customer" class="hover:bg-gray-50">
              <td class="px-3 py-2">
                <div class="font-semibold text-gray-900">{{ r.sap_customer_code || r.customer }}</div>
                <div class="text-xs text-gray-600">{{ r.customer }}</div>
              </td>
              <td class="px-3 py-2 text-right">{{ formatIndianNumber(r.opening_balance, false) }}</td>
              <td class="px-3 py-2 text-right">{{ formatIndianNumber(r.total_invoice, false) }}</td>
              <td class="px-3 py-2 text-right">{{ formatIndianNumber(r.total_credit_note, false) }}</td>
              <td class="px-3 py-2 text-right font-medium">{{ formatIndianNumber((r.total_invoice || 0) - (r.total_credit_note || 0), false) }}</td>
              <td class="px-3 py-2 text-right">{{ formatIndianNumber(r.collections, false) }}</td>
              <td class="px-3 py-2 text-right">{{ formatIndianNumber(r.deductions, false) }}</td>
              <td class="px-3 py-2 text-right font-medium">{{ formatIndianNumber(r.closing_balance, false) }}</td>
            </tr>
            <tr v-if="!isLoading && salesTableData.length === 0">
              <td colspan="8" class="px-3 py-6 text-center text-gray-600">No data. Adjust filters and Apply.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
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

const fromDate = ref('2024-01-01')
const toDate = ref('2024-01-31')
const custGroup = ref('Domestic E-com Customer')

const salesCountRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.SALES_DASHBOARD.SALES_ORDER_COUNT,
  method: 'GET',
  makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const salesTotalRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.SALES_DASHBOARD.TOTAL_SALES_ORDER,
  method: 'GET',
  makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const openSalesCountRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.SALES_DASHBOARD.OPEN_SALES_ORDER,
  method: 'GET',
  makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const openSalesTotalRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.SALES_DASHBOARD.TOTAL_SALES_ORDER_OPEN,
  method: 'GET',
  makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const salesTableRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.SALES_DASHBOARD.PREPARE_SALES_TABLE,
  method: 'GET',
  makeParams: () => ({ cust_group: custGroup.value, from_date: fromDate.value, to_date: toDate.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const isLoading = computed(() =>
  salesCountRes.loading ||
  salesTotalRes.loading ||
  openSalesCountRes.loading ||
  openSalesTotalRes.loading ||
  salesTableRes.loading
)

const errorMessage = computed(() => {
  const err =
    salesCountRes.error || salesCountRes.data?.error ||
    salesTotalRes.error || salesTotalRes.data?.error ||
    openSalesCountRes.error || openSalesCountRes.data?.error ||
    openSalesTotalRes.error || openSalesTotalRes.data?.error ||
    salesTableRes.error || salesTableRes.data?.error
  return err ? String(err?.message || err) : ''
})

const salesCount = computed(() => salesCountRes.data?.value ?? 0)
const salesTotal = computed(() => salesTotalRes.data?.value ?? 0)
const openSalesCount = computed(() => openSalesCountRes.data?.value ?? 0)
const openSalesTotal = computed(() => openSalesTotalRes.data?.value ?? 0)
const salesTableData = computed(() => (Array.isArray(salesTableRes.data) ? salesTableRes.data : []))

const topCustomersRevenueChartEl = ref(null)
const revenueMixChartEl = ref(null)
const topCustomersBalanceChartEl = ref(null)
const invoiceVsCollectionsChartEl = ref(null)
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
function formatIndianNumber(value, includeDecimals = true) {
  if (value === null || value === undefined) return ''
  const x = String(value).split('.')
  let lastThree = x[0].substring(x[0].length - 3)
  const otherNumbers = x[0].substring(0, x[0].length - 3)
  if (otherNumbers !== '') lastThree = ',' + lastThree
  const formattedNumber = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree
  return includeDecimals && x.length > 1 ? formattedNumber + '.' + x[1] : formattedNumber
}

function getRevenue(row) {
  return Number(row.total_invoice || 0) - Number(row.total_credit_note || 0)
}

function destroyCharts() {
  chartInstances.forEach(ch => { if (ch) ch.destroy() })
  chartInstances = []
}

function buildCharts() {
  const data = salesTableData.value
  destroyCharts()
  if (!data.length) return

  const revenueSorted = [...data].sort((a, b) => getRevenue(b) - getRevenue(a)).slice(0, 10)
  const balanceSorted = [...data].sort((a, b) => Number(b.closing_balance || 0) - Number(a.closing_balance || 0)).slice(0, 10)

  if (topCustomersRevenueChartEl.value) {
    const ch = new Chart(topCustomersRevenueChartEl.value.getContext('2d'), {
      type: 'bar',
      data: {
        labels: revenueSorted.map(r => (r.sap_customer_code || r.customer || '').slice(0, 12)),
        datasets: [{ label: 'Revenue (₹)', data: revenueSorted.map(r => getRevenue(r)), backgroundColor: 'rgba(59, 130, 246, 0.7)', borderColor: 'rgb(59, 130, 246)', borderWidth: 1 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { callback: v => '₹' + (v / 1e5).toFixed(1) + 'L' } }, x: { ticks: { maxRotation: 45 } } } }
    })
    chartInstances.push(ch)
  }

  const totalRevenue = data.reduce((s, r) => s + getRevenue(r), 0)
  const totalCollections = data.reduce((s, r) => s + Number(r.collections || 0), 0)
  const totalClosing = data.reduce((s, r) => s + Number(r.closing_balance || 0), 0)
  if (revenueMixChartEl.value) {
    const ch = new Chart(revenueMixChartEl.value.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['Revenue (Inv − CN)', 'Collections', 'Outstanding'],
        datasets: [{ data: [totalRevenue, totalCollections, totalClosing], backgroundColor: ['rgba(34, 197, 94, 0.8)', 'rgba(59, 130, 246, 0.8)', 'rgba(239, 68, 68, 0.8)'], borderWidth: 2 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    })
    chartInstances.push(ch)
  }

  if (topCustomersBalanceChartEl.value) {
    const ch = new Chart(topCustomersBalanceChartEl.value.getContext('2d'), {
      type: 'bar',
      data: {
        labels: balanceSorted.map(r => (r.sap_customer_code || r.customer || '').slice(0, 12)),
        datasets: [{ label: 'Closing Balance (₹)', data: balanceSorted.map(r => Number(r.closing_balance || 0)), backgroundColor: 'rgba(239, 68, 68, 0.7)', borderWidth: 1 }]
      },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { callback: v => '₹' + (v / 1e5).toFixed(1) + 'L' } } } }
    })
    chartInstances.push(ch)
  }

  const top8 = [...data].sort((a, b) => getRevenue(b) - getRevenue(a)).slice(0, 8)
  if (invoiceVsCollectionsChartEl.value) {
    const ch = new Chart(invoiceVsCollectionsChartEl.value.getContext('2d'), {
      type: 'bar',
      data: {
        labels: top8.map(r => (r.sap_customer_code || r.customer || '').slice(0, 10)),
        datasets: [
          { label: 'Invoice Total', data: top8.map(r => Number(r.total_invoice || 0)), backgroundColor: 'rgba(99, 102, 241, 0.7)' },
          { label: 'Collections', data: top8.map(r => Number(r.collections || 0)), backgroundColor: 'rgba(34, 197, 94, 0.7)' }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true }, x: { ticks: { maxRotation: 45 } } } }
    })
    chartInstances.push(ch)
  }
}

async function refreshAll() {
  await Promise.all([
    salesCountRes.fetch(),
    salesTotalRes.fetch(),
    openSalesCountRes.fetch(),
    openSalesTotalRes.fetch(),
    salesTableRes.fetch()
  ])
  await nextTick()
  buildCharts()
}

watch(salesTableData, () => nextTick(buildCharts), { deep: true })

onMounted(() => {
  refreshAll()
})
</script>
