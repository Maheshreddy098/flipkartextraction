<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Purchase Orders</h1>
      <div class="flex items-center gap-2">
        <button
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
        <router-link
          v-if="session.isProcurement"
          to="/khanalfoods/purchase-orders/new"
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >+ New PO</router-link>
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
      :columns="columns"
      :rows="orders"
      :total="total"
      :page="page"
      @row-click="viewOrder"
      @page-change="changePage"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-sap="{ row }">
        <span v-if="!['Approved', 'Accepted', 'Received'].includes(row.status)" class="text-gray-400">—</span>
        <span v-else-if="row.sap_po_doc_entry || row.sap_grpo_doc_entry || row.sap_inventory_transfer_doc_entry" class="text-green-600 text-xs font-medium">Sent to SAP</span>
        <span v-else-if="row.sap_sync_status === 'Error'" class="text-red-600 text-xs font-medium">SAP Error</span>
        <span v-else class="text-amber-600 text-xs">Not sent</span>
      </template>
      <template #cell-total_accepted_qty="{ value }">
        <span v-if="value != null && value !== ''" class="tabular-nums">{{ value }}</span>
        <span v-else class="text-gray-400">—</span>
      </template>
      <template #actions="{ row }">
        <div class="flex gap-2">
          <button
            v-if="row.status === 'Draft' && session.isProcurement"
            @click.stop="submitForApproval(row.name)"
            class="text-xs text-blue-600 hover:underline"
          >Submit</button>
          <button
            v-if="row.status === 'Pending Approval' && session.isProcurementManager"
            @click.stop="openApproveDialog(row)"
            class="text-xs text-green-600 hover:underline"
          >Approve</button>
          <button
            v-if="row.status === 'Pending Approval' && session.isProcurementManager"
            @click.stop="openRejectDialog(row)"
            class="text-xs text-red-600 hover:underline"
          >Reject</button>
        </div>
      </template>
    </DataTable>

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Purchase Order"
      :message="`Approve ${selectedRow?.purchase_order_name || selectedRow?.name || ''}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Purchase Order"
      :message="`Reject ${selectedRow?.purchase_order_name || selectedRow?.name || ''}? Provide a reason:`"
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
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchPurchaseOrders, submitPOForApproval, approvePO, rejectPO } from '@/core/api/purchaseOrders.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const router = useRouter()
const session = useSessionStore()
const notify = useNotificationStore()

const orders = ref([])
const total = ref(0)
const page = ref(1)
const currentFilter = ref('')

const statusFilters = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'Draft' },
  { label: 'Pending Approval', value: 'Pending Approval' },
  { label: 'Approved', value: 'Approved' },
  { label: 'Received', value: 'Received' },
]

const columns = [
  { key: 'purchase_order_name', label: 'Order Name' },
  { key: 'name', label: 'PO #' },
  { key: 'supplier_name', label: 'Supplier' },
  { key: 'status', label: 'Status' },
  { key: 'sap', label: 'SAP' },
  { key: 'total_qty', label: 'Total Qty' },
  { key: 'total_accepted_qty', label: 'Accepted Qty' },
  { key: 'total_amount', label: 'Total Amount' },
  { key: 'posting_date', label: 'Date' },
]

const exporting = ref(false)
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const selectedPO = ref('')
const selectedRow = ref(null)

async function loadOrders() {
  try {
    const params = { page: page.value }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchPurchaseOrders(params)
    orders.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load purchase orders') }
}

function viewOrder(row) {
  router.push(`/khanalfoods/purchase-orders/${row.name}`)
}

function changePage(p) { page.value = p }

async function submitForApproval(name) {
  try {
    await submitPOForApproval(name)
    notify.success('PO submitted for approval')
    loadOrders()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed to submit') }
}

function openApproveDialog(row) {
  selectedRow.value = row
  selectedPO.value = row.name
  showApproveDialog.value = true
}
function openRejectDialog(row) {
  selectedRow.value = row
  selectedPO.value = row.name
  showRejectDialog.value = true
}

async function handleApprove() {
  try {
    await approvePO(selectedPO.value)
    notify.success('PO approved')
    showApproveDialog.value = false
    loadOrders()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed to approve') }
}

async function handleReject(reason) {
  try {
    await rejectPO(selectedPO.value, reason)
    notify.success('PO rejected')
    showRejectDialog.value = false
    loadOrders()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed to reject') }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchPurchaseOrders(params)
    const exportColumns = [
      { key: 'purchase_order_name', label: 'Order Name' },
      { key: 'name', label: 'PO #' },
      { key: 'supplier_name', label: 'Supplier' },
      { key: 'vendor_code', label: 'Vendor Code' },
      { key: 'vendor_name', label: 'Vendor Name' },
      { key: 'vendor_ref_no', label: 'Vendor Ref #' },
      { key: 'posting_date', label: 'Date' },
      { key: 'status', label: 'Status' },
      { key: 'total_qty', label: 'Total Qty' },
      { key: 'total_accepted_qty', label: 'Accepted Qty' },
      { key: 'total_amount', label: 'Total Amount' },
      { key: 'remarks', label: 'Remarks' },
      { key: 'created_by_user', label: 'Created By' },
      { key: 'approved_by', label: 'Approved By' },
      { key: 'accepted_by', label: 'Accepted By' },
      { key: 'sap_sync_status', label: 'SAP Sync Status' },
      { key: 'sap_po_doc_entry', label: 'SAP PO Entry' },
      { key: 'sap_po_doc_num', label: 'SAP PO#' },
      { key: 'sap_grpo_doc_entry', label: 'SAP GRPO Entry' },
      { key: 'sap_grpo_doc_num', label: 'SAP GRPO#' },
      { key: 'sap_inventory_transfer_doc_entry', label: 'SAP IT Entry' },
      { key: 'modified', label: 'Last Modified' },
    ]
    downloadCsv('Purchase_Orders', exportColumns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch(currentFilter, () => { page.value = 1; loadOrders() })
onMounted(loadOrders)
</script>
