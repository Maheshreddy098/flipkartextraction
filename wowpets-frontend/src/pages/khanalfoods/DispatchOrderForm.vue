<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <router-link to="/khanalfoods/dispatch-orders" class="p-2 rounded-lg hover:bg-gray-200 transition text-gray-500">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </router-link>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">
            {{ isEdit ? (doc.name || orderId) : 'New Dispatch Order' }}
          </h1>
          <p class="text-sm text-gray-500 mt-0.5">Manager approves → warehouse accepts (creates Sales Order in SAP) → prepare → dispatch.</p>
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
        <template v-if="docStatus === 'Error' && isManager">
          <button @click="handleRetrySap" :disabled="saving" class="px-5 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
            {{ saving ? 'Retrying...' : 'Retry SAP' }}
          </button>
        </template>
        <button v-if="isEdit && docStatus === 'Rejected' && isKhanalFoods && isManager" @click="handleRevertToDraft" :disabled="saving" class="px-5 py-2.5 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
          Revert to Draft
        </button>
        <button
          v-if="isEdit && session.team === 'warehouse'"
          type="button"
          @click="showTicketDialog = true"
          class="px-4 py-2.5 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium shadow-sm"
        >
          Raise Ticket
        </button>
        <button
          v-if="canDelete"
          type="button"
          @click="showDeleteDialog = true"
          :disabled="saving"
          class="px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition text-sm font-medium shadow-sm"
        >
          Delete
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-gray-400 py-12 text-center">Loading...</div>

    <div v-else class="space-y-6">
      <div class="bg-white rounded-xl shadow-sm border p-6">
        <h2 class="text-base font-semibold text-gray-800 mb-4">Dispatch Order Name &amp; Customer</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Dispatch Order Name</label>
            <input v-model="form.dispatch_order_name" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="e.g. March dispatch 1" />
          </div>
          <div class="md:col-span-2 relative" ref="customerWrapper">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Customer (SAP) *</label>
            <input
              v-model="customerQuery"
              @input="onCustomerSearch"
              @focus="showCustomerDropdown = customerResults.length > 0"
              type="text"
              class="input-field"
              :class="{ 'bg-gray-50': isReadOnly }"
              :readonly="isReadOnly"
              placeholder="Type to search customer (CardCode / Name)"
            />
            <p v-if="form.card_name" class="mt-1.5 text-sm font-medium text-gray-700">Customer name: {{ form.card_name }}</p>
            <Teleport to="body">
              <div
                v-if="showCustomerDropdown && (customerResults.length || customerError)"
                data-customer-dropdown
                class="fixed z-[9999] mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto min-w-[320px]"
                :style="customerDropdownStyle"
              >
                <div v-if="customerError" class="px-4 py-3 text-sm text-red-600">{{ customerError }}</div>
                <button
                  v-for="c in customerResults"
                  :key="c.card_code"
                  type="button"
                  @mousedown.prevent="selectCustomer(c)"
                  class="w-full text-left px-4 py-2 hover:bg-blue-50 text-sm border-b border-gray-100 last:border-0"
                >
                  <span class="font-medium text-gray-900">{{ c.card_code }}</span>
                  <span class="text-gray-500 ml-2">{{ c.card_name }}</span>
                </button>
              </div>
            </Teleport>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Doc Date *</label>
            <input v-model="form.doc_date" type="date" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Due Date</label>
            <input v-model="form.doc_due_date" type="date" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" />
          </div>
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Mobile Number</label>
            <div v-if="!isReadOnly" class="flex gap-2">
              <select v-model="mobileCountryCode" class="input-field w-28 shrink-0" @change="onCountryCodeChange">
                <option value="+1">+1 (US)</option>
                <option value="+44">+44 (UK)</option>
                <option value="+91">+91 (IN)</option>
                <option value="+61">+61 (AU)</option>
                <option value="+52">+52 (MX)</option>
                <option value="+64">+64 (NZ)</option>
              </select>
              <input
                v-model="mobileLocalNumber"
                @input="formatMobileNumber"
                type="tel"
                class="input-field flex-1"
                :placeholder="mobileCountryCode === '+1' ? '(555) 123-4567' : 'Phone number'"
                maxlength="20"
              />
            </div>
            <span v-else class="text-gray-800 text-sm">{{ form.mobile_number || '—' }}</span>
          </div>
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Reference (Num at Card) *</label>
            <input
              v-model="form.num_at_card"
              class="input-field"
              :class="{ 'bg-gray-50': isReadOnly }"
              :readonly="isReadOnly"
              placeholder="e.g. Customer PO or reference"
            />
          </div>
          <div class="md:col-span-3" v-if="(form.card_code || '').trim()">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Ship-To Address (SAP) *</label>
            <div class="flex flex-wrap items-center gap-2">
              <select
                v-model="form.ship_to_code"
                class="input-field flex-1 min-w-[320px] max-w-full"
                :class="{ 'bg-gray-50': isReadOnly }"
                :disabled="isReadOnly"
              >
                <option value="">— Select address (required for Sales Order) —</option>
                <option v-for="a in customerAddresses" :key="a.address_name" :value="a.address_name" :title="fullAddressLabel(a)">
                  {{ fullAddressLabel(a) }}
                </option>
              </select>
              <button
                v-if="!isReadOnly"
                type="button"
                @click="addAddressType = 'ship'; showAddAddressModal = true"
                class="px-4 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 transition"
              >
                Add address in SAP
              </button>
            </div>
            <p v-if="addressLoading" class="mt-1 text-sm text-gray-500">Loading addresses from SAP...</p>
            <p v-if="addressError" class="mt-1 text-sm text-red-600">{{ addressError }}</p>
          </div>
          <div class="md:col-span-3" v-if="(form.card_code || '').trim()">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Bill-To Address (SAP) *</label>
            <div class="flex flex-wrap items-center gap-2">
              <select
                v-model="form.bill_to_code"
                class="input-field flex-1 min-w-[320px] max-w-full"
                :class="{ 'bg-gray-50': isReadOnly }"
                :disabled="isReadOnly"
              >
                <option value="">— Select address (required for Sales Order) —</option>
                <option v-for="a in customerAddresses" :key="'bill-' + a.address_name" :value="a.address_name" :title="fullAddressLabel(a)">
                  {{ fullAddressLabel(a) }}
                </option>
              </select>
              <button
                v-if="!isReadOnly"
                type="button"
                @click="addAddressType = 'bill'; showAddAddressModal = true"
                class="px-4 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 transition"
              >
                Add address in SAP
              </button>
            </div>
            <p v-if="addressLoading" class="mt-1 text-sm text-gray-500">Loading addresses from SAP...</p>
            <p v-if="addressError" class="mt-1 text-sm text-red-600">{{ addressError }}</p>
          </div>
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Comments *</label>
            <textarea v-model="form.comments" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" rows="2" placeholder="Required" />
          </div>
        </div>
        <div v-if="isEdit" class="mt-4 pt-4 border-t space-y-2">
          <p
            v-if="docStatus === 'Error' && isKhanalFoods"
            class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
          >
            Warehouse raised an issue (SAP error). Update customer / addresses / lines as needed, click <strong>Save</strong>, then <strong>Retry SAP</strong>.
          </p>
          <p class="text-sm text-gray-600"><span class="font-medium">Status:</span> {{ doc.status }}</p>
          <p v-if="doc.sap_doc_num" class="text-sm text-green-600">SAP Sales Order # {{ doc.sap_doc_num }}</p>
          <p v-if="doc.sap_delivery_doc_num" class="text-sm text-green-600">
            SAP Delivery Note # {{ doc.sap_delivery_doc_num }}
          </p>
          <p v-if="doc.sap_invoice_doc_num" class="text-sm text-green-600">
            SAP AR Invoice # {{ doc.sap_invoice_doc_num }}
          </p>
          <p v-if="doc.sap_sync_error" class="text-sm text-red-600">{{ doc.sap_sync_error }}</p>
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border">
        <div class="flex items-center justify-between px-6 py-4 border-b">
          <h2 class="text-base font-semibold text-gray-800">Line Items</h2>
          <p class="text-xs text-gray-400">{{ form.items.length }} item(s)</p>
          <div v-if="!isReadOnly" class="flex gap-2">
            <button type="button" @click="addBlankRow" class="px-3 py-1.5 text-sm border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50 transition">+ Add Row</button>
          </div>
        </div>
        <div v-if="!isReadOnly" class="px-6 py-3 border-b bg-gray-50/50 space-y-3">
          <p class="text-xs text-gray-600">Add items with quantity available in WO - STR or WO - FG (from SAP). Select batch per line.</p>
          <div class="flex flex-wrap gap-4 items-end">
            <div class="flex-1 min-w-[200px]">
              <label class="block text-xs font-medium text-gray-500 mb-1">Search SAP items</label>
              <ItemSearch placeholder="Search SAP items..." :clearOnSelect="true" @select="addItem" />
            </div>
          </div>
        </div>
        <div v-if="form.items.length" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50/80">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-12">#</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[100px]">Item Code</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[140px]">Item Name</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">Quantity</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">Units/Box</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">No. Boxes</th>
                <th class="px-4 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-14" title="Units/Box × No. Boxes = Quantity">Match</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[180px]">Batch (WO -FG)</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Unit Price</th>
                <th v-if="!isReadOnly" class="px-4 py-2.5 w-12"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in form.items" :key="idx" class="border-b border-gray-100 hover:bg-blue-50/30">
                <td class="px-4 py-2.5 text-gray-400 font-mono text-xs">{{ idx + 1 }}</td>
                <td class="px-4 py-2.5 font-medium text-gray-800">{{ item.item_code || '—' }}</td>
                <td class="px-4 py-2.5 text-gray-600">{{ item.item_name || '—' }}</td>
                <td class="px-4 py-2.5">
                  <span class="text-gray-800 font-medium">{{ rowTotalQty(item) }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input v-if="!isReadOnly" v-model.number="item.number_of_units_per_box" type="number" min="0" class="input-field-sm w-20" @input="onUnitsPerBoxChange(item)" />
                  <span v-else class="text-gray-600">{{ item.number_of_units_per_box ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input v-if="!isReadOnly" v-model.number="item.number_of_boxes" type="number" min="0" class="input-field-sm w-20" />
                  <span v-else class="text-gray-600">{{ item.number_of_boxes ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5 text-center align-middle">
                  <span
                    v-if="lineValid(item)"
                    class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600"
                    title="Units/Box × No. Boxes = Quantity"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-100 text-red-600"
                    title="Advisory: Units/Box × No. Boxes doesn't equal Quantity (won't block saving)"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
                  </span>
                </td>
                <td class="px-4 py-2.5 align-top">
                  <div v-if="!isReadOnly" class="space-y-2">
                    <template v-if="(item.item_code || '').trim()">
                      <div v-for="(b, bi) in (item.batches || [])" :key="bi" class="flex items-center gap-2">
                        <select
                          v-if="batchOptionsForItem(item.item_code) !== null"
                          v-model="b.batch_number"
                          class="input-field-sm w-full min-w-[140px]"
                          @focus="loadBatchesForItem(item)"
                        >
                          <option v-if="!(batchOptionsForItem(item.item_code) || []).length" value="">No batches (WO -FG)</option>
                          <option v-else value="">— Select batch (required) —</option>
                          <option v-for="opt in (batchOptionsForItem(item.item_code) || [])" :key="opt.batch_number + (opt.warehouse_code || '')" :value="opt.batch_number">
                            {{ opt.batch_number }} ({{ opt.warehouse_code }}: {{ opt.quantity }})
                          </option>
                        </select>
                        <select v-else disabled class="input-field-sm w-full min-w-[140px] bg-gray-100 text-gray-500">
                          <option>Loading batches...</option>
                        </select>
                        <input v-model.number="b.qty" type="number" min="0" step="any" class="input-field-sm w-20" placeholder="Qty" />
                        <button v-if="(item.batches || []).length > 1" type="button" @click="removeBatch(item, bi)" class="text-gray-300 hover:text-red-500 transition text-lg" title="Remove batch">&times;</button>
                      </div>
                      <button type="button" @click="addBatch(item)" class="text-xs text-blue-600 hover:underline">+ Add batch</button>
                    </template>
                    <span v-else class="text-gray-400 text-xs">Set item above</span>
                  </div>
                  <span v-else class="text-gray-600">
                    <template v-if="(item.batches || []).length">
                      {{ (item.batches || []).map((b) => `${b.batch_number || '—'} (${b.qty})`).join(', ') }}
                    </template>
                    <template v-else>—</template>
                  </span>
                </td>
                <td class="px-4 py-2.5">
                  <input
                    v-if="!isReadOnly"
                    v-model.number="item.unit_price"
                    type="number"
                    min="0"
                    step="0.01"
                    class="input-field-sm w-20"
                  />
                  <span v-else class="text-gray-800">{{ item.unit_price ?? '—' }}</span>
                </td>
                <td v-if="!isReadOnly" class="px-4 py-2.5 text-center">
                  <button @click="form.items.splice(idx, 1)" type="button" class="text-gray-300 hover:text-red-500 transition text-lg">&times;</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="form.items.length && !isReadOnly" class="px-6 py-2 text-xs text-gray-500 border-t border-gray-100">
            <strong>Match</strong> column: advisory check — green tick when Units/Box × No. Boxes equals Quantity, but won't block saving. Batch quantities cannot exceed available in WO -FG.
          </p>
        </div>
        <div v-if="!form.items.length" class="px-6 py-12 text-center text-gray-400 text-sm">No items. Search and add from SAP (WO -FG).</div>
      </div>
    </div>

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Dispatch Order"
      message="Approve for warehouse? They will create the Sales Order in SAP when they accept the order."
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />
    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Dispatch Order"
      :message="`Reject ${doc.name || orderId}? Provide a reason:`"
      confirm-text="Reject"
      variant="danger"
      show-input
      input-placeholder="Reason"
      @confirm="handleReject"
      @cancel="showRejectDialog = false"
    />
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="Delete Dispatch Order"
      :message="`Permanently delete '${doc.name || orderId}'? This cannot be undone.`"
      confirm-text="Delete"
      variant="danger"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <KFAttachments
      doctype="WowPets Dispatch Order"
      :docname="orderId"
    />

    <TicketDialog
      :visible="showTicketDialog"
      title="Raise Ticket for Dispatch Order"
      section="Dispatch Order"
      reference-doctype="WowPets Dispatch Order"
      :reference-name="orderId"
      :submitting="ticketSubmitting"
      @submit="handleTicketSubmit"
      @cancel="showTicketDialog = false"
    />

    <!-- Add Ship-To or Bill-To Address in SAP -->
    <Teleport to="body">
      <div v-if="showAddAddressModal" class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/40 p-4" @click.self="showAddAddressModal = false">
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
          <h3 class="text-lg font-semibold text-gray-900">{{ addAddressType === 'bill' ? 'Add Bill-To Address in SAP' : 'Add Ship-To Address in SAP' }}</h3>
          <p class="text-sm text-gray-600">New {{ addAddressType === 'bill' ? 'Bill-To' : 'Ship-To' }} address will be added for customer {{ form.card_code }}. Then select it above.</p>
          <div class="space-y-3">
            <div>
              <label class="block text-sm font-medium text-gray-600 mb-1">Address name (e.g. Main, Warehouse 1) *</label>
              <input v-model="newAddress.address_name" class="input-field w-full" placeholder="e.g. Main" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-600 mb-1">Street *</label>
              <input v-model="newAddress.street" class="input-field w-full" placeholder="Street address" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-600 mb-1">City</label>
                <input v-model="newAddress.city" class="input-field w-full" placeholder="City" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-600 mb-1">State</label>
                <input v-model="newAddress.state" class="input-field w-full" placeholder="State (optional – SAP uses state master)" />
                <p class="mt-0.5 text-xs text-gray-500">Leave blank if your state is not in SAP’s list; you can set it later in SAP.</p>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-600 mb-1">Zip</label>
                <input v-model="newAddress.zip_code" class="input-field w-full" placeholder="Zip" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-600 mb-1">Country</label>
                <input v-model="newAddress.country" class="input-field w-full" placeholder="Country" />
              </div>
            </div>
          </div>
          <p v-if="addAddressError" class="text-sm text-red-600">{{ addAddressError }}</p>
          <div class="flex justify-end gap-2 pt-2">
            <button type="button" @click="showAddAddressModal = false" class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">Cancel</button>
            <button type="button" @click="handleAddAddress" :disabled="addingAddress" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium">
              {{ addingAddress ? 'Adding...' : 'Add in SAP' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  fetchDispatchOrder,
  createDispatchOrder,
  updateDispatchOrder,
  submitDispatchOrder,
  approveDispatchOrder,
  rejectDispatchOrder,
  retryDispatchOrderSap,
  revertDispatchOrderToDraft,
  searchSAPCustomers,
  getCustomerAddresses,
  addCustomerAddress,
  getBatchesForDispatchItem,
  warehouseRequestKfAssistanceDispatch,
  deleteDispatchOrder,
} from '@/core/api/dispatchOrders.js'
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

const loading = ref(false)
const saving = ref(false)
const docStatus = ref('')
const doc = ref({})
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const showDeleteDialog = ref(false)
const customerQuery = ref('')
const customerResults = ref([])
const customerError = ref('')
const showCustomerDropdown = ref(false)
const customerWrapper = ref(null)
const customerDropdownStyle = ref({ top: '0', left: '0', width: '320px' })
let customerDebounce = null

const mobileCountryCode = ref('+1')
const mobileLocalNumber = ref('')

watch([mobileCountryCode, mobileLocalNumber], () => {
  const local = mobileLocalNumber.value.trim()
  form.value.mobile_number = local ? `${mobileCountryCode.value} ${local}` : ''
})

function formatMobileNumber() {
  if (mobileCountryCode.value !== '+1') return
  const digits = mobileLocalNumber.value.replace(/\D/g, '').slice(0, 10)
  if (!digits) { mobileLocalNumber.value = ''; return }
  if (digits.length <= 3) {
    mobileLocalNumber.value = `(${digits}`
  } else if (digits.length <= 6) {
    mobileLocalNumber.value = `(${digits.slice(0, 3)}) ${digits.slice(3)}`
  } else {
    mobileLocalNumber.value = `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
  }
}

function onCountryCodeChange() {
  mobileLocalNumber.value = ''
}

const form = ref({
  dispatch_order_name: '',
  card_code: '',
  card_name: '',
  doc_date: new Date().toISOString().slice(0, 10),
  doc_due_date: new Date().toISOString().slice(0, 10),
  num_at_card: '',
  ship_to_code: '',
  bill_to_code: '',
  comments: '',
  mobile_number: '',
  items: [],
})
const customerAddresses = ref([])
const addressLoading = ref(false)
const addressError = ref('')
const showAddAddressModal = ref(false)
const addAddressType = ref('ship') // 'ship' | 'bill'
const newAddress = ref({ address_name: '', street: '', city: '', state: '', zip_code: '', country: '' })
const addingAddress = ref(false)
const addAddressError = ref('')
const batchOptionsMap = ref({})
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

function rowTotalQty(item) {
  if (item.batches && item.batches.length) {
    return item.batches.reduce((s, b) => s + (Number(b.qty) || 0), 0)
  }
  return 0
}

function addBatch(item) {
  if (!item.batches) item.batches = []
  item.batches.push({ batch_number: '', qty: 0 })
}

function removeBatch(item, batchIdx) {
  if (!item.batches || item.batches.length <= 1) return
  item.batches.splice(batchIdx, 1)
}

const isReadOnly = computed(() => {
  if (!isEdit.value) return false
  if (isKhanalFoods.value && doc.value?.warehouse_awaiting_kf) return false
  if (docStatus.value === 'Draft') return false
  // After warehouse ticket / SAP failure: KhanalFoods can fix data then Save + Retry SAP
  if (docStatus.value === 'Error' && isKhanalFoods.value) return false
  return true
})

function updateCustomerDropdownPos() {
  nextTick(() => {
    if (!customerWrapper.value) return
    const r = customerWrapper.value.getBoundingClientRect()
    customerDropdownStyle.value = { top: `${r.bottom + 4}px`, left: `${r.left}px`, width: `${Math.max(r.width, 320)}px` }
  })
}

function onCustomerSearch() {
  clearTimeout(customerDebounce)
  customerError.value = ''
  if (customerQuery.value.length < 2) {
    customerResults.value = []
    showCustomerDropdown.value = false
    return
  }
  customerDebounce = setTimeout(async () => {
    try {
      const res = await searchSAPCustomers(customerQuery.value)
      if (res.error) {
        customerError.value = res.error
        customerResults.value = []
      } else {
        customerResults.value = res.data || []
      }
      showCustomerDropdown.value = true
      updateCustomerDropdownPos()
    } catch (e) {
      customerError.value = e.response?.data?.message || 'Search failed'
      customerResults.value = []
      showCustomerDropdown.value = true
      updateCustomerDropdownPos()
    }
  }, 300)
}

function selectCustomer(c) {
  form.value.card_code = c.card_code
  form.value.card_name = (c.card_name || '').trim() || c.card_code
  form.value.ship_to_code = ''
  form.value.bill_to_code = ''
  customerQuery.value = c.card_code
  showCustomerDropdown.value = false
  customerResults.value = []
  fetchAddresses()
}

/** Full address line for Ship-To dropdown: name + street, city, state zip, country */
function fullAddressLabel(a) {
  if (!a) return ''
  const name = (a.address_name || '').trim()
  const parts = [(a.street || '').trim(), (a.city || '').trim(), (a.state || '').trim(), (a.zip_code || '').trim(), (a.country || '').trim()].filter(Boolean)
  const fullAddr = parts.join(', ')
  if (!fullAddr) return name || '—'
  return name ? `${name} — ${fullAddr}` : fullAddr
}

async function fetchAddresses() {
  const code = (form.value.card_code || '').trim()
  if (!code) {
    customerAddresses.value = []
    addressError.value = ''
    return
  }
  addressLoading.value = true
  addressError.value = ''
  try {
    const res = await getCustomerAddresses(code)
    if (res.error) {
      addressError.value = res.error
      customerAddresses.value = []
    } else {
      customerAddresses.value = res.data || []
    }
  } catch (e) {
    addressError.value = e.response?.data?.message || 'Failed to load addresses'
    customerAddresses.value = []
  } finally {
    addressLoading.value = false
  }
}

async function handleAddAddress() {
  addAddressError.value = ''
  const name = (newAddress.value.address_name || '').trim()
  const street = (newAddress.value.street || '').trim()
  if (!name) {
    addAddressError.value = 'Address name is required'
    return
  }
  if (!street) {
    addAddressError.value = 'Street is required'
    return
  }
  const code = (form.value.card_code || '').trim()
  if (!code) {
    addAddressError.value = 'Customer is required'
    return
  }
  addingAddress.value = true
  const isBillTo = addAddressType.value === 'bill'
  const sapAddressType = isBillTo ? 'bo_BillTo' : 'bo_ShipTo'
  try {
    const res = await addCustomerAddress(code, {
      address_name: name,
      street,
      city: (newAddress.value.city || '').trim(),
      state: (newAddress.value.state || '').trim(),
      zip_code: (newAddress.value.zip_code || '').trim(),
      country: (newAddress.value.country || '').trim(),
    }, sapAddressType)
    const addedName = (res && res.address_name) || name
    showAddAddressModal.value = false
    newAddress.value = { address_name: '', street: '', city: '', state: '', zip_code: '', country: '' }
    await fetchAddresses()
    if (isBillTo) {
      form.value.bill_to_code = addedName
    } else {
      form.value.ship_to_code = addedName
    }
    notify.success(res?.message || (isBillTo ? 'Bill-To address added in SAP. Select it above.' : 'Ship-To address added in SAP. Select it above.'))
  } catch (e) {
    addAddressError.value = e.response?.data?.message || e.message || 'Failed to add address in SAP'
  } finally {
    addingAddress.value = false
  }
}

function batchOptionsForItem(itemCode) {
  const key = (itemCode || '').trim()
  return key ? (batchOptionsMap.value[key] ?? null) : null
}

async function loadBatchesForItem(item) {
  const code = (item?.item_code || '').trim()
  if (!code || code in batchOptionsMap.value) return
  batchOptionsMap.value = { ...batchOptionsMap.value, [code]: null }
  try {
    const res = await getBatchesForDispatchItem(code)
    batchOptionsMap.value = { ...batchOptionsMap.value, [code]: res.data || [] }
  } catch {
    batchOptionsMap.value = { ...batchOptionsMap.value, [code]: [] }
  }
}

function onUnitsPerBoxChange(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  if (upb > 0 && qty > 0) item.number_of_boxes = Math.round(qty / upb)
}

/** Row valid when Units/Box × No. Boxes equals total quantity (sum of batch qtys). */
function lineValid(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  const boxes = Number(item.number_of_boxes) || 0
  return qty > 0 && upb > 0 && boxes > 0 && Math.abs(upb * boxes - qty) < 0.001
}

function addItem(item) {
  form.value.items.push({
    item_code: item.item_code,
    item_name: item.item_name || '',
    unit_price: 0,
    uom: item.uom || 'Nos',
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    batches: [{ batch_number: '', qty: 1 }],
  })
  loadBatchesForItem(form.value.items[form.value.items.length - 1])
}

function addBlankRow() {
  form.value.items.push({
    item_code: '',
    item_name: '',
    unit_price: 0,
    uom: 'Nos',
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    batches: [{ batch_number: '', qty: 0 }],
  })
}

/** Flatten form items (one row per item with batches) to API payload (one line per batch). */
function buildDispatchItemsPayload() {
  const lines = []
  for (const row of form.value.items || []) {
    const code = (row.item_code || '').trim()
    if (!code) continue
    const batches = (row.batches || []).filter((b) => (Number(b.qty) || 0) > 0 && (b.batch_number || '').trim())
    if (!batches.length) continue
    const totalBatchQty = batches.reduce((s, b) => s + (Number(b.qty) || 0), 0)
    const userUnitsPerBox = parseInt(row.number_of_units_per_box, 10) || 0
    const userBoxes = parseInt(row.number_of_boxes, 10) || 0
    const unitPrice = Number(row.unit_price) || 0
    const uom = row.uom || 'Nos'

    if (batches.length === 1) {
      const b = batches[0]
      const wh = resolveWarehouseForBatch(code, (b.batch_number || '').trim())
      lines.push({
        item_code: code,
        item_name: row.item_name || '',
        quantity: Number(b.qty) || 0,
        number_of_units_per_box: userUnitsPerBox,
        number_of_boxes: userBoxes,
        batch_number: (b.batch_number || '').trim(),
        warehouse_code: wh,
        unit_price: unitPrice,
        uom,
      })
      continue
    }

    const totalBoxes = userBoxes || 0
    let boxesPerBatch
    if (totalBoxes > 0 && totalBatchQty > 0) {
      boxesPerBatch = batches.map((b) => {
        const q = Number(b.qty) || 0
        return Math.max(0, Math.round(totalBoxes * (q / totalBatchQty)))
      })
      let sum = boxesPerBatch.reduce((a, x) => a + x, 0)
      if (sum !== totalBoxes) {
        const diff = totalBoxes - sum
        const idx = diff > 0 ? boxesPerBatch.findIndex((x) => x >= 0) : boxesPerBatch.length - 1
        if (idx >= 0) boxesPerBatch[idx] = (boxesPerBatch[idx] || 0) + diff
      }
    } else {
      boxesPerBatch = batches.map((b) => (userUnitsPerBox > 0 ? Math.round((Number(b.qty) || 0) / userUnitsPerBox) : 0))
    }

    batches.forEach((b, i) => {
      const qty = Number(b.qty) || 0
      const boxes = boxesPerBatch[i] || 0
      const wh = resolveWarehouseForBatch(code, (b.batch_number || '').trim())
      lines.push({
        item_code: code,
        item_name: row.item_name || '',
        quantity: qty,
        // Backend requires the same Units/Box across all rows for an item.
        number_of_units_per_box: userUnitsPerBox,
        number_of_boxes: boxes,
        batch_number: (b.batch_number || '').trim(),
        warehouse_code: wh,
        unit_price: unitPrice,
        uom,
      })
    })
  }
  return lines
}

/** Resolve SAP warehouse code for a selected batch from batch options (WO - STR / WO - FG). */
function resolveWarehouseForBatch(itemCode, batchNumber) {
  const opts = batchOptionsForItem(itemCode) || []
  const bn = (batchNumber || '').trim()
  if (!bn) return ''
  const match = opts.find((o) => (o.batch_number || '').trim() === bn)
  return match ? (match.warehouse_code || '').trim() : ''
}

function getBatchAvailableQty(itemCode, batchNumber) {
  const list = batchOptionsForItem(itemCode) || []
  const bn = (batchNumber || '').trim()
  if (!bn) return null
  const match = list.find((b) => (b.batch_number || '').trim() === bn)
  if (!match) return null
  const qty = Number(match.quantity)
  return Number.isFinite(qty) ? qty : null
}

function validateForm() {
  if (!(form.value.card_code || '').trim()) {
    notify.error('Customer (SAP) is required')
    return false
  }
  if (!(form.value.ship_to_code || '').trim()) {
    notify.error('Ship-To address (SAP) is required. Select an address or add one in SAP.')
    return false
  }
  if (!(form.value.bill_to_code || '').trim()) {
    notify.error('Bill-To address (SAP) is required. Select an address or add one in SAP.')
    return false
  }
  if (!form.value.doc_date) {
    notify.error('Doc Date is required')
    return false
  }
  if (!(form.value.num_at_card || '').trim()) {
    notify.error('Reference (Num at Card) is required')
    return false
  }
  if (!(form.value.comments || '').trim()) {
    notify.error('Comments are required')
    return false
  }
  const itemsToValidate = (form.value.items || []).filter((row) => (row.item_code || '').trim())
  if (!itemsToValidate.length) {
    notify.error('Add at least one line item with Item Code')
    return false
  }
  for (let i = 0; i < itemsToValidate.length; i++) {
    const row = itemsToValidate[i]
    if (!(row.item_code || '').trim()) {
      notify.error(`Row ${i + 1}: Item Code is required`)
      return false
    }
    const batches = (row.batches || []).filter((b) => (Number(b.qty) || 0) > 0)
    if (!batches.length || batches.every((b) => !(b.batch_number || '').trim())) {
      notify.error(`Row ${i + 1} (${row.item_code}): Add at least one batch with quantity and select batch from WO - STR / WO - FG`)
      return false
    }
    for (const b of batches) {
      if (!(b.batch_number || '').trim()) {
        notify.error(`Row ${i + 1} (${row.item_code}): Every batch must have a batch selected`)
        return false
      }
      const available = getBatchAvailableQty(row.item_code, b.batch_number)
      const q = Number(b.qty) || 0
      if (available != null && q > available) {
        notify.error(`Row ${i + 1} (${row.item_code}): Batch ${b.batch_number} quantity ${q} exceeds available ${available}. Reduce or select another batch.`)
        return false
      }
    }
    const totalQty = rowTotalQty(row)
    if (totalQty <= 0) {
      notify.error(`Row ${i + 1}: Total quantity must be greater than 0`)
      return false
    }
    if (Number(row.unit_price) <= 0) {
      notify.error(`Row ${i + 1}: Unit Price is required and must be greater than 0`)
      return false
    }
  }
  return true
}

async function loadDoc() {
  if (!orderId.value) return
  loading.value = true
  try {
    const res = await fetchDispatchOrder(orderId.value)
    doc.value = res
    docStatus.value = res.status || ''
    form.value.dispatch_order_name = res.dispatch_order_name || ''
    form.value.card_code = res.card_code || ''
    form.value.card_name = res.card_name || ''
    form.value.doc_date = (res.doc_date || '').toString().slice(0, 10)
    form.value.doc_due_date = (res.doc_due_date || res.doc_date || '').toString().slice(0, 10)
    form.value.num_at_card = res.num_at_card || ''
    form.value.ship_to_code = res.ship_to_code || ''
    form.value.bill_to_code = res.bill_to_code || ''
    form.value.comments = res.comments || ''
    const rawMobile = res.mobile_number || ''
    form.value.mobile_number = rawMobile
    if (rawMobile) {
      const match = rawMobile.match(/^(\+\d+)\s+(.+)$/)
      if (match) {
        mobileCountryCode.value = match[1]
        mobileLocalNumber.value = match[2]
      } else {
        mobileCountryCode.value = '+1'
        mobileLocalNumber.value = rawMobile
      }
    } else {
      mobileCountryCode.value = '+1'
      mobileLocalNumber.value = ''
    }
    const flatItems = res.items || []
    const byItemCode = new Map()
    for (const r of flatItems) {
      const code = (r.item_code || '').trim()
      if (!code) continue
      if (!byItemCode.has(code)) {
        byItemCode.set(code, {
          item_code: code,
          item_name: r.item_name || '',
          unit_price: Number(r.unit_price) || 0,
          uom: r.uom || 'Nos',
          number_of_units_per_box: Number(r.number_of_units_per_box) || 0,
          number_of_boxes: 0,
          batches: [],
        })
      }
      const item = byItemCode.get(code)
      item.batches.push({
        batch_number: r.batch_number || '',
        qty: Number(r.quantity) || 0,
      })
      item.number_of_units_per_box = item.number_of_units_per_box || Number(r.number_of_units_per_box) || 0
      item.number_of_boxes += Number(r.number_of_boxes) || 0
      item.unit_price = Number(r.unit_price) || item.unit_price || 0
    }
    form.value.items = Array.from(byItemCode.values())
    customerQuery.value = res.card_code || ''
    if ((form.value.card_code || '').trim()) fetchAddresses()
    form.value.items.forEach((it) => loadBatchesForItem(it))
  } catch {
    notify.error('Failed to load dispatch order')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!validateForm()) return
  saving.value = true
  const payload = { ...form.value, items: buildDispatchItemsPayload() }
  try {
    if (isEdit.value) {
      await updateDispatchOrder(orderId.value, payload)
      notify.success('Dispatch order updated')
      await loadDoc()
    } else {
      const created = await createDispatchOrder(payload)
      notify.success('Dispatch order created')
      router.push(`/khanalfoods/dispatch-orders/${created.name}`)
      return
    }
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
    // Persist current form (including batches, Units/Box and No. Boxes) before submitting,
    // so the server doc that is validated on submit has the latest values.
    const items = buildDispatchItemsPayload()
    const payload = { ...form.value, items }
    await updateDispatchOrder(orderId.value, payload)
    await submitDispatchOrder(orderId.value)
    notify.success('Submitted for approval')
    await loadDoc()
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
    await approveDispatchOrder(orderId.value)
    notify.success('Approved – warehouse can accept to create Sales Order in SAP')
    await loadDoc()
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
    await rejectDispatchOrder(orderId.value, reason)
    notify.success('Rejected')
    await loadDoc()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Reject failed')
  } finally {
    saving.value = false
  }
}

async function handleRevertToDraft() {
  saving.value = true
  try {
    await revertDispatchOrderToDraft(orderId.value)
    notify.success('Reverted to Draft')
    await loadDoc()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Revert failed')
  } finally {
    saving.value = false
  }
}

const canDelete = computed(() => {
  if (!isEdit.value || !isKhanalFoods.value) return false
  const d = doc.value
  if (!d) return false
  if ((d.sap_doc_entry || '').trim()) return false
  if (isManager) return ['Draft', 'Pending Approval', 'Approved', 'Rejected'].includes(docStatus.value)
  return d.owner === session.userEmail && docStatus.value === 'Draft'
})

async function handleDelete() {
  showDeleteDialog.value = false
  saving.value = true
  try {
    await deleteDispatchOrder(orderId.value)
    notify.success('Dispatch Order deleted')
    router.push('/khanalfoods/dispatch-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Delete failed')
  } finally {
    saving.value = false
  }
}

async function handleRetrySap() {
  saving.value = true
  try {
    await retryDispatchOrderSap(orderId.value)
    notify.success('Sales Order posted — dispatch order is now Accepted for warehouse to continue.')
    await loadDoc()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Retry failed')
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
    if (session.team === 'warehouse' && orderId.value) {
      await warehouseRequestKfAssistanceDispatch(orderId.value)
    }
    notify.success('Ticket raised')
    showTicketDialog.value = false
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to raise ticket')
  } finally {
    ticketSubmitting.value = false
  }
}

function onClickOutside(e) {
  if (customerWrapper.value && !customerWrapper.value.contains(e.target) && !e.target.closest('[data-customer-dropdown]')) {
    showCustomerDropdown.value = false
  }
}

onMounted(() => {
  loadDoc()
  document.addEventListener('click', onClickOutside)
})
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>
