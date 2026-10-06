<template>
  <div class="p-4 md:p-6">
    <!-- Top bar: title + actions -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <router-link to="/khanalfoods/work-orders" class="p-1.5 rounded-lg hover:bg-gray-200 text-gray-500"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg></router-link>
        <h1 class="text-lg font-bold text-gray-900">{{ isEdit ? woId : 'New Work Order' }}</h1>
        <StatusBadge v-if="isEdit && docStatus" :status="docStatus" />
      </div>
      <div class="flex gap-2">
        <button type="button" @click="$router.back()" class="px-4 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">{{ isReadOnly ? 'Back' : 'Cancel' }}</button>
        <template v-if="!isReadOnly && !kfResumeEditMode">
          <button @click="handleSave" :disabled="saving || !canSave" class="px-5 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium">{{ saving ? 'Saving...' : 'Save' }}</button>
          <button v-if="isEdit && docStatus === 'Draft'" @click="handleSubmitForApproval" :disabled="saving" class="px-4 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium">Submit for Approval</button>
        </template>
        <template v-if="docStatus === 'Pending Approval' && isManager">
          <button @click="showApproveDialog = true" class="px-4 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium">Approve</button>
          <button @click="showRejectDialog = true" class="px-4 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium">Reject</button>
        </template>
        <button v-if="docStatus === 'Rejected'" @click="handleRevertToDraft" :disabled="saving" class="px-4 py-1.5 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 text-sm font-medium">Revert to Draft</button>
        <button
          v-if="isEdit && isKhanalFoods && !kfResumeEditMode"
          type="button"
          @click="showTicketDialog = true"
          class="px-4 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium bg-white"
        >
          Raise Ticket
        </button>
        <button
          v-if="canDelete"
          type="button"
          @click="showDeleteDialog = true"
          :disabled="saving"
          class="px-4 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
        >
          Delete
        </button>
        <template v-if="kfResumeEditMode">
          <button type="button" @click="handleKfReleaseHold" :disabled="saving" class="px-4 py-1.5 border border-amber-400 text-amber-900 bg-amber-50 rounded-lg hover:bg-amber-100 disabled:opacity-50 text-sm font-medium">
            Release warehouse hold
          </button>
          <button type="button" @click="handleSave" :disabled="saving || !canSaveKfResume" class="px-5 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium">
            {{ saving ? 'Saving...' : 'Save & release warehouse' }}
          </button>
        </template>
      </div>
    </div>

    <div
      v-if="kfResumeEditMode"
      class="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 text-sm text-amber-900"
    >
      <strong>Warehouse on hold</strong> after a support ticket. Update batches or details below, then <strong>Save & release warehouse</strong>.
      If you fixed SAP only (e.g. Retry PO) without changing lines here, use <strong>Release warehouse hold</strong>.
    </div>

    <!-- Fields bar: all key fields -->
    <div class="bg-white rounded-xl shadow-sm border p-4 mb-4">
      <div class="flex flex-wrap items-end gap-x-4 gap-y-3">
        <!-- Order Name -->
        <div class="flex-1 min-w-[200px]">
          <label class="block text-xs font-medium text-gray-500 mb-1">Order Name *</label>
          <input
            v-model="form.work_order_name"
            class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            :readonly="isReadOnly || kfResumeRestrictedHeader"
            :class="{'bg-gray-50': isReadOnly || kfResumeRestrictedHeader}"
            placeholder="e.g. March Nulo replenishment 1"
          />
        </div>
        <!-- Finished Item -->
        <div class="min-w-[12rem] max-w-[22rem]">
          <label class="block text-xs font-medium text-gray-500 mb-1">Finished Item *</label>
          <ItemSearch v-if="!isReadOnly && !isEdit" placeholder="Search item..." @select="onFinishedItemSelect" />
          <div v-if="form.finished_item_code" class="px-2 py-1.5 bg-blue-50 border border-blue-200 rounded text-xs">
            <span class="font-semibold text-blue-800 block">{{ form.finished_item_code }}</span>
            <span class="text-blue-600 whitespace-normal break-words block mt-0.5">{{ form.finished_item_name }}</span>
          </div>
        </div>
        <!-- Qty -->
        <div class="w-24">
          <label class="block text-xs font-medium text-gray-500 mb-1">Qty *</label>
          <input v-model.number="form.qty_to_produce" type="number" min="1" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm" :readonly="isReadOnly || kfResumeRestrictedHeader" :class="{'bg-gray-50': isReadOnly || kfResumeRestrictedHeader}" @change="recalcComponentQtys" />
        </div>
        <!-- BOM -->
        <div class="w-28">
          <label class="block text-xs font-medium text-gray-500 mb-1">BOM</label>
          <input :value="form.bom_no" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm bg-gray-50" readonly />
        </div>
        <!-- Production Order Type -->
        <div class="w-36">
          <label class="block text-xs font-medium text-gray-500 mb-1">PO Type</label>
          <select
            v-if="!isReadOnly && !kfResumeRestrictedHeader"
            v-model="form.production_order_type"
            class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
          >
            <option value="Standard">Standard</option>
            <option value="Special">Special</option>
          </select>
          <input v-else :value="form.production_order_type" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm bg-gray-50" readonly />
        </div>
        <!-- FG Batch -->
        <div class="w-44">
          <label class="block text-xs font-medium text-gray-500 mb-1">FG Batch *</label>
          <input v-model="form.finished_goods_batch" class="w-full px-2 py-1.5 border rounded text-sm" :class="(isReadOnly && !kfResumeFgOnly) ? 'bg-gray-50 border-gray-300' : (form.finished_goods_batch ? 'border-gray-300' : 'border-red-400')" :readonly="isReadOnly && !kfResumeFgOnly" placeholder="Batch code" />
        </div>
        <!-- Posting Date -->
        <div class="w-36">
          <label class="block text-xs font-medium text-gray-500 mb-1">Date *</label>
          <input v-model="form.posting_date" type="date" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm" :readonly="isReadOnly || kfResumeRestrictedHeader" :class="{'bg-gray-50': isReadOnly || kfResumeRestrictedHeader}" />
        </div>
        <!-- Warehouse -->
        <div class="w-36">
          <label class="block text-xs font-medium text-gray-500 mb-1">Warehouse</label>
          <input :value="form.warehouse" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm bg-gray-50" readonly />
        </div>
        <!-- Remarks -->
        <div class="flex-1 min-w-[160px]">
          <label class="block text-xs font-medium text-gray-500 mb-1">Remarks *</label>
          <input
            v-model="form.remarks"
            class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            :readonly="isReadOnly && !kfResumeEditMode"
            :class="{'bg-gray-50': isReadOnly && !kfResumeEditMode}"
            placeholder="Required"
          />
        </div>
        <!-- Edit meta -->
        <template v-if="isEdit">
          <div v-if="doc.created_by_user" class="text-xs text-gray-400"><span class="block">By</span>{{ doc.created_by_user }}</div>
          <div v-if="doc.approved_by" class="text-xs text-gray-400"><span class="block">Approved</span>{{ doc.approved_by }}</div>
        </template>
      </div>
      <p v-if="bomError && !isReadOnly" class="mt-2 text-xs text-red-500">{{ bomError }}</p>
    </div>

    <!-- SAP Integration (compact, only when relevant) -->
    <div v-if="isEdit && isKhanalFoods && (docStatus === 'In Progress' || docStatus === 'Completed')" class="bg-white rounded-xl shadow-sm border p-4 mb-4">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
        <span class="text-sm font-semibold text-gray-700">SAP B1</span>
        <!-- Statuses inline -->
        <div class="flex items-center gap-1.5 text-xs">
          <span class="text-gray-500">PO:</span>
          <span v-if="doc.sap_production_order_doc_entry" class="text-green-600 font-medium">#{{ doc.sap_production_order_doc_num || doc.sap_production_order_doc_entry }}</span>
          <span v-else-if="doc.sap_sync_status === 'Error' && !doc.sap_issue_doc_entry" class="text-red-600 font-medium">Failed</span>
          <span v-else class="text-amber-600">Pending</span>
        </div>
        <div class="flex items-center gap-1.5 text-xs">
          <span class="text-gray-500">Issue:</span>
          <span v-if="doc.sap_issue_doc_entry" class="text-green-600 font-medium">{{ doc.sap_issue_doc_entry }}</span>
          <span v-else-if="doc.sap_production_order_doc_entry && (doc.sap_sync_status === 'Error' || doc.warehouse_consumed)" class="text-red-600 font-medium">Failed</span>
          <span v-else class="text-amber-600">Pending</span>
        </div>
        <div class="flex items-center gap-1.5 text-xs">
          <span class="text-gray-500">Receipt:</span>
          <span v-if="doc.sap_receipt_doc_entry" class="text-green-600 font-medium">{{ doc.sap_receipt_doc_entry }}</span>
          <span v-else-if="doc.sap_issue_doc_entry && doc.sap_sync_status === 'Error'" class="text-red-600 font-medium">Failed</span>
          <span v-else class="text-amber-600">Pending</span>
        </div>

        <!-- Series for PO retry -->
        <select v-if="!doc.sap_production_order_doc_entry" v-model="selectedPoSeries" class="text-xs border border-gray-300 rounded px-1.5 py-1 w-28">
          <option :value="null">Series: Default</option>
          <option v-for="s in poSeriesList" :key="s.series" :value="s.series">{{ s.series_name || s.series }}</option>
        </select>

        <!-- Retry buttons inline -->
        <button v-if="!doc.sap_production_order_doc_entry" :disabled="sapLoading" class="px-3 py-1 bg-purple-600 text-white rounded text-xs font-medium hover:bg-purple-700 disabled:opacity-50" @click="handleRetryCreatePO">{{ sapLoading ? '...' : 'Retry PO' }}</button>
        <button v-if="doc.sap_production_order_doc_entry && !doc.sap_issue_doc_entry" :disabled="sapLoading" class="px-3 py-1 bg-amber-600 text-white rounded text-xs font-medium hover:bg-amber-700 disabled:opacity-50" @click="handleConsumeAndIssue">{{ sapLoading ? '...' : 'Retry Issue' }}</button>
        <button v-if="doc.sap_issue_doc_entry && !doc.sap_receipt_doc_entry" :disabled="sapLoading" class="px-3 py-1 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700 disabled:opacity-50" @click="handleRetryReceipt">{{ sapLoading ? '...' : 'Retry Receipt' }}</button>
      </div>
      <p v-if="doc.sap_sync_error" class="mt-2 text-xs text-red-600">{{ doc.sap_sync_error }}</p>
    </div>

    <!-- Components table (full width) -->
    <div class="bg-white rounded-xl shadow-sm border">
      <div class="flex items-center justify-between px-4 py-3 border-b">
        <span class="text-sm font-semibold text-gray-800">Components <span class="font-normal text-gray-400">({{ components.length }})</span> <span v-if="form.bom_no" class="text-green-600 text-xs ml-1">SAP BOM</span></span>
        <div v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly" class="flex gap-2">
          <button v-if="form.finished_item_code && form.bom_no" type="button" @click="reloadBom" class="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50">Reload BOM</button>
          <button type="button" @click="addBlankComponent" class="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50">+ Add</button>
        </div>
      </div>

      <div v-if="loadingBom" class="px-4 py-8 text-center text-sm text-gray-400">
        <svg class="w-4 h-4 animate-spin inline mr-1" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
        Loading BOM...
      </div>

      <table v-else-if="components.length" class="w-full text-sm wo-table">
        <thead>
          <tr class="bg-gray-50 text-xs text-gray-500 uppercase">
            <th class="px-3 py-2 text-left w-8">#</th>
            <th class="px-3 py-2 text-left" style="min-width:130px">Item Code</th>
            <th class="px-3 py-2 text-left" style="min-width:180px">Item Name</th>
            <th class="px-3 py-2 text-right w-20">Req Qty</th>
            <th class="px-3 py-2 text-left" style="min-width:180px">Batch</th>
            <th class="px-3 py-2 text-right w-20">Batch Qty</th>
            <th class="px-3 py-2 w-16"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(comp, cIdx) in components" :key="cIdx">
            <!-- First batch row (shows component info) -->
            <tr class="border-b hover:bg-blue-50/30" :class="{ 'border-t-2 border-t-gray-200': cIdx > 0 }">
              <td class="px-3 py-2 text-gray-400 font-mono text-xs" :rowspan="comp.batches.length || 1">{{ cIdx + 1 }}</td>
              <td class="px-3 py-2" :rowspan="comp.batches.length || 1">
                <ItemSearch v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly" :initial-value="comp.item_code" placeholder="Search..." :clear-on-select="false" class="item-search-inline" @select="(p) => onComponentItemSelect(cIdx, p)" />
                <span v-else class="font-medium text-gray-900">{{ comp.item_code }}</span>
              </td>
              <td class="px-3 py-2 text-gray-700 min-w-[200px] whitespace-normal break-words" :rowspan="comp.batches.length || 1">
                {{ comp.item_name }}
              </td>
              <td class="px-3 py-2 text-right" :rowspan="comp.batches.length || 1">
                <input v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly" v-model.number="comp.total_required_qty" type="number" min="0" step="any" class="w-16 px-1 py-0.5 border border-gray-300 rounded text-sm text-right" @change="onTotalQtyChange(cIdx)" />
                <span v-else class="font-semibold">{{ comp.total_required_qty }}</span>
              </td>
              <!-- First batch -->
              <td class="px-3 py-2">
                <template v-if="comp.batches.length">
                  <select v-if="kfResumeBatchOnly || (!isReadOnly && !kfResumeFgOnly)" v-model="comp.batches[0].batch_number" class="w-full px-1.5 py-1 border border-gray-300 rounded text-sm" :class="{ 'border-red-400': !(comp.batches[0].batch_number || '').trim() }" @focus="loadBatchesForComp(comp)">
                    <option value="">— Select —</option>
                    <option v-for="b in batchOptionsForComp(comp)" :key="b.batch_number" :value="b.batch_number">{{ b.batch_number }} ({{ b.quantity }})</option>
                  </select>
                  <span v-else class="text-gray-800">{{ comp.batches[0].batch_number || '—' }}</span>
                </template>
              </td>
              <td class="px-3 py-2 text-right">
                <template v-if="comp.batches.length">
                  <input v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly" v-model.number="comp.batches[0].quantity" type="number" min="0" step="any" class="w-16 px-1 py-0.5 border border-gray-300 rounded text-sm text-right" />
                  <span v-else class="font-medium">{{ comp.batches[0].quantity }}</span>
                </template>
              </td>
              <td class="px-3 py-2 text-center whitespace-nowrap" :rowspan="comp.batches.length || 1">
                <template v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly">
                  <button v-if="(comp.item_code || '').trim()" type="button" @click="addBatchRow(cIdx)" class="text-blue-500 hover:text-blue-700 text-xs mr-1" title="Add batch">+B</button>
                  <button type="button" @click="removeComponent(cIdx)" class="text-gray-300 hover:text-red-500 text-base leading-none" title="Remove">&times;</button>
                </template>
              </td>
            </tr>
            <!-- Additional batch rows -->
            <tr v-for="(batch, bIdx) in comp.batches.slice(1)" :key="`${cIdx}-b-${bIdx+1}`" class="border-b bg-gray-50/50">
              <td class="px-3 py-1.5">
                <select v-if="kfResumeBatchOnly || (!isReadOnly && !kfResumeFgOnly)" v-model="batch.batch_number" class="w-full px-1.5 py-1 border border-gray-300 rounded text-sm" :class="{ 'border-red-400': !(batch.batch_number || '').trim() }" @focus="loadBatchesForComp(comp)">
                  <option value="">— Select —</option>
                  <option v-for="b in batchOptionsForComp(comp)" :key="b.batch_number" :value="b.batch_number">{{ b.batch_number }} ({{ b.quantity }})</option>
                </select>
                <span v-else class="text-gray-800">{{ batch.batch_number || '—' }}</span>
              </td>
              <td class="px-3 py-1.5 text-right">
                <div class="flex items-center justify-end gap-1">
                  <input v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly" v-model.number="batch.quantity" type="number" min="0" step="any" class="w-16 px-1 py-0.5 border border-gray-300 rounded text-sm text-right" />
                  <span v-else class="font-medium">{{ batch.quantity }}</span>
                  <button v-if="!isReadOnly && !kfResumeBatchOnly && !kfResumeFgOnly" type="button" @click="removeBatchRow(cIdx, bIdx + 1)" class="text-gray-300 hover:text-red-500 text-sm ml-1">&times;</button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div v-else class="px-4 py-10 text-center text-sm text-gray-400">
        {{ bomError ? 'Could not load BOM.' : 'No components. Select a finished item above.' }}
        <p v-if="bomError" class="text-red-400 text-xs mt-1">{{ bomError }}</p>
      </div>
    </div>

    <KFAttachments
      doctype="WowPets Work Order"
      :docname="woId"
      :readonly="!isKhanalFoods"
    />

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Work Order"
      :message="`Approve ${form.work_order_name || woId}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />
    <ConfirmDialog :visible="showRejectDialog" title="Reject Work Order" :message="`Reject ${woId}?`" confirm-text="Reject" variant="danger" show-input input-placeholder="Reason" @confirm="handleReject" @cancel="showRejectDialog = false" />
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="Delete Work Order"
      :message="`Permanently delete '${form.work_order_name || woId}'? This cannot be undone.`"
      confirm-text="Delete"
      variant="danger"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
    <TicketDialog
      :visible="showTicketDialog"
      title="Raise Ticket for Work Order"
      section="Work Order"
      reference-doctype="WowPets Work Order"
      :reference-name="woId"
      :submitting="ticketSubmitting"
      @submit="handleTicketSubmit"
      @cancel="showTicketDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  createWorkOrder, updateWorkOrder, fetchWorkOrder,
  submitWOForApproval, approveWO, rejectWO, revertWOToDraft,
  retryCreateProductionOrderWO, consumeAndIssueWO, completeWO,
  receiptFromProduction, fetchProductionOrderSeries,
  kfUpdateForWarehouseResume, kfReleaseWarehouseHoldWO,
  deleteWorkOrder,
} from '@/core/api/workOrders.js'
import { fetchBOM, getBatchesForItem } from '@/core/api/sapMaster.js'
import ItemSearch from '@/components/common/ItemSearch.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import TicketDialog from '@/components/common/TicketDialog.vue'
import KFAttachments from '@/components/common/KFAttachments.vue'
import { createTicket, addTicketAttachment } from '@/core/api/tickets.js'

