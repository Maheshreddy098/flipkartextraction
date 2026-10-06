<template>
  <div class="procurement-detail mx-auto max-w-7xl min-w-0 p-4 sm:p-6">

    <div v-if="loading && !doc" class="py-16 text-center text-gray-400">Loading…</div>
    <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{{ loadError }}</div>

    <template v-else-if="doc">

      <!-- Breadcrumb -->
      <div class="mb-4 flex items-center gap-1.5 text-xs text-gray-500">
        <RouterLink to="/procurement" class="hover:text-teal-700">Purchase Requests (CPR)</RouterLink>
        <span>›</span>
        <span class="font-medium text-gray-700">{{ doc.name }}</span>
      </div>

      <!-- Split family: other CPRs from the same material request -->
      <div v-if="splitFamily.length > 1" class="mb-4 flex flex-wrap items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs">
        <span class="font-medium text-gray-500">Split family:</span>
        <template v-for="(f, i) in splitFamily" :key="f.name">
          <span v-if="i > 0" class="text-gray-300">·</span>
          <span v-if="f.name === doc.name" class="font-mono font-medium text-gray-700">{{ f.name }} (this)</span>
          <RouterLink v-else :to="`/procurement/${f.name}`" class="font-mono text-teal-700 hover:underline">{{ f.name }}</RouterLink>
          <span class="text-gray-400">— {{ f.status }}{{ f.item_count ? `, ${f.item_count} item${f.item_count === 1 ? '' : 's'}` : '' }}</span>
        </template>
      </div>

      <!-- ── Header ── -->
      <header class="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0">
          <h1 class="truncate font-mono text-xl font-semibold text-gray-900 sm:text-2xl">{{ doc.name }}</h1>
          <p class="mt-0.5 text-sm text-gray-500">Plant: <span class="font-medium text-gray-700">{{ doc.requesting_plant || '—' }}</span></p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-if="canApprovePo"
            type="button"
            :disabled="acting"
            class="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            @click="rejectPo"
          >Reject</button>
          <button
            v-if="canApprovePo"
            type="button"
            :disabled="acting"
            class="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
            @click="approvePo"
          >{{ acting ? 'Approving…' : 'Approve PO' }}</button>
          <button
            v-if="canDownloadPo"
            type="button"
            class="rounded-lg border border-teal-600 bg-white px-4 py-2 text-sm font-medium text-teal-700 hover:bg-teal-50"
            @click="downloadPurchaseOrderPdf"
          >Download PO PDF</button>
          <button
            v-if="canEditPo && !poQueued && doc.sap_last_error"
            type="button"
            :disabled="acting"
            class="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            @click="retryPosting"
          >Retry SAP Posting</button>
          <StatusBadge :status="doc.status" size="md" />
        </div>
      </header>

      <!-- Status Stepper -->
      <div class="mb-6 rounded-xl border border-gray-200 bg-white px-4 py-4">
        <StatusStepper
          :steps="cprSteps"
          :current="doc.status"
          :is-error="['Cancelled', 'Failed'].includes(doc.status)"
        />
      </div>

      <!-- Draft banner -->
      <div
        v-if="doc.status === 'Draft'"
        class="mb-4 rounded-lg border border-purple-200 bg-purple-50 px-4 py-3 text-sm text-purple-800"
      >
        <p class="font-semibold">Awaiting Super Admin Approval</p>
        <p class="mt-1">PO details have been submitted. A Super Admin needs to review and approve before the Purchase Order is posted to SAP.</p>
      </div>

      <!-- Rejected banner -->
      <div
        v-if="isRejected"
        class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
      >
        <p class="font-semibold">PO Rejected by Super Admin</p>
        <p class="mt-1">The Purchase Order was rejected. Please revise the details and resubmit for approval.</p>
        <button
          v-if="canEditPo && !editPoMode"
          type="button"
          class="mt-2 rounded-lg bg-red-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          @click="editPoMode = true"
        >Revise PO</button>
      </div>

      <!-- Transfer Pending banner -->
      <div
        v-if="doc.status === 'Transfer Pending'"
        class="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800"
      >
        <p class="font-semibold">Awaiting Inter-Plant Transfer</p>
        <p class="mt-1">
          Goods received at <strong>{{ doc.receiving_plant }}</strong>.
          A transfer to <strong>{{ doc.requesting_plant }}</strong> has been created automatically.
          Waiting for {{ doc.receiving_plant }} store manager to dispatch.
        </p>
      </div>

      <!-- Partial GRN banner — shown only to the plant selected to do GRN -->
      <div
        v-if="doc.status === 'PO Raised' && doc.sap_grpo_doc_num && canDoGrn"
        class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      >
        <p class="font-semibold">Partial Goods Receipt Completed</p>
        <p class="mt-1">
          A partial goods receipt has been posted (GRPO# <strong>{{ doc.sap_grpo_doc_num }}</strong>).
          The SAP Purchase Order is still open — please receive the remaining items below.
        </p>
      </div>

      <!-- SAP posting toast -->
      <div
        v-if="sapToast"
        class="mb-4 rounded-lg px-4 py-3 text-sm font-medium"
        :class="sapToast.level === 'success'
          ? 'border border-green-200 bg-green-50 text-green-800'
          : 'border border-red-200 bg-red-50 text-red-800'"
      >{{ sapToast.message }}</div>

      <!-- PO pending spinner -->
      <div
        v-if="poQueued || doc.status === 'PO Posting'"
        class="mb-4 flex items-center gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      >
        <svg class="h-4 w-4 shrink-0 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
        <span>Posting Purchase Order to SAP…</span>
      </div>

      <!-- SAP error detail -->
      <div
        v-if="doc.sap_last_error"
        class="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
      >
        <p class="font-semibold">SAP Error</p>
        <p class="mt-1 whitespace-pre-wrap text-xs">{{ doc.sap_last_error }}</p>
      </div>

      <div class="space-y-6">

        <!-- ── Summary card ── -->
        <section class="rounded-xl border border-gray-200 bg-white p-5">
          <h2 class="mb-4 text-sm font-semibold text-gray-900">Summary</h2>
          <dl class="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div class="min-w-0">
              <dt class="text-xs font-medium text-gray-500">Source Material Request (CMR)</dt>
              <dd class="mt-0.5 font-mono font-medium text-gray-900">{{ doc.cmr_reference || '—' }}</dd>
            </div>
            <div class="min-w-0">
              <dt class="text-xs font-medium text-gray-500">Requested by</dt>
              <dd class="mt-0.5 break-words font-medium text-gray-900">{{ doc.requested_by || '—' }}</dd>
            </div>
            <div class="min-w-0">
              <dt class="text-xs font-medium text-gray-500">Requested on</dt>
              <dd class="mt-0.5 font-medium text-gray-900">{{ formatDate(doc.requested_on) }}</dd>
            </div>
            <div class="min-w-0">
              <dt class="text-xs font-medium text-gray-500">Vendor</dt>
              <dd class="mt-0.5 font-mono font-medium text-gray-900">{{ doc.vendor_code || '—' }}</dd>
            </div>
            <div v-if="doc.receiving_plant" class="min-w-0">
              <dt class="text-xs font-medium text-gray-500">Receiving Plant</dt>
              <dd class="mt-0.5 font-medium text-blue-700">{{ doc.receiving_plant }}</dd>
            </div>
          </dl>

          <div v-if="doc.sap_po_doc_num || doc.sap_grpo_doc_num" class="mt-6 space-y-5 border-t border-gray-100 pt-5">
            <div v-if="doc.sap_po_doc_num">
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">SAP Purchase Order</h3>
              <dl class="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div class="min-w-0">
                  <dt class="text-xs font-medium text-gray-500">SAP PO #</dt>
                  <dd class="mt-0.5 font-mono text-base font-semibold text-green-700">{{ doc.sap_po_doc_num }}</dd>
                </div>
                <div v-if="doc.sap_po_series" class="min-w-0">
                  <dt class="text-xs font-medium text-gray-500">PO Series</dt>
                  <dd class="mt-0.5 font-mono font-medium text-gray-900">{{ doc.sap_po_series }}</dd>
                </div>
                <div v-if="doc.sap_document_date" class="min-w-0">
                  <dt class="text-xs font-medium text-gray-500">Document Date</dt>
                  <dd class="mt-0.5 font-medium tabular-nums text-gray-900">{{ formatDate(doc.sap_document_date) }}</dd>
                </div>
                <div v-if="doc.sap_delivery_date" class="min-w-0">
                  <dt class="text-xs font-medium text-gray-500">Delivery Date</dt>
                  <dd class="mt-0.5 font-medium tabular-nums text-gray-900">{{ formatDate(doc.sap_delivery_date) }}</dd>
                </div>
                <div v-if="doc.sap_ship_to_code" class="min-w-0">
                  <dt class="text-xs font-medium text-gray-500">Ship-to</dt>
                  <dd class="mt-0.5 break-words font-mono text-sm text-gray-900">{{ shipToLabel }}</dd>
                </div>
                <div v-if="doc.sap_bill_to_code" class="min-w-0">
                  <dt class="text-xs font-medium text-gray-500">Bill-to</dt>
                  <dd class="mt-0.5 break-words font-mono text-sm text-gray-900">{{ billToLabel }}</dd>
                </div>
              </dl>
            </div>
            <div v-if="doc.sap_grpo_doc_num">
              <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Goods Receipt (SAP)</h3>
              <dt class="text-xs font-medium text-gray-500">GRPO #</dt>
              <dd class="mt-0.5 font-mono text-base font-semibold text-blue-700">{{ doc.sap_grpo_doc_num }}</dd>
            </div>
          </div>
        </section>

        <!-- ── Warehouse Review ── -->
        <section
          v-if="doc.status === 'Awaiting Warehouse Decision' && canAct"
          class="rounded-xl border border-purple-300 bg-purple-50 p-5"
        >
          <h2 class="mb-4 text-sm font-semibold text-gray-900">Warehouse Review</h2>
          <div class="grid gap-4 sm:grid-cols-3">
            <div class="rounded-lg bg-white p-3">
              <p class="text-xs text-gray-600 mb-1">Available Quantity</p>
              <p class="text-lg font-bold text-gray-900">{{ doc.warehouse_available_qty || 0 }}</p>
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-gray-700">Decision</label>
              <select v-model="warehouseDecision" class="storeops-select w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                <option value="">Select decision…</option>
                <option value="Fulfill from Inventory">✓ Fulfill from Inventory</option>
                <option value="Escalate to Procurement">→ Escalate to Procurement</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-gray-700">Notes</label>
              <textarea v-model="warehouseNotes" rows="2" placeholder="Notes about this decision…" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs resize-none" />
            </div>
          </div>
          <div v-if="actionError" class="mt-2 text-xs text-red-600">{{ actionError }}</div>
          <button
            type="button"
            :disabled="acting || !warehouseDecision"
            class="mt-4 rounded-lg bg-purple-600 px-5 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
            @click="approveWarehouseDecision"
          >{{ acting ? 'Submitting…' : 'Confirm Decision' }}</button>
        </section>

        <!-- ── Raise PO — unified form ── -->
        <section
          v-if="isPoMode && canEditPo"
          class="rounded-xl border border-gray-200 bg-white"
        >
          <div class="border-b border-gray-100 px-5 py-4">
            <h2 class="text-sm font-semibold text-gray-900">Raise Purchase Order</h2>
            <p class="mt-0.5 text-xs text-gray-500">Fill in the PO details below and add all required items, then raise the PO in SAP.</p>
          </div>

          <!-- PO Options grid -->
          <div class="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4" ref="vendorWrap">
            <!-- Vendor -->
            <div class="sm:col-span-2">
              <label class="mb-1 block text-xs font-medium text-gray-700">Vendor <span class="text-red-500">*</span></label>
              <div v-if="selectedVendor" class="flex items-center justify-between gap-2 rounded-lg border border-teal-400 bg-teal-50 px-3 py-2">
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-gray-900">{{ selectedVendor.card_name }}</p>
                  <p class="font-mono text-xs text-gray-500">{{ selectedVendor.card_code }}</p>
                </div>
                <button type="button" class="shrink-0 text-gray-400 hover:text-gray-600" @click="clearVendor">✕</button>
              </div>
              <div v-else class="relative">
                <input
                  v-model="vendorSearch"
                  type="text"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400"
                  placeholder="Search vendor code or name…"
                  autocomplete="off"
                  @input="onVendorInput"
                  @focus="onVendorInput"
                  @keydown.down.prevent="highlightNext"
                  @keydown.up.prevent="highlightPrev"
                  @keydown.enter.prevent="selectHighlighted"
                  @keydown.escape="vendorDropdownOpen = false"
                />
                <span v-if="vendorSearching" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-gray-400">⏳</span>
                <div v-if="vendorDropdownOpen && (vendorResults.length || vendorSearchError)" class="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
                  <div v-if="vendorSearchError" class="px-3 py-2 text-xs text-red-600">{{ vendorSearchError }}</div>
                  <div v-else-if="!vendorResults.length" class="px-3 py-2 text-xs text-gray-400">No vendors found.</div>
                  <button
                    v-for="(v, i) in vendorResults"
                    :key="v.card_code"
                    type="button"
                    class="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left transition-colors"
                    :class="i === highlightedIndex ? 'bg-teal-50' : 'hover:bg-gray-50'"
                    @mouseenter="highlightedIndex = i"
                    @click="selectVendor(v)"
                  >
                    <span class="text-sm font-medium text-gray-900">{{ v.card_name }}</span>
                    <span class="font-mono text-xs text-gray-500">{{ v.card_code }}</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Ship-to -->
            <div>
              <label class="mb-1 block text-xs font-medium text-gray-700">Ship-to Address <span class="text-gray-400 font-normal">(optional)</span></label>
              <select v-model="poOptions.ship_to_code" class="storeops-select w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" :disabled="!plantShipAddresses.length">
                <option value="">{{ plantShipAddresses.length ? '— None —' : 'No addresses in SAP' }}</option>
                <option v-for="a in plantShipAddresses" :key="'s-' + a.address_code" :value="a.address_code">{{ a.label || a.address_code }}</option>
              </select>
            </div>

            <!-- Bill-to -->
            <div>
              <label class="mb-1 block text-xs font-medium text-gray-700">Bill-to Address <span class="text-gray-400 font-normal">(optional)</span></label>
              <select v-model="poOptions.bill_to_code" class="storeops-select w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" :disabled="!selectedVendor || !vendorBillAddresses.length">
                <option value="">{{ !selectedVendor ? 'Select vendor first' : (vendorBillAddresses.length ? '— None —' : 'No addresses found') }}</option>
                <option v-for="a in vendorBillAddresses" :key="'b-' + a.address_code" :value="a.address_code">{{ a.label || a.address_code }}</option>
              </select>
            </div>

            <!-- Receiving Plant -->
            <div class="sm:col-span-2">
              <label class="mb-1 block text-xs font-medium text-gray-700">Receiving Plant <span class="text-gray-400 font-normal">(optional — if goods arrive at a different plant first)</span></label>
              <select v-model="poOptions.receiving_plant" class="storeops-select w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                <option value="">— Same as requesting plant ({{ doc.requesting_plant }}) —</option>
                <option v-for="p in availablePlants.filter(p => p.plant_code !== doc.requesting_plant)" :key="p.plant_code" :value="p.plant_code">{{ p.plant_name || p.plant_code }}</option>
              </select>
              <p class="mt-1 text-xs text-gray-400">If set, an inventory transfer from this plant to {{ doc.requesting_plant }} will be auto-created after GRN.</p>
            </div>
          </div>

          <!-- Line items — table layout -->
          <div class="border-t border-gray-100 px-5 py-4">
            <h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Line Items</h3>

            <div class="overflow-x-auto rounded-lg border border-gray-200">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold text-gray-500">
                    <th v-if="showItemCheckboxes" class="w-8 px-3 py-2"></th>
                    <th class="px-3 py-2">Item</th>
                    <th class="px-3 py-2 text-right">Requested</th>
                    <th class="px-3 py-2">Status</th>
                    <th class="px-3 py-2 min-w-[120px]">Tax Code <span class="text-red-400">*</span></th>
                    <th class="px-3 py-2 min-w-[120px]">Warehouse <span class="text-red-400">*</span></th>
                    <th class="px-3 py-2 min-w-[100px]">PO Qty <span class="text-red-400">*</span></th>
                    <th class="px-3 py-2 min-w-[120px]">Unit Price <span class="text-red-400">*</span></th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="li in doc.line_items" :key="li.item_code" class="bg-white hover:bg-gray-50">
                    <td v-if="showItemCheckboxes" class="px-3 py-2 align-top">
                      <input type="checkbox" :value="li.name" v-model="splitSelection" class="rounded border-gray-300 text-teal-600" />
                    </td>
                    <td class="px-3 py-2">
                      <p class="font-mono text-xs font-semibold text-gray-900">{{ li.item_code }}</p>
                      <p class="text-xs text-gray-500">{{ li.item_name }}</p>
                    </td>
                    <td class="px-3 py-2 text-right text-xs text-gray-700">{{ li.quantity }} {{ li.uom }}</td>
                    <td class="px-3 py-2">
                      <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusClass(li.fulfillment_status)">{{ li.fulfillment_status || 'Pending' }}</span>
                    </td>
                    <td class="px-3 py-2">
                      <input v-model.trim="lineExtras[li.item_code].tax_code" type="text" placeholder="SAP tax code"
                        class="w-full rounded border px-2 py-1 text-xs text-gray-900 focus:ring-1 focus:ring-teal-400 focus:outline-none"
                        :class="lineExtras[li.item_code] && !lineExtras[li.item_code].tax_code ? 'border-red-300' : 'border-gray-300'" />
                      <p v-if="itemTaxHints[li.item_code]?.tax_code" class="mt-0.5 text-[10px] text-gray-400">
                        default: {{ itemTaxHints[li.item_code].tax_code }}
                      </p>
                    </td>
                    <td class="px-3 py-2">
                      <select v-model="lineExtras[li.item_code].warehouse_code"
                        class="w-full rounded border border-gray-300 px-2 py-1 text-xs text-gray-900">
                        <option value="" disabled>Select…</option>
                        <option v-for="w in plantWarehouses" :key="w.warehouse_code" :value="w.warehouse_code">{{ w.warehouse_code }}</option>
                      </select>
                    </td>
                    <td class="px-3 py-2">
                      <input v-model.number="lineExtras[li.item_code].sap_order_qty" type="number" :min="0.01"
                        :max="Math.max(0, (li.quantity || 0) - (li.quantity_received || 0))" step="0.01"
                        class="w-full rounded border border-gray-300 px-2 py-1 text-xs text-gray-900 focus:ring-1 focus:ring-teal-400 focus:outline-none" />
                    </td>
                    <td class="px-3 py-2">
                      <input v-model.number="itemPrices[li.item_code]" type="number" min="0.01" step="0.01" placeholder="0.00"
                        class="w-full rounded border px-2 py-1 text-xs text-gray-900 focus:ring-1 focus:ring-teal-400 focus:outline-none"
                        :class="!itemPrices[li.item_code] || Number(itemPrices[li.item_code]) <= 0 ? 'border-red-300' : 'border-gray-300'" />
                      <div v-if="previousPurchasePrices(li.item_code).length" class="mt-0.5 text-[10px] text-gray-400">
                        <p v-for="(p, i) in previousPurchasePrices(li.item_code)" :key="i">{{ p }}</p>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Split into another vendor's PO -->
            <div v-if="canSplitItems" class="flex items-center justify-between gap-3 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-3">
              <p class="text-xs text-gray-500">
                Sourcing items from more than one vendor? Select the items above that go to a
                different vendor, then split them into a separate purchase request.
              </p>
              <button
                type="button"
                :disabled="!splitSelection.length || splitting"
                class="shrink-0 rounded-lg border border-teal-400 bg-white px-3 py-1.5 text-xs font-medium text-teal-700 hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-50"
                @click="splitSelectedItems"
              >{{ splitting ? 'Splitting…' : `Split ${splitSelection.length || ''} Item${splitSelection.length === 1 ? '' : 's'} Out` }}</button>
            </div>

            <!-- This request is itself a split — let a mistaken item be sent back -->
            <div v-if="doc.split_from" class="flex items-center justify-between gap-3 rounded-lg border border-dashed border-amber-300 bg-amber-50 px-4 py-3">
              <p class="text-xs text-amber-800">
                This request was split from <span class="font-mono font-medium">{{ doc.split_from }}</span>.
                Item split here by mistake? Select it above and remove it — it goes back to the original.
                Removing every item deletes this now-empty request.
              </p>
              <button
                type="button"
                :disabled="!splitSelection.length || removing"
                class="shrink-0 rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                @click="removeSelectedItems"
              >{{ removing ? 'Removing…' : `Remove ${splitSelection.length || ''} Item${splitSelection.length === 1 ? '' : 's'} — Back to Original` }}</button>
            </div>
            <div v-if="splitError" class="text-xs text-red-600">{{ splitError }}</div>
            <div v-if="removeError" class="text-xs text-red-600">{{ removeError }}</div>

            <!-- Extra items added by procurement -->
            <div
              v-for="(ei, idx) in extraItems"
              :key="'extra-' + idx"
              class="rounded-lg border border-blue-200 bg-blue-50 p-4"
            >
              <div class="mb-3 flex items-center justify-between gap-3">
                <span class="text-xs font-semibold uppercase tracking-wide text-blue-700">Additional Item</span>
                <button type="button" class="text-xs text-gray-400 hover:text-red-600" @click="removeExtraItem(idx)">✕ Remove</button>
              </div>
              <!-- Item search -->
              <div class="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div class="relative" :ref="el => { if (el) extraItemRefs[idx] = el }">
                  <label class="mb-1 block text-xs font-medium text-gray-600">Item Code <span class="text-red-400">*</span></label>
                  <div v-if="ei.item_code && ei.item_name" class="flex items-center justify-between gap-2 rounded-lg border border-teal-400 bg-white px-2.5 py-1.5">
                    <div class="min-w-0">
                      <p class="font-mono text-sm font-semibold text-gray-900">{{ ei.item_code }}</p>
                    </div>
                    <button type="button" class="shrink-0 text-xs text-gray-400 hover:text-gray-600" @click="clearExtraItem(idx)">✕</button>
                  </div>
                  <div v-else>
                    <input
                      v-model="ei._search"
                      type="text"
                      placeholder="Search item code or name…"
                      autocomplete="off"
                      class="w-full rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:ring-2 focus:ring-teal-400 focus:outline-none"
                      @input="onExtraItemSearch(idx)"
                    />
                    <span v-if="ei._searching" class="absolute right-2.5 top-8 text-xs text-gray-400">⏳</span>
                    <div v-if="ei._open && (ei._results?.length || ei._error)"
                      class="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                      <div v-if="ei._error" class="px-3 py-2 text-xs text-red-600">{{ ei._error }}</div>
                      <div v-else-if="!ei._results?.length" class="px-3 py-2 text-xs text-gray-400">No items found.</div>
                      <button
                        v-for="r in ei._results"
                        :key="r.item_code"
                        type="button"
                        class="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-teal-50"
                        @click="selectExtraItem(idx, r)"
                      >
                        <span class="font-mono text-sm font-medium text-gray-900">{{ r.item_code }}</span>
                        <span class="text-xs text-gray-500">{{ r.item_name }}</span>
                      </button>
                    </div>
                  </div>
                </div>
                <div>
                  <label class="mb-1 block text-xs font-medium text-gray-600">Item Name</label>
                  <input v-model.trim="ei.item_name" type="text" placeholder="Auto-filled on selection"
                    class="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700" readonly />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <label class="mb-1 block text-xs font-medium text-gray-600">Quantity <span class="text-red-400">*</span></label>
                    <input v-model.number="ei.quantity" type="number" min="0.01" step="0.01"
                      class="w-full rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                  </div>
                  <div>
                    <label class="mb-1 block text-xs font-medium text-gray-600">UOM</label>
                    <input v-model.trim="ei.uom" type="text" placeholder="Pcs"
                      class="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700" />
                  </div>
                </div>
              </div>
              <!-- PO fields -->
              <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div>
                  <label class="mb-1 block text-xs font-medium text-gray-600">Tax Code <span class="text-red-400">*</span></label>
                  <input v-model.trim="ei.tax_code" type="text" placeholder="SAP tax code"
                    class="w-full rounded-lg border px-2.5 py-1.5 text-sm text-gray-900 focus:ring-2 focus:ring-teal-400 focus:outline-none"
                    :class="!ei.tax_code ? 'border-red-300' : 'border-gray-300'" />
                </div>
                <div>
                  <label class="mb-1 block text-xs font-medium text-gray-600">Warehouse <span class="text-red-400">*</span></label>
                  <select v-model="ei.warehouse_code"
                    class="storeops-select w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm text-gray-900">
                    <option value="" disabled>Select…</option>
                    <option v-for="w in plantWarehouses" :key="w.warehouse_code" :value="w.warehouse_code">{{ w.warehouse_code }}</option>
                  </select>
                </div>
                <div>
                  <label class="mb-1 block text-xs font-medium text-gray-600">Unit Price <span class="text-red-400">*</span></label>
                  <input v-model.number="ei.unit_price" type="number" min="0.01" step="0.01" placeholder="0.00"
                    class="w-full rounded-lg border px-2.5 py-1.5 text-sm text-gray-900 focus:ring-2 focus:ring-teal-400 focus:outline-none"
                    :class="!ei.unit_price || Number(ei.unit_price) <= 0 ? 'border-red-300' : 'border-gray-300'" />
                  <div v-if="previousPurchasePrices(ei.item_code).length" class="mt-0.5 text-[10px] text-gray-400">
                    <p class="font-medium">Previous purchases:</p>
                    <p v-for="(p, i) in previousPurchasePrices(ei.item_code)" :key="i">{{ p }}</p>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="!doc.line_items?.length && !extraItems.length" class="rounded-lg border border-dashed border-gray-200 py-6 text-center text-sm text-gray-400">
              No items from the original request.
            </div>

            <!-- Add item button -->
            <button type="button"
              class="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-teal-400 px-4 py-2 text-sm font-medium text-teal-700 hover:border-teal-600 hover:bg-teal-50"
              @click="addExtraItem">
              + Add Item to PO
            </button>
          </div>

          <!-- Raise PO footer -->
          <div class="border-t border-gray-100 px-5 py-4">
            <div v-if="poBlockReason" class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">{{ poBlockReason }}</div>
            <div v-if="actionError" class="mb-3 text-sm text-red-600">{{ actionError }}</div>
            <div class="flex items-center gap-3">
              <button
                type="button"
                :disabled="acting || !canRaisePo"
                class="rounded-lg bg-teal-600 px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-teal-700 disabled:opacity-60"
                @click="raisePO"
              >{{ acting ? 'Submitting…' : 'Submit PO' }}</button>
              <p v-if="!selectedVendor" class="text-xs text-gray-500">Select a vendor to continue.</p>
            </div>
          </div>
        </section>

        <!-- ── Read-only items (post-PO) ── -->
        <template v-if="!isPoMode || !canEditPo">

          <!-- Requested items (from CMR) -->
          <section class="rounded-xl border border-gray-200 bg-white">
            <div class="flex items-center justify-between border-b border-gray-100 px-5 py-3">
              <h2 class="text-sm font-semibold text-gray-900">Requested Items</h2>
              <span class="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-medium text-gray-600">From CMR</span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-gray-50 text-xs uppercase tracking-wider text-gray-600">
                  <tr>
                    <th class="px-4 py-3 text-left font-semibold">Item Code</th>
                    <th class="px-4 py-3 text-left font-semibold">Item Name</th>
                    <th class="px-4 py-3 text-right font-semibold">Ordered</th>
                    <th class="px-4 py-3 text-left font-semibold">UOM</th>
                    <th v-if="showGrnMode" class="px-4 py-3 text-left font-semibold">Batch No.</th>
                    <th v-if="showGrnMode" class="px-4 py-3 text-right font-semibold">Qty to Receive</th>
                    <th class="px-4 py-3 text-left font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="li in cmrLineItems.filter(l => !showGrnMode || l.fulfillment_status !== 'Received')" :key="li.name" class="hover:bg-gray-50">
                    <td class="px-4 py-3 font-medium text-gray-900">{{ li.item_code }}</td>
                    <td class="px-4 py-3 text-gray-700">{{ li.item_name || '—' }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ li.quantity }}</td>
                    <td class="px-4 py-3 text-gray-500">{{ li.uom || '—' }}</td>
                    <td v-if="showGrnMode" class="px-4 py-3">
                      <input v-model.trim="grnBatch[li.name]" type="text" placeholder="Batch no."
                        class="w-28 rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                    </td>
                    <td v-if="showGrnMode" class="px-4 py-3 text-right">
                      <input v-model.number="grnQty[li.name]" type="number" min="0" :max="Math.max(0, (li.quantity || 0) - (li.quantity_received || 0))" step="0.01"
                        class="w-24 rounded-lg border border-gray-300 px-2 py-1.5 text-right text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                    </td>
                    <td class="px-4 py-3">
                      <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusClass(li.fulfillment_status)">{{ li.fulfillment_status || 'Pending' }}</span>
                    </td>
                  </tr>
                  <tr v-if="!cmrLineItems.length">
                    <td colspan="8" class="px-4 py-8 text-center text-gray-400">No items.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- Procurement additions (extra items added by procurement) -->
          <section v-if="procurementAddedItems.length" class="rounded-xl border border-purple-200 bg-white">
            <div class="flex items-center justify-between border-b border-purple-100 px-5 py-3">
              <h2 class="text-sm font-semibold text-gray-900">Procurement Additions</h2>
              <span class="rounded-full bg-purple-100 px-2.5 py-0.5 text-[11px] font-medium text-purple-700">Added by Procurement</span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-purple-50 text-xs uppercase tracking-wider text-purple-700">
                  <tr>
                    <th class="px-4 py-3 text-left font-semibold">Item Code</th>
                    <th class="px-4 py-3 text-left font-semibold">Item Name</th>
                    <th class="px-4 py-3 text-right font-semibold">Ordered</th>
                    <th class="px-4 py-3 text-left font-semibold">UOM</th>
                    <th v-if="showGrnMode" class="px-4 py-3 text-left font-semibold">Batch No.</th>
                    <th v-if="showGrnMode" class="px-4 py-3 text-right font-semibold">Qty to Receive</th>
                    <th class="px-4 py-3 text-left font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-purple-50">
                  <tr v-for="li in procurementAddedItems.filter(l => !showGrnMode || l.fulfillment_status !== 'Received')" :key="li.name" class="hover:bg-purple-50">
                    <td class="px-4 py-3 font-medium text-gray-900">{{ li.item_code }}</td>
                    <td class="px-4 py-3 text-gray-700">{{ li.item_name || '—' }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ li.quantity }}</td>
                    <td class="px-4 py-3 text-gray-500">{{ li.uom || '—' }}</td>
                    <td v-if="showGrnMode" class="px-4 py-3">
                      <input v-model.trim="grnBatch[li.name]" type="text" placeholder="Batch no."
                        class="w-28 rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                    </td>
                    <td v-if="showGrnMode" class="px-4 py-3 text-right">
                      <input v-model.number="grnQty[li.name]" type="number" min="0" :max="Math.max(0, (li.quantity || 0) - (li.quantity_received || 0))" step="0.01"
                        class="w-24 rounded-lg border border-gray-300 px-2 py-1.5 text-right text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                    </td>
                    <td class="px-4 py-3">
                      <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusClass(li.fulfillment_status)">{{ li.fulfillment_status || 'Pending' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

        </template>

        <!-- ── GRN panel ── -->
        <section
          v-if="['PO Raised', 'GRN Done'].includes(doc.status) && canDoGrn && doc.line_items?.some(li => li.fulfillment_status !== 'Received')"
          class="rounded-xl border border-blue-300 bg-blue-50 p-5"
        >
          <h2 class="mb-1 text-sm font-semibold text-gray-900">Record Goods Receipt (GRN)</h2>
          <p class="mb-4 text-xs text-gray-600">Enter quantities and batch numbers received, then submit to post the GRPO in SAP.</p>
          <div v-if="!showGrnMode">
            <button type="button" class="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700" @click="showGrnMode = true">
              Enter Received Quantities
            </button>
          </div>
          <div v-else>
            <div v-if="actionError" class="mb-3 text-sm text-red-600">{{ actionError }}</div>
            <div class="flex flex-wrap gap-2">
              <button type="button" :disabled="acting"
                class="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                @click="submitGrn">{{ acting ? 'Submitting…' : 'Submit Goods Receipt (GRN) to SAP' }}</button>
              <button type="button" :disabled="acting"
                class="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                @click="rejectGrnDelivery">Reject Delivery</button>
              <button type="button" :disabled="acting"
                class="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 disabled:opacity-50"
                @click="showGrnMode = false">Cancel</button>
            </div>
          </div>
        </section>

        <!-- ── Success ── -->
        <div v-if="actionSuccess" class="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{{ actionSuccess }}</div>

      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { StatusBadge, StatusStepper } from '@/shared/components/index.js'
