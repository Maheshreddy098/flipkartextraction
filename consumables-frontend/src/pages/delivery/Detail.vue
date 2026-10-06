<template>
  <div class="max-w-6xl p-4 sm:p-6">

    <div v-if="deliveryStore.loading && !doc" class="py-16 text-center text-gray-500">
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
        <RouterLink to="/delivery" class="hover:text-teal-700">Store Consumptions</RouterLink>
        <span>›</span>
        <span class="font-medium text-gray-700">{{ doc.name }}</span>
      </div>

      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 sm:gap-4">
        <div class="min-w-0 flex-1">
          <h1 class="break-all font-mono text-lg font-bold text-gray-900 sm:text-2xl">{{ doc.name }}</h1>
          <p class="mt-0.5 text-sm text-gray-500">
            <span class="font-medium text-gray-700">{{ doc.plant || '—' }}</span>
            <span class="mx-1.5 text-gray-400">·</span>
            {{ doc.purpose || '—' }}
          </p>
        </div>
        <div class="flex items-center gap-1.5">
          <span
            v-if="isBackdated"
            class="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800"
          >
            Backdated
          </span>
          <StatusBadge v-if="doc.status" :status="doc.status" size="md" />
        </div>
      </div>

      <!-- Status Stepper -->
      <div class="mb-6 rounded-xl border border-gray-200 bg-white px-4 py-4">
        <StatusStepper
          :steps="cdnSteps"
          :current="doc.status || 'Draft'"
          :is-error="['Rejected', 'Failed', 'Cancelled'].includes(doc.status)"
        />
      </div>

      <div
        v-if="insufficientStockWarnings.length"
        class="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      >
        <p
          v-for="warning in insufficientStockWarnings"
          :key="warning.item_code"
          class="mb-1 last:mb-0"
        >
          Approval blocked: insufficient stock for {{ warning.item_name }}.
          Available: {{ warning.available }}, Requested: {{ warning.requested }}
        </p>
      </div>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <section class="mb-6 rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Store Consumption Details</h2>
            <dl class="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt class="text-gray-500">Requested by</dt>
                <dd class="text-gray-900">{{ doc.requested_by || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Requested on</dt>
                <dd class="text-gray-900">{{ formatWhen(doc.requested_on) || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Warehouse</dt>
                <dd class="text-gray-900">{{ doc.warehouse || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Purpose</dt>
                <dd class="text-gray-900">{{ doc.purpose || '—' }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">Delivery Date</dt>
                <dd class="text-gray-900">{{ doc.doc_date || '—' }}</dd>
              </div>
              <div v-if="isBackdated">
                <dt class="text-gray-500">Reason for backdating</dt>
                <dd class="text-gray-900">{{ doc.remarks || '—' }}</dd>
              </div>
            </dl>
          </section>

          <section class="mb-6">
            <h2 class="mb-2 text-sm font-semibold text-gray-900">Line Items</h2>
            <div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
              <div class="-mx-1 overflow-x-auto sm:mx-0">
            <table class="min-w-[32rem] text-xs sm:min-w-0 sm:text-sm">
                <thead class="bg-gray-50 text-gray-700">
                  <tr>
                    <th class="px-2 py-1.5 text-left font-medium sm:px-4 sm:py-2">Item Code</th>
                    <th class="px-2 py-1.5 text-left font-medium sm:px-4 sm:py-2">Item Name</th>
                    <th class="px-2 py-1.5 text-right font-medium sm:px-4 sm:py-2">Consumed Qty</th>
                    <th class="px-2 py-1.5 text-left font-medium sm:px-4 sm:py-2">UOM</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in lineRows" :key="idx" class="border-t border-gray-100 align-top">
                    <td class="px-2 py-1.5 text-gray-800 sm:px-4 sm:py-2">{{ row.item_code || '—' }}</td>
                    <td class="max-w-[8rem] truncate px-2 py-1.5 text-gray-800 sm:max-w-none sm:whitespace-normal sm:px-4 sm:py-2">{{ row.item_name || '—' }}</td>
                    <td class="px-2 py-1.5 text-right text-gray-800 sm:px-4 sm:py-2">{{ fmtQty(consumedQty(row)) }}</td>
                    <td class="px-2 py-1.5 text-gray-700 sm:px-4 sm:py-2">{{ row.uom || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
              <p v-if="!lineRows.length" class="px-4 py-6 text-sm text-gray-500">No line items.</p>
            </div>
          </section>

          <section v-if="showSapBlock" class="mb-6 rounded-xl border border-gray-200 bg-gray-50 p-4">
            <h2 class="mb-2 text-sm font-semibold text-gray-900">SAP Info</h2>
            <dl class="grid gap-2 text-sm">
              <div class="flex gap-2">
                <dt class="shrink-0 text-gray-500">SAP Reference:</dt>
                <dd class="font-mono text-gray-900">{{ doc.sap_doc_num || '—' }}</dd>
              </div>
              <div class="flex gap-2">
                <dt class="shrink-0 text-gray-500">Posting Date:</dt>
                <dd class="text-gray-900">{{ doc.sap_posting_date || '—' }}</dd>
              </div>
              <div v-if="doc.sap_last_error" class="whitespace-pre-wrap text-red-700">
                <span class="font-medium">Error:</span> {{ doc.sap_last_error }}
              </div>
            </dl>
          </section>
        </div>

        <aside class="space-y-4">
          <section class="rounded-xl border border-gray-200 bg-white p-4">
            <h2 class="mb-3 text-sm font-semibold text-gray-900">Actions</h2>
            <div v-if="canSubmit" class="mb-2">
              <button
                type="button"
                class="w-full rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="doSubmit"
              >
                {{ actionBusy ? 'Posting…' : 'Post Store Consumption' }}
              </button>
              <p class="mt-1 text-center text-[10px] text-gray-400">Posts this store consumption directly to SAP</p>
            </div>
            <div v-if="canRetrySap" class="mb-2">
              <button
                type="button"
                class="w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="doRetrySap"
              >
                Retry SAP Posting
              </button>
              <p class="mt-1 text-center text-[10px] text-gray-400">Re-attempt the failed SAP posting</p>
            </div>
            <div v-if="canCancel" class="mb-2">
              <button
                type="button"
                class="w-full rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="doCancel"
              >
                Cancel SAP Posting
              </button>
              <p class="mt-1 text-center text-[10px] text-gray-400">Super Admin only — cancels the live SAP document. Does not repost.</p>
            </div>
            <div v-if="canRepost" class="mb-2">
              <button
                type="button"
                class="w-full rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 sm:py-2"
                :disabled="actionBusy"
                @click="doRepost"
              >
                Repost to SAP
              </button>
              <p class="mt-1 text-center text-[10px] text-gray-400">Super Admin only — posts a fresh SAP document with the same items/batches</p>
            </div>
            <p v-if="!canSubmit && !canRetrySap && !canCancel && !canRepost" class="rounded-lg bg-gray-50 px-3 py-2 text-center text-xs text-gray-500">
              No actions available at this stage for your role.
            </p>
          </section>
        </aside>
      </div>
    </template>

  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'frappe-ui'
import { useAuthStore } from '@/stores/auth.js'
import { useDeliveryStore } from '@/stores/delivery.js'
import { StatusBadge, StatusStepper } from '@/shared/components/index.js'
import { useStoreopsSocket } from '@/composables/useStoreopsSocket.js'
import { parseApiError } from '@/utils/error.js'

const route = useRoute()
const authStore = useAuthStore()
const deliveryStore = useDeliveryStore()

const loadErr = ref('')
const actionBusy = ref(false)

const cdnSteps = [
  { key: ['draft'], label: 'Draft' },
  { key: ['posted'], label: 'Posted to SAP' },
]

const docName = () => decodeURIComponent(String(route.params.name || ''))
const doc = computed(() => deliveryStore.currentDeliveryNote)

const lineRows = computed(() => {
  const rows = doc.value?.line_items
  return Array.isArray(rows) ? rows : []
})

const isManagerOrAdmin = computed(() => authStore.isManager)

const isBackdated = computed(() => {
  const d = doc.value
  if (!d?.doc_date || !d?.requested_on) return false
  return String(d.doc_date).slice(0, 10) !== String(d.requested_on).slice(0, 10)
})

const showSapBlock = computed(() => !!doc.value?.sap_doc_num || !!doc.value?.sap_last_error || isManagerOrAdmin.value)

const canSubmit = computed(() => {
  if (doc.value?.status !== 'Draft') return false
  const requestedBy = String(doc.value?.requested_by || '').trim()
  return requestedBy === authStore.user || isManagerOrAdmin.value
})

const canRetrySap = computed(() => {
  if (doc.value?.status !== 'Failed') return false
  return isManagerOrAdmin.value
})

const canCancel = computed(() => {
  if (doc.value?.status !== 'Posted') return false
  return authStore.isSuperAdmin
})

const canRepost = computed(() => {
  if (doc.value?.status !== 'Cancelled') return false
  return authStore.isSuperAdmin
})

const insufficientStockWarnings = computed(() => {
  const out = []
  for (const row of lineRows.value) {
    if (row?.fefo_status !== 'Insufficient Stock') continue
    out.push({
      item_code: row.item_code || '',
      item_name: row.item_name || row.item_code || 'item',
      available: fmtQty(row.total_allocated_quantity || 0),
      requested: fmtQty(row.requested_quantity || 0),
    })
  }
  return out
})

function consumedQty(row) {
  const allocated = Number(row?.total_allocated_quantity)
  if (Number.isFinite(allocated) && allocated > 0) return allocated
  return row?.requested_quantity
}

function fmtQty(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return value ?? '—'
  if (Number.isInteger(n)) return String(n)
  return String(n)
}

function formatWhen(raw) {
  if (!raw) return ''
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? String(raw) : d.toLocaleString()
}

async function loadDoc() {
  loadErr.value = ''
  const name = docName()
  if (!name) {
    loadErr.value = 'Missing document name'
    return
  }
  deliveryStore.currentDeliveryNote = null
  try {
    await deliveryStore.fetchDeliveryNote(name)
  } catch (e) {
    loadErr.value = deliveryStore.error || parseApiError(e, 'Failed to load store consumption')
  }
}

async function wrap(fn, success = 'Updated') {
  actionBusy.value = true
  try {
    await fn()
    await deliveryStore.fetchDeliveryNote(docName(), { silent: true })
    toast.success(success)
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

async function doSubmit() {
  actionBusy.value = true
  try {
    await deliveryStore.submitDeliveryNote(docName())
    await deliveryStore.fetchDeliveryNote(docName(), { silent: true })
    const d = doc.value
    if (d?.status === 'Posted') {
      toast.success(`Posted to SAP${d.sap_doc_num ? ` — SAP#: ${d.sap_doc_num}` : ''}`)
    } else if (d?.status === 'Failed') {
      toast.error(d.sap_last_error || 'SAP posting failed')
    } else {
      toast.success('Submitted')
    }
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

function doRetrySap() {
  wrap(() => deliveryStore.retrySapPosting(docName()), 'Retry queued')
}

async function doCancel() {
  const d = doc.value
  const confirmed = window.confirm(
    `Cancel SAP delivery note ${d?.sap_doc_num || ''}? ` +
    `This reverses the live SAP document. It will NOT repost automatically — ` +
    `you'll need to click Repost separately. This cannot be undone.`
  )
  if (!confirmed) return

  actionBusy.value = true
  try {
    const result = await deliveryStore.cancelDeliveryNote(docName())
    await deliveryStore.fetchDeliveryNote(docName(), { silent: true })
    toast.success(`Cancelled SAP# ${result?.cancelled_doc_num || ''} — click Repost when ready`)
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

async function doRepost() {
  actionBusy.value = true
  try {
    const result = await deliveryStore.repostCancelledDeliveryNote(docName())
    await deliveryStore.fetchDeliveryNote(docName(), { silent: true })
    if (result?.status === 'Posted') {
      toast.success(`Reposted — new SAP#: ${result.sap_doc_num}`)
    } else if (result?.status === 'Failed') {
      toast.error(result.sap_last_error || 'SAP posting failed')
    } else {
      toast.success('Repost in progress')
    }
  } catch (e) {
    toast.error(parseApiError(e))
  } finally {
    actionBusy.value = false
  }
}

useStoreopsSocket(docName, (payload) => {
  deliveryStore.fetchDeliveryNote(docName(), { silent: true }).catch(() => {})
  if (payload?.level === 'error' && payload?.message) {
    toast.error(payload.message)
  } else if (payload?.level === 'success' && payload?.message) {
    toast.success(payload.message)
  }
})

watch(
  () => route.params.name,
  () => {
    loadDoc()
  },
)

loadDoc()
</script>