const props = defineProps({ id: String })
const router = useRouter()
const route = useRoute()
const session = useSessionStore()
const notify = useNotificationStore()

const isEdit = !!props.id || !!route.params.id
const woId = props.id || route.params.id
const isManager = session.isManager
const isKhanalFoods = computed(() => session.team === 'khanalfoods')

const saving = ref(false)
const sapLoading = ref(false)
const loadingBom = ref(false)
const isLoadingDoc = ref(false)
const docStatus = ref('')
const doc = ref({})
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const showDeleteDialog = ref(false)
const bomError = ref('')
const bomBaseQtys = ref([])
const batchOptionsMap = ref({})
const poSeriesList = ref([])
const selectedPoSeries = ref(null)

const SAP_WAREHOUSE_WO_STR = 'WO - STR'

const form = ref({
  finished_item_code: '',
  finished_item_name: '',
  bom_no: '',
  production_order_type: 'Standard',
  qty_to_produce: 1,
  finished_goods_batch: '',
  warehouse: 'WowPets Warehouse',
  posting_date: new Date().toISOString().slice(0, 10),
  work_order_name: '',
  remarks: '',
  items: [],
})

const components = ref([])

const woAwaitingKf = computed(() => !!doc.value?.warehouse_awaiting_kf)

const kfResumeEditMode = computed(
  () =>
    isKhanalFoods.value &&
    isEdit &&
    woAwaitingKf.value &&
    ['Approved', 'In Progress', 'Completed'].includes(docStatus.value),
)