import { useStoreopsSocket } from '@/composables/useStoreopsSocket.js'
import {
  get_purchase_request,
  get_split_family,
  raise_purchase_order,
  submit_grn,
  retry_sap_posting,
  approve_warehouse_decision,
  search_vendors,
  list_vendor_po_addresses,
  list_plant_ship_addresses,
  get_items_tax_info,
  get_purchase_order_pdf_url,
  approve_purchase_order,
  reject_purchase_order,
  split_purchase_request,
  remove_split_item,
} from '@/core/api/procurement.js'
import { parseApiError } from '@/utils/error.js'
import { fetchWarehouses, fetchInventory } from '@/core/api/inventory.js'
import { get_destination_plants } from '@/core/api/transfers.js'

function unwrapList(res) {
  const r = res?.message ?? res
  return Array.isArray(r) ? r : []
}

const route     = useRoute()
const router    = useRouter()
const authStore = useAuthStore()

const doc          = ref(null)
const loading      = ref(false)
const loadError    = ref('')
const splitFamily  = ref([])
const acting       = ref(false)
const actionError  = ref('')
const actionSuccess = ref('')
const showGrnMode  = ref(false)
const grnBatch     = ref({})
const grnQty       = ref({})
const itemPrices   = ref({})
const editPoMode = ref(false)
const poQueued  = ref(false)
const grnQueued = ref(false)
const sapToast = ref(null)
const warehouseDecision = ref('')
const warehouseNotes = ref('')
const poOptions = ref({
  ship_to_code: '',
  bill_to_code: '',
  receiving_plant: '',
})
const availablePlants = ref([])
const lineExtras = ref({})
const plantWarehouses = ref([])
const plantShipAddresses = ref([])
const vendorBillAddresses = ref([])
const itemTaxHints = ref({})   // item_code → { tax_code, tax_rate }

