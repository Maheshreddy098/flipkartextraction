<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Returns</h1>
      <button
        @click="exportData"
        :disabled="exporting"
        class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
      >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
    </div>

    <div class="flex gap-2 mb-4">
      <button
        v-for="f in statusFilters"
        :key="f.value"
        @click="currentFilter = f.value; page = 1; loadReturns()"
        :class="currentFilter === f.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border'"
        class="px-3 py-1.5 text-sm rounded-lg transition"
      >{{ f.label }}</button>
    </div>

    <div v-if="loading" class="text-gray-400 py-8 text-center">Loading...</div>

    <div v-else-if="!returns.length" class="bg-white rounded-xl border p-8 text-center text-gray-400">
      No returns found
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="ret in returns"
        :key="ret.name"
        class="bg-white rounded-xl shadow-sm border overflow-hidden"
      >
        <div
          class="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-gray-50 transition"
          @click="toggleExpand(ret.name)"
        >
          <div class="flex items-center gap-4">
            <span class="text-gray-400 text-sm">{{ expandedReturn === ret.name ? '▼' : '▶' }}</span>
            <div>
              <span class="font-semibold text-gray-900">{{ ret.name }}</span>
              <span class="text-gray-400 text-sm ml-3">{{ ret.posting_date }}</span>
            </div>
            <span class="text-xs px-2 py-0.5 rounded-full"
              :class="{
                'bg-blue-100 text-blue-700': ret.return_type === 'Purchase Return',
                'bg-purple-100 text-purple-700': ret.return_type === 'Production Return',
              }"
            >{{ ret.return_type }}</span>
            <StatusBadge :status="ret.status" />
          </div>
          <div class="flex items-center gap-3">
            <span v-if="ret.created_by_user" class="text-xs text-gray-400">by {{ ret.created_by_user }}</span>
            <button
              v-if="ret.status === 'Pending' && isManager"
              @click.stop="handleApprove(ret.name)"
              class="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
            >Approve</button>
            <button
              v-if="ret.status === 'Approved'"
              @click.stop="handleProcess(ret.name)"
              class="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700"
            >Process & Add to Inventory</button>
          </div>
        </div>

        <div v-if="expandedReturn === ret.name" class="border-t bg-gray-50 px-5 py-4">
          <div v-if="loadingDetail" class="text-gray-400 text-sm py-2">Loading items...</div>
          <div v-else-if="returnDetail">
            <div v-if="returnDetail.remarks" class="mb-3 text-sm text-gray-600">
              <span class="font-medium">Remarks:</span> {{ returnDetail.remarks }}
            </div>
            <div v-if="returnDetail.reference_name" class="mb-3 text-sm text-gray-600">
              <span class="font-medium">Reference:</span> {{ returnDetail.reference_doctype }} - {{ returnDetail.reference_name }}
            </div>
            <table class="w-full text-sm">
              <thead class="bg-white">
                <tr class="border-b">
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-500">#</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-500">Item Code</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-500">Item Name</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-500">Qty</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-500">UOM</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-500">Reason</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in returnDetail.items" :key="idx" class="border-b last:border-0">
                  <td class="px-3 py-2 text-gray-400">{{ idx + 1 }}</td>
                  <td class="px-3 py-2 font-medium text-gray-900">{{ item.item_code }}</td>
                  <td class="px-3 py-2 text-gray-600">{{ item.item_name }}</td>
                  <td class="px-3 py-2 font-semibold">{{ item.qty }}</td>
                  <td class="px-3 py-2 text-gray-500">{{ item.uom }}</td>
                  <td class="px-3 py-2 text-gray-500">{{ item.reason || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <div class="mt-2 text-sm text-gray-500 flex justify-between">
              <span>{{ returnDetail.items?.length || 0 }} item(s)</span>
              <span class="font-medium">Total Qty: {{ returnDetail.items?.reduce((s, i) => s + (i.qty || 0), 0) || 0 }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="total > returns.length" class="flex items-center justify-between mt-4 text-sm text-gray-500">
      <span>Showing {{ returns.length }} of {{ total }}</span>
      <div class="flex gap-2">
        <button :disabled="page <= 1" @click="page--; loadReturns()" class="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100">Prev</button>
        <button :disabled="returns.length < 20" @click="page++; loadReturns()" class="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100">Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchReturns, fetchReturn, approveReturn, processReturn } from '@/core/api/returns.js'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const session = useSessionStore()
const notify = useNotificationStore()
const isManager = session.isManager

const exporting = ref(false)
const returns = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const currentFilter = ref('Pending')
const expandedReturn = ref(null)
const returnDetail = ref(null)
const loadingDetail = ref(false)

const statusFilters = [
  { label: 'Pending', value: 'Pending' },
  { label: 'Approved', value: 'Approved' },
  { label: 'Processed', value: 'Processed' },
  { label: 'All', value: '' },
]

async function loadReturns() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchReturns(params)
    returns.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load returns') }
  loading.value = false
}

async function toggleExpand(name) {
  if (expandedReturn.value === name) {
    expandedReturn.value = null
    returnDetail.value = null
    return
  }
  expandedReturn.value = name
  returnDetail.value = null
  loadingDetail.value = true
  try {
    returnDetail.value = await fetchReturn(name)
  } catch { notify.error('Failed to load return details') }
  loadingDetail.value = false
}

async function handleApprove(name) {
  try {
    await approveReturn(name)
    notify.success('Return approved')
    loadReturns()
    if (expandedReturn.value === name) toggleExpand(name)
  } catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function handleProcess(name) {
  try {
    await processReturn(name)
    notify.success('Return processed - Inventory increased')
    loadReturns()
    if (expandedReturn.value === name) toggleExpand(name)
  } catch (e) { notify.error(e.response?.data?.message || 'Failed') }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchReturns(params)
    const exportColumns = [
      { key: 'name', label: 'Return #' },
      { key: 'posting_date', label: 'Date' },
      { key: 'return_type', label: 'Return Type' },
      { key: 'status', label: 'Status' },
      { key: 'reference_doctype', label: 'Reference Doctype' },
      { key: 'reference_name', label: 'Reference Name' },
      { key: 'created_by_user', label: 'Created By' },
      { key: 'modified', label: 'Last Modified' },
    ]
    downloadCsv('Returns', exportColumns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

onMounted(loadReturns)
</script>
