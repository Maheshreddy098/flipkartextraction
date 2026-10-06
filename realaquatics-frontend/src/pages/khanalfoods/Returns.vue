<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Returns</h1>
      <div class="flex items-center gap-2">
        <button
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
        <button @click="showCreateForm = !showCreateForm" class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition">
          {{ showCreateForm ? 'Cancel' : '+ New Return' }}
        </button>
      </div>
    </div>

    <!-- Create Form -->
    <div v-if="showCreateForm" class="bg-white rounded-xl shadow-sm border p-6 mb-6">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Return Type</label>
          <select v-model="newReturn.return_type" class="input-field">
            <option value="Purchase Return">Purchase Return</option>
            <option value="Production Return">Production Return</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Reference (optional)</label>
          <input v-model="newReturn.reference_name" class="input-field" placeholder="PO or WO number" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Remarks</label>
          <input v-model="newReturn.remarks" class="input-field" placeholder="Reason for return" />
        </div>
      </div>

      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-semibold">Items</h3>
        <button type="button" @click="addBlankItem" class="text-xs text-blue-600 border border-blue-500 px-2 py-1 rounded hover:bg-blue-50">+ Add Row</button>
      </div>
      <div class="mb-3">
        <ItemSearch placeholder="Search items to add..." :clearOnSelect="true" @select="addReturnItem" />
      </div>

      <table v-if="newReturn.items.length" class="w-full text-sm">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-3 py-2 text-left w-8">#</th>
            <th class="px-3 py-2 text-left">Item Code</th>
            <th class="px-3 py-2 text-left">Item Name</th>
            <th class="px-3 py-2 text-left w-24">Qty</th>
            <th class="px-3 py-2 text-left">Reason</th>
            <th class="px-3 py-2 w-10"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in newReturn.items" :key="idx" class="border-b">
            <td class="px-3 py-2 text-gray-400">{{ idx + 1 }}</td>
            <td class="px-3 py-2"><input v-model="item.item_code" class="input-field-sm" placeholder="Item code" /></td>
            <td class="px-3 py-2"><input v-model="item.item_name" class="input-field-sm" placeholder="Item name" /></td>
            <td class="px-3 py-2"><input v-model.number="item.qty" type="number" min="1" class="input-field-sm" /></td>
            <td class="px-3 py-2"><input v-model="item.reason" class="input-field-sm" placeholder="Reason" /></td>
            <td class="px-3 py-2"><button @click="newReturn.items.splice(idx, 1)" class="text-red-400 hover:text-red-600 text-lg">&times;</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-gray-400 text-sm">Search above or click "Add Row" to add items.</p>

      <button @click="handleCreate" :disabled="saving" class="mt-4 px-5 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
        {{ saving ? 'Creating...' : 'Create Return' }}
      </button>
    </div>

    <!-- Filters -->
    <div class="flex gap-2 mb-4">
      <button
        v-for="f in statusFilters"
        :key="f.value"
        @click="currentFilter = f.value; page = 1; loadReturns()"
        :class="currentFilter === f.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border'"
        class="px-3 py-1.5 text-sm rounded-lg transition"
      >{{ f.label }}</button>
    </div>

    <!-- Returns List -->
    <div v-if="loadingList" class="text-gray-400 py-8 text-center">Loading...</div>

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
            <button
              v-if="ret.status === 'Draft'"
              @click.stop="submitRet(ret.name)"
              class="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
            >Submit</button>
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
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchReturns, fetchReturn, createReturn, submitReturn } from '@/core/api/returns.js'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ItemSearch from '@/components/common/ItemSearch.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const notify = useNotificationStore()
const exporting = ref(false)
const returns = ref([])
const total = ref(0)
const page = ref(1)
const loadingList = ref(false)
const showCreateForm = ref(false)
const saving = ref(false)
const currentFilter = ref('')
const expandedReturn = ref(null)
const returnDetail = ref(null)
const loadingDetail = ref(false)

const statusFilters = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'Draft' },
  { label: 'Pending', value: 'Pending' },
  { label: 'Approved', value: 'Approved' },
  { label: 'Processed', value: 'Processed' },
]

const newReturn = ref({ return_type: 'Purchase Return', reference_name: '', remarks: '', items: [] })

async function loadReturns() {
  loadingList.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (currentFilter.value) params.status = currentFilter.value
    const res = await fetchReturns(params)
    returns.value = res.data || []
    total.value = res.total || 0
  } catch { notify.error('Failed to load returns') }
  loadingList.value = false
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

function addReturnItem(item) {
  newReturn.value.items.push({ item_code: item.item_code, item_name: item.item_name, qty: 1, reason: '' })
}

function addBlankItem() {
  newReturn.value.items.push({ item_code: '', item_name: '', qty: 1, reason: '' })
}

async function handleCreate() {
  if (!newReturn.value.items.length) { notify.error('Add at least one item'); return }
  saving.value = true
  try {
    await createReturn(newReturn.value)
    notify.success('Return created')
    showCreateForm.value = false
    newReturn.value = { return_type: 'Purchase Return', reference_name: '', remarks: '', items: [] }
    loadReturns()
  } catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { saving.value = false }
}

async function submitRet(name) {
  try {
    await submitReturn(name)
    notify.success('Return submitted for approval')
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

<style scoped>
.input-field { @apply w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none; }
.input-field-sm { @apply w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-1 focus:ring-blue-500 outline-none; }
</style>