let poQueuedTimeout = null
let pollInterval    = null

// Vendor autocomplete
const vendorWrap       = ref(null)
const vendorSearch     = ref('')
const selectedVendor   = ref(null)
const vendorResults    = ref([])
const vendorDropdownOpen = ref(false)
const vendorSearching  = ref(false)
const vendorSearchError = ref('')
const highlightedIndex = ref(-1)
let vendorDebounce     = null

const extraItems = ref([])
const extraItemRefs = ref([])
let extraItemDebounces = []

function downloadPurchaseOrderPdf() {
  if (!doc.value?.name) return
  window.open(get_purchase_order_pdf_url(doc.value.name), '_blank', 'noopener')
}

function previousPurchasePrices(itemCode) {
  const info = itemTaxHints.value[itemCode] || {}
  const history = info.previous_purchase_prices
  if (Array.isArray(history) && history.length) {
    return history
      .slice(0, 3)
      .map(h => `${h.currency ? h.currency + ' ' : ''}${Number(h.price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`)
  }
  const price = Number(info.previous_purchase_price || 0)
  if (!price) return []
  const currency = info.previous_purchase_currency || ''
  return [`${currency ? currency + ' ' : ''}${price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`]
}

function addExtraItem() {
  const firstWh = plantWarehouses.value[0]?.warehouse_code || ''
  extraItems.value.push({
    item_code: '', item_name: '', uom: '', quantity: 1,
    purpose: '', tax_code: '', warehouse_code: firstWh, unit_price: '',
    _search: '', _searching: false, _results: [], _open: false, _error: '',
  })
}

