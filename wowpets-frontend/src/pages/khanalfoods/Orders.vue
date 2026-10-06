<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">FBA Transfers</h1>
      <div class="flex items-center gap-2">
        <button
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
        <router-link
          v-if="isKhanalFoods"
          :to="newPath"
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >+ New FBA Transfer</router-link>
      </div>
    </div>

    <div class="flex gap-2 mb-4">
      <button
        v-for="f in statusFilters"
        :key="f.value"
        @click="currentFilter = f.value"
        :class="currentFilter === f.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border'"
        class="px-3 py-1.5 text-sm rounded-lg transition"
      >{{ f.label }}</button>
    </div>

    <DataTable
      :columns="visibleColumns"
      :rows="orders"
      :total="total"
      :page="page"
      @row-click="viewOrder"
      @page-change="changePage"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="isKhanalFoods ? value : (value === 'Sent to SAP' ? 'Completed' : value)" />
      </template>
      <template v-if="isKhanalFoods" #cell-sap_request_doc_entry="{ value }">
        <span v-if="value" class="text-amber-700 text-xs font-medium">Req # {{ value }}</span>
        <span v-else class="text-gray-400">—</span>
      </template>
      <template v-if="isKhanalFoods" #cell-sap_doc_entry="{ value }">
        <span v-if="value" class="text-green-600 text-xs font-medium">TR # {{ value }}</span>
        <span v-else class="text-gray-400">—</span>
      </template>
      <template v-if="isKhanalFoods" #actions="{ row }">
        <div class="flex gap-2">
          <button
            v-if="row.status === 'Draft'"
            @click.stop="submitForApproval(row.name)"
            class="text-xs text-blue-600 hover:underline"
          >Submit</button>
          <button
            v-if="row.status === 'Pending Approval' && isManager"
            @click.stop="openApproveDialog(row)"
            class="text-xs text-green-600 hover:underline"
          >Approve</button>
          <button
            v-if="row.status === 'Pending Approval' && isManager"
            @click.stop="openRejectDialog(row)"
            class="text-xs text-red-600 hover:underline"
          >Reject</button>
        </div>
      </template>
    </DataTable>

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve FBA Transfer"
      :message="`Approve ${selectedRow?.fba_transfer_name || selectedRow?.name || ''}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject FBA Transfer"
      :message="`Reject ${selectedRow?.fba_transfer_name || selectedRow?.name || ''}? Provide a reason:`"
      confirm-text="Reject"
      variant="danger"
      show-input
      input-placeholder="Reason for rejection"
      @confirm="handleReject"
      @cancel="showRejectDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  fetchOrders,
  submitOrder,
  approveOrder,
  rejectOrder,
} from '@/core/api/orders.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const router = useRouter()
const session = useSessionStore()
const notify = useNotificationStore()

const isKhanalFoods = computed(() => session.team === 'khanalfoods')
const isManager = session.isManager
const orders = ref([])
const total = ref(0)
const page = ref(1)
const currentFilter = ref('')

const newPath = computed(() => (isKhanalFoods.value ? '/khanalfoods/orders/new' : '#'))
const listPath = computed(() => (session.team === 'khanalfoods' ? '/khanalfoods/orders' : '/warehouse/orders'))

const statusFilters = computed(() => {
  const base = [
    { label: 'All', value: '' },
    { label: 'Draft', value: 'Draft' },
    { label: 'Pending Approval', value: 'Pending Approval' },
    { label: 'Approved', value: 'Approved' },
    { label: 'Accepted', value: 'Accepted' },
    { label: 'Packaging', value: 'Packaging' },
    { label: 'Dispatched', value: 'Dispatched' },
    { label: 'Sent to SAP', value: 'Sent to SAP' },
    { label: 'Error', value: 'Error' },
  ]
  if (session.team === 'warehouse') {
    // Warehouse: Draft/Pending Approval hidden
    return base.filter((f) => !['Draft', 'Pending Approval', 'Sent to SAP'].includes(f.value))
  }
  return base
})

const columns = [
  { key: 'fba_transfer_name', label: 'Transfer Name' },
  { key: 'name', label: 'FBA Transfer #' },
  { key: 'doc_date', label: 'Date' },
  { key: 'to_warehouse', label: 'To Warehouse' },
  { key: 'status', label: 'Status' },
  { key: 'sap_request_doc_entry', label: 'SAP Request' },
  { key: 'sap_doc_entry', label: 'SAP Transfer' },
]

// Warehouse team should not see the SAP columns; KhanalFoods sees them.
const visibleColumns = computed(() =>
  session.team === 'warehouse'
    ? columns.filter((c) => !['sap_request_doc_entry', 'sap_doc_entry'].includes(c.key))
    : columns
)

const exporting = ref(false)
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const selectedRow = ref(null)

async function loadOrders() {
  try {
    const params = { page: page.value }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchOrders(params)
    orders.value = res.data || []
    total.value = res.total || 0
  } catch {
    notify.error('Failed to load orders')
  }
}

function viewOrder(row) {
  if (session.team === 'khanalfoods') {
    router.push(`/khanalfoods/orders/${row.name}`)
  } else {
    router.push(`/warehouse/orders/${row.name}`)
  }
}

function changePage(p) {
  page.value = p
}

async function submitForApproval(name) {
  try {
    await submitOrder(name)
    notify.success('FBA Transfer submitted for approval')
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to submit')
  }
}

function openApproveDialog(row) {
  selectedRow.value = row
  showApproveDialog.value = true
}
function openRejectDialog(row) {
  selectedRow.value = row
  showRejectDialog.value = true
}

async function handleApprove() {
  try {
    await approveOrder(selectedRow.value.name)
    notify.success('FBA Transfer approved')
    showApproveDialog.value = false
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to approve')
  }
}

async function handleReject(reason) {
  try {
    await rejectOrder(selectedRow.value.name, reason)
    notify.success('FBA Transfer rejected')
    showRejectDialog.value = false
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to reject')
  }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchOrders(params)
    const exportColumns = [
      { key: 'fba_transfer_name', label: 'Transfer Name' },
      { key: 'name', label: 'FBA Transfer #' },
      { key: 'doc_date', label: 'Date' },
      { key: 'to_warehouse', label: 'To Warehouse' },
      { key: 'status', label: 'Status' },
      { key: 'accepted_by', label: 'Accepted By' },
      { key: 'comments', label: 'Comments' },
      { key: 'modified', label: 'Last Modified' },
      ...(isKhanalFoods.value
        ? [
            { key: 'sap_request_doc_entry', label: 'SAP Request #' },
            { key: 'sap_doc_entry', label: 'SAP Transfer #' },
            { key: 'sap_doc_num', label: 'SAP Doc #' },
            { key: 'sap_sync_error', label: 'SAP Error' },
          ]
        : []),
    ]
    downloadCsv('FBA_Transfers', exportColumns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch(currentFilter, () => {
  page.value = 1
  loadOrders()
})
onMounted(loadOrders)
</script>
