<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Shiphero Transfers</h1>
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
        >+ New Transfer</router-link>
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
      :rows="transfers"
      :total="total"
      :page="page"
      @row-click="viewTransfer"
      @page-change="changePage"
    >
      <template #cell-status="{ value }">
        <!-- Warehouse sees warehouse-only status labels (no SAP); KhanalFoods sees full status -->
        <StatusBadge :status="isWarehouse && value === 'Sent to SAP' ? 'Posted' : (value || '')" />
      </template>
      <template v-if="isKhanalFoods" #cell-sap_doc_entry="{ value }">
        <span v-if="value" class="text-green-600 text-xs font-medium">SAP # {{ value }}</span>
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
      title="Approve Shiphero Transfer"
      :message="`Approve ${selectedRow?.inventory_transfer_name || selectedRow?.name || ''}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Shiphero Transfer"
      :message="`Reject ${selectedRow?.inventory_transfer_name || selectedRow?.name || ''}? Provide a reason:`"
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
  fetchShipheroTransfers,
  submitShipheroTransfer,
  approveShipheroTransfer,
  rejectShipheroTransfer,
} from '@/core/api/shipheroTransfers.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const router = useRouter()
const session = useSessionStore()
const notify = useNotificationStore()

const isKhanalFoods = computed(() => session.team === 'khanalfoods')
const isWarehouse = computed(() => session.team === 'warehouse')
const isManager = session.isManager
const transfers = ref([])
const total = ref(0)
const page = ref(1)
const currentFilter = ref('')

const newPath = computed(() => (isKhanalFoods.value ? '/khanalfoods/shiphero-transfers/new' : '#'))
const listPath = computed(() => (session.team === 'khanalfoods' ? '/khanalfoods/shiphero-transfers' : '/warehouse/shiphero-transfers'))

const statusFilters = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'Draft' },
  { label: 'Pending Approval', value: 'Pending Approval' },
  { label: 'Approved', value: 'Approved' },
  { label: 'Accepted', value: 'Accepted' },
  { label: 'Received', value: 'Received' },
  { label: 'Error', value: 'Error' },
]

const allColumns = [
  { key: 'inventory_transfer_name', label: 'Transfer Name' },
  { key: 'name', label: 'Transfer #' },
  { key: 'doc_date', label: 'Date' },
  { key: 'from_warehouse', label: 'From' },
  { key: 'to_warehouse', label: 'To' },
  { key: 'total_qty', label: 'Qty' },
  { key: 'total_accepted_qty', label: 'Accepted Qty' },
  { key: 'status', label: 'Status' },
  { key: 'sap_doc_entry', label: 'SAP' },
]
const columns = computed(() =>
  // Warehouse should not see the SAP column, but both teams see Qty / Accepted Qty.
  isWarehouse.value ? allColumns.filter((c) => c.key !== 'sap_doc_entry') : allColumns
)

const exporting = ref(false)
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const selectedRow = ref(null)

async function loadTransfers() {
  try {
    const params = { page: page.value }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchShipheroTransfers(params)
    transfers.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load Shiphero transfers') }
}

function viewTransfer(row) {
  if (session.team === 'khanalfoods') {
    router.push(`/khanalfoods/shiphero-transfers/${row.name}`)
  } else {
    router.push(`/warehouse/shiphero-transfers/${row.name}`)
  }
}

function changePage(p) { page.value = p }

async function submitForApproval(name) {
  try {
    await submitShipheroTransfer(name)
    notify.success('Transfer submitted for approval')
    loadTransfers()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed to submit') }
}

function openApproveDialog(row) { selectedRow.value = row; showApproveDialog.value = true }
function openRejectDialog(row) { selectedRow.value = row; showRejectDialog.value = true }

async function handleApprove() {
  try {
    await approveShipheroTransfer(selectedRow.value.name)
    notify.success('Transfer approved')
    showApproveDialog.value = false
    loadTransfers()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed to approve') }
}

async function handleReject(reason) {
  try {
    await rejectShipheroTransfer(selectedRow.value.name, reason)
    notify.success('Transfer rejected')
    showRejectDialog.value = false
    loadTransfers()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed to reject') }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchShipheroTransfers(params)
    const exportColumns = [
      { key: 'inventory_transfer_name', label: 'Transfer Name' },
      { key: 'name', label: 'Transfer #' },
      { key: 'doc_date', label: 'Date' },
      { key: 'from_warehouse', label: 'From Warehouse' },
      { key: 'to_warehouse', label: 'To Warehouse' },
      { key: 'total_qty', label: 'Total Qty' },
      { key: 'total_accepted_qty', label: 'Accepted Qty' },
      { key: 'status', label: 'Status' },
      { key: 'accepted_by', label: 'Accepted By' },
      { key: 'comments', label: 'Comments' },
      { key: 'modified', label: 'Last Modified' },
      ...(isKhanalFoods.value
        ? [
            { key: 'sap_doc_entry', label: 'SAP Entry #' },
            { key: 'sap_doc_num', label: 'SAP Doc #' },
            { key: 'sap_sync_error', label: 'SAP Error' },
          ]
        : []),
    ]
    downloadCsv('Shiphero_Transfers', exportColumns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch(currentFilter, () => { page.value = 1; loadTransfers() })
onMounted(loadTransfers)
</script>