function removeExtraItem(idx) {
  extraItems.value.splice(idx, 1)
  extraItemDebounces.splice(idx, 1)
  extraItemRefs.value.splice(idx, 1)
}

function clearExtraItem(idx) {
  const ei = extraItems.value[idx]
  ei.item_code = ''
  ei.item_name = ''
  ei.uom = ''
  ei._search = ''
  ei._results = []
  ei._open = false
}

function onExtraItemSearch(idx) {
  const ei = extraItems.value[idx]
  ei._open = true
  ei._error = ''
  clearTimeout(extraItemDebounces[idx])
  const q = (ei._search || '').trim()
  if (q.length < 2) { ei._results = []; ei._open = false; return }
  ei._searching = true
  extraItemDebounces[idx] = setTimeout(() => fetchExtraItemResults(idx, q), 300)
}

async function fetchExtraItemResults(idx, q) {
  const ei = extraItems.value[idx]
  if (!ei) return
  const plant = doc.value?.requesting_plant
  if (!plant) { ei._searching = false; return }
  const warehouses = plantWarehouses.value.map(w => w.warehouse_code).filter(Boolean)
  if (!warehouses.length) { ei._searching = false; return }
  try {
    const payloads = await Promise.all(
      warehouses.map(wh =>
        fetchInventory(plant, wh, { search: q, page: 1, page_size: 50, paginate_by_item: 1 }).catch(() => ({ items: [] }))
      )
    )
    if (!extraItems.value[idx]) return
    const seen = new Set()
    const merged = []
    for (const p of payloads) {
      for (const item of (p?.items || [])) {
        if (!seen.has(item.item_code)) {
          seen.add(item.item_code)
          merged.push(item)
        }
      }
    }
    ei._results = merged
    ei._open = true
    ei._error = ''
  } catch {
    if (extraItems.value[idx]) ei._error = 'SAP search failed.'
  } finally {
    if (extraItems.value[idx]) ei._searching = false
  }
}