const kfResumeBatchOnly = computed(() => {
  if (!kfResumeEditMode.value || docStatus.value !== 'In Progress') return false
  const po = doc.value?.sap_production_order_doc_entry
  const issue = doc.value?.sap_issue_doc_entry
  return !!(po && !issue)
})

const kfResumeFgOnly = computed(() => {
  if (!kfResumeEditMode.value) return false
  if (docStatus.value === 'Completed' && !doc.value?.sap_receipt_doc_entry) return true
  if (
    docStatus.value === 'In Progress' &&
    doc.value?.sap_issue_doc_entry &&
    !doc.value?.warehouse_completed
  ) {
    return true
  }
  return false
})

const kfResumeRestrictedHeader = computed(
  () => kfResumeEditMode.value && (kfResumeBatchOnly.value || kfResumeFgOnly.value),
)

const isReadOnly = computed(() => {
  if (kfResumeEditMode.value) return false
  return isEdit && docStatus.value !== 'Draft'
})

const canSave = computed(() => !!form.value.finished_item_code && components.value.length > 0 && !!form.value.finished_goods_batch)

const canSaveKfResume = computed(() => {
  if (!kfResumeEditMode.value) return false
  if (kfResumeFgOnly.value) return !!form.value.finished_goods_batch?.trim()
  if (kfResumeBatchOnly.value) {
    return components.value.length > 0 && components.value.every((c) => {
      if (!(c.item_code || '').trim()) return false
      return (c.batches || []).every((b) => (b.batch_number || '').trim() && (Number(b.quantity) || 0) > 0)
    })
  }
  return canSave.value
})
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

