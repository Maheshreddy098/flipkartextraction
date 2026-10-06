<template>
  <div class="po-form w-full px-4 sm:px-6 py-6">
    <!-- Header -->
    <header class="flex flex-wrap items-center justify-between gap-4 mb-8">
      <div class="flex items-center gap-3 min-w-0">
        <router-link
          to="/khanalfoods/purchase-orders"
          class="po-form__back flex-shrink-0 p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition"
          aria-label="Back to list"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </router-link>
        <div class="min-w-0">
          <h1 class="text-xl sm:text-2xl font-semibold text-gray-900 truncate">
            {{ isEdit ? (form.purchase_order_name || poId) : 'New Purchase Order' }}
          </h1>
          <p v-if="!isEdit" class="text-sm text-gray-500 mt-0.5">Add items from SAP and submit for approval</p>
          <StatusBadge v-else-if="docStatus" :status="docStatus" class="mt-1" />
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button type="button" @click="$router.back()" class="btn btn--secondary">
          {{ isReadOnly ? 'Back' : 'Cancel' }}
        </button>
        <template v-if="!isReadOnly">
          <button @click="handleSave" :disabled="saving" class="btn btn--primary">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
          <button v-if="isEdit && docStatus === 'Draft' && session.isProcurement && !session.isProcurementManager" @click="handleSubmitForApproval" :disabled="saving" class="btn btn--accent">
            Submit for Approval
          </button>
        </template>
        <template v-if="docStatus === 'Pending Approval' && session.isProcurementManager">
          <button @click="showApproveDialog = true" class="btn btn--success">Approve</button>
          <button @click="showRejectDialog = true" class="btn btn--danger">Reject</button>
        </template>
        <template v-if="docStatus === 'Rejected' && session.isProcurement">
          <button @click="handleRevertToDraft" :disabled="saving" class="btn btn--warning">Revert to Draft</button>
        </template>
        <button
          v-if="isEdit && session.team === 'warehouse'"
          type="button"
          @click="showTicketDialog = true"
          class="btn btn--secondary"
        >
          Raise Ticket
        </button>
        <button
          v-if="canDelete"
          type="button"
          @click="showDeleteDialog = true"
          :disabled="saving"
          class="btn btn--danger"
        >
          Delete
        </button>
      </div>
    </header>

    <div v-if="loading" class="flex flex-col items-center justify-center py-16 text-gray-500">
      <svg class="w-10 h-10 animate-spin text-blue-500 mb-3" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      <span class="text-sm">Loading...</span>
    </div>

    <div v-else class="space-y-6">
      <!-- Warehouse Hold Banner -->
      <div v-if="isEdit && doc.warehouse_awaiting_kf" class="flex flex-wrap items-center justify-between gap-3 px-4 py-3 rounded-xl bg-amber-50 border border-amber-200">
        <div class="flex items-center gap-2 text-amber-800">
          <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
          <span class="text-sm font-medium">Warehouse raised a support ticket — this PO is on hold pending your action.</span>
        </div>
        <button
          v-if="session.team === 'khanalfoods' || session.isProcurement"
          type="button"
          @click="handleReleaseHold"
          :disabled="saving"
          class="px-3 py-1.5 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition disabled:opacity-50"
        >{{ saving ? 'Releasing...' : 'Release Hold' }}</button>
      </div>

      <!-- Order Details Card -->
      <section class="card">
        <h2 class="card__title">Order Details</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="field md:col-span-3">
            <label class="field__label">Order Name *</label>
            <input
              v-model="form.purchase_order_name"
              class="input-field"
              :class="{ 'bg-gray-50': isReadOnly }"
              :readonly="isReadOnly"
              placeholder="e.g. March Nulo replenishment 1"
            />
          </div>
          <div class="field">
            <label class="field__label">Vendor</label>
            <VendorSearch
              v-if="!isReadOnly"
              :initial-value="form.vendor_code || form.supplier_name"
              placeholder="Search SAP vendor..."
              :clear-on-select="false"
              @select="onVendorSelect"
            />
            <div v-else class="input-field bg-gray-50 border-gray-200">
              <p class="text-sm font-medium text-gray-800">{{ form.vendor_code || form.supplier_name }}</p>
              <p v-if="form.vendor_name" class="text-xs text-gray-600 mt-0.5">{{ form.vendor_name }}</p>
            </div>
            <p v-if="!isReadOnly && form.vendor_name" class="text-xs text-gray-600 mt-0.5">{{ form.vendor_name }}</p>
          </div>
          <div class="field">
            <label class="field__label">Posting Date</label>
            <input v-model="form.posting_date" type="date" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" />
          </div>
          <div class="field">
            <label class="field__label">Vendor Reference No *</label>
            <input
              v-model="form.vendor_ref_no"
              class="input-field"
              :class="{ 'bg-gray-50': isReadOnly }"
              :readonly="isReadOnly"
              :required="!isReadOnly"
              placeholder="e.g. PO-12345"
            />
          </div>
          <div class="field md:col-span-3">
            <label class="field__label">Remarks *</label>
            <input v-model="form.remarks" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" placeholder="Required" />
          </div>
        </div>
        <!-- /grid -->
        <div v-if="isEdit && (doc.created_by_user || doc.approved_by || doc.accepted_by)" class="grid grid-cols-1 md:grid-cols-3 gap-5 mt-5 pt-5 border-t border-gray-100">
          <div v-if="doc.created_by_user" class="field">
            <label class="field__label text-gray-400">Created By</label>
            <p class="text-sm text-gray-700">{{ doc.created_by_user }}</p>
          </div>
          <div v-if="doc.approved_by" class="field">
            <label class="field__label text-gray-400">Approved By</label>
            <p class="text-sm text-gray-700">{{ doc.approved_by }}</p>
          </div>
          <div v-if="doc.accepted_by" class="field">
            <label class="field__label text-gray-400">Accepted By</label>
            <p class="text-sm text-gray-700">{{ doc.accepted_by }}</p>
          </div>
        </div>
        <div v-if="isEdit && ['Approved', 'Accepted', 'Received'].includes(docStatus)" class="mt-5 pt-5 border-t border-gray-100">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">SAP B1</h3>
          <p class="text-xs text-gray-500 mb-2">PO is posted to SAP when Procurement Manager approves. After warehouse marks as received, KhanalFoods team reviews and manually posts GRN to SAP.</p>
          <div class="space-y-2">
            <div class="flex flex-wrap items-center gap-2">
              <span v-if="doc.sap_po_doc_entry || doc.sap_grpo_doc_entry || doc.sap_inventory_transfer_doc_entry" class="text-sm font-medium text-green-600">Posted to SAP</span>
              <span v-else-if="doc.sap_sync_status === 'Error'" class="text-sm font-medium text-red-600">SAP sync failed</span>
              <span v-else class="text-sm font-medium text-amber-600">Not sent to SAP</span>
            </div>
            <div v-if="doc.sap_po_doc_entry || doc.sap_grpo_doc_entry || doc.sap_inventory_transfer_doc_entry" class="text-sm text-gray-700">
              <span v-if="doc.sap_po_doc_entry">SAP PO # <strong>{{ doc.sap_po_doc_num || doc.sap_po_doc_entry }}</strong></span>
              <span v-if="doc.sap_grpo_doc_entry" class="ml-3">SAP GRN # <strong>{{ doc.sap_grpo_doc_num || doc.sap_grpo_doc_entry }}</strong></span>
              <span v-if="doc.sap_inventory_transfer_doc_entry" class="ml-3">SAP Transfer # <strong>{{ doc.sap_inventory_transfer_doc_entry }}</strong></span>
            </div>
            <p v-if="doc.sap_sync_status === 'Error' && doc.sap_sync_error" class="text-sm text-red-600">{{ doc.sap_sync_error }}</p>
            <div v-if="!doc.sap_po_doc_entry && !doc.sap_grpo_doc_entry && !doc.sap_inventory_transfer_doc_entry" class="flex flex-wrap items-center gap-2">
              <button type="button" @click="handleRetrySapSync" :disabled="saving" class="px-3 py-1.5 text-sm bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 transition">
                {{ saving ? 'Sending...' : 'Retry Send PO to SAP' }}
              </button>
            </div>
            <div v-else-if="doc.sap_po_doc_entry && !doc.sap_grpo_doc_entry && !doc.sap_inventory_transfer_doc_entry" class="flex flex-wrap items-center gap-2">
              <button type="button" @click="openGrnConfirm" :disabled="saving" class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
                {{ saving ? 'Posting...' : 'Review & Post GRN' }}
              </button>
            </div>
            <div v-else-if="doc.sap_grpo_doc_entry && session.isProcurement" class="flex flex-wrap items-center gap-2">
              <button type="button" @click="handleRevertGrn" :disabled="saving" class="px-3 py-1.5 text-sm bg-red-100 text-red-800 rounded-lg hover:bg-red-200 transition">
                {{ saving ? 'Reverting...' : 'Revert GRN (already cancelled in SAP)' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- GRN Review Card: KhanalFoods edits before posting GRN -->
      <section v-if="canEditGrn" class="card">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 class="card__title mb-0">GRN Review</h2>
            <p class="text-xs text-gray-500 mt-0.5">Update details before posting GRN to SAP. Accepted Qty and batch numbers are sent to SAP as-is.</p>
          </div>
          <div class="flex gap-2">
            <button type="button" @click="handleSaveGrnDetails" :disabled="savingGrn" class="btn btn--secondary btn--sm">
              {{ savingGrn ? 'Saving...' : 'Save Changes' }}
            </button>
            <button type="button" @click="openGrnConfirm" :disabled="saving" class="btn btn--primary btn--sm">
              {{ saving ? 'Posting...' : 'Review & Post GRN' }}
            </button>
          </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
          <div class="field">
            <label class="field__label">GRN Date <span class="text-red-500">*</span></label>
            <input v-model="grnForm.received_date" type="date" class="input-field" />
          </div>
          <div class="field">
            <label class="field__label">Vendor Ref No</label>
            <input v-model="grnForm.vendor_ref_no" class="input-field" placeholder="Vendor reference / invoice number" />
          </div>
          <div class="field">
            <label class="field__label">Remarks</label>
            <input v-model="grnForm.remarks" class="input-field" placeholder="Comments sent to SAP" />
          </div>
        </div>
        <div v-if="doc.sap_sync_status === 'Error' && doc.sap_sync_error" class="mb-4 p-3 rounded-lg bg-red-50 border border-red-200">
          <p class="text-sm text-red-700 font-medium">Last GRN attempt failed:</p>
          <p class="text-sm text-red-600 mt-0.5">{{ doc.sap_sync_error }}</p>
        </div>
        <div class="overflow-x-auto">
          <table class="po-table">
            <thead>
              <tr>
                <th class="po-table__th w-10">#</th>
                <th class="po-table__th min-w-[120px]">Item Code</th>
                <th class="po-table__th min-w-[220px]">Item Name</th>
                <th class="po-table__th w-24">Ordered Qty</th>
                <th class="po-table__th w-24">Accepted Qty</th>
                <th class="po-table__th min-w-[160px]">Batch Number</th>
                <th class="po-table__th min-w-[180px]">Acceptance Remarks</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in grnForm.items" :key="idx" class="po-table__row">
                <td class="po-table__cell text-gray-400 font-mono text-xs">{{ idx + 1 }}</td>
                <td class="po-table__cell font-medium text-gray-800">{{ item.item_code }}</td>
                <td class="po-table__cell text-gray-600 text-sm">{{ item.item_name }}</td>
                <td class="po-table__cell tabular-nums text-gray-700">{{ item.ordered_qty }}</td>
                <td class="po-table__cell">
                  <input v-model.number="item.accepted_qty" type="number" min="0" :max="item.ordered_qty" step="1" class="input-sm input-num" placeholder="0" />
                </td>
                <td class="po-table__cell">
                  <input v-model="item.batch_number" class="input-sm w-full" placeholder="Batch #" />
                </td>
                <td class="po-table__cell">
                  <input v-model="item.acceptance_remarks" class="input-sm w-full" placeholder="Optional" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Line Items Card -->
      <section class="card overflow-hidden">
        <div class="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div class="flex items-center gap-3">
            <h2 class="card__title mb-0">Line Items</h2>
            <span class="badge">{{ form.items.length }} item{{ form.items.length !== 1 ? 's' : '' }}</span>
          </div>
          <div v-if="!isReadOnly" class="flex items-center gap-2">
            <div class="flex-1 min-w-[200px] max-w-sm">
              <ItemSearch placeholder="Search item code or name..." :clearOnSelect="true" @select="addItem" />
            </div>
            <button type="button" @click="addBlankRow" class="btn btn--secondary btn--sm whitespace-nowrap">
              + Add row
            </button>
          </div>
        </div>

        <div v-if="form.items.length" class="overflow-x-auto">
          <table class="po-table">
            <thead>
              <tr>
                <th class="po-table__th w-10">#</th>
                <th class="po-table__th min-w-[120px]">Item Code</th>
                <th class="po-table__th min-w-[280px]">Item Name</th>
                <th class="po-table__th w-20">Qty</th>
                <th class="po-table__th w-20">UOM</th>
                <th class="po-table__th w-24">Units/Box *</th>
                <th class="po-table__th w-24">No. Boxes *</th>
                <th class="po-table__th w-28">Weight/Pcs</th>
                <th class="po-table__th w-28">Qty (Pcs)</th>
                <th class="po-table__th w-12 text-center">✓</th>
                <th v-if="showAcceptedQtyColumn" class="po-table__th w-24">Accepted Qty</th>
                <th v-if="showAcceptanceRemarksColumn" class="po-table__th min-w-[220px]">Acceptance Remarks</th>
                <th class="po-table__th w-28">Unit Price ($)</th>
                <th class="po-table__th w-32">Line Total ($)</th>
                <th class="po-table__th w-24">Warehouse</th>
                <th class="po-table__th min-w-[220px]">Batches</th>
                <th v-if="!isReadOnly" class="po-table__th w-10"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in form.items" :key="idx" class="po-table__row">
                <td class="po-table__cell text-gray-400 font-mono text-xs">{{ idx + 1 }}</td>
                <td class="po-table__cell">
                  <input
                    v-if="!isReadOnly"
                    v-model="item.item_code"
                    class="input-sm font-medium row-item-input"
                    placeholder="Code"
                    @input="onRowItemInput(item, idx, 'code')"
                    @focus="onRowItemFocus($event, idx)"
                  />
                  <span v-else class="font-medium text-gray-800">{{ item.item_code }}</span>
                </td>
                <td class="po-table__cell min-w-[280px] whitespace-normal break-words">
                  <input
                    v-if="!isReadOnly"
                    v-model="item.item_name"
                    class="input-sm row-item-input min-w-[260px]"
                    placeholder="Name"
                    @input="onRowItemInput(item, idx, 'name')"
                    @focus="onRowItemFocus($event, idx)"
                  />
                  <span v-else class="text-gray-600">{{ item.item_name }}</span>
                </td>
                <td class="po-table__cell">
                  <span class="font-semibold text-gray-800 tabular-nums">{{ rowTotalQty(item) }}</span>
                </td>
                <td class="po-table__cell">
                  <input v-if="!isReadOnly" v-model="item.uom" class="input-sm w-full max-w-[4rem]" />
                  <span v-else class="text-gray-600">{{ item.uom }}</span>
                </td>
                <td class="po-table__cell">
                  <input v-if="!isReadOnly" v-model.number="item.number_of_units_per_box" type="number" min="0" class="input-sm input-num" @input="onUnitsPerBoxChange(item)" />
                  <span v-else class="text-gray-600">{{ item.number_of_units_per_box ?? '—' }}</span>
                </td>
                <td class="po-table__cell">
                  <input v-if="!isReadOnly" v-model.number="item.number_of_boxes" type="number" min="0" class="input-sm input-num" />
                  <span v-else class="text-gray-600">{{ item.number_of_boxes ?? '—' }}</span>
                </td>
                <td class="po-table__cell">
                  <input v-if="!isReadOnly" v-model.number="item.weight_pcs" type="number" min="0" step="any" class="input-sm input-num" @input="onWeightPcsChange(item)" />
                  <span v-else class="text-gray-600">{{ item.weight_pcs ? item.weight_pcs : '—' }}</span>
                </td>
                <td class="po-table__cell">
                  <input v-if="!isReadOnly" v-model.number="item.pcs" type="number" min="0" step="any" class="input-sm input-num" @input="onPcsChange(item)" />
                  <span v-else class="text-gray-600">{{ item.pcs ? item.pcs : '—' }}</span>
                </td>
                <td class="po-table__cell text-center">
                  <span v-if="poLineValid(item)" class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-600" title="Units/box × Boxes = Qty">✓</span>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td v-if="showAcceptedQtyColumn" class="po-table__cell">
                  <span class="font-semibold text-gray-800 tabular-nums">{{ item.accepted_qty != null && item.accepted_qty !== '' ? Number(item.accepted_qty) : '—' }}</span>
                </td>
                <td v-if="showAcceptanceRemarksColumn" class="po-table__cell">
                  <span class="text-gray-600">{{ item.acceptance_remarks || '—' }}</span>
                </td>
                <td class="po-table__cell">
                  <span v-if="!isReadOnly" class="inline-flex items-center gap-1 w-full">
                    <span class="text-gray-400 text-sm">$</span>
                    <input v-model.number="item.unit_price" type="number" min="0" step="0.01" class="input-sm flex-1 min-w-0" placeholder="0" />
                  </span>
                  <span v-else class="text-gray-800 tabular-nums">$ {{ formatDollar(item.unit_price ?? item.rate) }}</span>
                </td>
                <td class="po-table__cell">
                  <span class="text-gray-700 tabular-nums font-medium">$ {{ formatDollar(rowLineTotal(item)) }}</span>
                </td>
                <td class="po-table__cell">
                  <span class="text-gray-600 text-sm font-medium">{{ PO_WAREHOUSE }}</span>
                </td>
                <td class="po-table__cell">
                  <div class="batch-list">
                    <div v-for="(b, bi) in (item.batches || [])" :key="bi" class="batch-chip">
                      <input v-if="!isReadOnly" v-model="b.batch_number" class="batch-chip__batch" placeholder="Batch" />
                      <input v-if="!isReadOnly" v-model.number="b.qty" type="number" min="0" step="any" class="batch-chip__qty" placeholder="Qty" />
                      <template v-else>
                        <span class="batch-chip__label">{{ b.batch_number || '—' }}</span>
                        <span class="batch-chip__qty-display">{{ b.qty }}</span>
                      </template>
                      <button v-if="!isReadOnly && (item.batches || []).length > 1" type="button" @click="removeBatch(item, bi)" class="batch-chip__remove" title="Remove batch" aria-label="Remove batch">×</button>
                    </div>
                    <button v-if="!isReadOnly" type="button" @click="addBatch(item)" class="batch-add">+ Add batch</button>
                  </div>
                </td>
                <td v-if="!isReadOnly" class="po-table__cell text-center">
                  <button @click="form.items.splice(idx, 1)" type="button" class="row-remove" title="Remove row" aria-label="Remove row">×</button>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="bg-gray-50/80 border-t-2 border-gray-200">
                <td :colspan="6" class="po-table__cell py-3.5 text-right font-semibold text-gray-600">Total</td>
                <td class="po-table__cell py-3.5 font-bold text-gray-900 tabular-nums" title="Total Qty">{{ totalQty }}</td>
                <td class="po-table__cell py-3.5 text-gray-400 text-xs text-center">—</td>
                <td class="po-table__cell py-3.5 font-bold text-gray-900 tabular-nums" title="Total Pcs">{{ totalPcs || '—' }}</td>
                <td :colspan="2 + (showAcceptedQtyColumn ? 1 : 0) + (showAcceptanceRemarksColumn ? 1 : 0)" class="po-table__cell"></td>
                <td class="po-table__cell py-3.5 font-bold text-gray-900 tabular-nums" title="Grand Total">$ {{ formatDollar(grandTotal) }}</td>
                <td :colspan="isReadOnly ? 2 : 3" class="po-table__cell"></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <p v-if="form.items.length && !isReadOnly" class="px-6 py-3 text-xs text-gray-500 bg-gray-50/50 border-t border-gray-100">Units/box × No. boxes should equal quantity (optional). Green check when valid.</p>
        <div v-if="!form.items.length" class="empty-state">
          <svg class="empty-state__icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8 4-8-4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>
          <p class="empty-state__text">No line items yet</p>
          <p v-if="!isReadOnly" class="empty-state__hint">Search for items above or click “Add row” to add manually</p>
        </div>
      </section>
    </div>

    <!-- Approve Dialog -->
    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Purchase Order"
      :message="`Approve ${form.purchase_order_name || poId}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <!-- Reject Dialog -->
    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Purchase Order"
      :message="`Reject ${form.purchase_order_name || poId}? Provide a reason:`"
      confirm-text="Reject"
      variant="danger"
      show-input
      input-placeholder="Reason for rejection"
      @confirm="handleReject"
      @cancel="showRejectDialog = false"
    />

    <!-- Delete Dialog -->
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="Delete Purchase Order"
      :message="`Permanently delete '${form.purchase_order_name || poId}'? This cannot be undone.`"
      confirm-text="Delete"
      variant="danger"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <!-- GRN Post Confirmation Modal -->
    <Teleport to="body">
      <div v-if="showGrnConfirm" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="closeGrnConfirm" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6">
          <h3 class="text-lg font-semibold text-gray-900">Confirm GRN Before Posting</h3>
          <p class="mt-1 text-sm text-gray-600">Verify the GRN date and line items below. This creates a real GRPO in SAP B1 — go back and edit if anything is wrong.</p>

          <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div>
              <label class="text-gray-400 block mb-1">GRN Date <span class="text-red-500">*</span></label>
              <input v-model="grnForm.received_date" type="date" class="input-field" />
            </div>
            <div>
              <span class="text-gray-400 block">Vendor Ref No</span>
              <span class="font-medium text-gray-800">{{ grnForm.vendor_ref_no || '—' }}</span>
            </div>
            <div>
              <span class="text-gray-400 block">Remarks</span>
              <span class="font-medium text-gray-800">{{ grnForm.remarks || '—' }}</span>
            </div>
          </div>

          <div class="mt-4 overflow-x-auto border border-gray-100 rounded-lg">
            <table class="po-table">
              <thead>
                <tr>
                  <th class="po-table__th">Item Code</th>
                  <th class="po-table__th">Item Name</th>
                  <th class="po-table__th">Ordered</th>
                  <th class="po-table__th">Accepted (to SAP)</th>
                  <th class="po-table__th">Batch #</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in grnForm.items" :key="idx" class="po-table__row">
                  <td class="po-table__cell font-medium text-gray-800">{{ item.item_code }}</td>
                  <td class="po-table__cell text-sm text-gray-600">{{ item.item_name }}</td>
                  <td class="po-table__cell tabular-nums">{{ item.ordered_qty }}</td>
                  <td class="po-table__cell tabular-nums font-semibold" :class="Number(item.accepted_qty) !== Number(item.ordered_qty) ? 'text-amber-600' : 'text-gray-800'">{{ item.accepted_qty }}</td>
                  <td class="po-table__cell text-sm">{{ item.batch_number || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="flex justify-end gap-3 mt-6">
            <button type="button" @click="closeGrnConfirm" class="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition">
              Go Back &amp; Edit
            </button>
            <button type="button" @click="handleCreateGrn" :disabled="saving" class="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition">
              {{ saving ? 'Posting...' : 'Confirm & Post to SAP' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Inline row item search dropdown (SAP) -->
    <Teleport to="body">
      <div
        v-if="inlineSearchVisible && (inlineSearchResults.length || inlineSearchNoResults)"
        data-inline-item-search
        class="fixed z-[9999] py-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-56 overflow-y-auto min-w-[320px]"
        :style="inlineSearchStyle"
      >
        <div v-if="inlineSearchLoading" class="px-4 py-3 text-sm text-gray-400">Searching...</div>
        <div v-else-if="inlineSearchNoResults" class="px-4 py-3 text-sm text-gray-400">No items found for "{{ inlineSearchQuery }}"</div>
        <button
          v-for="sapItem in inlineSearchResults"
          :key="sapItem.item_code"
          type="button"
          @mousedown.prevent="selectInlineItem(sapItem)"
          class="w-full text-left px-4 py-2 hover:bg-blue-50 text-sm border-b border-gray-100 last:border-0 whitespace-normal break-words"
        >
          <span class="font-medium text-gray-900">{{ sapItem.item_code }}</span>
          <span class="text-gray-500 ml-2">{{ sapItem.item_name }}</span>
          <span v-if="sapItem.uom" class="text-gray-400 ml-2 text-xs">({{ sapItem.uom }})</span>
        </button>
      </div>
    </Teleport>

    <KFAttachments
      doctype="WowPets Purchase Order"
      :docname="poId"
    />

    <TicketDialog
      :visible="showTicketDialog"
      title="Raise Ticket for Purchase Order"
      section="Purchase Order"
      reference-doctype="WowPets Purchase Order"
      :reference-name="poId"
      :submitting="ticketSubmitting"
      @submit="handleTicketSubmit"
      @cancel="showTicketDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  createPurchaseOrder, updatePurchaseOrder, fetchPurchaseOrder,
  submitPOForApproval, approvePO, rejectPO, revertPOToDraft,
  retryPOSapSync, createPOGrn, revertPOGrn, kfUpdateGrnDetails, kfReleaseWarehouseHoldPO,
  warehouseRequestKfAssistancePO, deletePurchaseOrder,
} from '@/core/api/purchaseOrders.js'
import { searchSAPItems } from '@/core/api/sapMaster.js'
import ItemSearch from '@/components/common/ItemSearch.vue'
import VendorSearch from '@/components/common/VendorSearch.vue'
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

const PO_WAREHOUSE = 'WO - STR'

const poId = computed(() => props.id || route.params.id)
const isEdit = computed(() => !!poId.value)

const loading = ref(false)
const saving = ref(false)
const savingGrn = ref(false)
const docStatus = ref('')
const doc = ref({})
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const showDeleteDialog = ref(false)

const grnForm = ref({ vendor_ref_no: '', remarks: '', received_date: '', items: [] })
const showGrnConfirm = ref(false)

const canEditGrn = computed(() =>
  isEdit.value &&
  docStatus.value === 'Received' &&
  session.isProcurement &&
  doc.value?.sap_po_doc_entry &&
  !doc.value?.sap_grpo_doc_entry &&
  !doc.value?.sap_inventory_transfer_doc_entry
)

const showAcceptedQtyColumn = computed(() => {
  if (!isEdit.value) return false
  if (docStatus.value === 'Received' || docStatus.value === 'Accepted') return true
  return (form.value.items || []).some((i) => i.accepted_qty != null && i.accepted_qty !== '')
})

const showAcceptanceRemarksColumn = computed(() => {
  if (!isEdit.value || !isReadOnly.value) return false
  return (form.value.items || []).some((i) => (i.acceptance_remarks || '').trim())
})

const inlineSearchRowIndex = ref(-1)
const inlineSearchResults = ref([])
const inlineSearchLoading = ref(false)
const inlineSearchNoResults = ref(false)
const inlineSearchQuery = ref('')
const inlineSearchStyle = ref({ top: '0', left: '0' })
let activeRowInputEl = null
let inlineSearchDebounce = null
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

const inlineSearchVisible = computed(() => inlineSearchRowIndex.value >= 0 && (inlineSearchResults.value.length > 0 || inlineSearchNoResults.value || inlineSearchLoading.value))

function onRowItemFocus(ev, idx) {
  activeRowInputEl = ev && ev.target ? ev.target : null
  inlineSearchRowIndex.value = idx
  inlineSearchResults.value = []
  inlineSearchNoResults.value = false
}

function onRowItemInput(item, idx, field) {
  const q = (field === 'code' ? (item.item_code || '') : (item.item_name || '')).trim()
  inlineSearchRowIndex.value = idx
  inlineSearchQuery.value = q
  if (q.length < 2) {
    inlineSearchResults.value = []
    inlineSearchNoResults.value = false
    if (inlineSearchDebounce) clearTimeout(inlineSearchDebounce)
    return
  }
  if (inlineSearchDebounce) clearTimeout(inlineSearchDebounce)
  inlineSearchDebounce = setTimeout(async () => {
    inlineSearchLoading.value = true
    inlineSearchNoResults.value = false
    try {
      const res = await searchSAPItems(q)
      if (res.error) {
        inlineSearchResults.value = []
      } else {
        inlineSearchResults.value = res.data || []
        inlineSearchNoResults.value = inlineSearchResults.value.length === 0
      }
      nextTick(updateInlineSearchPosition)
    } catch {
      inlineSearchResults.value = []
      inlineSearchNoResults.value = true
    }
    inlineSearchLoading.value = false
  }, 300)
}

function updateInlineSearchPosition() {
  if (!activeRowInputEl) return
  const r = activeRowInputEl.getBoundingClientRect()
  inlineSearchStyle.value = {
    top: `${r.bottom + 4}px`,
    left: `${r.left}px`,
    width: `${Math.max(r.width, 320)}px`,
  }
}

function selectInlineItem(sapItem) {
  const idx = inlineSearchRowIndex.value
  if (idx < 0 || !form.value.items[idx]) return
  const row = form.value.items[idx]
  row.item_code = sapItem.item_code
  row.item_name = sapItem.item_name
  row.uom = sapItem.uom || ''
  if (row.unit_price == null || row.unit_price === '') row.unit_price = 0
  inlineSearchRowIndex.value = -1
  inlineSearchResults.value = []
  inlineSearchNoResults.value = false
  inlineSearchQuery.value = ''
}

function onClickOutsideInlineSearch(e) {
  if (e.target.closest('[data-inline-item-search]')) return
  if (e.target.closest('.row-item-input')) return
  inlineSearchRowIndex.value = -1
  inlineSearchResults.value = []
  inlineSearchNoResults.value = false
}

const form = ref({
  vendor_code: '',
  vendor_name: '',
  supplier_name: '',
  vendor_ref_no: '',
  posting_date: new Date().toISOString().slice(0, 10),
  purchase_order_name: '',
  remarks: '',
  items: [],
})

const isReadOnly = computed(() => {
  // KhanalFoods team (non-procurement) can only view
  if (session.team === 'khanalfoods') return true
  if (!isEdit.value) return false
  // Warehouse hold: only procurement team can edit even on Accepted POs
  if (doc.value?.warehouse_awaiting_kf) return false
  // Procurement manager can edit Draft and Pending Approval
  if (session.isProcurementManager) return !['Draft', 'Pending Approval'].includes(docStatus.value)
  // Procurement user can only edit Draft
  return docStatus.value !== 'Draft'
})

function formatDollar(val) {
  if (val == null || val === '') return '—'
  const n = Number(val)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function rowTotalQty(item) {
  return (item.batches || []).reduce((s, b) => s + (Number(b.qty) || 0), 0)
}

const totalQty = computed(() =>
  form.value.items.reduce((sum, i) => sum + rowTotalQty(i), 0)
)

function addBatch(item) {
  if (!item.batches) item.batches = []
  item.batches.push({ batch_number: '', qty: 1 })
}

function removeBatch(item, batchIdx) {
  if (!item.batches || item.batches.length <= 1) return
  item.batches.splice(batchIdx, 1)
}

function onVendorSelect(payload) {
  form.value.vendor_code = payload.vendor_code ?? ''
  form.value.vendor_name = payload.vendor_name ?? ''
  form.value.supplier_name = payload.vendor_name ?? ''
}

function onUnitsPerBoxChange(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  if (upb > 0 && qty > 0) item.number_of_boxes = Math.round(qty / upb)
}

function onWeightPcsChange(item) {
  const qty = rowTotalQty(item)
  const wpcs = Number(item.weight_pcs) || 0
  if (wpcs > 0 && qty > 0) item.pcs = parseFloat((qty / wpcs).toFixed(4))
  else if (wpcs === 0) item.pcs = 0
}

function onPcsChange(item) {
  const qty = rowTotalQty(item)
  const pcs = Number(item.pcs) || 0
  if (pcs > 0 && qty > 0) item.weight_pcs = parseFloat((qty / pcs).toFixed(6))
  else if (pcs === 0) item.weight_pcs = 0
}

const totalPcs = computed(() =>
  form.value.items.reduce((sum, i) => sum + (Number(i.pcs) || 0), 0)
)

function rowLineTotal(item) {
  return rowTotalQty(item) * (Number(item.unit_price ?? item.rate) || 0)
}

const grandTotal = computed(() =>
  form.value.items.reduce((sum, i) => sum + rowLineTotal(i), 0)
)

function poLineValid(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  const boxes = Number(item.number_of_boxes) || 0
  return qty > 0 && upb > 0 && boxes > 0 && Math.abs(upb * boxes - qty) < 0.001
}

function addItem(item) {
  const code = (item.item_code || '').trim()
  const existing = form.value.items.find((r) => (r.item_code || '').trim().toLowerCase() === code.toLowerCase())
  if (existing) {
    addBatch(existing)
    return
  }
  form.value.items.push({
    item_code: item.item_code,
    item_name: item.item_name,
    uom: item.uom || '',
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    weight_pcs: 0,
    pcs: 0,
    unit_price: 0,
    tax_code: 'PA0',
    warehouse: PO_WAREHOUSE,
    batches: [{ batch_number: '', qty: 1 }],
  })
}

function addBlankRow() {
  form.value.items.push({
    item_code: '',
    item_name: '',
    uom: '',
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    weight_pcs: 0,
    pcs: 0,
    unit_price: 0,
    tax_code: 'PA0',
    warehouse: PO_WAREHOUSE,
    batches: [{ batch_number: '', qty: 1 }],
  })
}

function validateForm() {
  if (!form.value.purchase_order_name || !String(form.value.purchase_order_name).trim()) {
    notify.error('Order Name is required')
    return false
  }
  if (!form.value.vendor_code && !form.value.supplier_name) {
    notify.error('Select a vendor from SAP')
    return false
  }
  if (!form.value.vendor_ref_no || !String(form.value.vendor_ref_no).trim()) {
    notify.error('Vendor Reference No is required')
    return false
  }
  if (!form.value.posting_date) {
    notify.error('Posting Date is required')
    return false
  }
  if (!form.value.remarks || !String(form.value.remarks).trim()) {
    notify.error('Remarks are required')
    return false
  }
  if (!form.value.items.length) {
    notify.error('Add at least one item')
    return false
  }
  for (let i = 0; i < form.value.items.length; i++) {
    const row = form.value.items[i]
    if (!row.item_code || !String(row.item_code).trim()) {
      notify.error(`Row ${i + 1}: Item Code is required`)
      return false
    }
    if (row.unit_price == null || row.unit_price === '' || Number(row.unit_price) <= 0) {
      notify.error(`Row ${i + 1}: Unit Price is required and must be greater than 0`)
      return false
    }
    const batches = row.batches || []
    if (!batches.length || batches.every((b) => !(Number(b.qty) || 0))) {
      notify.error(`Row ${i + 1}: Add at least one batch with quantity`)
      return false
    }
    for (let bi = 0; bi < batches.length; bi++) {
      const b = batches[bi]
      const q = Number(b.qty) || 0
      const batchNo = (b.batch_number || '').trim()
      if (q > 0 && !batchNo) {
        notify.error(`Row ${i + 1}: Batch ${bi + 1} must have a Batch Number when quantity is set`)
        return false
      }
      if (q <= 0 && batchNo) {
        notify.error(`Row ${i + 1}: Batch ${bi + 1} must have quantity greater than 0 when Batch Number is set`)
        return false
      }
    }
    const qty = rowTotalQty(row)
    if (qty <= 0) {
      notify.error(`Row ${i + 1}: Total quantity (sum of batches) must be greater than 0`)
      return false
    }
  }
  return true
}

/** Divisors of n (positive, <= n). */
function divisors(n) {
  if (n <= 0) return []
  const out = []
  for (let d = 1; d <= n; d++) if (n % d === 0) out.push(d)
  return out
}

/**
 * Distribute totalBoxes across batches so each batch gets integer boxes and qty[i] % boxes[i] === 0.
 * Returns array of box counts (one per batch), or fallback to 1 box per batch if no valid split.
 */
function distributeBoxesAcrossBatches(qtys, totalBoxes) {
  const n = qtys.length
  if (n === 0 || totalBoxes < n) return qtys.map(() => 1)

  if (n === 1) {
    const q = qtys[0]
    if (q <= 0) return [1]
    // One batch: use totalBoxes if qty % totalBoxes === 0, else 1
    if (totalBoxes > 0 && q % totalBoxes === 0) return [totalBoxes]
    return [1]
  }

  if (n === 2) {
    const [q0, q1] = qtys
    const divs0 = divisors(q0)
    for (const d0 of divs0) {
      const d1 = totalBoxes - d0
      if (d1 > 0 && q1 % d1 === 0) return [d0, d1]
    }
    return [1, 1]
  }

  // 3+ batches: proportional then adjust so each qty % boxes === 0
  const totalQty = qtys.reduce((s, q) => s + q, 0)
  if (totalQty <= 0) return qtys.map(() => 1)
  const raw = qtys.map((q) => Math.max(1, Math.round((totalBoxes * q) / totalQty)))
  let sum = raw.reduce((s, x) => s + x, 0)
  // adjust to sum to totalBoxes (rounding can make sum !== totalBoxes)
  if (sum !== totalBoxes) {
    const diff = totalBoxes - sum
    const idx = diff > 0 ? raw.findIndex((r, i) => qtys[i] % (r + 1) === 0) : raw.findIndex((r, i) => r > 1 && qtys[i] % (r - 1) === 0)
    if (idx >= 0) {
      if (diff > 0) raw[idx] += 1
      else raw[idx] -= 1
      sum += diff
    }
  }
  const valid = raw.every((r, i) => qtys[i] % r === 0)
  if (valid && sum === totalBoxes) return raw
  // fallback: 1 per batch
  return qtys.map(() => 1)
}

async function handleSave() {
  if (!validateForm()) return
  saving.value = true
  const items = []
  for (const row of form.value.items) {
    const userUnitsPerBox = parseInt(row.number_of_units_per_box, 10) || 0
    const userBoxes = parseInt(row.number_of_boxes, 10) || 0
    const batches = (row.batches || []).filter((b) => (Number(b.qty) || 0) > 0)
    if (!batches.length) continue
    const totalBatchQty = batches.reduce((s, b) => s + (Number(b.qty) || 0), 0)

    if (batches.length === 1) {
      // Single batch: use user's values exactly
      const b = batches[0]
      const qty = Number(b.qty) || 0
      items.push({
        item_code: row.item_code,
        item_name: row.item_name,
        qty,
        uom: row.uom,
        number_of_units_per_box: userUnitsPerBox,
        number_of_boxes: userBoxes,
        weight_pcs: row.weight_pcs ?? 0,
        pcs: row.pcs ?? 0,
        rate: row.unit_price ?? row.rate ?? 0,
        unit_price: row.unit_price ?? row.rate ?? 0,
        tax_code: row.tax_code || 'PA0',
        warehouse: row.warehouse || PO_WAREHOUSE,
        batch_number: (b.batch_number || '').trim() || undefined,
      })
      continue
    }

    // Multiple batches: use user's total boxes and distribute so backend gets valid lines (units_per_box × number_of_boxes = qty per line).
    const totalBoxes = userBoxes > 0 ? userBoxes : 1
    const qtys = batches.map((b) => Number(b.qty) || 0)
    const boxCounts = distributeBoxesAcrossBatches(qtys, totalBoxes)
    const totalRowPcs = Number(row.pcs) || 0
    batches.forEach((b, idx) => {
      const qty = qtys[idx]
      const boxes = boxCounts[idx] || 1
      const unitsPerBox = boxes > 0 && qty % boxes === 0 ? qty / boxes : qty
      const lineBoxes = boxes > 0 ? boxes : 1
      // Distribute pcs proportionally across batch lines by qty share
      const linePcs = totalRowPcs > 0 && totalBatchQty > 0
        ? parseFloat((totalRowPcs * qty / totalBatchQty).toFixed(4))
        : 0
      items.push({
        item_code: row.item_code,
        item_name: row.item_name,
        qty,
        uom: row.uom,
        number_of_units_per_box: unitsPerBox,
        number_of_boxes: lineBoxes,
        weight_pcs: row.weight_pcs ?? 0,
        pcs: linePcs,
        rate: row.unit_price ?? row.rate ?? 0,
        unit_price: row.unit_price ?? row.rate ?? 0,
        tax_code: row.tax_code || 'PA0',
        warehouse: row.warehouse || PO_WAREHOUSE,
        batch_number: (b.batch_number || '').trim() || undefined,
      })
    })
  }
  const payload = {
    ...form.value,
    items,
  }
  try {
    if (isEdit.value) {
      await updatePurchaseOrder(poId.value, payload)
      notify.success('Purchase Order updated')
    } else {
      await createPurchaseOrder(payload)
      notify.success('Purchase Order created')
    }
    router.push('/khanalfoods/purchase-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Save failed')
  } finally { saving.value = false }
}

async function handleSubmitForApproval() {
  if (!validateForm()) return
  saving.value = true
  try {
    await submitPOForApproval(poId.value)
    notify.success('PO submitted for approval')
    router.push('/khanalfoods/purchase-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to submit')
  } finally { saving.value = false }
}

async function handleApprove() {
  showApproveDialog.value = false
  saving.value = true
  try {
    await approvePO(poId.value)
    notify.success('PO approved')
    router.push('/khanalfoods/purchase-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to approve')
  } finally { saving.value = false }
}

async function handleReject(reason) {
  showRejectDialog.value = false
  saving.value = true
  try {
    await rejectPO(poId.value, reason)
    notify.success('PO rejected')
    router.push('/khanalfoods/purchase-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to reject')
  } finally { saving.value = false }
}

async function handleRevertToDraft() {
  saving.value = true
  try {
    await revertPOToDraft(poId.value)
    notify.success('PO reverted to Draft')
    docStatus.value = 'Draft'
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to revert')
  } finally { saving.value = false }
}

const canDelete = computed(() => {
  if (!isEdit.value || !session.isProcurement) return false
  const d = doc.value
  if (!d) return false
  if (d.sap_po_doc_entry || d.sap_grpo_doc_entry || d.sap_inventory_transfer_doc_entry) return false
  if (session.isProcurementManager) return ['Draft', 'Pending Approval', 'Approved', 'Rejected'].includes(docStatus.value)
  return d.owner === session.userEmail && docStatus.value === 'Draft'
})

async function handleDelete() {
  showDeleteDialog.value = false
  saving.value = true
  try {
    await deletePurchaseOrder(poId.value)
    notify.success('Purchase Order deleted')
    router.push('/khanalfoods/purchase-orders')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Delete failed')
  } finally {
    saving.value = false
  }
}

async function handleRetrySapSync() {
  saving.value = true
  try {
    const data = await retryPOSapSync(poId.value)
    doc.value = data
    notify.success('SAP sync retried successfully')
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Retry SAP sync failed')
  } finally { saving.value = false }
}

async function handleSaveGrnDetails() {
  savingGrn.value = true
  try {
    const payload = {
      vendor_ref_no: grnForm.value.vendor_ref_no,
      remarks: grnForm.value.remarks,
      received_date: grnForm.value.received_date,
      items: grnForm.value.items.map((i) => ({
        accepted_qty: i.accepted_qty,
        batch_number: i.batch_number,
        acceptance_remarks: i.acceptance_remarks,
      })),
    }
    const data = await kfUpdateGrnDetails(poId.value, payload)
    doc.value = data
    notify.success('GRN details saved')
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to save GRN details')
  } finally {
    savingGrn.value = false
  }
}

async function handleReleaseHold() {
  saving.value = true
  try {
    const data = await kfReleaseWarehouseHoldPO(poId.value)
    doc.value = data
    notify.success('Warehouse hold released')
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to release hold')
  } finally {
    saving.value = false
  }
}

function openGrnConfirm() {
  if (!grnForm.value.received_date) {
    notify.error('GRN date is required before posting')
    return
  }
  showGrnConfirm.value = true
}

function closeGrnConfirm() {
  showGrnConfirm.value = false
}

async function handleCreateGrn() {
  saving.value = true
  try {
    const payload = {
      vendor_ref_no: grnForm.value.vendor_ref_no,
      remarks: grnForm.value.remarks,
      received_date: grnForm.value.received_date,
      items: grnForm.value.items.map((i) => ({
        accepted_qty: i.accepted_qty,
        batch_number: i.batch_number,
        acceptance_remarks: i.acceptance_remarks,
      })),
    }
    await kfUpdateGrnDetails(poId.value, payload)
    const data = await createPOGrn(poId.value)
    doc.value = data
    notify.success('GRN posted to SAP successfully')
    showGrnConfirm.value = false
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to post GRN to SAP')
  } finally {
    saving.value = false
  }
}

async function handleRevertGrn() {
  if (!confirm('Only revert after the GRPO has already been cancelled in SAP B1. Continue?')) return
  saving.value = true
  try {
    const data = await revertPOGrn(poId.value)
    doc.value = data
    notify.success('GRN reference cleared — ready to post again')
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to revert GRN')
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
    if (session.team === 'warehouse' && poId.value) {
      await warehouseRequestKfAssistancePO(poId.value)
    }
    notify.success('Ticket raised')
    showTicketDialog.value = false
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to raise ticket')
  } finally {
    ticketSubmitting.value = false
  }
}

function mergeItemsByItemCode(apiItems) {
  const byCode = new Map()
  for (const i of apiItems) {
    const code = (i.item_code || '').trim()
    if (!code) continue
    const key = code.toLowerCase()
    if (!byCode.has(key)) {
      byCode.set(key, {
        item_code: i.item_code,
        item_name: i.item_name,
        uom: i.uom || '',
        number_of_units_per_box: i.number_of_units_per_box ?? 0,
        number_of_boxes: 0, // summed below when merging batch lines
        weight_pcs: i.weight_pcs ?? 0,
        pcs: 0, // summed below when merging batch lines
        rate: i.rate,
        unit_price: i.unit_price ?? i.rate,
        tax_code: i.tax_code || 'PA0',
        warehouse: i.warehouse || PO_WAREHOUSE,
        batches: [],
        accepted_qty: null,
        acceptance_remarks: '',
      })
    }
    const merged = byCode.get(key)
    merged.number_of_boxes = (merged.number_of_boxes || 0) + (i.number_of_boxes ?? 0)
    merged.pcs = (merged.pcs || 0) + (Number(i.pcs) || 0)
    const lineAccepted = i.accepted_qty != null && i.accepted_qty !== '' ? Number(i.accepted_qty) : 0
    merged.accepted_qty = (merged.accepted_qty ?? 0) + lineAccepted
    if (i.acceptance_remarks) {
      merged.acceptance_remarks = merged.acceptance_remarks
        ? `${merged.acceptance_remarks}; ${i.acceptance_remarks}`
        : i.acceptance_remarks
    }
    merged.batches.push({
      batch_number: i.batch_number || '',
      qty: i.qty ?? 0,
    })
  }
  const result = Array.from(byCode.values())
  for (const m of result) {
    if (m.accepted_qty === 0) m.accepted_qty = null
  }
  // Derive row-level Units/Box from total qty and total boxes when consistent, so we don't show first batch's upb (e.g. 65) when total is 100 and boxes 2
  for (const m of result) {
    const totalQty = (m.batches || []).reduce((s, b) => s + (Number(b.qty) || 0), 0)
    const totalBoxes = m.number_of_boxes || 0
    if (totalBoxes > 0 && totalQty > 0 && totalQty % totalBoxes === 0) {
      m.number_of_units_per_box = totalQty / totalBoxes
    }
  }
  return result
}

async function loadPO() {
  loading.value = true
  try {
    const data = await fetchPurchaseOrder(poId.value)
    doc.value = data
    docStatus.value = data.status || 'Draft'
    form.value = {
      vendor_code: data.vendor_code || '',
      vendor_name: data.vendor_name || '',
      supplier_name: data.supplier_name || data.vendor_name || '',
      vendor_ref_no: data.vendor_ref_no || '',
      posting_date: data.posting_date || '',
      purchase_order_name: data.purchase_order_name || '',
      remarks: data.remarks || '',
      items: mergeItemsByItemCode(data.items || []),
    }
    grnForm.value = {
      vendor_ref_no: data.vendor_ref_no || '',
      remarks: data.remarks || '',
      received_date: data.received_date || new Date().toISOString().slice(0, 10),
      items: (data.items || []).map((item) => ({
        item_code: item.item_code,
        item_name: item.item_name,
        ordered_qty: item.qty,
        accepted_qty: item.accepted_qty != null ? Number(item.accepted_qty) : Number(item.qty) || 0,
        batch_number: item.batch_number || '',
        acceptance_remarks: item.acceptance_remarks || '',
      })),
    }
  } catch { notify.error('Failed to load PO') }
  loading.value = false
}

onMounted(async () => {
  document.addEventListener('click', onClickOutsideInlineSearch)
  if (isEdit.value) await loadPO()
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutsideInlineSearch)
})
</script>

<style scoped>
.po-form {
  font-feature-settings: "tnum";
}

/* Cards & sections */
.card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.05);
  padding: 1.5rem 1.5rem;
}
.card__title {
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 1.25rem;
}

/* Form fields */
.field__label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #4b5563;
  margin-bottom: 0.375rem;
}
.input-field {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: white;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-field:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

/* Buttons */
.btn {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.btn--sm {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
}
.btn--secondary {
  background: white;
  border: 1px solid #d1d5db;
  color: #374151;
}
.btn--secondary:hover {
  background: #f9fafb;
  border-color: #9ca3af;
}
.btn--primary {
  background: #2563eb;
  color: white;
  border: none;
}
.btn--primary:hover:not(:disabled) {
  background: #1d4ed8;
}
.btn--primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn--accent {
  background: #4f46e5;
  color: white;
  border: none;
}
.btn--accent:hover:not(:disabled) {
  background: #4338ca;
}
.btn--success {
  background: #059669;
  color: white;
  border: none;
}
.btn--success:hover {
  background: #047857;
}
.btn--danger {
  background: #dc2626;
  color: white;
  border: none;
}
.btn--danger:hover {
  background: #b91c1c;
}
.btn--warning {
  background: #d97706;
  color: white;
  border: none;
}
.btn--warning:hover:not(:disabled) {
  background: #b45309;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
  background: #f3f4f6;
  border-radius: 6px;
}

/* Table */
.po-table {
  width: 100%;
  font-size: 0.875rem;
  border-collapse: collapse;
}
.po-table__th {
  padding: 0.625rem 0.75rem;
  text-align: left;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}
.po-table__cell {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: middle;
}
.po-table__row:hover {
  background: #f8fafc;
}

.input-sm {
  width: 100%;
  padding: 0.375rem 0.5rem;
  font-size: 0.8125rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
}
.input-sm:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.input-num {
  width: 5rem;
  max-width: 100%;
}

/* Batch chips */
.batch-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.batch-chip {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-wrap: wrap;
}
.batch-chip__batch {
  flex: 1;
  min-width: 4.5rem;
  padding: 0.25rem 0.5rem;
  font-size: 0.8125rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.batch-chip__batch:focus {
  outline: none;
  border-color: #3b82f6;
}
.batch-chip__qty {
  width: 2.75rem;
  padding: 0.25rem 0.375rem;
  font-size: 0.8125rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  text-align: right;
}
.batch-chip__label {
  font-size: 0.8125rem;
  color: #4b5563;
}
.batch-chip__qty-display {
  font-size: 0.8125rem;
  font-weight: 500;
  color: #1f2937;
  margin-left: 0.25rem;
}
.batch-chip__remove {
  padding: 0.125rem 0.25rem;
  font-size: 1rem;
  line-height: 1;
  color: #9ca3af;
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.batch-chip__remove:hover {
  color: #dc2626;
  background: #fef2f2;
}
.batch-add {
  font-size: 0.75rem;
  font-weight: 500;
  color: #2563eb;
  background: none;
  border: none;
  padding: 0.125rem 0;
  cursor: pointer;
}
.batch-add:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.row-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  font-size: 1.25rem;
  line-height: 1;
  color: #9ca3af;
  background: none;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.row-remove:hover {
  color: #dc2626;
  background: #fef2f2;
}

.empty-state {
  padding: 3rem 1.5rem;
  text-align: center;
}
.empty-state__icon {
  width: 3rem;
  height: 3rem;
  margin: 0 auto 1rem;
  color: #d1d5db;
}
.empty-state__text {
  font-size: 0.9375rem;
  font-weight: 500;
  color: #6b7280;
  margin-bottom: 0.25rem;
}
.empty-state__hint {
  font-size: 0.8125rem;
  color: #9ca3af;
}
</style>
