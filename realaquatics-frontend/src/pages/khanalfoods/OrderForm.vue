<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <router-link :to="listPath" class="p-2 rounded-lg hover:bg-gray-200 transition text-gray-500">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </router-link>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">
            {{ isEdit ? (form.fba_transfer_name || orderId) : 'New FBA Transfer' }}
          </h1>
          <p class="text-sm text-gray-500 mt-0.5">{{ isEdit ? '' : 'FBA transfer flows to manager approval, then warehouse accept → packaging → complete (SAP transfer from RP-FG)' }}</p>
        </div>
        <StatusBadge v-if="isEdit && docStatus" :status="docStatus" />
      </div>
      <div class="flex gap-3">
        <button type="button" @click="$router.back()" class="px-5 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium transition">
          {{ isReadOnly ? 'Back' : 'Cancel' }}
        </button>

        <template v-if="isKhanalFoods && !isReadOnly">
          <button @click="handleSave" :disabled="saving" class="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
          <button v-if="isEdit && docStatus === 'Draft'" @click="handleSubmit" :disabled="saving" class="px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
            Submit for Approval
          </button>
        </template>

        <template v-if="docStatus === 'Pending Approval' && isKhanalFoods && isManager">
          <button @click="showApproveDialog = true" class="px-5 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm font-medium shadow-sm">
            Approve
          </button>
          <button @click="showRejectDialog = true" class="px-5 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition text-sm font-medium shadow-sm">
            Reject
          </button>
        </template>

        <template v-if="isKhanalFoods && docStatus === 'Error'">
          <button @click="openPreviewModal" :disabled="saving" class="px-5 py-2.5 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition text-sm font-medium shadow-sm">
            Preview
          </button>
          <button @click="handleRetrySap" :disabled="saving" class="px-5 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
            {{ saving ? 'Retrying...' : 'Retry to SAP' }}
          </button>
        </template>
        <button
          v-if="isEdit && isKhanalFoods"
          type="button"
          @click="showTicketDialog = true"
          class="px-5 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium bg-white"
        >
          Raise Ticket
        </button>
        <button
          v-if="canDelete"
          type="button"
          @click="showDeleteDialog = true"
          :disabled="saving"
          class="px-5 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition text-sm font-medium shadow-sm"
        >
          Delete
        </button>
        <button v-if="isEdit && docStatus === 'Rejected' && isKhanalFoods && isManager" @click="handleRevertToDraft" :disabled="saving" class="px-5 py-2.5 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
          Revert to Draft
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-gray-400 py-12 text-center">Loading...</div>

    <div v-else class="space-y-6">
      <div class="bg-white rounded-xl shadow-sm border p-6">
        <h2 class="text-base font-semibold text-gray-800 mb-4">FBA Transfer Details</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Transfer Name *</label>
            <textarea
              v-model="form.fba_transfer_name"
              class="input-field"
              :class="{ 'bg-gray-50': isReadOnly }"
              :readonly="isReadOnly"
              rows="2"
              placeholder="e.g. March Nulo replenishment 1"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Doc Date</label>
            <input v-model="form.doc_date" type="date" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">To Warehouse</label>
            <div v-if="isReadOnly" class="input-field bg-gray-50 flex items-center">
              <span class="text-gray-800">{{ warehouseNameForCode(form.to_warehouse) || form.to_warehouse || '—' }}</span>
            </div>
            <select
              v-else
              v-model="form.to_warehouse"
              class="input-field"
            >
              <option disabled value="">Select warehouse (from SAP)</option>
              <option
                v-for="wh in toWarehouseOptions"
                :key="wh.warehouse_code"
                :value="wh.warehouse_code"
              >
                {{ wh.warehouse_name ? `${wh.warehouse_name} (${wh.warehouse_code})` : wh.warehouse_code }}
              </option>
            </select>
          </div>
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Comments</label>
            <textarea v-model="form.comments" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" rows="2" placeholder="Optional" />
          </div>
        </div>

        <h3 class="text-sm font-semibold text-gray-700 mt-6 mb-3">Address (USA format)</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Address Line 1 *</label>
            <input v-model="form.address_line1" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="Street address" />
          </div>
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Address Line 2</label>
            <input v-model="form.address_line2" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="Apt, suite, unit (optional)" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">City *</label>
            <input v-model="form.city" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="City" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">State *</label>
            <input v-model="form.state" class="input-field w-24" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="e.g. CA" maxlength="2" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">ZIP Code *</label>
            <input v-model="form.zip_code" class="input-field w-32" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="e.g. 90210" />
          </div>
        </div>

        <div v-if="isEdit" class="mt-4 pt-4 border-t space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1">Status</label>
            <p class="text-sm text-gray-800">
              <span class="font-medium">{{ doc.status || '—' }}</span>
              <span v-if="doc.status === 'Pending Approval'" class="text-amber-600 ml-1">(awaiting manager approval)</span>
              <span v-if="doc.status === 'Approved'" class="text-green-600 ml-1">(visible to warehouse to Accept)</span>
              <span v-if="doc.status === 'Accepted'" class="text-blue-600 ml-1">(warehouse will start packaging → then Dispatch)</span>
              <span v-if="doc.status === 'Packaging'" class="text-amber-600 ml-1">(warehouse is packaging; will Dispatch when ready)</span>
              <span v-if="doc.status === 'Dispatched'" class="text-amber-600 ml-1">(dispatched by warehouse – auto-sent to SAP)</span>
              <span v-if="doc.status === 'Sent to SAP'" class="text-green-600 ml-1">(sent to SAP)</span>
              <span v-if="doc.status === 'Error'" class="text-red-600 ml-1">(SAP failed – use Retry SAP)</span>
            </p>
          </div>
          <!-- SAP: Transfer Request + final Transfer -->
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1">SAP</label>
            <div class="space-y-1">
              <div>
                <span class="text-xs font-semibold text-gray-500 uppercase">Inventory Transfer Request</span>
                <p v-if="doc.sap_request_doc_entry" class="text-sm text-green-700">
                  Doc Entry: <strong>{{ doc.sap_request_doc_entry }}</strong>
                  <span v-if="doc.sap_request_doc_num">, Doc Num: <strong>{{ doc.sap_request_doc_num }}</strong></span>
                </p>
                <p v-else class="text-sm text-gray-400">Not created yet (created when warehouse Accepts)</p>
              </div>
              <div>
                <span class="text-xs font-semibold text-gray-500 uppercase">Inventory Transfer</span>
                <p v-if="doc.sap_doc_entry" class="text-sm text-green-700">
                  Doc Entry: <strong>{{ doc.sap_doc_entry }}</strong>
                  <span v-if="doc.sap_doc_num">, Doc Num: <strong>{{ doc.sap_doc_num }}</strong></span>
                </p>
                <p v-else class="text-sm text-gray-400">Not created yet (posted on Dispatch)</p>
              </div>
              <p v-if="doc.sap_sync_error" class="text-sm text-red-600 mt-1">{{ doc.sap_sync_error }}</p>
              <div v-if="isKhanalFoods && (doc.status === 'Error' || (doc.status === 'Dispatched' && !doc.sap_doc_entry))" class="mt-2">
                <button type="button" @click="handleRetrySap()" :disabled="saving" class="px-3 py-1.5 text-sm rounded-lg bg-amber-100 text-amber-800 hover:bg-amber-200 transition">
                  {{ saving ? 'Retrying...' : 'Retry to SAP' }}
                </button>
              </div>
            </div>
          </div>
          <div v-if="doc.approved_by">
            <label class="block text-xs font-medium text-gray-400 mb-1">Approved by</label>
            <p class="text-sm text-gray-700">{{ doc.approved_by }}</p>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border">
        <div class="flex items-center justify-between px-6 py-4 border-b">
          <h2 class="text-base font-semibold text-gray-800">Line Items</h2>
          <p class="text-xs text-gray-400">{{ form.items.length }} item(s)</p>
          <div v-if="!isReadOnly && isKhanalFoods" class="flex gap-2">
            <button type="button" @click="addBlankRow" class="px-3 py-1.5 text-sm border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50 transition">+ Add Row</button>
          </div>
        </div>

        <div v-if="!isReadOnly && isKhanalFoods" class="px-6 py-3 border-b bg-gray-50/50">
          <ItemSearch placeholder="Search SAP items..." :clearOnSelect="true" @select="addItem" />
        </div>

        <div v-if="form.items.length" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50/80">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-12">#</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[120px]">Item Code</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[160px]">Item Name</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Quantity</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">UOM</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-28">Units/Box</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">No. Boxes</th>
                <th class="px-4 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-16">OK</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[160px]">Batch (from RP-FG)</th>
                <th v-if="!isReadOnly && isKhanalFoods" class="px-4 py-2.5 w-12"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in form.items" :key="idx" class="border-b border-gray-100 hover:bg-blue-50/30">
                <td class="px-4 py-2.5 text-gray-400 font-mono text-xs">{{ idx + 1 }}</td>
                <td class="px-4 py-2.5 font-medium text-gray-800">{{ item.item_code }}</td>
                <td class="px-4 py-2.5 text-gray-600">{{ item.item_name }}</td>
                <td class="px-4 py-2.5">
                  <span class="text-gray-800 font-medium">{{ rowTotalQty(item) }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input v-if="!isReadOnly && isKhanalFoods" v-model="item.uom" type="text" class="input-field-sm w-20" placeholder="Nos" />
                  <span v-else class="text-gray-600">{{ item.uom || 'Nos' }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input v-if="!isReadOnly && isKhanalFoods" v-model.number="item.number_of_units_per_box" type="number" min="0" class="input-field-sm w-24" @input="onUnitsPerBoxChange(item)" />
                  <span v-else class="text-gray-600">{{ item.number_of_units_per_box ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input v-if="!isReadOnly && isKhanalFoods" v-model.number="item.number_of_boxes" type="number" min="0" class="input-field-sm w-24" />
                  <span v-else class="text-gray-600">{{ item.number_of_boxes ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5 text-center">
                  <span v-if="orderLineValid(item)" class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600" title="Units per box × No. boxes = Quantity">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                  </span>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td class="px-4 py-2.5">
                  <template v-if="!isReadOnly && isKhanalFoods">
                    <template v-if="(item.item_code || '').trim()">
                      <div class="space-y-2">
                        <div v-for="(b, bi) in (item.batches || [])" :key="bi" class="flex items-center gap-2">
                          <select
                            v-if="batchOptionsForKey(batchKey(item)) !== null"
                            v-model="b.batch_number"
                            class="input-field-sm w-full min-w-[140px]"
                            @focus="loadBatchesForRow(item)"
                          >
                            <option v-if="!(batchOptionsForKey(batchKey(item)) || []).length" value="">No batches in RP-FG</option>
                            <option v-else value="">— Select batch (from SAP) —</option>
                            <option v-for="opt in (batchOptionsForKey(batchKey(item)) || [])" :key="opt.batch_number" :value="opt.batch_number">
                              {{ opt.batch_number }} (Qty: {{ opt.quantity }})
                            </option>
                          </select>
                          <select v-else disabled class="input-field-sm w-full min-w-[140px] bg-gray-100 text-gray-500">
                            <option>Loading batches from SAP...</option>
                          </select>
                          <input v-model.number="b.qty" type="number" min="0" step="any" class="input-field-sm w-20" placeholder="Qty" />
                          <button
                            v-if="(item.batches || []).length > 1"
                            type="button"
                            @click="removeBatch(item, bi)"
                            class="text-gray-300 hover:text-red-500 transition text-lg"
                            title="Remove batch"
                          >
                            &times;
                          </button>
                        </div>
                        <button type="button" @click="addBatch(item)" class="text-xs text-blue-600 hover:underline">+ Add batch</button>
                      </div>
                    </template>
                    <span v-else class="text-gray-400 text-xs">Add item first</span>
                  </template>
                  <span v-else class="text-gray-600">
                    <template v-if="(item.batches || []).length">
                      {{ (item.batches || []).map((b) => `${b.batch_number || '—'} (${b.qty})`).join(', ') }}
                    </template>
                    <template v-else>{{ item.batch_number || '—' }}</template>
                  </span>
                </td>
                <td v-if="!isReadOnly && isKhanalFoods" class="px-4 py-2.5 text-center">
                  <button @click="form.items.splice(idx, 1)" type="button" class="text-gray-300 hover:text-red-500 transition text-lg">&times;</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="form.items.length && !isReadOnly && isKhanalFoods" class="px-6 py-2 text-xs text-gray-500 border-t">Units per box × Number of boxes (advisory). A green tick shows when they match quantity — but it won't block saving.</p>
        <div v-if="!form.items.length" class="px-6 py-12 text-center text-gray-400 text-sm">No items.</div>
      </div>

      <KFAttachments
        doctype="Real Aquatics Order"
        :docname="orderId"
      />
    </div>

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve FBA Transfer"
      :message="`Approve ${form.fba_transfer_name || orderId}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject FBA Transfer"
      :message="`Reject ${form.fba_transfer_name || orderId}? Provide a reason:`"
      confirm-text="Reject"
      variant="danger"
      show-input
      input-placeholder="Reason"
      @confirm="handleReject"
      @cancel="showRejectDialog = false"
    />

    <ConfirmDialog
      :visible="showDeleteDialog"
      title="Delete FBA Transfer"
      :message="`Permanently delete '${form.fba_transfer_name || orderId}'? This cannot be undone.`"
      confirm-text="Delete"
      variant="danger"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <TicketDialog
      :visible="showTicketDialog"
      title="Raise Ticket for FBA Transfer"
      section="FBA Transfer"
      reference-doctype="Real Aquatics Order"
      :reference-name="orderId"
      :submitting="ticketSubmitting"
      @submit="handleTicketSubmit"
      @cancel="showTicketDialog = false"
    />

    <!-- Preview SAP transfer modal -->
    <div v-if="showPreviewModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showPreviewModal = false">
      <div class="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b flex items-center justify-between">
          <h3 class="text-lg font-semibold text-gray-900">Preview – SAP inventory transfer</h3>
          <button type="button" @click="showPreviewModal = false" class="p-2 text-gray-400 hover:text-gray-600 rounded-lg">×</button>
        </div>
        <div class="px-6 py-4 overflow-y-auto flex-1">
          <template v-if="previewData">
            <div class="grid grid-cols-2 gap-4 text-sm mb-4">
              <div><span class="text-gray-500 block">From Warehouse</span><span class="font-medium">{{ previewData.from_warehouse }}</span></div>
              <div><span class="text-gray-500 block">To Warehouse</span><span class="font-medium">{{ previewData.to_warehouse }}</span></div>
              <div><span class="text-gray-500 block">Doc Date</span><span class="font-medium">{{ previewData.doc_date }}</span></div>
            </div>
            <table class="w-full text-sm border rounded-lg overflow-hidden">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600">Item</th>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600 w-20">Qty</th>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600">Batch</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(line, i) in (previewData.lines || [])" :key="i" class="border-t">
                  <td class="px-3 py-2">{{ line.item_code }} – {{ line.item_name }}</td>
                  <td class="px-3 py-2">{{ line.quantity }}</td>
                  <td class="px-3 py-2">{{ line.batch_number || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <div v-else class="text-gray-500 py-4">Loading preview...</div>
        </div>
        <div class="px-6 py-4 border-t flex justify-end gap-2">
          <button type="button" @click="showPreviewModal = false" class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">Close</button>
          <button type="button" @click="sendFromPreview" :disabled="saving" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium">
            {{ saving ? 'Sending...' : 'Send to SAP' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  fetchOrder,
  createOrder,
  updateOrder,
  submitOrder,
  approveOrder,
  rejectOrder,
  previewOrderSap,
  sendOrderToSap,
  retryOrderSap,
  revertOrderToDraft,
  deleteOrder,
} from '@/core/api/orders.js'
import { getWarehouses, getBatchesForItem } from '@/core/api/sapMaster.js'
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

const orderId = computed(() => props.id || route.params.id)
const isEdit = computed(() => !!orderId.value)
const isKhanalFoods = computed(() => session.team === 'khanalfoods')
const isManager = session.isManager

const listPath = computed(() => (session.team === 'khanalfoods' ? '/khanalfoods/orders' : '/warehouse/orders'))

const loading = ref(false)
const saving = ref(false)
const docStatus = ref('')
const doc = ref({})
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const showPreviewModal = ref(false)
const showTicketDialog = ref(false)
const showDeleteDialog = ref(false)
const ticketSubmitting = ref(false)
const previewData = ref(null)
const sapWarehouses = ref([])
const batchOptionsMap = ref({})

// Orders always consume from RP-FG; batches fetched from SAP for this warehouse
const ORDERS_FROM_WAREHOUSE = 'RP-FG'

// To Warehouse: exclude source (RP-FG) so user can only select destination warehouses
const toWarehouseOptions = computed(() => {
  const list = sapWarehouses.value || []
  const fromCode = (ORDERS_FROM_WAREHOUSE || '').trim().toUpperCase().replace(/\s+/g, '')
  return list.filter((wh) => {
    const code = (wh.warehouse_code || '').trim().toUpperCase().replace(/\s+/g, '')
    return code && code !== fromCode && (wh.warehouse_code || '').trim() !== ORDERS_FROM_WAREHOUSE
  })
})

function rowTotalQty(item) {
  return (item.batches || []).reduce((s, b) => s + (Number(b.qty) || 0), 0)
}

function onUnitsPerBoxChange(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  if (upb > 0 && qty > 0) item.number_of_boxes = Math.round(qty / upb)
}

function orderLineValid(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  const boxes = Number(item.number_of_boxes) || 0
  return qty > 0 && upb > 0 && boxes > 0 && Math.abs(upb * boxes - qty) < 0.001
}

function batchKey(item) {
  const code = (item?.item_code || '').trim()
  return code ? `${code}|${ORDERS_FROM_WAREHOUSE}` : ''
}

function batchOptionsForKey(key) {
  return batchOptionsMap.value[key] ?? null
}

function getBatchAvailableQty(item) {
  const key = batchKey(item)
  const list = batchOptionsForKey(key) || []
  const batchNo = (item.batch_number || '').trim()
  if (!batchNo) return null
  const match = list.find((b) => (b.batch_number || '').trim() === batchNo)
  if (!match) return null
  const qty = Number(match.quantity)
  return Number.isFinite(qty) ? qty : null
}

async function loadBatchesForRow(item) {
  const key = batchKey(item)
  if (!key || key in batchOptionsMap.value) return
  batchOptionsMap.value = { ...batchOptionsMap.value, [key]: null }
  try {
    const res = await getBatchesForItem(item.item_code, ORDERS_FROM_WAREHOUSE)
    batchOptionsMap.value = { ...batchOptionsMap.value, [key]: res.data || [] }
  } catch {
    batchOptionsMap.value = { ...batchOptionsMap.value, [key]: [] }
  }
}

function warehouseNameForCode(code) {
  if (!(code || '').trim()) return ''
  const list = sapWarehouses.value || []
  const wh = list.find((w) => (w.warehouse_code || '').trim() === (code || '').trim())
  return wh ? (wh.warehouse_name || wh.warehouse_code) : ''
}

const form = ref({
  doc_date: new Date().toISOString().slice(0, 10),
  to_warehouse: '',
  fba_transfer_name: '',
  comments: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  zip_code: '',
  items: [],
})

watch(() => [...form.value.items], () => {
  form.value.items.forEach((item) => {
    const key = batchKey(item)
    if (key && !(key in batchOptionsMap.value)) loadBatchesForRow(item)
  })
}, { deep: true })

const isReadOnly = computed(() => {
  if (!isEdit.value) return false
  if (isKhanalFoods.value && doc.value?.warehouse_awaiting_kf) return false
  return docStatus.value !== 'Draft'
})

const canDelete = computed(() => {
  if (!isEdit.value || !isKhanalFoods.value) return false
  const d = doc.value
  if (!d) return false
  if ((d.sap_request_doc_entry || '').trim() || (d.sap_doc_entry || '').trim()) return false
  if (isManager) return ['Draft', 'Pending Approval', 'Approved', 'Rejected'].includes(docStatus.value)
  return d.owner === session.userEmail && docStatus.value === 'Draft'
})

function addItem(item) {
  form.value.items.push({
    item_code: item.item_code,
    item_name: item.item_name || '',
    uom: 'Nos',
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    batch_number: '',
    batches: [{ batch_number: '', qty: 0 }],
  })
  const row = form.value.items[form.value.items.length - 1]
  loadBatchesForRow(row)
}

function addBlankRow() {
  form.value.items.push({
    item_code: '',
    item_name: '',
    uom: 'Nos',
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    batch_number: '',
    batches: [{ batch_number: '', qty: 0 }],
  })
}

function addBatch(item) {
  if (!item.batches) item.batches = []
  item.batches.push({ batch_number: '', qty: 0 })
}

function removeBatch(item, batchIdx) {
  if (!item.batches || item.batches.length <= 1) return
  item.batches.splice(batchIdx, 1)
}

function validateForm() {
  if (!form.value.fba_transfer_name || !String(form.value.fba_transfer_name).trim()) {
    notify.error('Transfer Name is required')
    return false
  }
  if (!form.value.doc_date) {
    notify.error('Doc Date is required')
    return false
  }
  const toWh = (form.value.to_warehouse || '').trim()
  if (!toWh) {
    notify.error('To Warehouse is required')
    return false
  }
  if (!(form.value.address_line1 || '').trim()) {
    notify.error('Address Line 1 is required')
    return false
  }
  if (!(form.value.city || '').trim()) {
    notify.error('City is required')
    return false
  }
  if (!(form.value.state || '').trim()) {
    notify.error('State is required (e.g. CA)')
    return false
  }
  if (!(form.value.zip_code || '').trim()) {
    notify.error('ZIP Code is required')
    return false
  }
  if (!form.value.items.length) {
    notify.error('Add at least one item')
    return false
  }
  for (let i = 0; i < form.value.items.length; i++) {
    const row = form.value.items[i]
    if (!(row.item_code || '').trim()) {
      notify.error(`Row ${i + 1}: Item Code is required`)
      return false
    }
    const qty = rowTotalQty(row)
    if (qty <= 0) {
      notify.error(`Row ${i + 1}: Total quantity (sum of batches) must be greater than 0`)
      return false
    }
    const batches = row.batches || []
    if (!batches.length || batches.every((b) => !(Number(b.qty) || 0))) {
      notify.error(`Row ${i + 1}: Add at least one batch with quantity`)
      return false
    }
    for (const b of batches) {
      const batchNo = (b.batch_number || '').trim()
      const bQty = Number(b.qty) || 0
      if (!batchNo || bQty <= 0) {
        notify.error(`Row ${i + 1} (${row.item_code}): Each batch must have a Batch and quantity greater than 0`)
        return false
      }
      const available = getBatchAvailableQty({ ...row, batch_number: batchNo })
      if (available === 0) {
        notify.error(`Row ${i + 1} (${row.item_code}): Selected batch ${batchNo} has no available quantity in RP-FG`)
        return false
      }
      if (available != null && bQty > available) {
        notify.error(`Row ${i + 1} (${row.item_code}): Batch quantity ${bQty} exceeds available ${available} in selected batch ${batchNo}`)
        return false
      }
    }
  }
  return true
}

async function handleSave() {
  if (!validateForm()) return
  saving.value = true
  try {
    const items = []
    for (const row of form.value.items) {
      const upb = parseInt(row.number_of_units_per_box, 10) || 0
      const batches = (row.batches || []).filter((b) => (Number(b.qty) || 0) > 0)
      if (!batches.length) continue
      for (const b of batches) {
        const qty = Number(b.qty) || 0
        let boxes = parseInt(row.number_of_boxes, 10) || 0
        if (upb > 0 && boxes > 0 && upb * boxes !== qty) {
          // fallback per-line: 1 box with qty units
          boxes = 1
        }
        const lineUpb = boxes > 0 && upb > 0 && upb * boxes === qty ? upb : qty
        const lineBoxes = boxes > 0 && lineUpb * boxes === qty ? boxes : 1
        items.push({
          item_code: row.item_code,
          item_name: row.item_name,
          quantity: qty,
          uom: (row.uom || 'Nos').trim() || 'Nos',
          number_of_units_per_box: lineUpb,
          number_of_boxes: lineBoxes,
          batch_number: (b.batch_number || '').trim() || undefined,
        })
      }
    }
    const payload = {
      fba_transfer_name: (form.value.fba_transfer_name || '').trim() || undefined,
      doc_date: form.value.doc_date,
      to_warehouse: form.value.to_warehouse,
      comments: form.value.comments,
      address_line1: (form.value.address_line1 || '').trim() || undefined,
      address_line2: (form.value.address_line2 || '').trim() || undefined,
      city: (form.value.city || '').trim() || undefined,
      state: (form.value.state || '').trim() || undefined,
      zip_code: (form.value.zip_code || '').trim() || undefined,
      items,
    }
    if (isEdit.value) {
      await updateOrder(orderId.value, payload)
      notify.success('FBA Transfer updated')
    } else {
      await createOrder(payload)
      notify.success('FBA Transfer created')
    }
    router.push(listPath.value)
  } catch (e) {
    notify.error(e.response?.data?.message || 'Save failed')
  } finally {
    saving.value = false
  }
}

async function handleSubmit() {
  if (!validateForm()) return
  saving.value = true
  try {
    await submitOrder(orderId.value)
    notify.success('FBA Transfer submitted for approval')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Submit failed')
  } finally {
    saving.value = false
  }
}

async function handleApprove() {
  showApproveDialog.value = false
  saving.value = true
  try {
    await approveOrder(orderId.value)
    notify.success('Approved')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Approve failed')
  } finally {
    saving.value = false
  }
}

async function handleReject(reason) {
  showRejectDialog.value = false
  saving.value = true
  try {
    await rejectOrder(orderId.value, reason)
    notify.success('Rejected')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Reject failed')
  } finally {
    saving.value = false
  }
}

async function openPreviewModal() {
  showPreviewModal.value = true
  previewData.value = null
  try {
    previewData.value = await previewOrderSap(orderId.value)
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to load preview')
    showPreviewModal.value = false
  }
}

async function sendFromPreview() {
  await handleRetrySap()
  showPreviewModal.value = false
}

async function handleSendToSap() {
  saving.value = true
  try {
    await sendOrderToSap(orderId.value)
    notify.success('Order sent to SAP.')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Send to SAP failed')
  } finally {
    saving.value = false
  }
}

async function handleRevertToDraft() {
  saving.value = true
  try {
    await revertOrderToDraft(orderId.value)
    notify.success('Reverted to Draft')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Revert failed')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  showDeleteDialog.value = false
  saving.value = true
  try {
    await deleteOrder(orderId.value)
    notify.success('FBA Transfer deleted')
    router.push(listPath.value)
  } catch (e) {
    notify.error(e.response?.data?.message || 'Delete failed')
  } finally {
    saving.value = false
  }
}

async function handleRetrySap() {
  saving.value = true
  try {
    await retryOrderSap(orderId.value)
    notify.success('Order sent to SAP.')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Retry SAP failed')
  } finally {
    saving.value = false
  }
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

async function loadOrder() {
  loading.value = true
  try {
    const data = await fetchOrder(orderId.value)
    doc.value = data
    docStatus.value = data.status || 'Draft'
    const byCode = new Map()
    for (const i of data.items || []) {
      const code = (i.item_code || '').trim()
      if (!code) continue
      const key = code.toLowerCase()
      if (!byCode.has(key)) {
        byCode.set(key, {
          item_code: i.item_code,
          item_name: i.item_name,
          uom: i.uom || 'Nos',
          number_of_units_per_box: i.number_of_units_per_box ?? 0,
          number_of_boxes: 0,
          batches: [],
        })
      }
      const merged = byCode.get(key)
      merged.number_of_boxes += i.number_of_boxes ?? 0
      merged.batches.push({
        batch_number: i.batch_number || '',
        qty: i.quantity,
      })
    }
    const items = Array.from(byCode.values())
    items.forEach((m) => {
      const totalQty = (m.batches || []).reduce((s, b) => s + (Number(b.qty) || 0), 0)
      const totalBoxes = m.number_of_boxes || 0
      if (totalBoxes > 0 && totalQty > 0 && totalQty % totalBoxes === 0) {
        m.number_of_units_per_box = totalQty / totalBoxes
      }
    })
    form.value = {
      doc_date: data.doc_date || '',
      to_warehouse: (data.to_warehouse || '').trim(),
      fba_transfer_name: data.fba_transfer_name || data.order_name || '',
      comments: data.comments || '',
      address_line1: data.address_line1 || '',
      address_line2: data.address_line2 || '',
      city: data.city || '',
      state: data.state || '',
      zip_code: data.zip_code || '',
      items,
    }
  } catch {
    notify.error('Failed to load order')
  }
  loading.value = false
}

async function loadSapWarehouses() {
  try {
    const res = await getWarehouses()
    sapWarehouses.value = res.data || []
    if (sapWarehouses.value.length && !form.value.to_warehouse) {
      const firstDestination = toWarehouseOptions.value[0]
      if (firstDestination) form.value.to_warehouse = firstDestination.warehouse_code
    }
  } catch {
    sapWarehouses.value = []
  }
}

onMounted(async () => {
  if (isKhanalFoods.value) await loadSapWarehouses()
  if (isEdit.value) await loadOrder()
  else {
    form.value.doc_date = new Date().toISOString().slice(0, 10)
  }
})
</script>

<style scoped>
.input-field {
  @apply w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white transition;
}
.input-field-sm {
  @apply w-full px-2.5 py-1.5 border border-gray-200 rounded-md text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white transition;
}
</style>