function batchKey(itemCode) {
  return (itemCode || '').trim() ? `${itemCode.trim()}|${SAP_WAREHOUSE_WO_STR}` : ''
}

function batchOptionsForComp(comp) {
  const key = batchKey(comp.item_code)
  return key ? (batchOptionsMap.value[key] || []) : []
}

/** Available quantity in SAP for the given batch of this component, or null if not found. */
function getBatchAvailableQty(comp, batchNumber) {
  if (!(batchNumber || '').trim()) return null
  const opts = batchOptionsForComp(comp)
  const b = opts.find((o) => (o.batch_number || '').trim() === (batchNumber || '').trim())
  return b ? (Number(b.quantity) ?? null) : null
}

async function loadBatchesForComp(comp) {
  const key = batchKey(comp.item_code)
  if (!key || key in batchOptionsMap.value) return
  batchOptionsMap.value = { ...batchOptionsMap.value, [key]: null }
  try {
    const res = await getBatchesForItem(comp.item_code, SAP_WAREHOUSE_WO_STR)
    batchOptionsMap.value = { ...batchOptionsMap.value, [key]: res.data || [] }
  } catch {
    batchOptionsMap.value = { ...batchOptionsMap.value, [key]: [] }
  }
}

function batchTotal(comp) {
  return (comp.batches || []).reduce((sum, b) => sum + (Number(b.quantity) || 0), 0)
}

