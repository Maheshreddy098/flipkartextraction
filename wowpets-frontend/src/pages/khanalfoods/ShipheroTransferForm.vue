<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <router-link :to="listPath" class="p-2 rounded-lg hover:bg-gray-200 transition text-gray-500">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </router-link>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">
            {{ isEdit ? (form.inventory_transfer_name || `Transfer: ${transferId}`) : 'New Shiphero Transfer' }}
          </h1>
          <p class="text-sm text-gray-500 mt-0.5">{{ isEdit ? '' : 'Shiphero → WowPets inventory transfer' }}</p>
        </div>
        <StatusBadge v-if="isEdit && docStatus" :status="isWarehouse && docStatus === 'Sent to SAP' ? 'Posted' : docStatus" />
      </div>
      <div class="flex gap-3">
        <button type="button" @click="$router.back()" class="px-5 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium transition">
          {{ isReadOnly && !showAccept ? 'Back' : 'Cancel' }}
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

        <button
          v-if="isWarehouse && docStatus === 'Approved'"
          @click="handleAccept"
          :disabled="saving"
          class="px-5 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition text-sm font-medium shadow-sm"
        >
          {{ saving ? 'Accepting...' : 'Accept' }}
        </button>

        <button
          v-if="isKhanalFoods && canShowSendToSap"
          @click="handleSendToSap"
          :disabled="saving"
          class="px-5 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition text-sm font-medium shadow-sm"
        >
          {{ saving ? 'Sending...' : 'Retry Send to SAP' }}
        </button>
        <button
          v-if="needsSapRequestRetry"
          @click="handleRetrySapRequest"
          :disabled="saving"
          class="px-5 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition text-sm font-medium shadow-sm"
        >
          {{ saving ? 'Retrying...' : 'Retry SAP Request' }}
        </button>
        <button
          v-if="showWarehouseMarkReceived"
          @click="handleMarkReceived"
          :disabled="saving"
          class="px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition text-sm font-medium shadow-sm"
        >
          {{ saving ? 'Updating...' : 'Mark as Received' }}
        </button>
        <button
          v-if="isWarehouse && docStatus === 'Error'"
          type="button"
          @click="showTicketDialog = true"
          class="px-6 py-2.5 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium"
        >
          Raise Ticket for KhanalFoods
        </button>
        <button
          v-if="isEdit && !(isWarehouse && docStatus === 'Error')"
          type="button"
          @click="showTicketDialog = true"
          class="px-4 py-2.5 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium shadow-sm"
        >
          Raise Ticket
        </button>
        <button v-if="isEdit && docStatus === 'Rejected' && isKhanalFoods && isManager" @click="handleRevertToDraft" :disabled="saving" class="px-5 py-2.5 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition text-sm font-medium shadow-sm">
          Revert to Draft
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
        <h2 class="text-base font-semibold text-gray-800 mb-4">Transfer Details</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Transfer Name *</label>
            <textarea
              v-model="form.inventory_transfer_name"
              class="input-field"
              :class="{ 'bg-gray-50': isReadOnly || isWarehouse }"
              :readonly="isReadOnly || isWarehouse"
              rows="2"
              placeholder="e.g. March Nulo replenishment 1"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Doc Date</label>
            <input v-model="form.doc_date" type="date" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">From Warehouse</label>
            <div v-if="isReadOnly" class="input-field bg-gray-50 flex items-center">
              <span class="text-gray-800">{{ warehouseNameForCode(form.from_warehouse || doc.from_warehouse) || (form.from_warehouse || doc.from_warehouse) || '—' }}</span>
            </div>
            <select
              v-else
              v-model="form.from_warehouse"
              class="input-field"
            >
              <option disabled value="">Select from warehouse</option>
              <option
                v-for="wh in fromWarehouseOptions"
                :key="wh.warehouse_code"
                :value="wh.warehouse_code"
              >
                {{ wh.warehouse_name ? `${wh.warehouse_name} (${wh.warehouse_code})` : wh.warehouse_code }}
              </option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">To Warehouse</label>
            <div v-if="isReadOnly" class="input-field bg-gray-50 flex items-center">
              <span class="text-gray-800">{{ warehouseNameForCode(form.to_warehouse || doc.to_warehouse) || (form.to_warehouse || doc.to_warehouse) || '—' }}</span>
            </div>
            <select
              v-else
              v-model="form.to_warehouse"
              class="input-field"
            >
              <option disabled value="">Select to warehouse</option>
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
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Comments *</label>
            <textarea v-model="form.comments" class="input-field" :class="{ 'bg-gray-50': isReadOnly }" :readonly="isReadOnly" rows="2" placeholder="Required" />
          </div>
        </div>

        <h3 class="text-sm font-semibold text-gray-700 mt-6 mb-3">Address (USA format)</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Address Line 1 *</label>
            <input v-model="form.address_line1" class="input-field" :class="{ 'bg-gray-50': isReadOnly || isWarehouse }" :readonly="isReadOnly || isWarehouse" placeholder="Street address" />
          </div>
          <div class="md:col-span-3">
            <label class="block text-sm font-medium text-gray-600 mb-1.5">Address Line 2</label>
            <input v-model="form.address_line2" class="input-field" :class="{ 'bg-gray-50': isReadOnly || isWarehouse }" :readonly="isReadOnly || isWarehouse" placeholder="Apt, suite, unit (optional)" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">City *</label>
            <input v-model="form.city" class="input-field" :class="{ 'bg-gray-50': isReadOnly || isWarehouse }" :readonly="isReadOnly || isWarehouse" placeholder="City" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">State *</label>
            <input v-model="form.state" class="input-field w-24" :class="{ 'bg-gray-50': isReadOnly || isWarehouse }" :readonly="isReadOnly || isWarehouse" placeholder="e.g. CA" maxlength="2" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-600 mb-1.5">ZIP Code *</label>
            <input v-model="form.zip_code" class="input-field w-32" :class="{ 'bg-gray-50': isReadOnly || isWarehouse }" :readonly="isReadOnly || isWarehouse" placeholder="e.g. 90210" />
          </div>
        </div>

        <!-- Approval & workflow (always visible when viewing a transfer) -->
        <div v-if="isEdit" class="mt-4 pt-4 border-t space-y-4">
          <p
            v-if="docStatus === 'Error' && isWarehouse && hasSapRequest && !hasSapDocEntry"
            class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
          >
            SAP posting failed. Use <strong>Raise Ticket for KhanalFoods</strong> if they need to correct batches or quantities.
            After they save the fix, click <strong>Mark as Received</strong> again to complete the transfer.
          </p>
          <p
            v-if="docStatus === 'Error' && isWarehouse && !hasSapRequest"
            class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
          >
            Transfer request is missing in SAP. Raise a ticket for KhanalFoods or use <strong>Retry SAP Request</strong> if shown.
          </p>
          <p
            v-if="docStatus === 'Error' && isKhanalFoods"
            class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
          >
            SAP error on this transfer. Update lines (batches, quantities, units/boxes) as needed, click <strong>Save</strong>,
            then either <strong>Retry Send to SAP</strong> (if warehouse has not finished) or ask the warehouse to
            <strong>Mark as Received</strong> again after your save.
          </p>
          <div>
            <label class="block text-xs font-medium text-gray-400 mb-1">Approval status</label>
            <p class="text-sm text-gray-800">
              <template v-if="isWarehouse">
                <!-- Warehouse: only warehouse-relevant status text, no SAP wording -->
                <span class="font-medium">{{ doc.status === 'Sent to SAP' ? 'Posted' : (doc.status || '—') }}</span>
                <span v-if="doc.status === 'Pending Approval'" class="text-amber-600 ml-1">(awaiting manager approval)</span>
                <span v-if="doc.status === 'Approved'" class="text-green-600 ml-1">(ready for you to Accept)</span>
                <span v-if="doc.status === 'Accepted' && hasSapRequest" class="text-green-600 ml-1">(ready for Mark as Received)</span>
                <span v-if="doc.status === 'Accepted' && !hasSapRequest" class="text-red-600 ml-1">(request failed — KhanalFoods will retry)</span>
                <span v-if="doc.status === 'Sent to SAP'" class="text-green-600 ml-1">(ready for Mark as Received)</span>
                <span v-if="doc.status === 'Received'" class="text-green-600 ml-1">(completed)</span>
                <span v-if="doc.status === 'Error'" class="text-red-600 ml-1">(sync failed)</span>
              </template>
              <template v-else>
                <span class="font-medium">{{ doc.status || '—' }}</span>
                <span v-if="doc.status === 'Pending Approval'" class="text-amber-600 ml-1">(awaiting manager approval)</span>
                <span v-if="doc.status === 'Approved'" class="text-green-600 ml-1">(ready for warehouse to Accept)</span>
                <span v-if="doc.status === 'Accepted'" class="text-blue-600 ml-1">(posting to SAP automatically…)</span>
                <span v-if="doc.status === 'Sent to SAP'" class="text-green-600 ml-1">(raised in SAP)</span>
                <span v-if="doc.status === 'Received'" class="text-green-600 ml-1">(completed)</span>
                <span v-if="doc.status === 'Error'" class="text-red-600 ml-1">(SAP failed – use Retry)</span>
              </template>
            </p>
          </div>
          <div v-if="doc.accepted_by">
            <label class="block text-xs font-medium text-gray-400 mb-1">Accepted by (warehouse)</label>
            <p class="text-sm text-gray-700">{{ doc.accepted_by }}</p>
          </div>
          <!-- SAP: Transfer Request + Transfer doc numbers – only for KhanalFoods -->
          <div v-if="isKhanalFoods && (doc.sap_request_doc_entry || doc.sap_doc_entry || doc.sap_sync_error || doc.status === 'Error')">
            <label class="block text-xs font-medium text-gray-400 mb-1">SAP Documents</label>

            <!-- Inventory Transfer Request -->
            <div class="mt-1">
              <span class="text-xs font-semibold text-gray-500 uppercase">Inventory Transfer Request</span>
              <p v-if="doc.sap_request_doc_entry" class="text-sm text-green-700">
                Doc Entry: <strong>{{ doc.sap_request_doc_entry }}</strong>
                <span v-if="doc.sap_request_doc_num">, Doc Num: <strong>{{ doc.sap_request_doc_num }}</strong></span>
              </p>
              <p v-else class="text-sm text-gray-400">Not created yet</p>
            </div>

            <!-- Inventory Transfer (final) -->
            <div class="mt-2">
              <span class="text-xs font-semibold text-gray-500 uppercase">Inventory Transfer</span>
              <p v-if="doc.sap_doc_entry" class="text-sm text-green-700">
                Doc Entry: <strong>{{ doc.sap_doc_entry }}</strong>
                <span v-if="doc.sap_doc_num">, Doc Num: <strong>{{ doc.sap_doc_num }}</strong></span>
              </p>
              <p v-else class="text-sm text-gray-400">Not created yet (posted on Mark as Received)</p>
            </div>

            <!-- Error -->
            <p v-if="doc.sap_sync_error" class="text-sm text-red-600 mt-2">Error: {{ doc.sap_sync_error }}</p>

            <!-- Retry button for final transfer -->
            <div v-if="!doc.sap_doc_entry && (doc.status === 'Error' || doc.status === 'Received')" class="mt-2">
              <button type="button" @click="handleSendToSap" :disabled="saving" class="px-3 py-1.5 text-sm bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 transition">
                {{ saving ? 'Sending...' : 'Retry Send to SAP (Transfer)' }}
              </button>
            </div>
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

        <!-- ========== WAREHOUSE TABLE (merged one row per item, no batches, OK icon) ========== -->
        <div v-if="isWarehouse && warehouseItems.length" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50/80">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-12">#</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[120px]">Item Code</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[160px]">Item Name</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Quantity</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">Units/Box</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">No. Boxes</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-28">Warehouse</th>
                <th class="px-4 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-16">OK</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Accepted Qty</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[140px]">Remarks</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(wItem, wIdx) in warehouseItems" :key="wIdx" class="border-b border-gray-100 hover:bg-blue-50/30">
                <td class="px-4 py-2.5 text-gray-400 font-mono text-xs">{{ wIdx + 1 }}</td>
                <td class="px-4 py-2.5 font-medium text-gray-800">{{ wItem.item_code }}</td>
                <td class="px-4 py-2.5 text-gray-600">{{ wItem.item_name }}</td>
                <td class="px-4 py-2.5 font-medium text-gray-800">{{ wItem.totalQty }}</td>
                <td class="px-4 py-2.5 text-gray-600">{{ wItem.number_of_units_per_box ?? '—' }}</td>
                <td class="px-4 py-2.5 text-gray-600">{{ wItem.number_of_boxes ?? '—' }}</td>
                <td class="px-4 py-2.5 text-gray-600">{{ wItem.warehouse_code || form.to_warehouse || '—' }}</td>
                <td class="px-4 py-2.5 text-center">
                  <span v-if="whLineValid(wItem)" class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600" title="Units × Boxes = Quantity">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                  </span>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td class="px-4 py-2.5">
                  <template v-if="docStatus === 'Accepted'">
                    <input
                      v-model.number="whAcceptedQtys[wIdx]"
                      type="number"
                      min="0"
                      :max="wItem.totalQty"
                      step="any"
                      class="input-field-sm w-24"
                      placeholder="Same as qty"
                    />
                    <span class="ml-1 text-gray-400 text-xs">max {{ wItem.totalQty }}</span>
                  </template>
                  <template v-else>
                    {{ wItem.accepted_qty != null ? wItem.accepted_qty : (wItem.totalQty + ' (full)') }}
                  </template>
                </td>
                <td class="px-4 py-2.5">
                  <template v-if="docStatus === 'Accepted'">
                    <input
                      v-model="whAcceptedRemarks[wIdx]"
                      type="text"
                      class="input-field-sm w-full min-w-[120px] max-w-[200px]"
                      placeholder="e.g. short, quality"
                    />
                  </template>
                  <span v-else class="text-gray-600 text-sm">{{ wItem.acceptance_remarks || '—' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="isWarehouse && docStatus === 'Accepted' && hasSapRequest && warehouseItems.length" class="px-6 py-2 text-xs text-gray-500 border-t">
          Enter accepted quantity and optional remarks per line, then click Mark as Received. This quantity will be posted to SAP.
        </p>
        <p v-if="isWarehouse && docStatus === 'Accepted' && !hasSapRequest && warehouseItems.length" class="px-6 py-2 text-xs text-red-500 border-t">
          Transfer request failed. KhanalFoods will retry; please wait before marking as received.
        </p>

        <!-- ========== KHANALFOODS TABLE (with batches, multi-batch editing) ========== -->
        <div v-if="isKhanalFoods && form.items.length" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50/80">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-12">#</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[120px]">Item Code</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[160px]">Item Name</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Quantity</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">Units/Box</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">No. Boxes</th>
                <th class="px-4 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-14" title="Advisory: Units/Box × No. Boxes = Quantity (green when matching, won't block save)">Match</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase min-w-[160px]">Batch</th>
                <th v-if="!isReadOnly" class="px-4 py-2.5 w-12"></th>
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
                  <input v-if="!isReadOnly" v-model.number="item.number_of_units_per_box" type="number" min="0" class="input-field-sm w-20" @input="onUnitsPerBoxChange(item)" />
                  <span v-else class="text-gray-600">{{ item.number_of_units_per_box ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input v-if="!isReadOnly" v-model.number="item.number_of_boxes" type="number" min="0" class="input-field-sm w-20" />
                  <span v-else class="text-gray-600">{{ item.number_of_boxes ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5 text-center align-middle">
                  <span
                    v-if="kfLineValid(item)"
                    class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600"
                    title="Units/Box × No. Boxes = Quantity"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-100 text-red-600"
                    title="Units/Box × No. Boxes must equal Quantity"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
                  </span>
                </td>
                <td class="px-4 py-2.5 align-top">
                  <div v-if="!isReadOnly" class="space-y-2">
                    <template v-if="(item.item_code || '').trim() && (form.from_warehouse || '').trim()">
                      <div v-for="(b, bi) in (item.batches || [])" :key="bi" class="flex items-center gap-2">
                        <select
                          v-if="batchOptionsForKey(batchKey(item)) !== null"
                          v-model="b.batch_number"
                          class="input-field-sm w-full min-w-[140px]"
                          @focus="loadBatchesForRow(item)"
                        >
                          <option v-if="!(batchOptionsForKey(batchKey(item)) || []).length" value="">No batches in {{ form.from_warehouse }}</option>
                          <option v-else value="">— Select batch (required) —</option>
                          <option v-for="opt in (batchOptionsForKey(batchKey(item)) || [])" :key="opt.batch_number" :value="opt.batch_number">
                            {{ opt.batch_number }} (Qty: {{ opt.quantity }})
                          </option>
                        </select>
                        <select v-else disabled class="input-field-sm w-full min-w-[140px] bg-gray-100 text-gray-500">
                          <option>Loading batches from SAP...</option>
                        </select>
                        <input v-model.number="b.qty" type="number" min="0" step="any" class="input-field-sm w-20" placeholder="Qty" />
                        <button v-if="(item.batches || []).length > 1" type="button" @click="removeBatch(item, bi)" class="text-gray-300 hover:text-red-500 transition text-lg" title="Remove batch">&times;</button>
                      </div>
                      <button type="button" @click="addBatch(item)" class="text-xs text-blue-600 hover:underline">+ Add batch</button>
                    </template>
                    <input v-else v-model="item.batch_number" class="input-field-sm w-full" placeholder="Set item & from warehouse" disabled />
                  </div>
                  <span v-else class="text-gray-600">
                    <template v-if="(item.batches || []).length">
                      {{ (item.batches || []).map((b) => `${b.batch_number || '—'} (${b.qty})`).join(', ') }}
                    </template>
                    <template v-else>{{ item.batch_number || '—' }}</template>
                  </span>
                </td>
                <td v-if="!isReadOnly" class="px-4 py-2.5 text-center">
                  <button @click="form.items.splice(idx, 1)" type="button" class="text-gray-300 hover:text-red-500 transition text-lg">&times;</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="form.items.length && !isReadOnly && isKhanalFoods" class="px-6 py-2 text-xs text-gray-500 border-t border-gray-100">
            <strong>Match</strong> column: advisory check — green tick when Units/Box × No. Boxes equals Quantity, but won't block saving.
          </p>
        </div>

        <div v-if="!form.items.length && !warehouseItems.length" class="px-6 py-12 text-center text-gray-400 text-sm">No items.</div>
      </div>
    </div>

    <!-- ========== SHIPHERO INVENTORY (SC-STR / SC-FG) – KHANALFOODS ONLY, ONLY WHILE CREATING ========== -->
    <div v-if="isKhanalFoods && !isEdit" class="bg-white rounded-xl shadow-sm border mt-6">
      <div class="flex items-center justify-between px-6 py-4 border-b">
        <div>
          <h2 class="text-base font-semibold text-gray-800">ShipHero Inventory (SC-STR / SC-FG)</h2>
          <p class="text-xs text-gray-500 mt-1">Read-only view of ShipHero stock for this transfer. Use it to pick batches confidently.</p>
        </div>
        <div class="flex items-center gap-2">
          <input
            v-model="shInvSearch"
            type="text"
            placeholder="Search by item code..."
            class="px-3 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 outline-none min-w-[180px]"
            @input="onShInvSearch"
          />
          <button
            type="button"
            @click="loadShipheroInventory"
            :disabled="shInvLoading"
            class="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            <svg v-if="shInvLoading" class="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            <span>{{ shInvLoading ? 'Refreshing...' : 'Refresh' }}</span>
          </button>
        </div>
      </div>
      <div class="px-6 py-4">
        <DataTable
          :columns="shInvColumns"
          :rows="shInvItems"
          :total="shInvTotal"
          :page="shInvPage"
          @page-change="p => { shInvPage = p; loadShipheroInventory() }"
          empty-text="No ShipHero inventory for SC-STR / SC-FG."
        >
          <template #cell-available_qty="{ value }">
            <span :class="value > 0 ? 'text-green-700 font-semibold' : 'text-gray-400'">{{ value }}</span>
          </template>
          <template #cell-allocated_qty="{ value }">
            <span :class="value > 0 ? 'text-purple-700 font-semibold' : 'text-gray-400'">{{ value }}</span>
          </template>
          <template #cell-total_qty="{ value }">
            <span class="font-semibold">{{ value }}</span>
          </template>
        </DataTable>
      </div>
    </div>

    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Shiphero Transfer"
      :message="`Approve ${form.inventory_transfer_name || transferId}?`"
      confirm-text="Approve"
      variant="success"
      @confirm="handleApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Shiphero Transfer"
      :message="`Reject ${form.inventory_transfer_name || transferId}? Provide a reason:`"
      confirm-text="Reject"
      variant="danger"
      show-input
      input-placeholder="Reason"
      @confirm="handleReject"
      @cancel="showRejectDialog = false"
    />

    <ConfirmDialog
      :visible="showDeleteDialog"
      title="Delete ShipHero Transfer"
      :message="`Permanently delete ${form.inventory_transfer_name || transferId}? This cannot be undone.`"
      confirm-text="Delete"
      variant="danger"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <KFAttachments
      doctype="WowPets Inventory Transfer"
      :docname="transferId"
    />

    <TicketDialog
      :visible="showTicketDialog"
      title="Raise Ticket for ShipHero Transfer"
      section="Shiphero Transfer"
      reference-doctype="WowPets Inventory Transfer"
      :reference-name="transferId"
      :submitting="ticketSubmitting"
      @submit="handleTicketSubmit"
      @cancel="showTicketDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  fetchShipheroTransfer,
  createShipheroTransfer,
  updateShipheroTransfer,
  submitShipheroTransfer,
  approveShipheroTransfer,
  rejectShipheroTransfer,
  acceptShipheroTransfer,
  updateShipheroAcceptedQuantities,
  sendShipheroTransferToSap,
  retrySapRequest,
  markReceivedShipheroTransfer,
  warehouseRequestKfAssistanceShiphero,
  revertShipheroTransferToDraft,
  deleteShipheroTransfer,
} from '@/core/api/shipheroTransfers.js'
import { getBatchesForItem, getWarehouses } from '@/core/api/sapMaster.js'
import { fetchShipheroInventory } from '@/core/api/inventory.js'
import DataTable from '@/components/common/DataTable.vue'
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

const transferId = computed(() => props.id || route.params.id)
const isEdit = computed(() => !!transferId.value)
const isKhanalFoods = computed(() => session.team === 'khanalfoods')
const isWarehouse = computed(() => session.team === 'warehouse')
const isManager = session.isManager

const listPath = computed(() => (session.team === 'khanalfoods' ? '/khanalfoods/shiphero-transfers' : '/warehouse/shiphero-transfers'))

const loading = ref(false)
const saving = ref(false)
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)
const docStatus = ref('')
const doc = ref({})
const acceptedQtys = ref([])
const acceptedRemarks = ref([])
const whAcceptedQtys = ref([])
const whAcceptedRemarks = ref([])
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const showDeleteDialog = ref(false)
const batchOptionsMap = ref({})
const sapWarehouses = ref([])

function rowTotalQty(item) {
  if (item.batches && item.batches.length) {
    return item.batches.reduce((s, b) => s + (Number(b.qty) || 0), 0)
  }
  return Number(item.quantity) || 0
}

function onUnitsPerBoxChange(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  if (upb > 0 && qty > 0) item.number_of_boxes = Math.round(qty / upb)
}

/** KhanalFoods row: Units/Box × No. Boxes must equal row total quantity (for save to be allowed). */
function kfLineValid(item) {
  const qty = rowTotalQty(item)
  const upb = Number(item.number_of_units_per_box) || 0
  const boxes = Number(item.number_of_boxes) || 0
  return qty > 0 && upb > 0 && boxes > 0 && Math.abs(upb * boxes - qty) < 0.001
}

function whLineValid(item) {
  const qty = Number(item.totalQty) || 0
  const upb = parseInt(item.number_of_units_per_box, 10) || 0
  const boxes = parseInt(item.number_of_boxes, 10) || 0
  if (qty <= 0) return false
  return upb > 0 && boxes > 0 && upb * boxes === qty
}

const warehouseItems = computed(() => {
  if (!isWarehouse.value) return []
  const byCode = new Map()
  for (const item of form.value.items) {
    const key = (item.item_code || '').trim().toLowerCase()
    if (!key) continue
    if (!byCode.has(key)) {
      byCode.set(key, {
        item_code: item.item_code,
        item_name: item.item_name,
        totalQty: 0,
        number_of_units_per_box: item.number_of_units_per_box ?? 0,
        number_of_boxes: 0,
        warehouse_code: item.warehouse_code,
        accepted_qty: null,
        acceptance_remarks: '',
        _sourceIndices: [],
      })
    }
    const merged = byCode.get(key)
    const qty = Number(item.quantity) || 0
    merged.totalQty += qty
    merged.number_of_boxes += Number(item.number_of_boxes) || 0
    merged._sourceIndices.push(form.value.items.indexOf(item))
    if (item.accepted_qty != null && item.accepted_qty !== '') {
      merged.accepted_qty = (merged.accepted_qty || 0) + Number(item.accepted_qty)
    }
    if (item.acceptance_remarks) {
      merged.acceptance_remarks = merged.acceptance_remarks
        ? merged.acceptance_remarks + '; ' + item.acceptance_remarks
        : item.acceptance_remarks
    }
  }
  return Array.from(byCode.values())
})

// ShipHero inventory (SC-STR / SC-FG) for KhanalFoods (with pagination)
const shInvItems = ref([])
const shInvTotal = ref(0)
const shInvPage = ref(1)
const shInvLoading = ref(false)
const shInvSearch = ref('')

const shInvColumns = [
  { key: 'item_code', label: 'Item Code' },
  { key: 'item_name', label: 'Item Name' },
  { key: 'warehouse', label: 'Warehouse' },
  { key: 'available_qty', label: 'Available' },
  { key: 'allocated_qty', label: 'Allocated' },
  { key: 'total_qty', label: 'Total' },
]

let shInvDebounce = null

async function loadShipheroInventory() {
  if (!isKhanalFoods.value) return
  shInvLoading.value = true
  try {
    const params = { page: shInvPage.value, page_size: 50, search: shInvSearch.value }
    const res = await fetchShipheroInventory(params)
    const rows =
      Array.isArray(res?.data) ? res.data :
      Array.isArray(res) ? res :
      []
    shInvItems.value = rows
    shInvTotal.value = (res && typeof res.total === 'number' ? res.total : rows.length) || 0
  } catch {
    shInvItems.value = []
    shInvTotal.value = 0
  } finally {
    shInvLoading.value = false
  }
}


function onShInvSearch() {
  clearTimeout(shInvDebounce)
  shInvDebounce = setTimeout(() => {
    shInvPage.value = 1
    loadShipheroInventory()
  }, 300)
}

function batchKey(item) {
  const code = (item?.item_code || '').trim()
  const fromWh = (form.value?.from_warehouse || '').trim()
  return code && fromWh ? `${code}|${fromWh}` : ''
}

function batchOptionsForKey(key) {
  return batchOptionsMap.value[key] ?? null
}

function getBatchAvailableQty(row, batchNumber) {
  const key = batchKey(row)
  const list = batchOptionsForKey(key) || []
  const bn = (batchNumber || '').trim()
  if (!bn) return null
  const match = list.find((b) => (b.batch_number || '').trim() === bn)
  if (!match) return null
  const qty = Number(match.quantity)
  return Number.isFinite(qty) ? qty : null
}

function warehouseNameForCode(code) {
  if (!(code || '').trim()) return ''
  const list = sapWarehouses.value || []
  const wh = list.find((w) => (w.warehouse_code || '').trim() === (code || '').trim())
  return wh ? (wh.warehouse_name || wh.warehouse_code) : ''
}

// From Warehouse = ShipCube (SC*); To Warehouse = WowPets (WO*) – from SAP only.
const fromWarehouseOptions = computed(() => {
  const list = sapWarehouses.value || []
  const filtered = list.filter((w) => /^SC/i.test((w.warehouse_code || '').trim()))
  return filtered.length ? filtered : list
})
const toWarehouseOptions = computed(() => {
  const list = sapWarehouses.value || []
  const filtered = list.filter((w) => /^WO/i.test((w.warehouse_code || '').trim()))
  return filtered.length ? filtered : list
})
const allWarehouseOptions = computed(() => sapWarehouses.value || [])

const form = ref({
  doc_date: new Date().toISOString().slice(0, 10),
  from_warehouse: 'SC-STR',
  to_warehouse: 'WO - STR',
  inventory_transfer_name: '',
  comments: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  zip_code: '',
  items: [],
})

async function loadBatchesForRow(item) {
  const key = batchKey(item)
  if (!key || key in batchOptionsMap.value) return
  batchOptionsMap.value = { ...batchOptionsMap.value, [key]: null }
  try {
    const fromWh = (form.value.from_warehouse || '').trim()
    const res = await getBatchesForItem(item.item_code, fromWh)
    batchOptionsMap.value = { ...batchOptionsMap.value, [key]: res.data || [] }
  } catch {
    batchOptionsMap.value = { ...batchOptionsMap.value, [key]: [] }
  }
}

watch(() => [form.value.items, form.value.from_warehouse], () => {
  form.value.items.forEach((item) => {
    const key = batchKey(item)
    if (key && !(key in batchOptionsMap.value)) loadBatchesForRow(item)
  })
}, { deep: true })

const isReadOnly = computed(() => {
  if (!isEdit.value) return false
  if (isWarehouse.value) return docStatus.value !== 'Approved'
  if (isKhanalFoods.value && doc.value?.warehouse_awaiting_kf) return false
  // KhanalFoods: edit Draft, or Error (after ticket — fix lines so warehouse can proceed or retry SAP)
  if (isKhanalFoods.value) return docStatus.value !== 'Draft' && docStatus.value !== 'Error'
  return true
})

const showAccept = computed(() => isWarehouse.value && docStatus.value === 'Approved')

const hasSapRequest = computed(() => !!(doc.value?.sap_request_doc_entry || '').trim())
const hasSapDocEntry = computed(() => !!(doc.value?.sap_doc_entry || '').trim())

/** Warehouse can complete posting after Accepted, after partial Sent to SAP, or after Error once KhanalFoods fixed lines. */
const showWarehouseMarkReceived = computed(() => {
  if (!isWarehouse.value || !hasSapRequest.value) return false
  if (docStatus.value === 'Accepted' || docStatus.value === 'Sent to SAP') return true
  if (docStatus.value === 'Error' && !hasSapDocEntry.value) return true
  return false
})

const needsSapRequestRetry = computed(() => {
  return isWarehouse.value && docStatus.value === 'Accepted' && !hasSapRequest.value
})

// Show only when SAP is not yet posted and user can retry (Error, or Accepted/Received without doc – edge case)
const canShowSendToSap = computed(() => {
  if (!isKhanalFoods.value) return false
  const entry = (doc.value?.sap_doc_entry || '').trim()
  if (entry) return false
  return docStatus.value === 'Error' || docStatus.value === 'Accepted' || docStatus.value === 'Received'
})

function getTargetWarehouseForItem(itemCode) {
  const code = (itemCode || '').toString().trim().toUpperCase()
  if (!code) {
    return form.value.to_warehouse || ''
  }
  if (code.startsWith('RM') || code.startsWith('PM') || code.startsWith('CO')) {
    return 'WO-STR'
  }
  if (code.startsWith('FG')) {
    return 'WO-FG'
  }
  return form.value.to_warehouse || ''
}

function addItem(item) {
  form.value.items.push({
    item_code: item.item_code,
    item_name: item.item_name || '',
    quantity: 0,
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    warehouse_code: form.value.to_warehouse,
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
    quantity: 0,
    number_of_units_per_box: 0,
    number_of_boxes: 0,
    warehouse_code: form.value.to_warehouse,
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
  if (!form.value.inventory_transfer_name || !String(form.value.inventory_transfer_name).trim()) {
    notify.error('Transfer Name is required')
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
  if (!form.value.doc_date) {
    notify.error('Doc Date is required')
    return false
  }
  if (!(form.value.comments || '').trim()) {
    notify.error('Comments are required')
    return false
  }
  const fromWh = (form.value.from_warehouse || '').trim()
  const toWh = (form.value.to_warehouse || '').trim()
  if (!fromWh) {
    notify.error('From Warehouse is required')
    return false
  }
  if (!toWh) {
    notify.error('To Warehouse is required')
    return false
  }
  const fromCodes = new Set(fromWarehouseOptions.value.map((w) => (w.warehouse_code || '').trim()))
  const toCodes = new Set(toWarehouseOptions.value.map((w) => (w.warehouse_code || '').trim()))
  if (fromWarehouseOptions.value.length && !fromCodes.has(fromWh)) {
    notify.error('Select a From Warehouse from the list (SAP)')
    return false
  }
  if (toWarehouseOptions.value.length && !toCodes.has(toWh)) {
    notify.error('Select a To Warehouse from the list (SAP)')
    return false
  }
  if (!fromWh || !toWh) {
    notify.error('From Warehouse and To Warehouse are required')
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
    const batches = row.batches || []
    if (!batches.length || batches.every((b) => !(Number(b.qty) || 0))) {
      notify.error(`Row ${i + 1}: Add at least one batch with quantity`)
      return false
    }
    for (const b of batches) {
      if (!(b.batch_number || '').trim()) {
        notify.error(`Row ${i + 1} (${row.item_code}): Select a batch for every entry`)
        return false
      }
      if (!b.qty || Number(b.qty) <= 0) {
        notify.error(`Row ${i + 1} (${row.item_code}): Batch quantity must be greater than 0`)
        return false
      }
      const available = getBatchAvailableQty(row, b.batch_number)
      const qty = Number(b.qty) || 0
      if (available === 0) {
        notify.error(`Row ${i + 1} (${row.item_code}): Selected batch ${b.batch_number} has no available quantity in ${form.value.from_warehouse}`)
        return false
      }
      if (available != null && qty > available) {
        notify.error(`Row ${i + 1} (${row.item_code}): Batch quantity ${qty} exceeds available ${available} in selected batch ${b.batch_number}`)
        return false
      }
    }
  }
  return true
}

/** Build items payload from form (uses user's Units/Box and No. Boxes exactly for single batch; distributes for multi-batch). */
function buildTransferItemsPayload() {
  const items = []
  for (const row of form.value.items) {
    const userUnitsPerBox = parseInt(row.number_of_units_per_box, 10) || 0
    const userBoxes = parseInt(row.number_of_boxes, 10) || 0
    const batches = (row.batches || []).filter((b) => (Number(b.qty) || 0) > 0)
    if (!batches.length) continue
    const totalBatchQty = batches.reduce((s, b) => s + (Number(b.qty) || 0), 0)

    if (batches.length === 1) {
      const b = batches[0]
      const qty = Number(b.qty) || 0
      items.push({
        item_code: row.item_code,
        item_name: row.item_name,
        quantity: qty,
        number_of_units_per_box: userUnitsPerBox,
        number_of_boxes: userBoxes,
        warehouse_code: form.value.to_warehouse,
        batch_number: (b.batch_number || '').trim() || undefined,
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
        if (idx >= 0) {
          boxesPerBatch[idx] = (boxesPerBatch[idx] || 0) + diff
        }
      }
    } else {
      boxesPerBatch = batches.map((b) => (userUnitsPerBox > 0 ? Math.round((Number(b.qty) || 0) / userUnitsPerBox) : 0))
    }

    batches.forEach((b, i) => {
      const qty = Number(b.qty) || 0
      const boxes = boxesPerBatch[i] || 0
      const upb = boxes > 0 ? Math.round(qty / boxes) : userUnitsPerBox
      items.push({
        item_code: row.item_code,
        item_name: row.item_name,
        quantity: qty,
        number_of_units_per_box: upb,
        number_of_boxes: boxes,
        warehouse_code: form.value.to_warehouse,
        batch_number: (b.batch_number || '').trim() || undefined,
      })
    })
  }
  return items
}

async function handleSave() {
  if (!validateForm()) return
  saving.value = true
  try {
    const items = buildTransferItemsPayload()
    const payload = {
      doc_date: form.value.doc_date,
      from_warehouse: form.value.from_warehouse,
      to_warehouse: form.value.to_warehouse,
      inventory_transfer_name: (form.value.inventory_transfer_name || '').trim() || undefined,
      comments: form.value.comments,
      address_line1: (form.value.address_line1 || '').trim() || undefined,
      address_line2: (form.value.address_line2 || '').trim() || undefined,
      city: (form.value.city || '').trim() || undefined,
      state: (form.value.state || '').trim() || undefined,
      zip_code: (form.value.zip_code || '').trim() || undefined,
      items,
    }
    if (isEdit.value) {
      const wasError = docStatus.value === 'Error'
      await updateShipheroTransfer(transferId.value, payload)
      notify.success(wasError ? 'Transfer updated — warehouse can retry Mark as Received, or use Retry Send to SAP as needed' : 'Transfer updated')
      if (wasError) {
        await loadTransfer()
        return
      }
    } else {
      await createShipheroTransfer(payload)
      notify.success('Transfer created')
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
    // Persist current form (including user's Units/Box and No. Boxes) before submitting, so submitted doc has correct values
    const items = buildTransferItemsPayload()
    const payload = {
      doc_date: form.value.doc_date,
      from_warehouse: form.value.from_warehouse,
      to_warehouse: form.value.to_warehouse,
      comments: form.value.comments,
      items,
    }
    await updateShipheroTransfer(transferId.value, payload)
    await submitShipheroTransfer(transferId.value)
    notify.success('Submitted for approval')
    await loadTransfer()
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
    await approveShipheroTransfer(transferId.value)
    notify.success('Approved')
    await loadTransfer()
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
    await rejectShipheroTransfer(transferId.value, reason)
    notify.success('Rejected')
    await loadTransfer()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Reject failed')
  } finally {
    saving.value = false
  }
}

async function handleRevertToDraft() {
  saving.value = true
  try {
    await revertShipheroTransferToDraft(transferId.value)
    notify.success('Reverted to Draft')
    await loadTransfer()
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
  if ((d.sap_request_doc_entry || '').trim() || (d.sap_doc_entry || '').trim()) return false
  if (isManager) return ['Draft', 'Approved'].includes(docStatus.value)
  return d.owner === session.userEmail && docStatus.value === 'Draft'
})

async function handleDelete() {
  showDeleteDialog.value = false
  saving.value = true
  try {
    await deleteShipheroTransfer(transferId.value)
    notify.success('ShipHero Transfer deleted')
    router.push(listPath.value)
  } catch (e) {
    notify.error(e.response?.data?.message || 'Delete failed')
  } finally {
    saving.value = false
  }
}

async function handleAccept() {
  saving.value = true
  try {
    const updated = await acceptShipheroTransfer(transferId.value)
    notify.success('Accepted')
    docStatus.value = updated?.status || 'Accepted'
    await loadTransfer()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Accept failed')
  } finally {
    saving.value = false
  }
}

async function handleRetrySapRequest() {
  saving.value = true
  try {
    await retrySapRequest(transferId.value)
    notify.success('SAP Transfer Request created successfully')
    await loadTransfer()
  } catch (e) {
    notify.error(e.response?.data?.message || 'SAP Transfer Request failed')
  } finally {
    saving.value = false
  }
}

async function handleSendToSap() {
  if (!form.value.items.length) {
    notify.error('Add at least one item')
    return
  }
  const missing = form.value.items
    .map((row, i) => {
      const hasBatch = (row.batch_number || '').trim() ||
        (row.batches || []).some(b => (b.batch_number || '').trim())
      return !hasBatch ? { row: i + 1, code: row.item_code } : null
    })
    .filter(Boolean)
  if (missing.length) {
    const list = missing.map((m) => `Row ${m.row} (${m.code})`).join(', ')
    notify.error(`Select a batch for every line before sending to SAP: ${list}`)
    return
  }
  saving.value = true
  try {
    await sendShipheroTransferToSap(transferId.value)
    notify.success('Sent to SAP')
    await loadTransfer()
  } catch (e) {
    const msg = e.response?.data?.message || 'Send to SAP failed'
    notify.error(msg)
  } finally {
    saving.value = false
  }
}

async function handleMarkReceived() {
  saving.value = true
  try {
    if (isWarehouse.value && docStatus.value === 'Accepted') {
      // Backend expects one value per document line (doc.items = flat API lines), not per grouped form row
      const flatItems = []
      const flatRemarks = []
      for (let formIdx = 0; formIdx < form.value.items.length; formIdx++) {
        const row = form.value.items[formIdx]
        const wItem = warehouseItems.value.find((w) => w._sourceIndices && w._sourceIndices.includes(formIdx))
        const whIdx = wItem ? warehouseItems.value.indexOf(wItem) : -1
        const acceptedTotal =
          whIdx >= 0 && whAcceptedQtys.value[whIdx] != null && Number.isFinite(Number(whAcceptedQtys.value[whIdx]))
            ? Number(whAcceptedQtys.value[whIdx])
            : rowTotalQty(row)
        const totalQty = rowTotalQty(row)
        const remarkText = whIdx >= 0 ? (whAcceptedRemarks.value[whIdx] || '').trim() : ''
        for (const b of row.batches || []) {
          const qty = Number(b.qty) || 0
          const ratio = totalQty > 0 ? qty / totalQty : 1 / (row.batches?.length || 1)
          flatItems.push(totalQty > 0 ? Math.round(acceptedTotal * ratio * 100) / 100 : acceptedTotal)
          flatRemarks.push(remarkText)
        }
      }
      await updateShipheroAcceptedQuantities(transferId.value, flatItems, flatRemarks)
    }
    await markReceivedShipheroTransfer(transferId.value)
    notify.success('Marked as received')
    await loadTransfer()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Mark as received failed')
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
    if (session.team === 'warehouse' && transferId.value) {
      await warehouseRequestKfAssistanceShiphero(transferId.value)
    }
    notify.success(session.team === 'warehouse' && docStatus.value === 'Error' ? 'Ticket raised for KhanalFoods team' : 'Ticket raised')
    showTicketDialog.value = false
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to raise ticket')
  } finally {
    ticketSubmitting.value = false
  }
}

async function loadTransfer() {
  loading.value = true
  try {
    const data = await fetchShipheroTransfer(transferId.value)
    doc.value = data
    docStatus.value = data.status || 'Draft'
    const norm = (c) => (c || '').trim().replace(/\s+/g, '')
    const fromWh = (data.from_warehouse ?? '').toString().trim() || 'SC-STR'
    const toWh = (data.to_warehouse ?? '').toString().trim() || 'WO-STR'
    const fromMatch = (sapWarehouses.value || []).find((w) => norm(w.warehouse_code) === norm(fromWh))
    const toMatch = (sapWarehouses.value || []).find((w) => norm(w.warehouse_code) === norm(toWh))
    const flatItems = (data.items || []).map((i) => {
      const wh = i.warehouse_code || getTargetWarehouseForItem(i.item_code)
      return {
        item_code: i.item_code,
        item_name: i.item_name,
        quantity: i.quantity,
        number_of_units_per_box: i.number_of_units_per_box ?? 0,
        number_of_boxes: i.number_of_boxes ?? 0,
        warehouse_code: wh,
        batch_number: i.batch_number || '',
        accepted_qty: i.accepted_qty,
        acceptance_remarks: i.acceptance_remarks || '',
      }
    })
    const grouped = new Map()
    for (const item of flatItems) {
      const key = (item.item_code || '').trim().toLowerCase() + '|' + (item.warehouse_code || '').trim().toLowerCase()
      if (!grouped.has(key)) {
        grouped.set(key, { ...item, batches: [], quantity: 0, number_of_boxes: 0 })
      }
      const g = grouped.get(key)
      g.batches.push({ batch_number: item.batch_number, qty: Number(item.quantity) || 0 })
      g.quantity += Number(item.quantity) || 0
      g.number_of_boxes += Number(item.number_of_boxes) || 0
    }
    form.value = {
      doc_date: data.doc_date || '',
      from_warehouse: fromMatch ? fromMatch.warehouse_code : fromWh,
      to_warehouse: toMatch ? toMatch.warehouse_code : toWh,
      inventory_transfer_name: data.inventory_transfer_name || '',
      comments: data.comments || '',
      address_line1: data.address_line1 || '',
      address_line2: data.address_line2 || '',
      city: data.city || '',
      state: data.state || '',
      zip_code: data.zip_code || '',
      items: Array.from(grouped.values()),
    }
    acceptedQtys.value = (data.items || []).map((i) => (i.accepted_qty != null && i.accepted_qty !== '' ? Number(i.accepted_qty) : null))
    acceptedRemarks.value = (data.items || []).map((i) => (i.acceptance_remarks || ''))

    nextTick(() => {
      whAcceptedQtys.value = warehouseItems.value.map((w) => w.accepted_qty)
      whAcceptedRemarks.value = warehouseItems.value.map((w) => w.acceptance_remarks || '')
    })
  } catch {
    notify.error('Failed to load transfer')
  }
  loading.value = false
}

async function loadSapWarehouses() {
  try {
    const res = await getWarehouses()
    sapWarehouses.value = res.data || []
    if (!isKhanalFoods.value) return
    const fromOpts = sapWarehouses.value.filter((w) => /^SC/i.test((w.warehouse_code || '').trim()))
    const toOpts = sapWarehouses.value.filter((w) => /^WO/i.test((w.warehouse_code || '').trim()))
    const fromCodes = new Set(fromOpts.map((w) => (w.warehouse_code || '').trim()))
    const toCodes = new Set(toOpts.map((w) => (w.warehouse_code || '').trim()))
    if (fromOpts.length && !fromCodes.has((form.value.from_warehouse || '').trim())) {
      form.value.from_warehouse = fromOpts[0].warehouse_code
    }
    if (toOpts.length && !toCodes.has((form.value.to_warehouse || '').trim())) {
      form.value.to_warehouse = toOpts[0].warehouse_code
    }
  } catch {
    sapWarehouses.value = []
  }
}

onMounted(async () => {
  if (isKhanalFoods.value) await loadSapWarehouses()
  else if (isEdit.value) await loadSapWarehouses() // warehouse team: load warehouses so From/To Warehouse header can display

  if (isEdit.value) {
    await loadTransfer()
  } else {
    form.value.doc_date = new Date().toISOString().slice(0, 10)
  }

  // Always load ShipHero inventory for KhanalFoods so the subsection is populated.
  if (isKhanalFoods.value) {
    loadShipheroInventory()
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
