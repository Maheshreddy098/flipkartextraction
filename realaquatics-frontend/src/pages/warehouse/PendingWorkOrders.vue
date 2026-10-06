<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Work Orders</h1>
      <button
        @click="exportData"
        :disabled="exporting"
        class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
      >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
    </div>

    <div class="flex gap-2 mb-4">
      <button
        v-for="f in filters"
        :key="f.value"
        @click="currentFilter = f.value"
        :class="currentFilter === f.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border'"
        class="px-3 py-1.5 text-sm rounded-lg transition"
      >{{ f.label }}</button>
    </div>

    <DataTable
      :columns="columns"
      :rows="filteredOrders"
      :total="total"
      :page="page"
      @row-click="row => $router.push(`/warehouse/work-orders/${row.name}`)"
      @page-change="p => { page = p; loadOrders() }"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #actions="{ row }">
        <div class="flex gap-2">
          <button
            v-if="row.status === 'Approved'"
            @click.stop="handleStart(row.name)"
            class="text-xs bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700"
          >Start Processing</button>
          <button
            v-if="row.status === 'In Progress'"
            @click.stop="completeTargetName = row.name; showCompleteModal = true"
            class="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
          >Complete</button>
        </div>
      </template>
    </DataTable>

    <ConfirmDialog
      :visible="showCompleteModal"
      title="Complete Work Order"
      message="Enter the finished goods batch code (optional)."
      confirm-text="Complete"
      variant="success"
      show-input
      input-placeholder="Finished goods batch code"
      @confirm="handleCompleteConfirm"
      @cancel="showCompleteModal = false; completeTargetName = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchWorkOrders, startProcessingWO, completeWO } from '@/core/api/workOrders.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const notify = useNotificationStore()
const exporting = ref(false)
const showCompleteModal = ref(false)
const completeTargetName = ref(null)
const orders = ref([])
const total = ref(0)
const page = ref(1)
const currentFilter = ref('Approved')

const filters = [
  { label: 'Approved', value: 'Approved' },
  { label: 'In Progress', value: 'In Progress' },
  { label: 'Completed', value: 'Completed' },
  { label: 'All', value: '' },
]

const columns = [
  { key: 'work_order_name', label: 'Order Name' },
  { key: 'name', label: 'WO #' },
  { key: 'finished_item_code', label: 'Item Code' },
  { key: 'finished_item_name', label: 'Item Name' },
  { key: 'status', label: 'Status' },
  { key: 'qty_to_produce', label: 'Qty to Produce' },
  { key: 'produced_qty', label: 'Produced' },
  { key: 'posting_date', label: 'Date' },
]

const filteredOrders = computed(() => {
  if (!currentFilter.value) return orders.value
  return orders.value.filter(o => o.status === currentFilter.value)
})

async function loadOrders() {
  try {
    const res = await fetchWorkOrders({ page: page.value, page_size: 50 })
    orders.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load work orders') }
}

async function handleStart(name) {
  try { await startProcessingWO(name); notify.success('Work order started - Inventory allocated'); loadOrders() }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function handleCompleteConfirm(finishedGoodsBatch) {
  const name = completeTargetName.value
  showCompleteModal.value = false
  completeTargetName.value = null
  if (!name) return
  try {
    await completeWO(name, null, finishedGoodsBatch || null)
    notify.success('Work order completed - Finished goods added to inventory')
    loadOrders()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed')
  }
}

async function exportData() {
  exporting.value = true
  try {
    const res = await fetchWorkOrders({ page: 1, page_size: 9999 })
    const rows = currentFilter.value
      ? (res.data || []).filter((r) => r.status === currentFilter.value)
      : (res.data || [])
    const exportColumns = [
      { key: 'work_order_name', label: 'Order Name' },
      { key: 'name', label: 'WO #' },
      { key: 'finished_item_code', label: 'Item Code' },
      { key: 'finished_item_name', label: 'Item Name' },
      { key: 'bom_no', label: 'BOM #' },
      { key: 'posting_date', label: 'Date' },
      { key: 'status', label: 'Status' },
      { key: 'qty_to_produce', label: 'Qty to Produce' },
      { key: 'produced_qty', label: 'Produced Qty' },
      { key: 'finished_goods_batch', label: 'Finished Goods Batch' },
      { key: 'remarks', label: 'Remarks' },
      { key: 'warehouse', label: 'Warehouse' },
      { key: 'modified', label: 'Last Modified' },
    ]
    downloadCsv('Work_Orders', exportColumns, rows)
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch(currentFilter, () => { page.value = 1 })
onMounted(loadOrders)
</script>
