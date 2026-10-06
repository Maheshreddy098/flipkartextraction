<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Work Orders</h1>
      <div class="flex items-center gap-2">
        <button
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
        <router-link
          to="/khanalfoods/work-orders/new"
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >+ New Work Order</router-link>
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
      @page-change="p => { page = p; loadOrders() }"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-warehouse_awaiting_kf="{ row }">
        <span v-if="row.warehouse_awaiting_kf" class="text-xs font-semibold text-amber-700 bg-amber-100 px-2 py-0.5 rounded">On hold</span>
        <span v-else class="text-gray-300">—</span>
      </template>
      <template #actions="{ row }">
        <div class="flex gap-2">
          <button
            v-if="row.status === 'Draft'"
            @click.stop="submitForApproval(row.name)"
            class="text-xs text-blue-600 hover:underline"
          >Submit</button>
          <button
            v-if="row.status === 'Pending Approval' && isManager"
            @click.stop="approveOrder(row.name)"
            class="text-xs text-green-600 hover:underline"
          >Approve</button>
          <button
            v-if="row.status === 'Pending Approval' && isManager"
            @click.stop="rejectOrder(row.name)"
            class="text-xs text-red-600 hover:underline"
          >Reject</button>
        </div>
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchWorkOrders, submitWOForApproval, approveWO, rejectWO } from '@/core/api/workOrders.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const router = useRouter()
const session = useSessionStore()
const notify = useNotificationStore()
const isManager = session.isManager

const exporting = ref(false)
const orders = ref([])
const total = ref(0)
const page = ref(1)
const currentFilter = ref('')

const statusFilters = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'Draft' },
  { label: 'Pending Approval', value: 'Pending Approval' },
  { label: 'Approved', value: 'Approved' },
  { label: 'In Progress', value: 'In Progress' },
  { label: 'Completed', value: 'Completed' },
]

const columns = [
  { key: 'work_order_name', label: 'Order Name' },
  { key: 'name', label: 'WO #' },
  { key: 'finished_item_code', label: 'Finished Item' },
  { key: 'status', label: 'Status' },
  { key: 'warehouse_awaiting_kf', label: 'Warehouse' },
  { key: 'qty_to_produce', label: 'Qty' },
  { key: 'posting_date', label: 'Date' },
]

async function loadOrders() {
  try {
    const params = { page: page.value }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchWorkOrders(params)
    orders.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load work orders') }
}

function viewOrder(row) { router.push(`/khanalfoods/work-orders/${row.name}`) }

async function submitForApproval(name) {
  try { await submitWOForApproval(name); notify.success('WO submitted'); loadOrders() }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function approveOrder(name) {
  try { await approveWO(name); notify.success('WO approved'); loadOrders() }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function rejectOrder(name) {
  try { await rejectWO(name); notify.success('WO rejected'); loadOrders() }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchWorkOrders(params)
    const exportColumns = [
      { key: 'work_order_name', label: 'Order Name' },
      { key: 'name', label: 'WO #' },
      { key: 'finished_item_code', label: 'Finished Item Code' },
      { key: 'finished_item_name', label: 'Finished Item Name' },
      { key: 'bom_no', label: 'BOM #' },
      { key: 'posting_date', label: 'Date' },
      { key: 'status', label: 'Status' },
      { key: 'qty_to_produce', label: 'Qty to Produce' },
      { key: 'produced_qty', label: 'Produced Qty' },
      { key: 'finished_goods_batch', label: 'Finished Goods Batch' },
      { key: 'remarks', label: 'Remarks' },
      { key: 'created_by_user', label: 'Created By' },
      { key: 'approved_by', label: 'Approved By' },
      { key: 'warehouse', label: 'Warehouse' },
      { key: 'sap_sync_status', label: 'SAP Status' },
      { key: 'sap_production_order_doc_num', label: 'SAP Production Order#' },
      { key: 'sap_production_order_series', label: 'SAP Series' },
      { key: 'sap_issue_doc_entry', label: 'SAP Issue Entry' },
      { key: 'sap_receipt_doc_entry', label: 'SAP Receipt Entry' },
      { key: 'sap_sync_error', label: 'SAP Error' },
      { key: 'modified', label: 'Last Modified' },
    ]
    downloadCsv('Work_Orders', exportColumns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch(currentFilter, () => { page.value = 1; loadOrders() })
onMounted(loadOrders)
</script>