async function selectExtraItem(idx, item) {
  const ei = extraItems.value[idx]
  ei.item_code = item.item_code
  ei.item_name = item.item_name || item.description || ''
  ei.uom = item.uom || item.inv_uom || ''
  ei._search = ''
  ei._results = []
  ei._open = false
  if (ei.item_code && !itemTaxHints.value[ei.item_code]) {
    try {
      const res = await get_items_tax_info(JSON.stringify([ei.item_code]))
      itemTaxHints.value = { ...itemTaxHints.value, ...(res?.message ?? res ?? {}) }
    } catch {
      // Previous price is a hint only; don't block item selection.
    }
  }
}

const cprSteps = [
  { key: ['submitted', 'draft', 'po pending', 'awaiting warehouse decision'], label: 'Submitted' },
  { key: ['po posting', 'po raised'],      label: 'PO Raised' },
  { key: ['grn done', 'transfer pending'], label: 'Goods Received (GRN)' },
]

const docName = computed(() => route.params.name)
const canAct    = computed(() => authStore.isSuperAdmin || authStore.isProcurementUser || authStore.isManager)
const canEditPo = computed(() => authStore.isSuperAdmin || authStore.isProcurementUser)

// GRN: Store Manager only — Procurement Users are explicitly excluded even if they hold both roles.
// For inter-plant CPRs the GRN is done at the receiving plant; otherwise at the requesting plant.
const canDoGrn = computed(() => {
  if (authStore.isSuperAdmin) return true
  if (authStore.isProcurementUser) return false   // procurement users never do GRN
  const grnRoles = ['Consumables Store Manager', 'Consumables Inventory Manager']
  if (!authStore.consumablesRoles.some(r => grnRoles.includes(r))) return false
  const grnPlant = doc.value?.receiving_plant || doc.value?.requesting_plant
  if (!grnPlant) return false
  return authStore.plants.some((p) => p.plant_code === grnPlant)
})
const isRejected = computed(() => doc.value?.status === 'PO Pending' && !!doc.value?.vendor_code)
const isPoMode = computed(() => {
  if (editPoMode.value && canEditPo.value) return true
  const s = doc.value?.status || ''
  if (s === 'Submitted') return true
  if (s === 'PO Pending' && !doc.value?.vendor_code) return true
  return false
})
const canDownloadPo = computed(() => !!(doc.value?.sap_po_doc_num || doc.value?.sap_po_doc_entry))
const canApprovePo = computed(() => authStore.isSuperAdmin && doc.value?.status === 'Draft')

