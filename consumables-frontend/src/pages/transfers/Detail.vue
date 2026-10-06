<template>
  <div class="p-4 sm:p-6">

    <!-- Loading / Error -->
    <div v-if="transfersStore.loading && !doc" class="py-16 text-center text-gray-400">Loading…</div>
    <div v-else-if="loadErr" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{{ loadErr }}</div>

    <template v-else-if="doc">
      <!-- ── Header ── -->
      <header class="mb-6 flex flex-wrap items-start justify-between gap-4">
        <!-- Breadcrumb -->
        <div class="w-full">
          <div class="flex items-center gap-1.5 text-xs text-gray-500">
            <RouterLink to="/transfers" class="hover:text-teal-700">Transfers (CTR)</RouterLink>
            <span>›</span>
            <span class="font-medium text-gray-700">{{ doc.name }}</span>
          </div>
        </div>
        <div class="flex min-w-0 items-center gap-3">
          <div class="min-w-0">
            <h1 class="truncate font-mono text-xl font-semibold text-gray-900 sm:text-2xl">{{ doc.name }}</h1>
            <p class="mt-0.5 text-sm text-gray-500">
              <span class="font-medium text-gray-700">{{ doc.from_plant || '—' }}</span>
              <span class="mx-1.5 text-gray-400">→</span>
              <span class="font-medium text-gray-700">{{ doc.to_plant || '—' }}</span>
            </p>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <!-- Header action buttons (non-destructive) -->
          <button
            v-if="canSubmit"
            type="button"
            :disabled="actionBusy"
            class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            @click="doSubmit"
          >{{ actionBusy ? 'Saving…' : 'Submit for Approval' }}</button>

          <button
            v-if="canApprove"
            type="button"
            :disabled="actionBusy"
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            @click="showApproveDialog = true"
          >Approve</button>

          <button
            v-if="canRejectRow"
            type="button"
            :disabled="actionBusy"
            class="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            @click="showRejectDialog = true"
          >Reject</button>

          <button
            v-if="canDispatch"
            type="button"
            :disabled="actionBusy"
            class="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
            @click="openDispatchDialog"
          >Dispatch</button>

          <button
            v-if="canDownloadChallan"
            type="button"
            :disabled="actionBusy || challanLoading"
            class="rounded-lg border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
            @click="openChallanModal"
          >{{ challanLoading ? 'Exporting…' : 'Download Delivery Challan' }}</button>

          <button
            v-if="canRetrySap"
            type="button"
            :disabled="actionBusy"
            class="rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900 disabled:opacity-50"
            @click="doRetrySap"
          >Retry SAP</button>

          <StatusBadge v-if="doc.status" :status="doc.status" size="md" />
        </div>
      </header>

      <!-- Status Stepper -->
      <div class="mb-6 rounded-xl border border-gray-200 bg-white px-4 py-4">
        <StatusStepper
          :steps="ctrSteps"
          :current="doc.status || 'Submitted'"
          :is-error="['Rejected', 'Failed', 'Partially Received'].includes(doc.status)"
        />
        <p v-if="stageInfo.next" class="mt-3 border-t border-gray-100 pt-3 text-xs text-gray-500">
          <span class="font-medium text-gray-700">Next:</span> {{ stageInfo.next }}
        </p>
      </div>

      <!-- ── Content grid ── -->
      <div class="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div class="space-y-6">

          <!-- Summary card -->
          <section class="rounded-xl border border-gray-200 bg-white p-5">
            <h2 class="mb-4 text-sm font-semibold text-gray-900">Summary</h2>
            <dl class="grid gap-3 text-sm sm:grid-cols-2 md:grid-cols-3">
              <div>
                <dt class="text-gray-500">From</dt>
                <dd class="font-medium text-gray-900">{{ doc.from_plant || '—' }}</dd>
                <dd class="text-xs text-gray-500">{{ doc.from_warehouse || '' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">To</dt>
                <dd class="font-medium text-gray-900">{{ doc.to_plant || '—' }}</dd>
                <dd class="text-xs text-gray-500">{{ doc.to_warehouse || '' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Requested By</dt>
                <dd class="font-medium text-gray-900">{{ doc.requested_by || doc.owner || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Date</dt>
                <dd class="font-medium text-gray-900">{{ fmtDate(doc.requested_on || doc.creation) }}</dd>
              </div>
              <div v-if="doc.approved_by">
                <dt class="text-gray-500">Approved By</dt>
                <dd class="font-medium text-gray-900">{{ doc.approved_by }}</dd>
              </div>
              <div v-if="doc.dispatched_by">
                <dt class="text-gray-500">Dispatched By</dt>
                <dd class="font-medium text-gray-900">{{ doc.dispatched_by }}</dd>
              </div>
              <div v-if="doc.received_by">
                <dt class="text-gray-500">Received By</dt>
                <dd class="font-medium text-gray-900">{{ doc.received_by }}</dd>
              </div>
            </dl>
          </section>

          <!-- SAP references (manager/admin only) -->
          <section v-if="showSapBlock" class="rounded-xl border border-gray-200 bg-white p-5">
            <h2 class="mb-4 text-sm font-semibold text-gray-900">SAP References</h2>
            <dl class="space-y-2 text-sm">
              <div v-if="doc.sap_transfer_doc_num" class="flex justify-between">
                <dt class="text-gray-500">Dispatch Transfer (→ In-Transit)</dt>
                <dd class="font-mono font-medium text-gray-900">{{ doc.sap_transfer_doc_num }}</dd>
              </div>
              <div v-if="doc.sap_transfer_request_doc_num" class="flex justify-between">
                <dt class="text-gray-500">Final Transfer (In-Transit →)</dt>
                <dd class="font-mono font-medium text-gray-900">{{ doc.sap_transfer_request_doc_num }}</dd>
              </div>
              <div v-if="doc.sap_last_error" class="mt-2 rounded-lg bg-red-50 p-3 text-xs text-red-700">
                <p class="font-semibold">SAP Error</p>
                <p class="mt-1 whitespace-pre-wrap">{{ doc.sap_last_error }}</p>
              </div>
              <p
                v-if="!doc.sap_transfer_request_doc_num && !doc.sap_transfer_doc_num && !doc.sap_last_error"
                class="text-sm text-gray-400"
              >No SAP references yet.</p>
            </dl>
          </section>

          <!-- Line items table -->
          <section class="rounded-xl border border-gray-200 bg-white">
            <div class="border-b border-gray-100 px-5 py-3">
              <h2 class="text-sm font-semibold text-gray-900">Line Items</h2>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-gray-50 text-xs uppercase tracking-wider text-gray-600">
                  <tr>
                    <th class="px-4 py-3 text-left font-semibold">Item Code</th>
                    <th class="px-4 py-3 text-left font-semibold">Item Name</th>
                    <th class="px-4 py-3 text-left font-semibold">Batch</th>
                    <th class="px-4 py-3 text-right font-semibold">Qty</th>
                    <th class="px-4 py-3 text-left font-semibold">UOM</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="(row, idx) in lineRows" :key="idx" class="hover:bg-gray-50">
                    <td class="px-4 py-3 font-medium text-gray-900">{{ row.item_code }}</td>
                    <td class="px-4 py-3 text-gray-700">{{ row.item_name || '—' }}</td>
                    <td class="px-4 py-3 font-mono text-xs text-gray-600">{{ row.batch_number || '—' }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ row.quantity }}</td>
                    <td class="px-4 py-3 text-gray-500">{{ row.uom || '—' }}</td>
                  </tr>
                  <tr v-if="!lineRows.length">
                    <td colspan="5" class="px-4 py-8 text-center text-gray-400">No line items.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- Confirm receipt (full-width prominent block) -->
          <section
            v-if="canReceive"
            class="rounded-xl border-2 border-teal-500 bg-teal-50 p-5"
          >
            <h2 class="text-sm font-semibold text-gray-900">Confirm Receipt</h2>
            <p class="mt-1 text-sm text-gray-600">
              Stock has physically arrived at your plant. Enter the quantities actually received — partial quantities or full rejection are both supported.
            </p>
            <div class="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                :disabled="actionBusy"
                class="rounded-lg bg-teal-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
                @click="openReceiveDialog"
              >
                {{ actionBusy ? 'Processing…' : 'Confirm Receipt' }}
              </button>
              <button
                type="button"
                :disabled="actionBusy"
                class="rounded-lg border border-red-300 bg-white px-6 py-2.5 text-sm font-semibold text-red-700 shadow-sm hover:bg-red-50 disabled:opacity-50"
                @click="openRejectReceiptDialog"
              >
                Reject Delivery
              </button>
            </div>
          </section>

          <!-- Received vs dispatched summary (after receipt) -->
          <section
            v-if="showReceiptSummary"
            class="rounded-xl border border-gray-200 bg-white"
          >
            <div class="border-b border-gray-100 px-5 py-3 flex items-center justify-between">
              <h2 class="text-sm font-semibold text-gray-900">Receipt Summary</h2>
              <span v-if="doc.receipt_notes" class="text-xs text-gray-500 italic">{{ doc.receipt_notes }}</span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-gray-50 text-xs uppercase tracking-wider text-gray-600">
                  <tr>
                    <th class="px-4 py-3 text-left font-semibold">Item</th>
                    <th class="px-4 py-3 text-right font-semibold">Dispatched</th>
                    <th class="px-4 py-3 text-right font-semibold">Received</th>
                    <th class="px-4 py-3 text-right font-semibold">Shortfall</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="(row, idx) in lineRows" :key="`rs-${idx}`" class="hover:bg-gray-50">
                    <td class="px-4 py-3">
                      <p class="font-medium text-gray-900">{{ row.item_code }}</p>
                      <p class="text-xs text-gray-500">{{ row.item_name || '' }}</p>
                    </td>
                    <td class="px-4 py-3 text-right text-gray-700">{{ row.quantity_dispatched || row.quantity }}</td>
                    <td class="px-4 py-3 text-right font-medium" :class="receiptQtyClass(row)">{{ row.quantity_received }}</td>
                    <td class="px-4 py-3 text-right text-sm">
                      <span v-if="shortfallFor(row) > 0" class="text-red-600 font-medium">-{{ shortfallFor(row) }}</span>
                      <span v-else class="text-green-600">✓</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

        </div>

        <!-- ── Right sidebar ── -->
        <aside class="space-y-4">
          <!-- Current stage -->
          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-2 text-sm font-semibold text-gray-900">Current Stage</h2>
            <p class="text-sm font-medium text-gray-800">{{ stageInfo.current }}</p>
            <p class="mt-1 text-xs text-gray-500">Owned by: {{ stageInfo.owner }}</p>
            <p class="mt-2 text-xs text-gray-600">{{ stageInfo.next }}</p>
          </section>

          <!-- Workflow timeline -->
          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Workflow</h2>
            <ol class="relative ml-2 space-y-4 border-l border-gray-200 pl-5">
              <li v-for="ev in timelineEvents" :key="ev.key" class="relative">
                <span class="absolute -left-[1.4rem] top-1 h-3 w-3 rounded-full bg-teal-600 ring-4 ring-white" />
                <p class="text-sm font-medium text-gray-900">{{ ev.title }}</p>
                <p class="text-xs text-gray-500">
                  <template v-if="ev.when">{{ fmtWhen(ev.when) }}</template>
                  <template v-if="ev.who"> · {{ ev.who }}</template>
                </p>
              </li>
            </ol>
          </section>
        </aside>
      </div>
    </template>

    <!-- Dialogs -->
    <ConfirmDialog
      :visible="showApproveDialog"
      title="Approve Transfer"
      :message="`Approve ${doc?.name}? Stock will be transferred to in-transit warehouse when dispatched.`"
      confirm-text="Approve"
      variant="success"
      @confirm="doApprove"
      @cancel="showApproveDialog = false"
    />

    <ConfirmDialog
      :visible="showRejectDialog"
      title="Reject Transfer"
      :message="`Reject ${doc?.name}? Provide a reason.`"
      confirm-text="Reject"
      variant="danger"
      show-input
      input-placeholder="Reason for rejection…"
      @confirm="doReject"
      @cancel="showRejectDialog = false"
    />

    <!-- Dispatch dialog with multi-batch inputs -->
    <div v-if="showDispatchDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div class="border-b border-gray-100 px-6 py-4">
          <h2 class="text-base font-semibold text-gray-900">Dispatch Transfer — {{ doc?.name }}</h2>
          <p class="mt-1 text-sm text-gray-500">Select batch(es) for each item. Split across batches if needed.</p>
        </div>
        <div class="max-h-[28rem] overflow-y-auto px-6 py-4 space-y-5">
          <div v-if="batchesLoading" class="py-8 text-center text-sm text-gray-400">Loading batches from warehouse…</div>
          <template v-else>
            <div v-for="(row, idx) in dispatchBatches" :key="idx" class="rounded-lg border border-gray-200 p-3">
              <!-- Item header -->
              <div class="mb-2 flex items-baseline justify-between">
                <span class="text-sm font-medium text-gray-800">
                  {{ row.item_code }}<span v-if="row.item_name" class="ml-1 font-normal text-gray-500">— {{ row.item_name }}</span>
                </span>
                <span class="text-xs" :class="splitTotal(row) === row.quantity ? 'text-green-600 font-medium' : 'text-gray-400'">
                  {{ splitTotal(row) }} / {{ row.quantity }} {{ row.uom }}
                </span>
              </div>

              <!-- No batches available -->
              <p v-if="row.available_batches.length === 0" class="text-xs text-amber-600">No batches available in source warehouse for this item.</p>

              <template v-else>
                <!-- Batch split rows -->
                <div v-for="(split, si) in row.splits" :key="si" class="mb-2 flex items-center gap-2">
                  <select
                    v-model="split.batch_number"
                    class="flex-1 rounded-lg border px-2 py-1.5 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                    :class="dispatchSubmitted && !split.batch_number ? 'border-red-400 bg-red-50' : 'border-gray-300'"
                  >
                    <option value="">— Select batch —</option>
                    <option v-for="b in row.available_batches" :key="b.batch_number" :value="b.batch_number">
                      {{ b.batch_number }} · Avail: {{ b.quantity }} {{ row.uom }}
                    </option>
                  </select>
                  <input
                    v-model.number="split.quantity"
                    type="number"
                    min="0.001"
                    :max="row.quantity"
                    class="w-20 rounded-lg border border-gray-300 px-2 py-1.5 text-right text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                    :class="dispatchSubmitted && split.quantity <= 0 ? 'border-red-400 bg-red-50' : ''"
                  />
                  <button
                    v-if="row.splits.length > 1"
                    type="button"
                    class="shrink-0 text-gray-400 hover:text-red-500"
                    @click="row.splits.splice(si, 1)"
                  >✕</button>
                </div>

                <!-- Validation messages -->
                <p v-if="dispatchSubmitted && row.splits.some(s => !s.batch_number)" class="mb-1 text-xs text-red-600">Select a batch for each row.</p>
                <p v-if="dispatchSubmitted && splitTotal(row) !== row.quantity" class="mb-1 text-xs text-red-600">
                  Quantities must add up to {{ row.quantity }} {{ row.uom }} (currently {{ splitTotal(row) }}).
                </p>

                <!-- Add another batch -->
                <button
                  v-if="row.available_batches.length > row.splits.length"
                  type="button"
                  class="mt-1 text-xs font-medium text-teal-600 hover:text-teal-700"
                  @click="row.splits.push({ batch_number: '', quantity: 0 })"
                >+ Add another batch</button>
              </template>
            </div>
          </template>
        </div>
        <div class="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            @click="showDispatchDialog = false; dispatchSubmitted = false"
          >Cancel</button>
          <button
            type="button"
            :disabled="actionBusy || batchesLoading"
            class="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50"
            @click="doDispatch"
          >{{ actionBusy ? 'Dispatching…' : 'Confirm Dispatch' }}</button>
        </div>
      </div>
    </div>

    <!-- Receipt qty modal -->
    <div v-if="showReceiveDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div class="border-b border-gray-100 px-6 py-4">
          <h2 class="text-base font-semibold text-gray-900">Confirm Receipt — {{ doc?.name }}</h2>
          <p class="mt-1 text-sm text-gray-500">Enter the quantity physically received. Leave at dispatched amount if all items arrived correctly.</p>
        </div>
        <div class="px-6 py-4 space-y-3">
          <div v-for="item in receiveQtys" :key="item.row_index" class="flex items-center justify-between gap-4">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-gray-800 truncate">{{ item.item_code }}</p>
              <p class="text-xs text-gray-500 truncate">{{ item.batch_number || item.item_name }}</p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <input
                v-model.number="item.received"
                type="number"
                min="0"
                :max="item.dispatched"
                class="w-24 rounded-lg border px-2 py-1.5 text-right text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
                :class="item.received < item.dispatched ? 'border-amber-400 bg-amber-50' : 'border-gray-300'"
              />
              <span class="text-xs text-gray-400">/ {{ item.dispatched }} {{ item.uom }}</span>
            </div>
          </div>

          <!-- Partial receipt warning -->
          <div v-if="isPartialReceipt" class="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <p class="font-semibold">Partial receipt detected</p>
            <p class="mt-0.5">A purchase order will be automatically raised for the shortfall. Please add a reason below.</p>
          </div>

          <!-- Notes field (required for partial, optional for full) -->
          <div class="pt-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Notes {{ isPartialReceipt ? '(required)' : '(optional)' }}
            </label>
            <textarea
              v-model="receiptNotes"
              rows="2"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              :class="isPartialReceipt && !receiptNotes.trim() && receiveSubmitted ? 'border-red-400' : ''"
              placeholder="e.g. 2 units damaged on arrival, batch X short-shipped..."
            />
            <p v-if="isPartialReceipt && !receiptNotes.trim() && receiveSubmitted" class="mt-1 text-xs text-red-600">Reason is required for partial receipt.</p>
          </div>
        </div>
        <div class="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button type="button" class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50" @click="showReceiveDialog = false; receiveSubmitted = false">Cancel</button>
          <button type="button" :disabled="actionBusy" class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50" @click="doReceive">
            {{ actionBusy ? 'Processing…' : (isPartialReceipt ? 'Confirm Partial Receipt' : 'Confirm Receipt') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delivery Challan modal -->
    <div v-if="showChallanModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-md rounded-2xl bg-white shadow-xl">
        <div class="border-b border-gray-100 px-6 py-4">
          <h2 class="text-base font-semibold text-gray-900">Download Delivery Challan</h2>
          <p class="mt-1 text-sm text-gray-500">Enter the SAP document number for the dispatch stock transfer.</p>
        </div>
        <div class="px-6 py-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">SAP Doc Entry <span class="text-red-600">*</span></label>
          <input
            v-model.trim="challanDocNumber"
            type="text"
            placeholder="e.g. 21541"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            :class="challanSubmitted && !challanDocNumber ? 'border-red-400' : ''"
            @keydown.enter="doDownloadChallan"
          />
          <p v-if="challanSubmitted && !challanDocNumber" class="mt-1 text-xs text-red-600">Doc entry is required.</p>
        </div>
        <div class="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button type="button" class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50" @click="showChallanModal = false; challanSubmitted = false">Cancel</button>
          <button type="button" :disabled="challanLoading" class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50" @click="doDownloadChallan">
            {{ challanLoading ? 'Exporting PDF…' : 'Download PDF' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reject at receipt dialog -->
    <div v-if="showRejectReceiptDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-md rounded-2xl bg-white shadow-xl">
        <div class="border-b border-gray-100 px-6 py-4">
          <h2 class="text-base font-semibold text-gray-900">Reject Delivery — {{ doc?.name }}</h2>
          <p class="mt-1 text-sm text-gray-500">
            Record that nothing was accepted. A new purchase order will be raised automatically for all items.
          </p>
        </div>
        <div class="px-6 py-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Rejection reason <span class="text-red-600">*</span></label>
          <textarea
            v-model="rejectReceiptReason"
            rows="3"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
            :class="rejectReceiptSubmitted && !rejectReceiptReason.trim() ? 'border-red-400' : ''"
            placeholder="e.g. Items not received, vehicle not arrived, wrong goods delivered..."
          />
          <p v-if="rejectReceiptSubmitted && !rejectReceiptReason.trim()" class="mt-1 text-xs text-red-600">Rejection reason is required.</p>
        </div>
        <div class="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button type="button" class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50" @click="showRejectReceiptDialog = false; rejectReceiptSubmitted = false">Cancel</button>
          <button type="button" :disabled="actionBusy" class="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50" @click="doRejectReceipt">
            {{ actionBusy ? 'Processing…' : 'Confirm Rejection' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'frappe-ui'
import { useAuthStore } from '@/stores/auth.js'
import { useTransfersStore } from '@/stores/transfers.js'
import { StatusBadge, StatusStepper, ConfirmDialog } from '@/shared/components/index.js'
import { useStoreopsSocket } from '@/composables/useStoreopsSocket.js'
import { parseApiError } from '@/utils/error.js'
import { get_transfer_dispatch_batches, download_delivery_challan } from '@/core/api/transfers.js'

const route = useRoute()
const authStore = useAuthStore()
const transfersStore = useTransfersStore()

const loadErr                 = ref('')
const actionBusy              = ref(false)
const showApproveDialog       = ref(false)
const showRejectDialog        = ref(false)
const showDispatchDialog      = ref(false)
const showReceiveDialog       = ref(false)
const showRejectReceiptDialog = ref(false)
const receiveQtys             = ref([])
const receiptNotes            = ref('')
const receiveSubmitted        = ref(false)
const rejectReceiptReason     = ref('')
const rejectReceiptSubmitted  = ref(false)
const dispatchBatches         = ref([])
const dispatchSubmitted       = ref(false)
const batchesLoading          = ref(false)
const showChallanModal        = ref(false)
const challanDocNumber        = ref('')
const challanLoading          = ref(false)
const challanSubmitted        = ref(false)

const ctrSteps = [
  { key: 'draft',              label: 'Submitted' },
  { key: 'submitted',          label: 'Awaiting Approval' },
  { key: 'approved',           label: 'Approved' },
  { key: 'in transit',         label: 'In Transit' },
  { key: ['completed', 'partially received'], label: 'Completed' },
]

const docName = () => decodeURIComponent(String(route.params.name || ''))
const doc     = computed(() => transfersStore.currentTransfer)
const lineRows = computed(() => Array.isArray(doc.value?.line_items) ? doc.value.line_items : [])

const showSapBlock = computed(() =>
  authStore.isSuperAdmin || authStore.consumablesRoles.includes('Consumables Store Manager'),
)
const isManagerOrAdmin = computed(() =>
  authStore.isSuperAdmin ||
  authStore.consumablesRoles.includes('Consumables Store Manager') ||
  authStore.consumablesRoles.includes('Consumables Inventory Manager'),
)
const canApproveTransfer = computed(() =>
  authStore.isSuperAdmin || (
    authStore.consumablesRoles.includes('Consumables Store Manager') &&
    authStore.consumablesRoles.includes('Consumables Inventory Manager')
  ),
)

function userAtDestination() {
  const to = doc.value?.to_plant
  if (!to) return false
  return (authStore.plants || []).some((p) => p.plant_code === to)
}

const canSubmit    = computed(() => doc.value?.status === 'Draft' && (authStore.user === doc.value?.owner || isManagerOrAdmin.value))
const canApprove   = computed(() => doc.value?.status === 'Submitted' && canApproveTransfer.value)
const canRejectRow = computed(() => canApprove.value)
const canDispatch  = computed(
  () => doc.value?.status === 'Approved' && (authStore.isSuperAdmin || authStore.consumablesRoles.includes('Consumables Inventory Manager')),
)
const canReceive   = computed(() => doc.value?.status === 'In Transit' && userAtDestination())
const canRetrySap  = computed(() => isManagerOrAdmin.value && doc.value?.status === 'Failed')

function userAtSource() {
  const from = doc.value?.from_plant
  if (!from) return false
  return (authStore.plants || []).some((p) => p.plant_code === from)
}
const canDownloadChallan = computed(() =>
  doc.value?.status === 'In Transit' &&
  isManagerOrAdmin.value
)
const showReceiptSummary = computed(() =>
  ['Completed', 'Partially Received'].includes(doc.value?.status) &&
  lineRows.value.some(r => r.quantity_dispatched > 0 || r.quantity_received > 0),
)
const isPartialReceipt = computed(() =>
  receiveQtys.value.some(r => Number(r.received) < Number(r.dispatched)),
)

const stageInfo = computed(() => {
  const s = doc.value?.status
  const map = {
    Draft:      { current: 'Submitted',                 owner: 'Store Manager',             next: 'Submit to send for Super Admin approval.' },
    Submitted:  { current: 'Awaiting approval',        owner: 'Super Admin',               next: 'Approve to create SAP Transfer Request.' },
    Approved:   { current: 'Ready to dispatch',        owner: 'Inventory Manager',         next: 'Dispatch when items leave the source plant.' },
    'In Transit': { current: 'In transit',             owner: 'Destination plant',         next: 'Confirm receipt when items arrive.' },
    Completed:           { current: 'Completed',              owner: 'Process finished',            next: 'SAP transfer posted and closed.' },
    'Partially Received': { current: 'Partially received',    owner: 'Destination plant',           next: 'A purchase order has been raised for the shortfall. Check linked CPR.' },
    Failed:              { current: 'SAP posting failed',     owner: 'Super Admin / Store Manager', next: 'Use Retry SAP after resolving the SAP error.' },
    Rejected:            { current: 'Rejected',               owner: 'Super Admin',                 next: 'Create a new request if needed.' },
  }
  return map[s] || { current: s || 'Unknown', owner: '—', next: '—' }
})

const timelineEvents = computed(() => {
  const d = doc.value
  if (!d) return []
  const evts = []
  if (d.requested_on || d.creation) evts.push({ key: 'requested',  title: 'Requested',            when: d.requested_on || d.creation, who: d.requested_by || d.owner })
  if (d.submitted_on)  evts.push({ key: 'submitted',  title: 'Submitted',            when: d.submitted_on,  who: d.submitted_by })
  if (d.approved_on)   evts.push({ key: 'approved',   title: 'Approved',             when: d.approved_on,   who: d.approved_by })
  if (d.dispatched_on) evts.push({ key: 'dispatched', title: 'Dispatched (In Transit)', when: d.dispatched_on, who: d.dispatched_by })
  if (d.received_on)   evts.push({ key: 'received',   title: 'Received',             when: d.received_on,   who: d.received_by })
  if (d.status === 'Rejected') evts.push({ key: 'rejected', title: 'Rejected', when: d.modified, who: '—' })
  return evts.sort((a, b) => new Date(a.when) - new Date(b.when))
})

function fmtDate(val) {
  if (!val) return '—'
  return new Date(val).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtWhen(val) {
  if (!val) return ''
  const d = new Date(val)
  return Number.isNaN(d.getTime()) ? String(val) : d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

function openChallanModal() {
  challanDocNumber.value = doc.value?.sap_transfer_doc_entry || ''
  challanSubmitted.value = false
  showChallanModal.value = true
}

async function doDownloadChallan() {
  challanSubmitted.value = true
  if (!challanDocNumber.value) return
  challanLoading.value = true
  try {
    const res = await download_delivery_challan(docName(), challanDocNumber.value)
    const data = res?.message ?? res
    const raw = data?.base64 || data
    if (!raw) { toast.error('No PDF data returned from SAP'); return }
    const base64 = String(raw).replace(/[\r\n\s]/g, '')
    let byteNums
    try {
      const byteChars = atob(base64)
      byteNums = new Uint8Array(byteChars.length)
      for (let i = 0; i < byteChars.length; i++) byteNums[i] = byteChars.charCodeAt(i)
    } catch {
      toast.error('PDF decode failed — check SAP Crystal Reports response format')
      return
    }
    const blob = new Blob([byteNums], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = data?.filename || `DeliveryChallan_${docName()}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showChallanModal.value = false
    toast.success('Delivery challan downloaded')
  } catch (e) {
    toast.error(parseApiError(e, 'Failed to export delivery challan'))
  } finally {
    challanLoading.value = false
  }
}

async function loadDoc() {
  loadErr.value = ''
  const name = docName()
  if (!name) { loadErr.value = 'Missing document name'; return }
  transfersStore.currentTransfer = null
  try {
    await transfersStore.fetchTransfer(name)
  } catch (e) {
    loadErr.value = transfersStore.error || parseApiError(e, 'Failed to load transfer')
  }
}

async function wrap(fn, successMsg = 'Updated') {
  actionBusy.value = true
  try {
    await fn()
    await transfersStore.fetchTransfer(docName(), { silent: true })
    toast.success(successMsg)
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

function doSubmit()  { wrap(() => transfersStore.submitTransfer(docName()), 'Submitted for approval') }
function doApprove() { showApproveDialog.value = false; wrap(() => transfersStore.approveTransfer(docName()), 'Transfer approved') }
function openReceiveDialog() {
  receiptNotes.value = ''
  receiveSubmitted.value = false
  receiveQtys.value = (doc.value?.line_items || []).map((li, idx) => ({
    row_index: idx,
    item_code: li.item_code || '',
    item_name: li.item_name || '',
    batch_number: li.batch_number || '',
    uom: li.uom || '',
    dispatched: Number(li.quantity || 0),
    received: Number(li.quantity || 0),
  }))
  showReceiveDialog.value = true
}

function openRejectReceiptDialog() {
  rejectReceiptReason.value = ''
  rejectReceiptSubmitted.value = false
  showRejectReceiptDialog.value = true
}

function doReceive() {
  receiveSubmitted.value = true
  if (isPartialReceipt.value && !receiptNotes.value.trim()) return
  showReceiveDialog.value = false
  receiveSubmitted.value = false
  const received_items = receiveQtys.value.map(r => ({
    row_index: r.row_index,
    quantity_received: Number(r.received || 0),
  }))
  const successMsg = isPartialReceipt.value
    ? 'Partial receipt confirmed — shortfall purchase order created'
    : 'Receipt confirmed — SAP transfer posted'
  wrap(
    () => transfersStore.receiveTransfer(docName(), received_items, receiptNotes.value.trim()),
    successMsg,
  )
}

function doRejectReceipt() {
  rejectReceiptSubmitted.value = true
  if (!rejectReceiptReason.value.trim()) return
  showRejectReceiptDialog.value = false
  rejectReceiptSubmitted.value = false
  // Send all items with 0 received and the reason as notes
  const received_items = (doc.value?.line_items || []).map((_, idx) => ({
    row_index: idx,
    quantity_received: 0,
  }))
  wrap(
    () => transfersStore.receiveTransfer(docName(), received_items, rejectReceiptReason.value.trim()),
    'Delivery rejected — a purchase order will be raised for the full quantity',
  )
}

function receiptQtyClass(row) {
  const received = Number(row.quantity_received || 0)
  const dispatched = Number(row.quantity_dispatched || row.quantity || 0)
  if (received <= 0) return 'text-red-600'
  if (received < dispatched) return 'text-amber-600'
  return 'text-green-600'
}

function shortfallFor(row) {
  const dispatched = Number(row.quantity_dispatched || row.quantity || 0)
  const received = Number(row.quantity_received || 0)
  return Math.max(0, dispatched - received)
}

async function openDispatchDialog() {
  dispatchSubmitted.value = false
  dispatchBatches.value = []
  showDispatchDialog.value = true
  batchesLoading.value = true
  try {
    const res = await get_transfer_dispatch_batches(docName())
    const rows = Array.isArray(res?.message) ? res.message : (Array.isArray(res) ? res : [])
    dispatchBatches.value = rows
      .filter(r => r.available_batches && r.available_batches.length > 0)
      .map(r => ({
        item_code: r.item_code || '',
        item_name: r.item_name || '',
        quantity: r.quantity || 0,
        uom: r.uom || '',
        available_batches: r.available_batches || [],
        splits: [{ batch_number: r.stored_batch || '', quantity: r.quantity || 0 }],
      }))
  } catch (e) {
    toast.error(parseApiError(e, 'Failed to load batches from warehouse'))
    showDispatchDialog.value = false
  } finally {
    batchesLoading.value = false
  }
}

function splitTotal(row) {
  return row.splits.reduce((s, sp) => s + Number(sp.quantity || 0), 0)
}

function doDispatch() {
  dispatchSubmitted.value = true
  const hasError = dispatchBatches.value.some(r =>
    r.available_batches.length > 0 && (
      r.splits.some(s => !s.batch_number.trim() || Number(s.quantity) <= 0) ||
      Math.abs(splitTotal(r) - r.quantity) > 0.001
    )
  )
  if (hasError) return
  showDispatchDialog.value = false
  dispatchSubmitted.value = false
  // Flatten splits: one entry per batch row (backend groups by item_code)
  const batchItems = dispatchBatches.value.flatMap(r =>
    r.splits.map(s => ({
      item_code: r.item_code,
      batch_number: s.batch_number.trim(),
      quantity: Number(s.quantity),
    }))
  )
  wrap(() => transfersStore.dispatchTransfer(docName(), batchItems), 'Dispatched — now in transit')
}
function doRetrySap() { wrap(() => transfersStore.retrySapPosting(docName()), 'SAP retry queued') }

function doReject(reason) {
  showRejectDialog.value = false
  if (!reason?.trim()) return
  wrap(() => transfersStore.rejectTransfer(docName(), reason.trim()), 'Transfer rejected')
}

useStoreopsSocket(docName, () => {
  transfersStore.fetchTransfer(docName(), { silent: true }).catch(() => {})
})

watch(() => route.params.name, loadDoc)
loadDoc()
</script>