function woLineValid(comp) {
  const req = Number(comp.total_required_qty) || 0
  const upb = Number(comp.number_of_units_per_box) || 0
  const boxes = Number(comp.number_of_boxes) || 0
  return req > 0 && upb > 0 && boxes > 0 && Math.abs(upb * boxes - req) < 0.001
}

function addBatchRow(cIdx) {
  components.value[cIdx].batches.push({ batch_number: '', quantity: 0 })
  loadBatchesForComp(components.value[cIdx])
}

function removeBatchRow(cIdx, bIdx) {
  components.value[cIdx].batches.splice(bIdx, 1)
}

function addBlankComponent() {
  components.value.push({
    item_code: '', item_name: '', total_required_qty: 0,
    number_of_units_per_box: 0, number_of_boxes: 0, uom: 'Nos', warehouse: 'WowPets Warehouse',
    batches: [{ batch_number: '', quantity: 0 }],
  })
}

function onComponentItemSelect(cIdx, payload) {
  const c = components.value[cIdx]
  c.item_code = payload.item_code ?? ''
  c.item_name = payload.item_name ?? ''
  c.uom = payload.uom ?? 'Nos'
  c.batches.forEach(b => { b.batch_number = '' })
  loadBatchesForComp(c)
}

function removeComponent(cIdx) {
  components.value.splice(cIdx, 1)
  bomBaseQtys.value.splice(cIdx, 1)
}

function recalcComponentQtys() {
  const qty = form.value.qty_to_produce || 1
  components.value.forEach((c, idx) => {
    if (bomBaseQtys.value[idx] !== undefined) {
      c.total_required_qty = bomBaseQtys.value[idx] * qty
      if (c.batches.length === 1) {
        c.batches[0].quantity = c.total_required_qty
      }
    }
  })
}

function onTotalQtyChange(cIdx) {
  const c = components.value[cIdx]
  if (c.batches.length === 1) {
    c.batches[0].quantity = c.total_required_qty
  }
}

function flattenComponentsToItems() {
  const items = []
  for (const comp of components.value) {
    if (!(comp.item_code || '').trim()) continue
    if (!comp.batches.length) {
      items.push({
        item_code: comp.item_code, item_name: comp.item_name,
        required_qty: comp.total_required_qty,
        number_of_units_per_box: comp.number_of_units_per_box || 0,
        number_of_boxes: comp.number_of_boxes || 0,
        uom: comp.uom || 'Nos', warehouse: comp.warehouse || 'WowPets Warehouse',
        batch_number: '',
      })
      continue
    }
    for (let bIdx = 0; bIdx < comp.batches.length; bIdx++) {
      const b = comp.batches[bIdx]
      items.push({
        item_code: comp.item_code, item_name: comp.item_name,
        required_qty: Number(b.quantity) || 0,
        number_of_units_per_box: bIdx === 0 ? (comp.number_of_units_per_box || 0) : 0,
        number_of_boxes: bIdx === 0 ? (comp.number_of_boxes || 0) : 0,
        uom: comp.uom || 'Nos', warehouse: comp.warehouse || 'WowPets Warehouse',
        batch_number: (b.batch_number || '').trim(),
      })
    }
  }
  return items
}

