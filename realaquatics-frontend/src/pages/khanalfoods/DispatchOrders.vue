<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Dispatch Orders</h1>
      <div class="flex items-center gap-2">
        <button
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
        <router-link
          v-if="isKhanalFoods"
          to="/khanalfoods/dispatch-orders/new"
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >+ New Dispatch Order</router-link>
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
        <StatusBadge :status="value" />
      </template>
      <template v-if="isKhanalFoods" #cell-sap_doc_num="{ row }">
        <div class="flex flex-col text-xs">
          <span v-if="row.sap_doc_num" class="text-green-600 font-medium">SO # {{ row.sap_doc_num }}</span>
          <span v-if="row.sap_delivery_doc_num" class="text-green-600 font-medium">DN # {{ row.sap_delivery_doc_num }}</span>
          <span v-if="row.sap_invoice_doc_num" class="text-green-600 font-medium">AR # {{ row.sap_invoice_doc_num }}</span>
          <span v-if="!row.sap_doc_num && !row.sap_delivery_doc_num && !row.sap_invoice_doc_num" class="text-gray-400">—</span>
        </div>
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
          <button
            v-if="row.status === 'Error' && isManager"
            @click.stop="retrySap(row.name)"
            class="text-xs text-amber-600 hover:underline"
          >Retry SAP</button>
        </div>
      </template>
    </DataTable>

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Dispatch Order"
      :message="`Approve ${selectedRow?.name || ''}? Warehouse will create the Sales Order in SAP when they accept.`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Dispatch Order"
      :message="`Reject ${selectedRow?.name || ''}? Provide a reason:`"
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
  fetchDispatchOrders,
  submitDispatchOrder,
  approveDispatchOrder,
  rejectDispatchOrder,
  retryDispatchOrderSap,
} from '@/core/api/dispatchOrders.js'
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

const statusFilters = computed(() => {
  const base = [
    { label: 'All', value: '' },
    { label: 'Draft', value: 'Draft' },
    { label: 'Pending Approval', value: 'Pending Approval' },
    { label: 'Approved', value: 'Approved' },
    { label: 'Accepted', value: 'Accepted' },
    { label: 'In Preparation', value: 'In Preparation' },
    { label: 'Dispatched', value: 'Dispatched' },
    { label: 'Error', value: 'Error' },
  ]
  if (session.team === 'warehouse') {
    // Warehouse should not see Draft/Pending Approval, but can see Error to know something failed.
    return base.filter((f) => !['Draft', 'Pending Approval'].includes(f.value))
  }
  return base
})

const columns = [
  { key: 'dispatch_order_name', label: 'Dispatch Order Name' },
  { key: 'name', label: 'Dispatch #' },
  { key: 'card_code', label: 'Customer' },
  { key: 'card_name', label: 'Customer Name' },
  { key: 'doc_date', label: 'Date' },
  { key: 'status', label: 'Status' },
  { key: 'sap_doc_num', label: 'SAP Docs' },
]

const visibleColumns = computed(() =>
  session.team === 'warehouse'
    ? columns.filter((c) => c.key !== 'sap_doc_num')
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
    const res = await fetchDispatchOrders(params)
    orders.value = res.data || []
    total.value = res.total || 0
  } catch {
    notify.error('Failed to load dispatch orders')
  }
}

function viewOrder(row) {
  if (session.team === 'khanalfoods') {
    router.push(`/khanalfoods/dispatch-orders/${row.name}`)
  } else {
    router.push(`/warehouse/dispatch-orders/${row.name}`)
  }
}

function changePage(p) {
  page.value = p
}

async function submitForApproval(name) {
  try {
    await submitDispatchOrder(name)
    notify.success('Dispatch order submitted for approval')
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
    await approveDispatchOrder(selectedRow.value.name)
    notify.success('Dispatch order approved – ready for warehouse to accept')
    showApproveDialog.value = false
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to approve')
  }
}

async function handleReject(reason) {
  try {
    await rejectDispatchOrder(selectedRow.value.name, reason)
    notify.success('Dispatch order rejected')
    showRejectDialog.value = false
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to reject')
  }
}

async function retrySap(name) {
  try {
    await retryDispatchOrderSap(name)
    notify.success('Sales Order posted — warehouse can start preparation.')
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to retry SAP')
  }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchDispatchOrders(params)
    const exportColumns = [
      { key: 'dispatch_order_name', label: 'Dispatch Order Name' },
      { key: 'name', label: 'Dispatch #' },
      { key: 'card_code', label: 'Customer Code' },
      { key: 'card_name', label: 'Customer Name' },
      { key: 'doc_date', label: 'Date' },
      { key: 'doc_due_date', label: 'Due Date' },
      { key: 'mobile_number', label: 'Mobile' },
      { key: 'num_at_card', label: 'Ref #' },
      { key: 'ship_to_code', label: 'Ship To Code' },
      { key: 'bill_to_code', label: 'Bill To Code' },
      { key: 'status', label: 'Status' },
      { key: 'accepted_by', label: 'Accepted By' },
      { key: 'dispatched_at', label: 'Dispatched At' },
      { key: 'comments', label: 'Comments' },
      { key: 'modified', label: 'Last Modified' },
      ...(session.team !== 'warehouse'
        ? [
            { key: 'approved_by', label: 'Approved By' },
            { key: 'sap_doc_entry', label: 'SAP SO Entry' },
            { key: 'sap_doc_num', label: 'SAP SO#' },
            { key: 'sap_delivery_doc_num', label: 'SAP DN#' },
            { key: 'sap_invoice_doc_num', label: 'SAP AR#' },
            { key: 'sap_sync_error', label: 'SAP Error' },
          ]
        : []),
    ]
    downloadCsv('Dispatch_Orders', exportColumns, res.data || [])
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