// Split into another vendor's PO — only before a PO is raised, and only when there's
// more than one item to split from (splitting the whole thing out is pointless).
const canSplitItems = computed(() => canEditPo.value && (doc.value?.line_items?.length || 0) > 1)
// Checkbox column shows for splitting out (needs 2+ items) OR removing a
// mistaken item back to the original (works even down to the last item).
const showItemCheckboxes = computed(() => canSplitItems.value || (canEditPo.value && !!doc.value?.split_from))
const splitSelection = ref([])
const splitting = ref(false)
const splitError = ref('')

// Send a mistakenly-split item back to the request it was split from.
const removing = ref(false)
const removeError = ref('')


const cmrLineItems = computed(() => (doc.value?.line_items || []).filter(li => !li.is_extra_item))
const procurementAddedItems = computed(() => (doc.value?.line_items || []).filter(li => !!li.is_extra_item))

const shipToLabel = computed(() => {
  const code = doc.value?.sap_ship_to_code || ''
  if (!code) return ''
  const match = plantShipAddresses.value.find(a => a.address_code === code)
  return match ? match.label : code
})
const billToLabel = computed(() => {
  const code = doc.value?.sap_bill_to_code || ''
  if (!code) return ''
  const match = vendorBillAddresses.value.find(a => a.address_code === code)
  return match ? match.label : code
})


const poBlockReason = computed(() => {
  if (!selectedVendor.value) return 'Select a vendor first.'
  for (const li of doc.value?.line_items || []) {
    const p = itemPrices.value[li.item_code]
    if (!p || Number(p) <= 0) return `Enter unit price for ${li.item_code}.`
    const ex = lineExtras.value[li.item_code]
    if (!ex || !(ex.tax_code || '').trim()) return `Enter tax code for ${li.item_code}.`
    if (!(ex.warehouse_code || '').trim()) return `Select warehouse for ${li.item_code}.`
  }
  for (const [idx, ei] of extraItems.value.entries()) {
    if (!ei.item_code.trim()) return `Enter item code for extra item row ${idx + 1}.`
    if (!ei.quantity || Number(ei.quantity) <= 0) return `Enter quantity for ${ei.item_code || 'extra item ' + (idx + 1)}.`
    if (!ei.tax_code.trim()) return `Enter tax code for ${ei.item_code}.`
    if (!ei.warehouse_code) return `Select warehouse for ${ei.item_code}.`
    if (!ei.unit_price || Number(ei.unit_price) <= 0) return `Enter unit price for ${ei.item_code}.`
  }
  return ''
})

const canRaisePo = computed(() => {
  if (poBlockReason.value) return false
  const hasOriginal = doc.value?.line_items?.length > 0
  const hasExtra = extraItems.value.length > 0
  if (!hasOriginal && !hasExtra) return false
  const originalOk = (doc.value?.line_items || []).every((li) => {
    const ex = lineExtras.value[li.item_code]
    if (!ex) return false
    const qty = Number(ex.sap_order_qty)
    if (!Number.isFinite(qty) || qty <= 0) return false
    if (qty - Number(li.quantity || 0) > 0.0001) return false
    return true
  })
  const extraOk = extraItems.value.every((ei) =>
    ei.item_code.trim() && Number(ei.quantity) > 0 && ei.tax_code.trim() && ei.warehouse_code && Number(ei.unit_price) > 0
  )
  return originalOk && extraOk
})

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling() {
  stopPolling()
  // Snapshot the modified timestamp at the moment polling starts.
  // Any write by the background job (sap_last_error, status, sap_po_doc_num)
  // bumps `modified`, so we detect completion reliably without comparing strings.
  const snapModified = doc.value?.modified || ''
  pollInterval = setInterval(async () => {
    const prevStatus = doc.value?.status
    await silentLoad()
    const newModified = doc.value?.modified || ''
    const newStatus   = doc.value?.status
    const newErr      = doc.value?.sap_last_error
    if (newModified !== snapModified) {
      poQueued.value  = false
      grnQueued.value = false
      stopPolling()
      clearTimeout(poQueuedTimeout)
      if (newErr) {
        sapToast.value = { message: 'SAP posting failed. See error details below.', level: 'error' }
      } else if (newStatus === 'PO Raised') {
        if (doc.value?.sap_grpo_doc_num) {
          // Status stayed PO Raised after GRN — SAP PO still open (partial GRN)
          sapToast.value = { message: `Partial GRN done. GRPO# ${doc.value?.sap_grpo_doc_num}. SAP PO still open — remaining items can be received.`, level: 'info' }
        } else {
          sapToast.value = { message: `Purchase Order posted to SAP. PO# ${doc.value?.sap_po_doc_num}`, level: 'success' }
        }
      } else if (newStatus === 'GRN Done' || newStatus === 'Transfer Pending') {
        sapToast.value = { message: `GRN posted to SAP. GRPO# ${doc.value?.sap_grpo_doc_num}`, level: 'success' }
      }
      setTimeout(() => { sapToast.value = null }, 7000)
    }
  }, 3000)
}

function stopPolling() {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
}

async function silentLoad() {
  try {
    const res = await get_purchase_request(route.params.name)
    const fresh = res?.message ?? res
    if (fresh) doc.value = fresh
  } catch (e) {
    if (e?.status === 401 || e?.status === 403 || e?.exc_type === 'AuthenticationError') {
      window.location.href = '/login'
    }
  }
}

function armSafetyTimeout() {
  clearTimeout(poQueuedTimeout)
  // SAP PO posting can take 1-2 min (Service Layer latency + queue wait).
  // Reload every 3 min to keep the spinner alive and re-snapshot modified timestamp.
  poQueuedTimeout = setTimeout(async () => {
    poQueued.value  = false
    grnQueued.value = false
    stopPolling()
    await load()
  }, 180000)
}