function reconstructComponentsFromItems(items) {
  const groups = {}
  const order = []
  for (const item of items) {
    const code = (item.item_code || '').trim()
    if (!code) continue
    if (!groups[code]) {
      groups[code] = {
        item_code: code, item_name: item.item_name || '',
        total_required_qty: 0,
        number_of_units_per_box: item.number_of_units_per_box || 0,
        number_of_boxes: item.number_of_boxes || 0,
        uom: item.uom || 'Nos', warehouse: item.warehouse || 'WowPets Warehouse',
        batches: [],
      }
      order.push(code)
    }
    const qty = Number(item.required_qty) || 0
    groups[code].total_required_qty += qty
    if (item.number_of_units_per_box > 0) groups[code].number_of_units_per_box = item.number_of_units_per_box
    if (item.number_of_boxes > 0) groups[code].number_of_boxes = item.number_of_boxes
    groups[code].batches.push({ batch_number: item.batch_number || '', quantity: qty })
  }
  return order.map(code => groups[code])
}

async function loadBomForItem(itemCode) {
  loadingBom.value = true
  bomError.value = ''
  try {
    const bom = await fetchBOM(itemCode)
    if (bom.error) { bomError.value = bom.error; form.value.bom_no = ''; components.value = []; bomBaseQtys.value = []; return }
    if (!bom.items?.length) { bomError.value = `No BOM found for ${itemCode}.`; form.value.bom_no = ''; components.value = []; bomBaseQtys.value = []; return }
    form.value.bom_no = bom.bom_no || ''
    if (bom.finished_item_name) form.value.finished_item_name = bom.finished_item_name
    bomBaseQtys.value = bom.items.map(i => i.required_qty)
    const qtyToProduce = form.value.qty_to_produce || 1
    components.value = bom.items.map(i => ({
      item_code: i.item_code, item_name: i.item_name,
      total_required_qty: i.required_qty * qtyToProduce,
      number_of_units_per_box: 0, number_of_boxes: 0,
      uom: i.uom || 'Nos', warehouse: i.warehouse || 'WowPets Warehouse',
      batches: [{ batch_number: '', quantity: i.required_qty * qtyToProduce }],
    }))
    for (const c of components.value) loadBatchesForComp(c)
    if (bom.warehouse) form.value.warehouse = bom.warehouse
  } catch { bomError.value = 'Failed to fetch BOM.'; form.value.bom_no = ''; components.value = []; bomBaseQtys.value = [] }
  finally { loadingBom.value = false }
}

async function onFinishedItemSelect(item) {
  form.value.finished_item_code = item.item_code
  form.value.finished_item_name = item.item_name
  if (form.value.production_order_type === 'Special') {
    form.value.bom_no = ''
    components.value = []
    bomBaseQtys.value = []
    bomError.value = ''
    return
  }
  await loadBomForItem(item.item_code)
}

function reloadBom() {
  if (form.value.finished_item_code) loadBomForItem(form.value.finished_item_code)
}

watch(() => form.value.production_order_type, (newType) => {
  if (isLoadingDoc.value) return
  if (newType === 'Special') {
    loadingBom.value = false
    bomError.value = ''
    form.value.bom_no = ''
    components.value = []
    bomBaseQtys.value = []
  } else if (newType === 'Standard' && form.value.finished_item_code) {
    loadBomForItem(form.value.finished_item_code)
  }
}, { flush: 'sync' })

function validateBeforeSave() {
  if (!form.value.work_order_name || !String(form.value.work_order_name).trim()) {
    notify.error('Order Name is required')
    return false
  }
  if (!form.value.finished_item_code) { notify.error('Select a finished item'); return false }
  if (!form.value.finished_goods_batch?.trim()) { notify.error('FG Batch is required'); return false }
  if (!form.value.remarks?.trim()) { notify.error('Remarks are required'); return false }
  if (!components.value.length) { notify.error('Add at least one component'); return false }
  for (let i = 0; i < components.value.length; i++) {
    const c = components.value[i]
    if (!(c.item_code || '').trim()) { notify.error(`Row ${i + 1}: Item code required`); return false }
    if (!c.batches.length) { notify.error(`Row ${i + 1} (${c.item_code}): Add a batch`); return false }
    const requiredQty = Number(c.total_required_qty) || 0
    let totalBatchQty = 0
    for (let j = 0; j < c.batches.length; j++) {
      const b = c.batches[j]
      if (!(b.batch_number || '').trim()) { notify.error(`Row ${i + 1} (${c.item_code}): Select batch ${j + 1}`); return false }
      const enteredQty = Number(b.quantity) || 0
      if (enteredQty <= 0) { notify.error(`Row ${i + 1} (${c.item_code}): Batch ${j + 1} qty must be > 0`); return false }
      totalBatchQty += enteredQty
      const available = getBatchAvailableQty(c, b.batch_number)
      if (available === null) {
        notify.error(`Row ${i + 1} (${c.item_code}): Selected batch "${b.batch_number}" was not found in SAP or has no quantity. Please select a batch with available stock.`)
        return false
      }
      if (available === 0) {
        notify.error(`Row ${i + 1} (${c.item_code}): Selected batch "${b.batch_number}" has no available quantity in SAP. Please select a batch with stock.`)
        return false
      }
      if (enteredQty > available) {
        notify.error(`Row ${i + 1} (${c.item_code}): Batch "${b.batch_number}" has only ${available} available in SAP; you entered ${enteredQty}. Reduce the batch quantity or choose another batch.`)
        return false
      }
    }
    if (totalBatchQty !== requiredQty) {
      notify.error(`Row ${i + 1} (${c.item_code}): Total batch quantity (${totalBatchQty}) must equal Required quantity (${requiredQty}). Adjust batch quantities or add/remove batches.`)
      return false
    }
  }
  return true
}

