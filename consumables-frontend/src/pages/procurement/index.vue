<template>
  <div class="p-4 sm:p-6">
    <!-- Page header -->
    <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">
          {{ isStoreManager && !authStore.isProcurementUser ? 'Goods Receipt (GRN)' : 'Purchase Requests' }}
          <span class="text-sm font-normal text-gray-400">(CPR)</span>
        </h1>
        <p class="mt-0.5 text-xs text-gray-500">
          {{ isStoreManager && !authStore.isProcurementUser ? 'Record goods received against raised purchase orders' : 'Raise purchase orders and record goods receipts in SAP' }}
        </p>
      </div>
    </div>

    <!-- Status tabs -->
    <div class="mb-4 flex gap-2 overflow-x-auto pb-1">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        type="button"
        class="shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm"
        :class="activeStatus === tab.value
          ? 'border-teal-600 bg-teal-600 text-white'
          : 'border-gray-300 bg-white text-gray-700 hover:border-teal-400'"
        @click="setStatus(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {{ error }}
    </div>

    <!-- DataTable -->
    <DataTable
      :columns="columns"
      :rows="items"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      empty-text="No purchase requests found."
      @row-click="(row) => router.push(`/procurement/${row.name}`)"
      @page-change="changePage"
    >
      <template #cell-name="{ value }">
        <span class="font-mono text-xs font-semibold text-gray-900">{{ value }}</span>
      </template>
      <template #cell-cmr_reference="{ value }">
        <span class="font-mono text-xs text-gray-600">{{ value || '—' }}</span>
      </template>
      <template #cell-vendor_code="{ value }">
        <span v-if="value" class="font-mono text-xs">{{ value }}</span>
        <span v-else class="text-gray-400">—</span>
      </template>
      <template #cell-sap_po_doc_num="{ row }">
        <div class="text-xs">
          <span v-if="row.sap_po_doc_num" class="text-green-700">PO# {{ row.sap_po_doc_num }}</span>
          <span v-if="row.sap_grpo_doc_num" class="ml-1 text-blue-700">GRN# {{ row.sap_grpo_doc_num }}</span>
          <span v-if="!row.sap_po_doc_num && !row.sap_grpo_doc_num" class="text-gray-400">—</span>
        </div>
      </template>
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-requested_on="{ value }">
        <span class="text-gray-500">{{ fmtDate(value) }}</span>
      </template>
      <template #actions="{ row }">
        <button
          v-if="row.sap_po_doc_num"
          type="button"
          class="text-xs font-medium text-teal-700 hover:underline"
          @click.stop="downloadPurchaseOrderPdf(row)"
        >PDF</button>
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { StatusBadge, DataTable } from '@/shared/components/index.js'
import { get_purchase_requests, get_purchase_order_pdf_url } from '@/core/api/procurement.js'
import { parseApiError } from '@/utils/error.js'
import { useAuthStore } from '@/stores/auth.js'

const route  = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isStoreManager = computed(() =>
  authStore.consumablesRoles.includes('Consumables Store Manager') ||
  authStore.consumablesRoles.includes('Consumables Inventory Manager')
)

const tabs = [
  { label: 'All',                    value: '' },
  { label: 'Awaiting PO',            value: 'Submitted' },
  { label: 'PO Raised',              value: 'PO Raised' },
  { label: 'Pending GRN',            value: 'Pending GRN' },
  { label: 'Goods Received (GRN)',   value: 'GRN Done' },
  { label: 'Cancelled',              value: 'Cancelled' },
]

const columns = [
  { key: 'name',             label: 'CPR #' },
  { key: 'cmr_reference',    label: 'Source CMR' },
  { key: 'requesting_plant', label: 'Plant' },
  { key: 'vendor_code',      label: 'Vendor' },
  { key: 'sap_po_doc_num',   label: 'PO / GRN #' },
  { key: 'status',           label: 'Status' },
  { key: 'requested_on',     label: 'Date' },
]

const activeStatus = ref(route.query.status || (isStoreManager.value && !authStore.isProcurementUser ? 'PO Raised' : ''))
const items    = ref([])
const total    = ref(0)
const page     = ref(1)
const pageSize = 20
const loading  = ref(false)
const error    = ref('')

function downloadPurchaseOrderPdf(row) {
  if (!row?.name) return
  window.open(get_purchase_order_pdf_url(row.name), '_blank', 'noopener')
}

function fmtDate(val) {
  if (!val) return '—'
  return new Date(val).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: page.value, page_size: pageSize }
    if (activeStatus.value) params.status = activeStatus.value
    const res  = await get_purchase_requests(params)
    const data = res?.message ?? res ?? {}
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    error.value = parseApiError(e, 'Failed to load purchase requests.')
  } finally {
    loading.value = false
  }
}

function setStatus(val) {
  activeStatus.value = val
  page.value = 1
  router.replace({ query: val ? { status: val } : {} })
}

function changePage(p) {
  page.value = p
  load()
}

watch(activeStatus, load)
onMounted(load)
</script>