// Socket (belt-and-suspenders with polling)
useStoreopsSocket(docName, async (payload) => {
  poQueued.value  = false
  grnQueued.value = false
  stopPolling()
  clearTimeout(poQueuedTimeout)
  sapToast.value = { message: payload.message, level: payload.level || 'info' }
  await load()
  setTimeout(() => { sapToast.value = null }, 7000)
})

watch(
  () => selectedVendor.value?.card_code,
  async (code) => {
    if (!canEditPo.value) return
    vendorBillAddresses.value = []
    poOptions.value.bill_to_code = doc.value?.sap_bill_to_code || ''
    if (!code) return
    try {
      const billRes = await list_vendor_po_addresses(code, 'B')
      vendorBillAddresses.value = unwrapList(billRes)
      if (!poOptions.value.bill_to_code && vendorBillAddresses.value.length > 0) {
        poOptions.value.bill_to_code = vendorBillAddresses.value[0].address_code
      }
    } catch {
      vendorBillAddresses.value = []
    }
  },
  { immediate: true },
)

watch(() => poOptions.value.receiving_plant, async (newPlant) => {
  if (!canEditPo.value) return
  const warehousePlant = newPlant || doc.value?.requesting_plant
  if (!warehousePlant) return
  try {
    const wRes = await fetchWarehouses(warehousePlant)
    const raw = wRes?.message ?? wRes
    plantWarehouses.value = Array.isArray(raw?.warehouses) ? raw.warehouses : []
  } catch {
    plantWarehouses.value = []
  }
  // Reset all line item warehouses to the new plant's first warehouse
  const firstWh = plantWarehouses.value[0]?.warehouse_code || ''
  for (const code of Object.keys(lineExtras.value)) {
    lineExtras.value[code] = { ...lineExtras.value[code], warehouse_code: firstWh }
  }
})