function validateKfBatchOnlyResume() {
  for (let i = 0; i < components.value.length; i++) {
    const c = components.value[i]
    if (!(c.item_code || '').trim()) {
      notify.error(`Row ${i + 1}: Item code required`)
      return false
    }
    for (let j = 0; j < (c.batches || []).length; j++) {
      const b = c.batches[j]
      if (!(b.batch_number || '').trim()) {
        notify.error(`Row ${i + 1}: Select batch ${j + 1}`)
        return false
      }
    }
  }
  return true
}

function validateKfFullResume() {
  if (!form.value.work_order_name || !String(form.value.work_order_name).trim()) {
    notify.error('Order Name is required')
    return false
  }
  if (!form.value.finished_item_code) {
    notify.error('Finished item required')
    return false
  }
  if (!form.value.finished_goods_batch?.trim()) {
    notify.error('FG Batch is required')
    return false
  }
  if (!components.value.length) {
    notify.error('Add at least one component')
    return false
  }
  for (let i = 0; i < components.value.length; i++) {
    const c = components.value[i]
    if (!(c.item_code || '').trim()) {
      notify.error(`Row ${i + 1}: Item code required`)
      return false
    }
    if (!c.batches.length) {
      notify.error(`Row ${i + 1}: Add a batch`)
      return false
    }
    let total = 0
    for (let j = 0; j < c.batches.length; j++) {
      const b = c.batches[j]
      if (!(b.batch_number || '').trim()) {
        notify.error(`Row ${i + 1}: Select batch ${j + 1}`)
        return false
      }
      const q = Number(b.quantity) || 0
      if (q <= 0) {
        notify.error(`Row ${i + 1}: Batch ${j + 1} qty must be > 0`)
        return false
      }
      total += q
    }
    const req = Number(c.total_required_qty) || 0
    if (total !== req) {
      notify.error(`Row ${i + 1}: Batch quantities must sum to required qty (${req})`)
      return false
    }
  }
  return true
}

async function applyDocToForm(data) {
  doc.value = data
  docStatus.value = data.status || 'Draft'
  isLoadingDoc.value = true
  form.value = {
    finished_item_code: data.finished_item_code || '',
    finished_item_name: data.finished_item_name || '',
    bom_no: data.bom_no || '',
    production_order_type: data.production_order_type || 'Standard',
    qty_to_produce: data.qty_to_produce || 1,
    finished_goods_batch: data.finished_goods_batch || '',
    warehouse: data.warehouse || 'WowPets Warehouse',
    posting_date: data.posting_date || '',
    work_order_name: data.work_order_name || '',
    remarks: data.remarks || '',
    items: (data.items || []).map((i) => ({
      item_code: i.item_code,
      item_name: i.item_name,
      required_qty: i.required_qty,
      uom: i.uom || 'Nos',
      warehouse: i.warehouse,
      number_of_units_per_box: i.number_of_units_per_box ?? 0,
      number_of_boxes: i.number_of_boxes ?? 0,
      batch_number: i.batch_number || '',
    })),
  }
  isLoadingDoc.value = false
  components.value = reconstructComponentsFromItems(form.value.items)
  for (const c of components.value) loadBatchesForComp(c)
}

async function handleKfReleaseHold() {
  saving.value = true
  try {
    const data = await kfReleaseWarehouseHoldWO(woId)
    await applyDocToForm(data)
    notify.success('Warehouse can continue.')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed')
  } finally {
    saving.value = false
  }
}

async function handleSave() {
  if (kfResumeEditMode.value) {
    saving.value = true
    try {
      let payload
      if (kfResumeFgOnly.value) {
        if (!form.value.finished_goods_batch?.trim()) {
          notify.error('FG Batch is required')
          saving.value = false
          return
        }
        payload = {
          finished_goods_batch: form.value.finished_goods_batch,
          remarks: form.value.remarks,
        }
      } else if (kfResumeBatchOnly.value) {
        await Promise.all(components.value.map((c) => loadBatchesForComp(c)))
        if (!validateKfBatchOnlyResume()) {
          saving.value = false
          return
        }
        payload = { ...form.value, items: flattenComponentsToItems(), remarks: form.value.remarks }
      } else {
        await Promise.all(components.value.map((c) => loadBatchesForComp(c)))
        if (!validateKfFullResume()) {
          saving.value = false
          return
        }
        payload = { ...form.value, items: flattenComponentsToItems() }
      }
      const data = await kfUpdateForWarehouseResume(woId, payload)
      await applyDocToForm(data)
      notify.success('Saved. Warehouse team can continue.')
    } catch (e) {
      notify.error(e.response?.data?.message || 'Save failed')
    } finally {
      saving.value = false
    }
    return
  }

  await Promise.all(components.value.map((c) => loadBatchesForComp(c)))
  if (!validateBeforeSave()) return
  const payload = { ...form.value, items: flattenComponentsToItems() }
  saving.value = true
  try {
    if (isEdit) {
      await updateWorkOrder(woId, payload)
      notify.success('Updated')
    } else {
      await createWorkOrder(payload)
      notify.success('Created')
    }
    router.push('/khanalfoods/work-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Save failed')
  } finally {
    saving.value = false
  }
}

