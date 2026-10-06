<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Purchase Orders</h1>
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
      @row-click="row => $router.push(`/warehouse/purchase-orders/${row.name}`)"
      @page-change="p => { page = p; loadOrders() }"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #actions="{ row }">
        <div class="flex gap-2">
          <button
            v-if="row.status === 'Approved'"
            @click.stop="handleAccept(row.name)"
            class="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
          >Accept</button>
          <button
            v-if="row.status === 'Accepted'"
            @click.stop="handleReceive(row.name)"
            class="text-xs bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700"
          >Mark Received</button>
        </div>
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchPurchaseOrders, acceptPO, receivePO } from '@/core/api/purchaseOrders.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const notify = useNotificationStore()
const exporting = ref(false)
const orders = ref([])
const total = ref(0)
const page = ref(1)
const currentFilter = ref('Approved')

const filters = [
  { label: 'Approved', value: 'Approved' },
  { label: 'Accepted', value: 'Accepted' },
  { label: 'Received', value: 'Received' },
  { label: 'All', value: '' },
]

const columns = [
  { key: 'purchase_order_name', label: 'Order Name' },
  { key: 'name', label: 'PO #' },
  { key: 'supplier_name', label: 'Supplier' },
  { key: 'status', label: 'Status' },
  { key: 'total_qty', label: 'Qty' },
  { key: 'total_accepted_qty', label: 'Accepted Qty' },
  { key: 'total_amount', label: 'Total Amount' },
  { key: 'posting_date', label: 'Date' },
]

const filteredOrders = computed(() => {
  if (!currentFilter.value) return orders.value
  return orders.value.filter(o => o.status === currentFilter.value)
})

async function loadOrders() {
  try {
    const res = await fetchPurchaseOrders({ page: page.value, page_size: 50 })
    orders.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load purchase orders') }
}

async function handleAccept(name) {
  try { await acceptPO(name); notify.success('PO accepted'); loadOrders() }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function handleReceive(name) {
  try { await receivePO(name); notify.success('PO received - Inventory updated'); loadOrders() }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function exportData() {
  exporting.value = true
  try {
    const res = await fetchPurchaseOrders({ page: 1, page_size: 9999 })
    const rows = currentFilter.value
      ? (res.data || []).filter((r) => r.status === currentFilter.value)
      : (res.data || [])
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
      { key: 'accepted_by', label: 'Accepted By' },
      { key: 'modified', label: 'Last Modified' },
    ]
    downloadCsv('Purchase_Orders', exportColumns, rows)
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch(currentFilter, () => { page.value = 1 })
onMounted(loadOrders)
</script>