async function hydratePoForm() {
  // Only procurement users and admins need the PO form data (warehouses, addresses, tax hints).
  // Store managers / inventory managers open the CPR solely to do GRN — skip all of this.
  if (!canEditPo.value) return

  if (!doc.value?.requesting_plant) {
    plantWarehouses.value = []
    plantShipAddresses.value = []
    lineExtras.value = {}
    itemTaxHints.value = {}
    return
  }

  // Load warehouses from receiving_plant if set, otherwise requesting_plant
  const warehousePlant = poOptions.value.receiving_plant || doc.value.requesting_plant
  try {
    const wRes = await fetchWarehouses(warehousePlant)
    const raw = wRes?.message ?? wRes
    plantWarehouses.value = Array.isArray(raw?.warehouses) ? raw.warehouses : []
  } catch {
    plantWarehouses.value = []
  }

  // Fetch ship-to from SAP OWHS using plant's warehouse codes
  try {
    const shipRes = await list_plant_ship_addresses(doc.value.requesting_plant)
    plantShipAddresses.value = unwrapList(shipRes)
  } catch {
    plantShipAddresses.value = []
  }

  // Restore saved ship-to or auto-select first
  const savedShip = doc.value.sap_ship_to_code || ''
  if (savedShip && plantShipAddresses.value.some(a => a.address_code === savedShip)) {
    poOptions.value.ship_to_code = savedShip
  } else if (plantShipAddresses.value.length > 0) {
    poOptions.value.ship_to_code = plantShipAddresses.value[0].address_code
  } else {
    poOptions.value.ship_to_code = ''
  }

  // Fetch item tax info from SAP for pre-filling tax code hints
  const itemCodes = (doc.value.line_items || []).map(li => li.item_code).filter(Boolean)
  if (itemCodes.length) {
    try {
      const taxRes = await get_items_tax_info(JSON.stringify(itemCodes))
      itemTaxHints.value = taxRes?.message ?? taxRes ?? {}
    } catch {
      itemTaxHints.value = {}
    }
  }

  // Initialise lineExtras for all items; pre-fill tax code from SAP item master
  const firstWh = plantWarehouses.value[0]?.warehouse_code || ''
  const next = {}
  for (const li of doc.value.line_items || []) {
    const code = li.item_code
    if (!code) continue
    const ord = Number(li.quantity || 0)
    const sapTax = itemTaxHints.value[code]?.tax_code || ''
    next[code] = {
      item_purpose: li.item_purpose || '',
      tax_code: li.tax_code || sapTax,
      warehouse_code: li.warehouse_code || firstWh,
      sap_order_qty: (li.sap_order_qty && Number(li.sap_order_qty) > 0) ? Number(li.sap_order_qty) : ord,
    }
  }
  lineExtras.value = next
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function formatDate(val) {
  if (!val) return '—'
  return new Date(val).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function statusClass(s) {
  if (s === 'Received') return 'bg-green-100 text-green-800'
  if (s === 'Partial')  return 'bg-amber-100 text-amber-800'
  return 'bg-gray-100 text-gray-700'
}

// ── Vendor autocomplete ──────────────────────────────────────────────────────
function onVendorInput() {
  vendorDropdownOpen.value = true
  highlightedIndex.value = -1
  clearTimeout(vendorDebounce)
  const q = vendorSearch.value.trim()
  if (q.length < 2) { vendorResults.value = []; vendorDropdownOpen.value = false; return }
  vendorSearching.value = true
  vendorSearchError.value = ''
  vendorDebounce = setTimeout(() => fetchVendors(q), 300)
}

async function fetchVendors(q) {
  try {
    const res = await search_vendors(q)
    vendorResults.value = res?.message ?? res ?? []
    vendorDropdownOpen.value = true
  } catch (e) {
    vendorSearchError.value = parseApiError(e, 'Search failed.')
    vendorResults.value = []
  } finally {
    vendorSearching.value = false
  }
}

function selectVendor(v) {
  selectedVendor.value = v
  vendorSearch.value = ''
  vendorResults.value = []
  vendorDropdownOpen.value = false
  highlightedIndex.value = -1
}

function clearVendor() {
  selectedVendor.value = null
  vendorSearch.value = ''
  vendorResults.value = []
  vendorDropdownOpen.value = false
  vendorBillAddresses.value = []
  poOptions.value.bill_to_code = ''
}

function highlightNext() {
  if (!vendorResults.value.length) return
  highlightedIndex.value = Math.min(highlightedIndex.value + 1, vendorResults.value.length - 1)
}
function highlightPrev() {
  highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
}
function selectHighlighted() {
  if (highlightedIndex.value >= 0 && vendorResults.value[highlightedIndex.value]) {
    selectVendor(vendorResults.value[highlightedIndex.value])
  }
}

function onClickOutside(e) {
  if (vendorWrap.value && !vendorWrap.value.contains(e.target)) vendorDropdownOpen.value = false
  for (const [idx, ref] of extraItemRefs.value.entries()) {
    if (ref && !ref.contains(e.target) && extraItems.value[idx]) {
      extraItems.value[idx]._open = false
    }
  }
}

async function loadSplitFamily() {
  if (!doc.value?.name) {
    splitFamily.value = []
    return
  }
  try {
    const res = await get_split_family(doc.value.name)
    splitFamily.value = (res?.message ?? res)?.items ?? []
  } catch {
    splitFamily.value = []
  }
}

// ── Data loading ─────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  loadError.value = ''
  editPoMode.value = false
  try {
    const res = await get_purchase_request(route.params.name)
    doc.value = res?.message ?? res
    if (doc.value) {
      loadSplitFamily()
      extraItems.value = []
      if (doc.value.vendor_code) {
        selectedVendor.value = { card_code: doc.value.vendor_code, card_name: doc.value.vendor_code }
      } else {
        selectedVendor.value = null
      }
      warehouseDecision.value = doc.value.warehouse_decision || ''
      warehouseNotes.value = doc.value.warehouse_notes || ''
      grnQty.value = Object.fromEntries(
        (doc.value.line_items || []).map((li) => {
          const remaining = (li.quantity || 0) - (li.quantity_received || 0)
          return [li.name, Math.max(0, remaining)]
        }),
      )
      grnBatch.value = Object.fromEntries(
        (doc.value.line_items || []).map((li) => [li.name, li.batch_number || '']),
      )
      itemPrices.value = Object.fromEntries(
        (doc.value.line_items || []).map((li) => [
          li.item_code,
          li.po_unit_price && Number(li.po_unit_price) > 0 ? Number(li.po_unit_price) : '',
        ]),
      )
      // Pre-init lineExtras with defaults so v-model never reads from undefined
      const extras = {}
      for (const li of doc.value.line_items || []) {
        if (li.item_code) {
          extras[li.item_code] = {
            item_purpose: li.item_purpose || '',
            tax_code: li.tax_code || '',
            warehouse_code: li.warehouse_code || '',
            sap_order_qty: li.sap_order_qty || 0,
          }
        }
      }
      lineExtras.value = extras
      // Pre-fill receiving_plant from saved doc so hydratePoForm loads the right warehouses
      if (doc.value.receiving_plant) {
        poOptions.value.receiving_plant = doc.value.receiving_plant
      }
      await hydratePoForm()
      // Auto-start polling if PO posting was in progress when page was loaded/refreshed
      if (doc.value.status === 'PO Posting' && !pollInterval) {
        poQueued.value = true
        armSafetyTimeout()
        startPolling()
      }
    }
  } catch (e) {
    loadError.value = parseApiError(e, 'Failed to load.')
  } finally {
    loading.value = false
  }
}

// ── Actions ──────────────────────────────────────────────────────────────────
async function splitSelectedItems() {
  if (!splitSelection.value.length || !doc.value?.name) return
  splitting.value = true
  splitError.value = ''
  try {
    const res = await split_purchase_request(doc.value.name, JSON.stringify(splitSelection.value))
    const newName = res?.message?.new?.name ?? res?.new?.name
    splitSelection.value = []
    await load()
    actionSuccess.value = newName
      ? `Items split into new purchase request ${newName}.`
      : 'Items split into a new purchase request.'
  } catch (e) {
    splitError.value = parseApiError(e, 'Failed to split items.')
  } finally {
    splitting.value = false
  }
}

async function removeSelectedItems() {
  if (!splitSelection.value.length || !doc.value?.name) return
  const originalName = doc.value.split_from
  removing.value = true
  removeError.value = ''
  try {
    const res = await remove_split_item(doc.value.name, JSON.stringify(splitSelection.value))
    const result = res?.message ?? res
    splitSelection.value = []
    if (result?.source_deleted) {
      // This request no longer exists — go back to the original it was split from.
      router.push({ name: 'ProcurementDetail', params: { name: originalName } })
      return
    }
    await load()
    actionSuccess.value = `Item(s) moved back to ${result?.target?.name || originalName}.`
  } catch (e) {
    removeError.value = parseApiError(e, 'Failed to remove item(s).')
  } finally {
    removing.value = false
  }
}

async function raisePO() {
  if (!selectedVendor.value || !canRaisePo.value) return
  acting.value = true
  actionError.value = ''
  try {
    await raise_purchase_order(
      doc.value.name,
      selectedVendor.value.card_code,
      JSON.stringify(itemPrices.value),
      JSON.stringify({
        ship_to_code: (poOptions.value.ship_to_code || '').trim(),
        bill_to_code: (poOptions.value.bill_to_code || '').trim(),
        receiving_plant: (poOptions.value.receiving_plant || '').trim(),
      }),
      JSON.stringify(lineExtras.value),
      JSON.stringify(extraItems.value),
    )
    await load()
    if (doc.value?.sap_last_error) {
      actionError.value = doc.value.sap_last_error
    } else if (doc.value?.status === 'Draft') {
      actionSuccess.value = 'PO submitted. Awaiting Super Admin approval.'
    } else {
      actionSuccess.value = `Purchase Order posted to SAP. PO# ${doc.value?.sap_po_doc_num || ''}`
    }
  } catch (e) {
    actionError.value = parseApiError(e, 'Failed to submit PO.')
    poQueued.value = false
  } finally {
    acting.value = false
  }
}

async function approveWarehouseDecision() {
  if (!warehouseDecision.value) return
  acting.value = true
  actionError.value = ''
  try {
    const res = await approve_warehouse_decision(doc.value.name, warehouseDecision.value, warehouseNotes.value)
    actionSuccess.value = res?.message || 'Warehouse decision recorded.'
    await load()
  } catch (e) {
    actionError.value = parseApiError(e, 'Failed to submit warehouse decision.')
  } finally {
    acting.value = false
  }
}

async function submitGrn() {
  const allLineItems = doc.value?.line_items || []
  const receivingRows = allLineItems.filter(li => Number(grnQty.value[li.name] || 0) > 0)
  const missingBatch = receivingRows.find(li => !String(grnBatch.value[li.name] || '').trim())
  if (missingBatch) {
    actionError.value = `Batch number is mandatory for item ${missingBatch.item_code}.`
    return
  }
  acting.value = true
  actionError.value = ''
  try {
    const grn_items = allLineItems
      .filter(li => Number(grnQty.value[li.name] ?? 0) > 0)
      .map((li) => ({
        row_name: li.name,
        item_code: li.item_code,
        quantity_received: Number(grnQty.value[li.name]),
        batch_number: String(grnBatch.value[li.name] || '').trim(),
      }))
    await submit_grn(doc.value.name, grn_items)
    showGrnMode.value = false
    await load()
    if (doc.value?.sap_last_error) {
      actionError.value = doc.value.sap_last_error
    } else if (doc.value?.status === 'PO Raised' && doc.value?.sap_grpo_doc_num) {
      actionSuccess.value = `Partial GRN done. GRPO# ${doc.value?.sap_grpo_doc_num}. SAP PO still open — remaining items can be received.`
    } else {
      actionSuccess.value = `GRN posted to SAP. GRPO# ${doc.value?.sap_grpo_doc_num || ''}`
    }
  } catch (e) {
    actionError.value = parseApiError(e, 'Failed to submit GRN.')
  } finally {
    acting.value = false
  }
}

function rejectGrnDelivery() {
  // Zero out all GRN quantities to record a full rejection
  grnQty.value = Object.fromEntries(Object.keys(grnQty.value).map(k => [k, 0]))
  grnBatch.value = Object.fromEntries(Object.keys(grnBatch.value).map(k => [k, '']))
  showGrnMode.value = false
  actionError.value = 'Delivery rejected — no goods received. Contact the vendor to arrange redelivery.'
}

async function rejectPo() {
  acting.value = true
  actionError.value = ''
  try {
    await reject_purchase_order(doc.value.name)
    await load()
    actionSuccess.value = 'PO rejected. Returned to procurement for revision.'
  } catch (e) {
    actionError.value = parseApiError(e, 'Failed to reject PO.')
  } finally {
    acting.value = false
  }
}

async function approvePo() {
  acting.value = true
  actionError.value = ''
  try {
    await approve_purchase_order(doc.value.name)
    poQueued.value = true
    armSafetyTimeout()
    startPolling()
    await load()
  } catch (e) {
    actionError.value = parseApiError(e, 'Failed to approve PO.')
  } finally {
    acting.value = false
  }
}

async function retryPosting() {
  acting.value = true
  actionError.value = ''
  try {
    await retry_sap_posting(doc.value.name)
    await load()
    if (doc.value?.sap_last_error) {
      actionError.value = doc.value.sap_last_error
    } else {
      actionSuccess.value = `Purchase Order posted to SAP. PO# ${doc.value?.sap_po_doc_num || ''}`
    }
  } catch (e) {
    actionError.value = parseApiError(e, 'Retry failed.')
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  load()
  document.addEventListener('click', onClickOutside)
  try {
    const res = await get_destination_plants()
    availablePlants.value = (res?.message ?? res) || []
  } catch {}
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  clearTimeout(vendorDebounce)
  clearTimeout(poQueuedTimeout)
  stopPolling()
})
</script>
