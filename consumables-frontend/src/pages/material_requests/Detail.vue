<template>
  <div class="max-w-6xl p-4 sm:p-6">

    <div v-if="materialRequestsStore.loading && !doc" class="py-16 text-center text-gray-500">
      Loading...
    </div>

    <div
      v-else-if="loadErr"
      class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {{ loadErr }}
    </div>

    <template v-else-if="doc">
      <!-- Breadcrumb -->
      <div class="mb-4 flex items-center gap-1.5 text-xs text-gray-500">
        <RouterLink to="/material-requests" class="hover:text-teal-700">Material Requests (CMR)</RouterLink>
        <span>›</span>
        <span class="font-medium text-gray-700">{{ doc.name }}</span>
      </div>

      <!-- Header -->
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 sm:gap-4">
        <div class="min-w-0 flex-1">
          <h1 class="break-all font-mono text-lg font-bold text-gray-900 sm:text-2xl">{{ doc.name }}</h1>
          <p class="mt-0.5 text-sm text-gray-500">
            Plant: <span class="font-medium text-gray-700">{{ doc.plant_code || '—' }}</span>
            <span v-if="doc.urgency && doc.urgency !== 'Normal'"
              class="ml-2 rounded px-1.5 py-0.5 text-[10px] font-bold"
              :class="doc.urgency === 'Critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'">
              {{ doc.urgency }}
            </span>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <StatusBadge :status="doc.status || 'Submitted'" size="md" />
        </div>
      </div>

      <!-- Status Stepper -->
      <div class="mb-6 rounded-xl border border-gray-200 bg-white px-4 py-4">
        <StatusStepper
          :steps="cmrSteps"
          :current="doc.status || 'Submitted'"
          :is-error="['Rejected', 'Cancelled'].includes(doc.status)"
        />
        <p v-if="stepHint" class="mt-3 border-t border-gray-100 pt-3 text-xs text-gray-500">{{ stepHint }}</p>
      </div>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div class="space-y-6">
          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Request Details</h2>
            <dl class="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt class="text-gray-500">Request ID</dt>
                <dd class="font-mono text-gray-900">{{ doc.name }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Status</dt>
                <dd class="text-gray-900">{{ doc.status || 'Submitted' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Urgency</dt>
                <dd class="text-gray-900">{{ doc.urgency || 'Medium' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Requested By</dt>
                <dd class="text-gray-900">{{ doc.requested_by || doc.owner || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Plant</dt>
                <dd class="text-gray-900">{{ doc.plant_code || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Date</dt>
                <dd class="text-gray-900">{{ formatWhen(doc.transaction_date || doc.creation) || '—' }}</dd>
              </div>
              <div class="sm:col-span-2">
                <dt class="text-gray-500">Reason</dt>
                <dd class="whitespace-pre-wrap text-gray-900">{{ doc.reason || '—' }}</dd>
              </div>
            </dl>
          </section>

          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Requested Items &amp; Fulfillment Progress</h2>
            <div class="space-y-4">
              <div v-for="(row, idx) in lineRows" :key="`${row.item_code}-${idx}`" class="rounded-lg border border-gray-200 p-3">
                <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p class="text-sm font-medium text-gray-900">
                    {{ row.item_code }} <span class="text-gray-600">· {{ row.item_name || '—' }}</span>
                  </p>
                  <p class="text-xs text-gray-600">
                    Requested: {{ fmtQty(row.quantity || row.requested_quantity) }} {{ row.uom || '' }}
                  </p>
                </div>
                <div class="h-2 overflow-hidden rounded-full bg-gray-200">
                  <div
                    class="h-full rounded-full bg-teal-600"
                    :style="{ width: `${itemProgress(row)}%` }"
                  />
                </div>
                <p class="mt-1 text-xs text-gray-600">
                  <span class="font-semibold text-teal-700">{{ fmtQty(receivedDisplayQty(row)) }}</span>
                  <span class="text-gray-400"> / </span>
                  <span>{{ fmtQty(row.quantity || row.requested_quantity || 0) }} {{ row.uom || 'Pcs' }} received</span>
                </p>
              </div>
            </div>
            <p v-if="!lineRows.length" class="text-sm text-gray-500">No item lines found.</p>
          </section>

          <section v-if="showManagerDecisionPanel" class="rounded-xl border border-amber-300 bg-amber-50 p-4">
            <h2 class="mb-1 text-sm font-semibold text-gray-900">How should we source these items?</h2>
            <p class="mb-4 text-xs text-gray-600">
              For each item, enter how many units to move from available stock in other plants and/or how many to order fresh from a supplier.
            </p>

            <div class="space-y-4">
              <div
                v-for="(row, idx) in lineRows"
                :key="`decision-${row.item_code}-${idx}`"
                class="rounded-xl border border-amber-200 bg-white p-4"
              >
                <!-- Item header -->
                <div class="mb-4 flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="font-semibold text-gray-900">{{ row.item_name || row.item_code }}</p>
                    <p class="text-xs text-gray-400">{{ row.item_code }}</p>
                  </div>
                  <div class="shrink-0 rounded-lg bg-amber-50 px-3 py-1.5 text-right">
                    <p class="text-[10px] font-medium uppercase tracking-wide text-amber-700">Needed</p>
                    <p class="text-base font-bold text-gray-900">
                      {{ fmtQty(row.quantity || row.requested_quantity) }}
                      <span class="text-xs font-normal text-gray-500">{{ row.uom || 'pcs' }}</span>
                    </p>
                  </div>
                </div>

                <!-- Move from other plants -->
                <div class="mb-3">
                  <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Move from another plant</p>
                  <div v-if="!stockRowsFor(row.item_code).length" class="rounded-lg bg-gray-50 px-3 py-2.5 text-xs text-gray-500">
                    No stock found in other plants right now.
                  </div>
                  <div v-else class="space-y-2">
                    <div
                      v-for="wh in stockRowsFor(row.item_code)"
                      :key="`${row.item_code}-${wh.warehouse_code}`"
                      class="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5"
                    >
                      <div class="min-w-0 flex-1">
                        <p class="text-sm font-medium text-gray-800">{{ wh.plant_code }}</p>
                        <p class="text-xs text-gray-500">
                          {{ wh.warehouse_code }} ·
                          <span class="font-medium text-green-700">{{ fmtQty(wh.quantity) }} in stock</span>
                        </p>
                      </div>
                      <div class="flex shrink-0 items-center gap-1.5">
                        <label class="text-xs text-gray-500">Move</label>
                        <input
                          :value="decisionQty(row.item_code, wh.plant_code, wh.warehouse_code)"
                          type="number" min="0" :max="Math.floor(wh.quantity)" step="1"
                          class="w-20 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-center text-sm font-semibold text-gray-900 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                          @input="setDecisionQty(row.item_code, wh.plant_code, wh.warehouse_code, $event.target.value)"
                        />
                        <span class="text-xs text-gray-500">{{ row.uom || 'pcs' }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Order fresh -->
                <div class="mb-4 flex items-center gap-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2.5">
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-gray-800">Order fresh from supplier</p>
                    <p class="text-xs text-gray-500">A purchase order will be placed for this quantity</p>
                  </div>
                  <div class="flex shrink-0 items-center gap-1.5">
                    <label class="text-xs text-gray-500">Buy</label>
                    <input
                      :value="decisionPoQty(row.item_code)"
                      type="number" min="0" step="1"
                      class="w-20 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-center text-sm font-semibold text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      @input="setDecisionPoQty(row.item_code, $event.target.value)"
                    />
                    <span class="text-xs text-gray-500">{{ row.uom || 'pcs' }}</span>
                  </div>
                </div>

                <!-- Coverage status -->
                <div
                  class="flex items-center justify-between rounded-lg px-3 py-2"
                  :class="totalAllocated(row.item_code) >= (row.quantity || row.requested_quantity)
                    ? 'border border-green-200 bg-green-50'
                    : 'border border-amber-200 bg-amber-50'"
                >
                  <p
                    class="text-xs font-medium"
                    :class="totalAllocated(row.item_code) >= (row.quantity || row.requested_quantity) ? 'text-green-700' : 'text-amber-700'"
                  >
                    {{ totalAllocated(row.item_code) >= (row.quantity || row.requested_quantity) ? '✓ Fully covered' : 'Not fully covered yet' }}
                  </p>
                  <p
                    class="text-sm font-bold"
                    :class="totalAllocated(row.item_code) >= (row.quantity || row.requested_quantity) ? 'text-green-700' : 'text-amber-700'"
                  >
                    {{ fmtQty(totalAllocated(row.item_code)) }} / {{ fmtQty(row.quantity || row.requested_quantity) }} {{ row.uom || 'pcs' }}
                  </p>
                </div>
              </div>
            </div>

            <div class="mt-4 flex flex-col gap-2 sm:flex-row">
              <p v-if="decisionError" class="w-full rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {{ decisionError }}
              </p>
              <button
                type="button"
                class="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 sm:w-auto sm:py-2"
                :disabled="actionBusy"
                @click="confirmDecision"
              >
                {{ actionBusy ? 'Saving…' : 'Confirm & Start Fulfillment' }}
              </button>
              <button
                type="button"
                class="w-full rounded-lg border border-red-300 bg-white px-4 py-2.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 sm:w-auto sm:py-2"
                :disabled="actionBusy"
                @click="showRejectModal = true"
              >
                Reject Request
              </button>
            </div>
          </section>

          <section v-if="showLinkedPanel" class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Fulfillment Activity</h2>
            <div class="space-y-4 text-sm">

              <!-- Transfers -->
              <div>
                <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Stock being moved from other plants</p>
                <p v-if="!transferLinks.length" class="text-sm text-gray-400">None</p>
                <div v-else class="space-y-2">
                  <div
                    v-for="link in transferLinks"
                    :key="`ctr-${link.name}`"
                    class="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5"
                  >
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0 flex-1">
                        <RouterLink
                          v-if="link.name"
                          :to="`/transfers/${link.name}`"
                          class="font-mono text-xs text-teal-700 hover:underline"
                        >{{ link.name }}</RouterLink>
                        <p class="mt-0.5 text-xs text-gray-600">
                          From <span class="font-medium text-gray-800">{{ link.from_plant }}</span>
                          → <span class="font-medium text-gray-800">{{ doc.plant_code }}</span>
                          · {{ fmtQty(link.quantity) }} units
                        </p>
                        <div v-if="link.sap_last_error" class="mt-1 text-xs text-red-600">
                          ⚠ Issue: {{ link.sap_last_error }}
                        </div>
                      </div>
                      <span
                        class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        :class="{
                          'bg-green-100 text-green-700': link.status === 'Completed',
                          'bg-amber-100 text-amber-700': link.status === 'In Transit',
                          'bg-blue-100 text-blue-700': link.status === 'Approved',
                          'bg-gray-100 text-gray-600': !['Completed','In Transit','Approved'].includes(link.status),
                        }"
                      >{{ link.status || '—' }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Purchase orders -->
              <div>
                <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Items ordered from supplier</p>
                <p v-if="!purchaseLinks.length" class="text-sm text-gray-400">None</p>
                <div v-else class="space-y-2">
                  <div
                    v-for="link in purchaseLinks"
                    :key="`cpr-${link.name}`"
                    class="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5"
                  >
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0 flex-1">
                        <RouterLink
                          v-if="link.name && (authStore.isProcurementUser || authStore.isSuperAdmin || authStore.consumablesRoles.includes('Consumables Store Manager'))"
                          :to="`/procurement/${link.name}`"
                          class="font-mono text-xs text-teal-700 hover:underline"
                        >{{ link.name }}</RouterLink>
                        <span v-else class="font-mono text-xs text-gray-700">{{ link.name }}</span>
                        <p v-if="link.sap_po_number" class="mt-0.5 text-xs text-gray-600">
                          SAP PO: <span class="font-medium">{{ link.sap_po_number }}</span>
                        </p>
                        <p v-if="link.sap_grpo_number" class="text-xs text-green-700">
                          Goods received: <span class="font-medium">{{ link.sap_grpo_number }}</span>
                        </p>
                      </div>
                      <span
                        class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        :class="{
                          'bg-green-100 text-green-700': link.status === 'GRN Done',
                          'bg-blue-100 text-blue-700': link.status === 'PO Raised',
                          'bg-gray-100 text-gray-600': !['GRN Done','PO Raised'].includes(link.status),
                        }"
                      >{{ link.status || '—' }}</span>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </section>

          <!-- GRN section: visible to Store Manager / Inventory Manager when CPR is PO Raised or GRN Done -->
          <section
            v-if="canRecordGrn && cprGrnList.length"
            v-for="cpr in cprGrnList"
            :key="`grn-${cpr.name}`"
            class="rounded-xl border border-blue-200 bg-blue-50 p-4"
          >
            <div class="mb-3 flex items-center justify-between">
              <h2 class="text-sm font-semibold text-gray-900">Record Goods Receipt (GRN) — {{ cpr.name }}</h2>
              <span class="rounded-full px-2 py-0.5 text-xs font-medium"
                :class="cpr.status === 'GRN Done' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'">
                {{ cpr.status }}
              </span>
            </div>
            <div class="mb-3 flex flex-wrap gap-4 text-xs text-gray-600">
              <span>Vendor: <span class="font-mono text-gray-900">{{ cpr.vendor_code || '—' }}</span></span>
              <span>SAP PO#: <span class="font-mono font-semibold text-gray-900">{{ cpr.sap_po_doc_num || '—' }}</span></span>
              <span v-if="cpr.sap_grpo_doc_num">GRPO#: <span class="font-mono text-green-700">{{ cpr.sap_grpo_doc_num }}</span></span>
            </div>
            <div v-if="cpr.sap_last_error" class="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
              Last SAP error: {{ cpr.sap_last_error }}
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b border-gray-200 text-left text-gray-500">
                    <th class="pb-2 pr-3">Item Code</th>
                    <th class="pb-2 pr-3">Item Name</th>
                    <th class="pb-2 pr-3">Ordered</th>
                    <th class="pb-2 pr-3">Qty Receiving Now *</th>
                    <th class="pb-2">Batch No. *</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="li in cpr.line_items" :key="`${cpr.name}-${li.item_code}`" class="border-b border-gray-100">
                    <td class="py-2 pr-3 font-mono">{{ li.item_code }}</td>
                    <td class="py-2 pr-3 text-gray-700">{{ li.item_name || '—' }}</td>
                    <td class="py-2 pr-3">{{ fmtQty(li.quantity) }} {{ li.uom }}</td>
                    <td class="py-2 pr-3">
                      <input
                        v-model.number="grnForm[cpr.name][li.item_code].qty"
                        type="number"
                        min="0"
                        class="w-20 rounded border border-gray-300 px-2 py-1 text-xs"
                        :class="!grnForm[cpr.name]?.[li.item_code]?.qty ? 'border-red-300' : ''"
                        placeholder="0"
                      />
                    </td>
                    <td class="py-2">
                      <input
                        v-model.trim="grnForm[cpr.name][li.item_code].batch"
                        type="text"
                        class="w-32 rounded border border-gray-300 px-2 py-1 text-xs"
                        :class="!grnForm[cpr.name]?.[li.item_code]?.batch ? 'border-red-300' : ''"
                        placeholder="Batch no."
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button
              type="button"
              class="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              :disabled="grnSubmitting[cpr.name]"
              @click="submitGrn(cpr)"
            >
              {{ grnSubmitting[cpr.name] ? 'Submitting…' : 'Submit Goods Receipt (GRN) to SAP' }}
            </button>
          </section>
        </div>

        <aside class="space-y-4">
          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Timeline</h2>
            <ol class="relative ml-2 space-y-4 border-l border-gray-200 pl-5">
              <li v-for="ev in timelineEvents" :key="ev.key">
                <span class="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full bg-teal-600 ring-4 ring-white" />
                <p class="text-sm font-medium text-gray-900">{{ ev.title }}</p>
                <p class="text-xs text-gray-500">{{ ev.when ? formatWhen(ev.when) : '—' }}</p>
              </li>
            </ol>
          </section>

          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Actions</h2>
            <div class="space-y-2">
              <div v-if="canSubmit">
                <button
                  type="button"
                  class="w-full rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 sm:py-2"
                  :disabled="actionBusy"
                  @click="doSubmit"
                >
                  Submit for Review
                </button>
                <p class="mt-1 text-center text-[10px] text-gray-400">Sends request to store manager for approval</p>
              </div>
              <div v-if="canApprove">
                <button
                  type="button"
                  class="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 sm:py-2"
                  :disabled="actionBusy"
                  @click="doApprove"
                >
                  Begin Review
                </button>
                <p class="mt-1 text-center text-[10px] text-gray-400">Moves request to "Under Review" for fulfillment planning</p>
              </div>
              <div v-if="canConfirmPhysicalReceipt">
                <button
                  type="button"
                  class="w-full rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50 sm:py-2"
                  :disabled="actionBusy"
                  @click="openReceiptModal"
                >
                  Confirm Goods Received
                </button>
                <p class="mt-1 text-center text-[10px] text-gray-400">Confirm items have physically arrived at your plant</p>
              </div>
              <button
                v-if="canRetrySap"
                type="button"
                class="w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="doRetrySap"
              >
                Retry SAP Sync
              </button>
              <button
                v-if="canReject"
                type="button"
                class="w-full rounded-lg border border-red-300 bg-white px-4 py-2.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="showRejectModal = true"
              >
                Reject Request
              </button>
              <button
                v-if="canDelete"
                type="button"
                class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="doDelete"
              >
                Delete Request
              </button>
              <p
                v-if="!canSubmit && !canDelete && !canApprove && !canReject && !canRetrySap && !canConfirmPhysicalReceipt"
                class="rounded-lg bg-gray-50 px-3 py-2 text-center text-xs text-gray-500"
              >
                No actions available at this stage for your role.
              </p>
            </div>
          </section>
        </aside>
      </div>
    </template>

    <!-- Confirm Goods Received popup -->
    <div
      v-if="showReceiptModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="showReceiptModal = false"
    >
      <div class="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div class="border-b border-gray-100 px-6 py-4">
          <h2 class="text-base font-semibold text-gray-900">Confirm Goods Received</h2>
          <p class="mt-1 text-sm text-gray-500">Enter the quantity you physically received for each item.</p>
        </div>
        <div class="max-h-[28rem] overflow-y-auto">
          <div v-if="receiptModalLoading" class="py-10 text-center text-sm text-gray-400">Loading transfer details…</div>
          <div v-else class="px-6 py-4 space-y-4">
            <div v-for="ctr in receiptModalCtrs" :key="ctr.name" class="rounded-lg border border-gray-200">
              <div class="flex items-center gap-2 rounded-t-lg border-b border-gray-100 bg-gray-50 px-4 py-2">
                <span class="font-mono text-xs font-semibold text-teal-700">{{ ctr.name }}</span>
                <span class="text-xs text-gray-500">From {{ ctr.from_plant }}</span>
              </div>
              <div class="divide-y divide-gray-100 px-4 py-2">
                <div
                  v-for="item in ctr.items"
                  :key="item.row_index"
                  class="flex items-center justify-between gap-4 py-2"
                >
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-gray-800">{{ item.item_code }}</p>
                    <p class="text-xs text-gray-500">{{ item.batch_number || item.item_name || '' }}</p>
                  </div>
                  <div class="flex shrink-0 items-center gap-2">
                    <input
                      v-model.number="item.received"
                      type="number"
                      min="0"
                      :max="item.dispatched"
                      class="w-20 rounded-lg border px-2 py-1.5 text-right text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
                      :class="receiptQtyDiffers(item.received, item.dispatched) ? 'border-amber-400 bg-amber-50' : 'border-gray-300'"
                    />
                    <span class="whitespace-nowrap text-xs text-gray-400">/ {{ item.dispatched }} {{ item.uom }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="hasReceiptMismatch" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
              <p class="text-xs font-semibold text-amber-800">Quantity mismatch detected</p>
              <p class="mt-0.5 text-xs text-amber-700">
                Received quantity must exactly match dispatched quantity. If physically received less or more, add a reason and reject the delivery.
              </p>
            </div>

            <div>
              <label class="mb-1 block text-xs font-medium text-gray-700">
                Notes
                <span v-if="hasReceiptMismatch" class="text-red-500">*</span>
                <span v-else class="font-normal text-gray-400">(optional)</span>
              </label>
              <textarea
                v-model="receiptModalNotes"
                rows="2"
                class="w-full rounded-lg border px-3 py-2 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                :class="hasReceiptMismatch && !receiptModalNotes.trim() && receiptModalSubmitted ? 'border-red-400' : 'border-gray-300'"
                placeholder="e.g. 2 units damaged on arrival, short-shipped..."
              />
              <p v-if="hasReceiptMismatch && !receiptModalNotes.trim() && receiptModalSubmitted" class="mt-1 text-xs text-red-600">
                Reason is required to reject this delivery.
              </p>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            @click="showReceiptModal = false"
          >Cancel</button>
          <button
            v-if="hasReceiptMismatch"
            type="button"
            :disabled="actionBusy"
            class="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            @click="doRejectReceiptModal"
          >Reject Delivery</button>
          <button
            v-else
            type="button"
            :disabled="actionBusy || receiptModalLoading"
            class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
            @click="doConfirmReceiptModal"
          >{{ actionBusy ? 'Processing...' : 'Confirm Receipt' }}</button>
        </div>
      </div>
    </div>

    <div
      v-if="showRejectModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="showRejectModal = false"
    >
      <div class="w-full max-w-md space-y-4 rounded-xl bg-white p-5 shadow-lg">
        <h3 class="text-lg font-semibold text-gray-900">Reject material request</h3>
        <label class="block text-sm text-gray-700">Reason <span class="text-red-600">*</span></label>
        <textarea
          v-model="rejectReason"
          rows="4"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          placeholder="Explain rejection reason..."
        />
        <div class="flex justify-end gap-2">
          <button type="button" class="px-3 py-2 text-sm text-gray-700" @click="showRejectModal = false">
            Cancel
          </button>
          <button
            type="button"
            class="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            :disabled="actionBusy || !rejectReason.trim()"
            @click="doReject"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import { useRoute, useRouter } from 'vue-router'
import { fetchInventory } from '@/core/api/inventory.js'
import { useAuthStore } from '@/stores/auth.js'
import { useMaterialRequestsStore } from '@/stores/material_requests.js'
import { StatusBadge, StatusStepper } from '@/shared/components/index.js'
import { useStoreopsSocket } from '@/composables/useStoreopsSocket.js'
import { parseApiError } from '@/utils/error.js'
import { submit_grn, get_cpr_grn_info } from '@/core/api/procurement.js'
import { get_transfer_request, receive_transfer_request } from '@/core/api/transfers.js'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const materialRequestsStore = useMaterialRequestsStore()

const loadErr = ref('')
const actionBusy = ref(false)
const checkingStatus = ref(false)
const showRejectModal = ref(false)
const rejectReason = ref('')

const showReceiptModal = ref(false)
const receiptModalLoading = ref(false)
const receiptModalCtrs = ref([])
const receiptModalNotes = ref('')
const receiptModalSubmitted = ref(false)

const receiptQtyDiffers = (received, dispatched) => Math.abs(Number(received || 0) - Number(dispatched || 0)) > 0.0001
const hasReceiptMismatch = computed(() =>
  receiptModalCtrs.value.some(ctr => ctr.items.some(i => receiptQtyDiffers(i.received, i.dispatched)))
)

const stockByItem = ref({})
const transferQtyByItemWarehouse = ref({})
const poQtyByItem = ref({})
const decisionError = ref('')

const cmrSteps = [
  { key: 'draft',              label: 'Request Raised' },
  { key: ['submitted'],        label: 'Pending Approval' },
  { key: 'under review',       label: 'Manager Planning' },
  { key: ['fulfilling', 'partially fulfilled'], label: 'Dispatched' },
  { key: ['fully fulfilled', 'completed'],      label: 'All Received' },
]

const stepHint = computed(() => {
  const s = normalizedStatus.value
  if (s === 'draft') return 'Your request is saved. Press "Submit for Review" to send it to the manager.'
  if (s === 'submitted') return 'Request sent — a manager will review it shortly and arrange for your items.'
  if (s === 'under review') return 'A manager is checking what\'s available across all plants and deciding the best way to get your items.'
  if (s === 'fulfilling') return 'Stock has been dispatched from another plant and/or a purchase order has been placed. You\'ll be notified when goods arrive at your plant.'
  if (s === 'partially fulfilled') return 'Some of your items have arrived. The rest have been dispatched or are being ordered.'
  if (s === 'fully fulfilled') return 'All done — every item on this request has been received at your plant.'
  if (s === 'rejected') return 'This request was not approved. Please speak with your manager and raise a new request if needed.'
  return ''
})

const docName = () => decodeURIComponent(String(route.params.name || ''))
const doc = computed(() => materialRequestsStore.current)

const lineRows = computed(() => {
  const rows = doc.value?.line_items
  return Array.isArray(rows) ? rows : []
})

const isManagerOrAdmin = computed(
  () =>
    authStore.isSuperAdmin ||
    authStore.consumablesRoles.includes('Consumables Store Manager') ||
    authStore.consumablesRoles.includes('Consumables Inventory Manager'),
)

const userPlantCodes = computed(() =>
  (authStore.plants || []).map((p) => String(p.plant_code || '').trim()).filter(Boolean),
)
/** True if this user created the request (cannot review own MR). */
const isRequestCreator = computed(() => {
  const uid = String(authStore.user || '').toLowerCase().trim()
  const reqBy = String(doc.value?.requested_by || '').toLowerCase().trim()
  return !!(uid && reqBy && uid === reqBy)
})
/** Reviewer must hold BOTH Store Manager + Inventory Manager roles. Creator cannot self-review. */
const canReviewMaterialRequest = computed(() => {
  if (authStore.isSuperAdmin) return true
  const hasStore = authStore.consumablesRoles.includes('Consumables Store Manager')
  const hasInventory = authStore.consumablesRoles.includes('Consumables Inventory Manager')
  if (!hasStore || !hasInventory) return false
  return !isRequestCreator.value
})
const isEligibleReviewer = computed(() => canReviewMaterialRequest.value)

const normalizedStatus = computed(() => String(doc.value?.status || '').toLowerCase())
const submitted = computed(() => normalizedStatus.value === 'submitted')
const underReview = computed(() => normalizedStatus.value === 'under review')
const showManagerDecisionPanel = computed(() => isEligibleReviewer.value && underReview.value)
const transferLinks = computed(() => (Array.isArray(doc.value?.transfer_links) ? doc.value.transfer_links : []))
const purchaseLinks = computed(() => (Array.isArray(doc.value?.purchase_links) ? doc.value.purchase_links : []))

const showLinkedPanel = computed(() => {
  const status = normalizedStatus.value
  return ['fulfilling', 'partially fulfilled', 'fully fulfilled', 'approved', 'in transit', 'completed', 'posted'].includes(status)
})

// GRN: only the Store Manager assigned to THIS plant, and not the original requester.
const canRecordGrn = computed(() => {
  if (authStore.isSuperAdmin) return true
  if (!authStore.consumablesRoles.includes('Consumables Store Manager')) return false
  const plant = String(doc.value?.requesting_plant || '').trim()
  return !!(plant && userPlantCodes.value.includes(plant))
})
const cprGrnList = ref([])   // CPR objects with line_items fetched from backend
const grnForm = ref({})      // { [cpr_name]: { [item_code]: { qty, batch } } }
const grnSubmitting = ref({})

watch(
  () => purchaseLinks.value,
  async (links) => {
    if (!canRecordGrn.value) return
    const names = links
      .filter(l => l.name && l.status === 'PO Raised')
      .map(l => l.name)
    if (!names.length) { cprGrnList.value = []; return }
    try {
      const res = await get_cpr_grn_info(JSON.stringify(names))
      const list = res?.message ?? res ?? []
      cprGrnList.value = Array.isArray(list) ? list : []
      // Init grnForm entries
      const form = {}
      for (const cpr of cprGrnList.value) {
        form[cpr.name] = {}
        for (const li of cpr.line_items) {
          form[cpr.name][li.item_code] = { qty: 0, batch: '' }
        }
      }
      grnForm.value = form
    } catch {
      cprGrnList.value = []
    }
  },
  { immediate: true },
)

async function submitGrn(cpr) {
  const form = grnForm.value[cpr.name] || {}
  const items = cpr.line_items
    .map(li => ({
      item_code: li.item_code,
      quantity_received: Number(form[li.item_code]?.qty || 0),
      batch_number: (form[li.item_code]?.batch || '').trim(),
    }))
    .filter(i => i.quantity_received > 0)
  if (!items.length) {
    toast({ title: 'Enter at least one received quantity.', icon: 'alert-triangle' })
    return
  }
  const missing = items.find(i => !i.batch_number)
  if (missing) {
    toast({ title: `Batch number required for ${missing.item_code}`, icon: 'alert-triangle' })
    return
  }
  grnSubmitting.value[cpr.name] = true
  try {
    await submit_grn(cpr.name, JSON.stringify(items))
    toast({ title: `GRN queued for ${cpr.name}. SAP posting in progress.`, icon: 'check' })
    // Refresh doc to pick up updated status
    await materialRequestsStore.fetchOne(doc.value.name, { silent: true })
  } catch (e) {
    toast({ title: parseApiError(e, 'GRN submission failed.'), icon: 'x' })
  } finally {
    grnSubmitting.value[cpr.name] = false
  }
}

const canSubmit = computed(() => normalizedStatus.value === 'draft')
const canDelete = computed(
  () => normalizedStatus.value === 'draft' && String(doc.value?.requested_by || doc.value?.owner || '') === String(authStore.user || ''),
)
const canApprove = computed(() => canReviewMaterialRequest.value && submitted.value)
const canReject = computed(() => canReviewMaterialRequest.value && (submitted.value || underReview.value))
const canRetrySap = computed(
  () => canReviewMaterialRequest.value &&
    ['fulfilling', 'partially fulfilled'].includes(normalizedStatus.value) &&
    !!doc.value?.sap_last_error,
)

const hasInboundInTransit = computed(() =>
  transferLinks.value.some((l) => String(l.status || '').toLowerCase() === 'in transit'),
)
/** Requesting (destination) plant users can confirm when goods are in transit. */
const userCanAccessRequestingPlant = computed(() => {
  if (authStore.isSuperAdmin) return true
  const pc = String(doc.value?.plant_code || '').trim()
  return !!pc && userPlantCodes.value.includes(pc)
})
const canConfirmPhysicalReceipt = computed(
  () =>
    userCanAccessRequestingPlant.value &&
    ['fulfilling', 'partially fulfilled'].includes(normalizedStatus.value) &&
    transferLinks.value.some((l) => String(l.status || '').toLowerCase() === 'in transit'),
)

const timelineEvents = computed(() => {
  const d = doc.value
  if (!d) return []
  const out = []
  if (d.submitted_on || d.status === 'Submitted') out.push({ key: 'submitted', title: 'Request submitted', when: d.submitted_on || d.transaction_date })
  if (d.reviewed_on || d.status === 'Under Review') out.push({ key: 'review', title: 'Review started', when: d.reviewed_on || d.modified || d.creation })
  if (d.fulfilling_on || d.status === 'Fulfilling') out.push({ key: 'fulfilling', title: 'Fulfillment plan confirmed', when: d.fulfilling_on || d.modified || d.creation })
  if (d.status === 'Partially Fulfilled') out.push({ key: 'partial', title: 'Partially fulfilled', when: d.modified || d.creation })
  if (d.status === 'Fully Fulfilled') out.push({ key: 'full', title: 'Fully fulfilled', when: d.modified || d.creation })
  if (d.status === 'Rejected') out.push({ key: 'reject', title: 'Request rejected', when: d.modified || d.creation })
  return out
})

function formatWhen(raw) {
  if (!raw) return ''
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? String(raw) : d.toLocaleString()
}

function fmtQty(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value ?? 0)
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(2)
}

function itemProgress(row) {
  const req = Number(row.quantity || row.requested_quantity || 0)
  const done = Number(row.fulfilled_quantity || row.allocated_quantity || 0)
  if (!req || req <= 0) return 0
  return Math.max(0, Math.min(100, Math.round((done / req) * 100)))
}

function receivedDisplayQty(row) {
  const req = Number(row.quantity || row.requested_quantity || 0)
  const done = Number(row.fulfilled_quantity || row.allocated_quantity || 0)
  if (!Number.isFinite(req) || req <= 0) return done
  return Math.min(done, req)
}

function stockRowsFor(itemCode) {
  return stockByItem.value[itemCode] || []
}

function decisionKey(itemCode, plantCode, whCode) {
  return `${itemCode}::${plantCode}::${whCode}`
}

function decisionQty(itemCode, plantCode, whCode) {
  return transferQtyByItemWarehouse.value[decisionKey(itemCode, plantCode, whCode)] ?? ''
}

function setDecisionQty(itemCode, plantCode, whCode, value) {
  decisionError.value = ''
  const parsed = value === '' || value === null ? '' : Math.max(0, Math.floor(Number(value) || 0))
  transferQtyByItemWarehouse.value = {
    ...transferQtyByItemWarehouse.value,
    [decisionKey(itemCode, plantCode, whCode)]: parsed,
  }
}

function decisionPoQty(itemCode) {
  return poQtyByItem.value[itemCode] ?? ''
}

function setDecisionPoQty(itemCode, value) {
  decisionError.value = ''
  const parsed = value === '' || value === null ? '' : Math.max(0, Math.floor(Number(value) || 0))
  poQtyByItem.value = {
    ...poQtyByItem.value,
    [itemCode]: parsed,
  }
}

function totalAllocated(itemCode) {
  const stockRows = stockRowsFor(itemCode)
  const transfer = stockRows.reduce(
    (sum, row) => sum + Number(decisionQty(itemCode, row.plant_code, row.warehouse_code) || 0),
    0,
  )
  const po = Number(decisionPoQty(itemCode) || 0)
  return transfer + po
}

function validateDecision() {
  for (const row of lineRows.value) {
    const itemCode = row.item_code
    const requested = Number(row.quantity || row.requested_quantity || 0)
    if (!itemCode || requested <= 0) continue

    const stockRows = stockRowsFor(itemCode)
    for (const s of stockRows) {
      const qty = Number(decisionQty(itemCode, s.plant_code, s.warehouse_code) || 0)
      const available = Number(s.quantity || 0)
      if (qty < 0) return `Transfer qty cannot be negative for ${itemCode}`
      if (qty > available) return `Transfer qty for ${itemCode} exceeds stock in ${s.warehouse_code}`
      if (qty > 0 && String(s.plant_code || '') === String(doc.value?.plant_code || '')) {
        return `Transfer source plant cannot be requesting plant for ${itemCode}`
      }
    }

    const po = Number(decisionPoQty(itemCode) || 0)
    if (po < 0) return `PO qty cannot be negative for ${itemCode}`
    const allocated = totalAllocated(itemCode)
    if (allocated < requested - 0.0001) return `Total assigned must cover requested qty for ${itemCode}`
  }
  return ''
}

function normalizeKey(value) {
  return String(value || '').trim().toLowerCase()
}

async function loadStockSnapshot() {
  const d = doc.value
  if (!isEligibleReviewer.value) {
    stockByItem.value = {}
    return
  }
  if (!d?.plant_code || !lineRows.value.length) return
  const byItem = {}
  const reqPlantKey = normalizeKey(d.plant_code)
  const reqWhSet = new Set((Array.isArray(d.requesting_warehouses) ? d.requesting_warehouses : []).map(normalizeKey))
  const sourceCandidates = (authStore.sourcePlants || authStore.plants || [])
    .flatMap((p) => (p.warehouses || []).map((w) => ({ plant_code: p.plant_code, warehouse_code: w.warehouse_code || w.name })))
    .filter((x) => {
      if (!x.plant_code || !x.warehouse_code) return false
      const plantKey = normalizeKey(x.plant_code)
      // Ignore synthetic aggregate plants (e.g. "All Plant", "All code").
      if (plantKey.startsWith('all ')) return false
      if (normalizeKey(x.plant_code) === reqPlantKey) return false
      if (reqWhSet.has(normalizeKey(x.warehouse_code))) return false
      return true
    })
  const seenWarehouses = new Set()
  const sources = sourceCandidates.filter((x) => {
    const whKey = normalizeKey(x.warehouse_code)
    if (!whKey || seenWarehouses.has(whKey)) return false
    seenWarehouses.add(whKey)
    return true
  })
  if (!sources.length) return
  for (const row of lineRows.value) {
    const code = row.item_code
    if (!code) continue
    byItem[code] = []
    for (const src of sources) {
      try {
        const payload = await fetchInventory(src.plant_code, src.warehouse_code, {
          search: code,
          page: 1,
          page_size: 25,
          paginate_by_item: 1,
        })
        const items = Array.isArray(payload?.items) ? payload.items : []
        const match = items.find((x) => String(x.item_code || '').toLowerCase() === String(code).toLowerCase())
        const quantity = Number(match?.quantity || match?.qty || 0)
        if (quantity > 0) {
          byItem[code].push({
            plant_code: src.plant_code,
            warehouse_code: src.warehouse_code,
            quantity,
          })
        }
      } catch {
        // Ignore failed/empty source rows in decision table.
      }
    }
  }
  stockByItem.value = byItem
}

async function loadDoc() {
  loadErr.value = ''
  const name = docName()
  if (!name) {
    loadErr.value = 'Missing document name'
    return
  }
  materialRequestsStore.current = null
  try {
    await materialRequestsStore.fetchOne(name)
    await loadStockSnapshot()
  } catch (e) {
    loadErr.value = materialRequestsStore.error || parseApiError(e, 'Failed to load material request')
  }
}

async function wrap(fn, success = 'Updated') {
  actionBusy.value = true
  try {
    await fn()
    await materialRequestsStore.fetchOne(docName(), { silent: true })
    await loadStockSnapshot()
    toast.success(success)
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

function doSubmit() {
  wrap(() => materialRequestsStore.submit(docName()), 'Submitted')
}

function doApprove() {
  wrap(() => materialRequestsStore.approve(docName()), 'Approved')
}

function doRetrySap() {
  wrap(() => materialRequestsStore.retrySapPosting(docName()), 'Status refreshed')
}

async function openReceiptModal() {
  showReceiptModal.value = true
  receiptModalLoading.value = true
  receiptModalCtrs.value = []
  receiptModalNotes.value = ''
  receiptModalSubmitted.value = false

  const inTransitLinks = transferLinks.value.filter(l =>
    String(l.status || '').toLowerCase() === 'in transit'
  )

  try {
    const ctrs = await Promise.all(
      inTransitLinks.map(async link => {
        const res = await get_transfer_request(link.name)
        const ctr = res?.message ?? res
        return {
          name: link.name,
          from_plant: link.from_plant || ctr?.from_plant || '',
          items: (ctr?.line_items || []).map((li, idx) => ({
            row_index: idx,
            item_code: li.item_code || '',
            item_name: li.item_name || '',
            batch_number: li.batch_number || '',
            uom: li.uom || '',
            dispatched: Number(li.quantity || 0),
            received: Number(li.quantity || 0),
          })),
        }
      })
    )
    receiptModalCtrs.value = ctrs
  } catch {
    toast.error('Failed to load transfer details')
    showReceiptModal.value = false
  } finally {
    receiptModalLoading.value = false
  }
}

async function doConfirmReceiptModal() {
  receiptModalSubmitted.value = true
  if (hasReceiptMismatch.value) {
    toast.error('Received quantity must exactly match dispatched quantity. Reject the delivery if quantities differ.')
    return
  }
  showReceiptModal.value = false
  receiptModalSubmitted.value = false
  actionBusy.value = true
  try {
    for (const ctr of receiptModalCtrs.value) {
      const received_items = JSON.stringify(
        ctr.items.map(i => ({ row_index: i.row_index, quantity_received: Number(i.received || 0) }))
      )
      await receive_transfer_request(ctr.name, received_items, receiptModalNotes.value.trim())
    }
    toast.success('Receipt confirmed')
    await materialRequestsStore.fetchOne(docName(), { silent: true })
    await loadStockSnapshot()
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

async function doRejectReceiptModal() {
  receiptModalSubmitted.value = true
  if (!receiptModalNotes.value.trim()) return
  showReceiptModal.value = false
  receiptModalSubmitted.value = false
  actionBusy.value = true
  try {
    for (const ctr of receiptModalCtrs.value) {
      // Pass 0 for every item — backend detect total_received=0 as full rejection
      const receivedItems = JSON.stringify(
        ctr.items.map((i) => ({ row_index: i.row_index, quantity_received: Number(i.received || 0) })),
      )
      await receive_transfer_request(ctr.name, receivedItems, receiptModalNotes.value.trim(), 1)
    }
    toast.success('Delivery rejected')
    await materialRequestsStore.fetchOne(docName(), { silent: true })
    await loadStockSnapshot()
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

async function doDelete() {
  actionBusy.value = true
  try {
    await materialRequestsStore.remove(docName())
    toast.success('Draft deleted')
    router.push({ name: 'MaterialRequestsIndex' })
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

async function doReject() {
  const reason = rejectReason.value.trim()
  if (!reason) return
  actionBusy.value = true
  try {
    await materialRequestsStore.reject(docName(), reason)
    showRejectModal.value = false
    rejectReason.value = ''
    await materialRequestsStore.fetchOne(docName(), { silent: true })
    toast.success('Rejected')
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

function confirmDecision() {
  decisionError.value = ''
  const error = validateDecision()
  if (error) {
    decisionError.value = error
    toast.error(error)
    return
  }
  const decisions = lineRows.value.map((row) => {
    const itemCode = String(row.item_code || '')
    const stockRows = stockRowsFor(itemCode)
    const transfers = stockRows
      .map((wh) => ({
        plant: wh.plant_code,
        wh: wh.warehouse_code,
        qty: Number(decisionQty(itemCode, wh.plant_code, wh.warehouse_code) || 0),
      }))
      .filter((x) => x.qty > 0)
    const transferQty = transfers.reduce((sum, x) => sum + x.qty, 0)
    const firstWh = transfers[0]?.wh || ''
    const firstPlant = transfers[0]?.plant || ''
    return {
      item_code: itemCode,
      transfer_qty: transferQty,
      po_qty: Number(decisionPoQty(itemCode) || 0),
      from_plant: firstPlant,
      from_warehouse: firstWh,
      transfers: transfers.map((x) => ({
        from_plant: x.plant,
        from_warehouse: x.wh,
        transfer_qty: x.qty,
      })),
    }
  })
  wrap(() => materialRequestsStore.decide(docName(), decisions), 'Decision confirmed')
}

async function checkStatus() {
  checkingStatus.value = true
  try {
    await materialRequestsStore.syncFulfillmentStatus(docName())
    await materialRequestsStore.fetchOne(docName(), { silent: true })
    await loadStockSnapshot()
    toast.success('Status refreshed')
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    checkingStatus.value = false
  }
}

useStoreopsSocket(docName, () => {
  materialRequestsStore.fetchOne(docName(), { silent: true }).then(loadStockSnapshot).catch(() => {})
})

watch(
  () => route.params.name,
  () => {
    transferQtyByItemWarehouse.value = {}
    poQtyByItem.value = {}
    stockByItem.value = {}
    loadDoc()
  },
)

loadDoc()
</script>