async function handleSubmitForApproval() {
  await Promise.all(components.value.map((c) => loadBatchesForComp(c)))
  if (!validateBeforeSave()) return
  saving.value = true
  try {
    const payload = { ...form.value, items: flattenComponentsToItems() }
    await updateWorkOrder(woId, payload)
    await submitWOForApproval(woId)
    notify.success('Submitted for approval')
    router.push('/khanalfoods/work-orders')
  } catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { saving.value = false }
}

async function handleApprove() {
  showApproveDialog.value = false; saving.value = true
  try { await approveWO(woId); notify.success('Approved'); router.push('/khanalfoods/work-orders') }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { saving.value = false }
}

async function handleReject(reason) {
  showRejectDialog.value = false; saving.value = true
  try { await rejectWO(woId, reason); notify.success('Rejected'); router.push('/khanalfoods/work-orders') }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { saving.value = false }
}

async function handleRevertToDraft() {
  saving.value = true
  try {
    await revertWOToDraft(woId); notify.success('Reverted to Draft')
    const data = await fetchWorkOrder(woId); doc.value = data; docStatus.value = data.status || 'Draft'
  } catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { saving.value = false }
}

const canDelete = computed(() => {
  if (!isEdit || !isKhanalFoods.value) return false
  const d = doc.value
  if (!d) return false
  if (d.sap_production_order_doc_entry || d.sap_issue_doc_entry || d.sap_receipt_doc_entry) return false
  if (isManager) return ['Draft', 'Approved'].includes(docStatus.value)
  return d.owner === session.userEmail && docStatus.value === 'Draft'
})

async function handleDelete() {
  showDeleteDialog.value = false
  saving.value = true
  try {
    await deleteWorkOrder(woId)
    notify.success('Work Order deleted')
    router.push('/khanalfoods/work-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Delete failed')
  } finally {
    saving.value = false
  }
}

async function handleRetryCreatePO() {
  sapLoading.value = true
  try { const data = await retryCreateProductionOrderWO(woId, selectedPoSeries.value); doc.value = data; notify.success('Production Order created') }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { sapLoading.value = false }
}

async function handleConsumeAndIssue() {
  sapLoading.value = true
  try { const data = await consumeAndIssueWO(woId); doc.value = data; notify.success('Issue posted') }
  catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { sapLoading.value = false }
}

async function handleRetryReceipt() {
  sapLoading.value = true
  try {
    const data = await completeWO(woId, null, doc.value.finished_goods_batch || form.value.finished_goods_batch)
    doc.value = data; docStatus.value = data.status || docStatus.value; notify.success('Receipt posted')
  } catch (e) { notify.error(e.response?.data?.message || 'Failed') }
  finally { sapLoading.value = false }
}

async function handleTicketSubmit(payload) {
  if (!payload) {
    notify.error('Title and description are required')
    return
  }
  ticketSubmitting.value = true
  try {
    const { ticket, attachment } = payload
    const created = await createTicket(ticket)
    if (attachment && created?.name) {
      await addTicketAttachment(created.name, attachment.file_name, attachment.filedata)
    }
    notify.success('Ticket raised')
    showTicketDialog.value = false
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to raise ticket')
  } finally {
    ticketSubmitting.value = false
  }
}

onMounted(async () => {
  if (isEdit) {
    isLoadingDoc.value = true
    try {
      const data = await fetchWorkOrder(woId)
      doc.value = data; docStatus.value = data.status || 'Draft'
      form.value = {
        finished_item_code: data.finished_item_code || '', finished_item_name: data.finished_item_name || '',
        bom_no: data.bom_no || '', production_order_type: data.production_order_type || 'Standard',
        qty_to_produce: data.qty_to_produce || 1,
        finished_goods_batch: data.finished_goods_batch || '',
        warehouse: data.warehouse || 'WowPets Warehouse', posting_date: data.posting_date || '',
        work_order_name: data.work_order_name || '',
        remarks: data.remarks || '',
        items: (data.items || []).map(i => ({
          item_code: i.item_code, item_name: i.item_name, required_qty: i.required_qty,
          uom: i.uom || 'Nos', warehouse: i.warehouse,
          number_of_units_per_box: i.number_of_units_per_box ?? 0,
          number_of_boxes: i.number_of_boxes ?? 0, batch_number: i.batch_number || '',
        })),
      }
      isLoadingDoc.value = false
      components.value = reconstructComponentsFromItems(form.value.items)
      for (const c of components.value) loadBatchesForComp(c)
      if (session.team === 'khanalfoods') {
        try { const res = await fetchProductionOrderSeries(); poSeriesList.value = (res?.data) || [] } catch {}
      }
    } catch {
      isLoadingDoc.value = false
      notify.error('Failed to load Work Order')
    }
  }
})
</script>

<style scoped>
.wo-table th, .wo-table td { vertical-align: middle; }
.wo-table select, .wo-table input[type="number"] { font-size: 0.8125rem; }
.item-search-inline :deep(input) { font-size: 0.8125rem; padding: 4px 6px; }
</style>
