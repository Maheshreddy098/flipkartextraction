<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ po?.purchase_order_name || `PO: ${poId}` }}
      </h1>
      <router-link to="/warehouse/purchase-orders" class="text-sm text-gray-500 hover:text-gray-700">&larr; Back</router-link>
    </div>

    <div v-if="loading" class="text-gray-400">Loading...</div>

    <div v-else-if="po" class="space-y-6">
      <div class="bg-white rounded-xl shadow-sm border p-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><span class="text-gray-500 block">Status</span><StatusBadge :status="po.status" /></div>
          <div><span class="text-gray-500 block">Supplier</span>{{ po.supplier_name || '-' }}</div>
          <div><span class="text-gray-500 block">Date</span>{{ po.posting_date }}</div>
          <div><span class="text-gray-500 block">Total Qty</span>{{ po.total_qty }}</div>
          <div><span class="text-gray-500 block">Created By</span>{{ po.created_by_user }}</div>
          <div><span class="text-gray-500 block">Approved By</span>{{ po.approved_by || '-' }}</div>
          <div><span class="text-gray-500 block">Accepted By</span>{{ po.accepted_by || '-' }}</div>
        </div>
        <div v-if="po.remarks" class="mt-4 text-sm"><span class="text-gray-500">Remarks:</span> {{ po.remarks }}</div>
        <div
          v-if="po.warehouse_awaiting_kf"
          class="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900"
        >
          <strong>On hold.</strong> KhanalFoods is updating this purchase order after your ticket. You can continue as soon as they save.
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border p-6">
        <h2 class="text-lg font-semibold mb-4">Line Items</h2>
        <table class="w-full text-sm border-collapse">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Item Code</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Item Name</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Qty (Ordered)</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">UOM</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Units/Box</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">No. Boxes</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Weight/Pcs</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Qty (Pcs)</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Accepted Qty</th>
              <th class="px-3 py-2 text-left font-medium text-gray-700">Remarks</th>
              <th v-if="po.status === 'Accepted'" class="px-3 py-2 text-left font-medium text-gray-700 w-16"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(merged, mIdx) in mergedItems" :key="merged.item_code + mIdx" class="border-b border-gray-100">
              <td class="px-3 py-2 font-medium">{{ merged.item_code }}</td>
              <td class="px-3 py-2">{{ merged.item_name }}</td>
              <td class="px-3 py-2">{{ merged.totalQty }}</td>
              <td class="px-3 py-2">{{ merged.uom || '—' }}</td>
              <td class="px-3 py-2">{{ merged.number_of_units_per_box ?? '—' }}</td>
              <td class="px-3 py-2">{{ merged.totalBoxes }}</td>
              <td class="px-3 py-2">{{ merged.weight_pcs || '—' }}</td>
              <td class="px-3 py-2">{{ merged.totalPcs || '—' }}</td>
              <td class="px-3 py-2">
                <template v-if="po.status === 'Accepted'">
                  <div class="flex flex-col">
                    <div>
                      <input
                        v-model.number="mergedAcceptedQtys[mIdx]"
                        type="number"
                        min="0"
                        :max="merged.totalQty"
                        step="any"
                        class="w-24 px-2 py-1.5 border rounded text-sm"
                        :class="acceptedErrors[mIdx] ? 'border-red-500' : 'border-gray-300'"
                        placeholder="Same as ordered"
                      />
                      <span class="ml-1 text-gray-400 text-xs">max {{ merged.totalQty }}</span>
                    </div>
                    <p v-if="acceptedErrors[mIdx]" class="mt-1 text-xs text-red-600">
                      {{ acceptedErrors[mIdx] }}
                    </p>
                  </div>
                </template>
                <template v-else>
                  {{ merged.totalAcceptedQty != null ? merged.totalAcceptedQty : (merged.totalQty + ' (full)') }}
                </template>
              </td>
              <td class="px-3 py-2">
                <template v-if="po.status === 'Accepted'">
                  <input
                    v-model="mergedRemarks[mIdx]"
                    type="text"
                    class="w-full min-w-[140px] max-w-xs px-2 py-1.5 border border-gray-300 rounded text-sm"
                    placeholder="e.g. short delivery, quality issue"
                  />
                </template>
                <template v-else>
                  <span class="text-gray-600">{{ merged.remarksDisplay || '—' }}</span>
                </template>
              </td>
              <td v-if="po.status === 'Accepted'" class="px-3 py-2"></td>
            </tr>
          </tbody>
        </table>
        <p v-if="po.status === 'Accepted' && po.items && po.items.length" class="mt-3 text-xs text-gray-500">
          Enter the quantity you actually received per line and optional remarks. Click Mark as Received to save and submit.
        </p>
      </div>

      <div class="flex gap-3">
        <button
          v-if="!po.warehouse_awaiting_kf && po.status === 'Approved'"
          @click="handleAccept"
          :disabled="processing"
          class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm"
        >{{ processing ? 'Accepting...' : 'Accept PO' }}</button>
        <button
          v-if="!po.warehouse_awaiting_kf && po.status === 'Accepted'"
          @click="handleReceive"
          :disabled="processing"
          class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm"
        >{{ processing ? 'Processing...' : 'Mark as Received' }}</button>
        <button
          v-if="!po.warehouse_awaiting_kf && ['Approved', 'Accepted'].includes(po.status)"
          type="button"
          @click="showTicketDialog = true"
          class="px-6 py-2 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium"
        >
          Raise Ticket for KhanalFoods
        </button>
      </div>
      <KFAttachments
        doctype="WowPets Purchase Order"
        :docname="poId"
        :readonly="true"
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
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { fetchPurchaseOrder, acceptPO, receivePO, updateAcceptedQuantities, warehouseRequestKfAssistancePO } from '@/core/api/purchaseOrders.js'
import StatusBadge from '@/components/common/StatusBadge.vue'
import TicketDialog from '@/components/common/TicketDialog.vue'
import KFAttachments from '@/components/common/KFAttachments.vue'
import { createTicket, addTicketAttachment } from '@/core/api/tickets.js'

const props = defineProps({ id: String })
const route = useRoute()
const notify = useNotificationStore()

const poId = props.id || route.params.id
const loading = ref(true)
const processing = ref(false)
const po = ref(null)
const mergedAcceptedQtys = ref([])
const mergedRemarks = ref([])
const acceptedErrors = ref([])
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

/** One row per item (merge po.items by item_code). */
const mergedItems = computed(() => {
  if (!po.value?.items?.length) return []
  const byCode = new Map()
  for (let i = 0; i < po.value.items.length; i++) {
    const item = po.value.items[i]
    const code = (item.item_code || '').trim().toLowerCase()
    if (!code) continue
    if (!byCode.has(code)) {
      byCode.set(code, {
        item_code: item.item_code,
        item_name: item.item_name,
        uom: item.uom,
        totalQty: 0,
        totalBoxes: 0,
        totalPcs: 0,
        weight_pcs: item.weight_pcs ?? 0,
        totalAcceptedQty: null,
        remarksDisplay: '',
        number_of_units_per_box: item.number_of_units_per_box,
        _sourceIndices: [],
      })
    }
    const m = byCode.get(code)
    const qty = Number(item.qty) || 0
    m.totalQty += qty
    m.totalBoxes += Number(item.number_of_boxes) || 0
    m.totalPcs += Number(item.pcs) || 0
    m._sourceIndices.push(i)
    if (item.accepted_qty != null && item.accepted_qty !== '') {
      m.totalAcceptedQty = (m.totalAcceptedQty ?? 0) + Number(item.accepted_qty)
    }
    if (item.acceptance_remarks) {
      m.remarksDisplay = m.remarksDisplay ? m.remarksDisplay + '; ' + item.acceptance_remarks : item.acceptance_remarks
    }
  }
  const result = Array.from(byCode.values())
  // Derive row-level Units/Box so that Units/Box × No. Boxes = Qty (Ordered), matching KhanalFoods display
  for (const m of result) {
    const totalQty = m.totalQty || 0
    const totalBoxes = m.totalBoxes || 0
    if (totalBoxes > 0 && totalQty > 0 && totalQty % totalBoxes === 0) {
      m.number_of_units_per_box = totalQty / totalBoxes
    }
  }
  return result
})

watch([po, mergedItems], () => {
  const merged = mergedItems.value
  if (merged.length) {
    mergedAcceptedQtys.value = merged.map((m) => {
      if (m.totalAcceptedQty != null) return m.totalAcceptedQty
      return m.totalQty || 0
    })
    mergedRemarks.value = merged.map((m) => m.remarksDisplay || '')
    acceptedErrors.value = merged.map(() => '')
  } else {
    mergedAcceptedQtys.value = []
    mergedRemarks.value = []
    acceptedErrors.value = []
  }
}, { immediate: true })

async function loadPO() {
  try {
    po.value = await fetchPurchaseOrder(poId)
  } catch { notify.error('Failed to load PO') }
  loading.value = false
}

async function handleAccept() {
  if (processing.value) return
  processing.value = true
  try {
    await acceptPO(poId)
    notify.success('PO accepted')
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed')
  } finally {
    processing.value = false
  }
}

/**
 * Distribute accepted total across batches as integers. Decrease is taken from one batch only
 * (fill from first: first batches get min(ordered, remaining), so the shortfall falls on the last batch).
 */
function distributeAcceptedToBatchesInteger(orderedQtys, acceptedTotal) {
  const n = orderedQtys.length
  if (n === 0) return []
  if (n === 1) return [Math.max(0, Math.floor(Number(acceptedTotal) || 0))]
  let remaining = Math.max(0, Math.floor(Number(acceptedTotal) || 0))
  const out = []
  for (let i = 0; i < n; i++) {
    const ordered = Math.max(0, Math.floor(Number(orderedQtys[i]) || 0))
    const q = Math.min(ordered, remaining)
    out.push(q)
    remaining -= q
  }
  return out
}

/** Build flat accepted qtys and remarks from merged state and save to backend. */
async function saveAcceptedQuantities() {
  if (!po.value?.items?.length || po.value.status !== 'Accepted') return
  acceptedErrors.value = (mergedItems.value || []).map(() => '')
  const flatQtys = []
  const flatRemarks = []
  const items = po.value.items
  mergedItems.value.forEach((m, mIdx) => {
    const totalQty = m.totalQty || 0
    const acceptedTotal = Number(mergedAcceptedQtys.value[mIdx])
    if (acceptedTotal > totalQty) {
      const msg = `Accepted quantity (${acceptedTotal}) cannot exceed ordered quantity (${totalQty})`
      acceptedErrors.value[mIdx] = msg
      notify.error(msg)
      throw new Error('Accepted qty exceeds ordered qty')
    }
    const remark = (mergedRemarks.value[mIdx] || '').trim()
    const sourceIndices = m._sourceIndices
    const orderedQtys = sourceIndices.map((srcIdx) => Number(items[srcIdx].qty) || 0)
    const distributed = distributeAcceptedToBatchesInteger(orderedQtys, acceptedTotal)
    sourceIndices.forEach((srcIdx, i) => {
      flatQtys[srcIdx] = distributed[i] ?? 0
      flatRemarks[srcIdx] = remark
    })
  })
  const acceptedQtysFlat = items.map((_, idx) => flatQtys[idx] ?? 0)
  const acceptedRemarksFlat = items.map((_, idx) => flatRemarks[idx] ?? '')
  await updateAcceptedQuantities(poId, acceptedQtysFlat, acceptedRemarksFlat)
}

async function handleReceive() {
  if (processing.value) return
  const merged = mergedItems.value || []
  const totalAccepted = merged.reduce((sum, m, idx) => {
    const v = Number(mergedAcceptedQtys.value[idx])
    return sum + (Number.isNaN(v) ? 0 : v)
  }, 0)
  if (totalAccepted <= 0) {
    const msg = 'Accepted quantity must be greater than 0 for at least one line before marking as received'
    acceptedErrors.value = merged.map(() => msg)
    notify.error(msg)
    return
  }
  processing.value = true
  try {
    await saveAcceptedQuantities()
    await receivePO(poId)
    notify.success('PO marked as received. KhanalFoods team will review and post GRN to SAP.')
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed')
  } finally {
    processing.value = false
  }
}

async function handleTicketSubmit(payload) {
  if (!payload) {
    notify.error('Title and description are required')
    return
  }
  ticketSubmitting.value = true
  try {
    await warehouseRequestKfAssistancePO(poId)
    const { ticket, attachment } = payload
    try {
      const created = await createTicket(ticket)
      if (attachment && created?.name) {
        await addTicketAttachment(created.name, attachment.file_name, attachment.filedata)
      }
    } catch (te) {
      notify.success('Purchase order is on hold for KhanalFoods.')
      notify.error(
        (te.response?.data?.message || 'Could not create ticket') +
          '. Add one from Tickets and link this purchase order if needed.',
      )
      showTicketDialog.value = false
      await loadPO()
      return
    }
    notify.success('On hold. KhanalFoods will update this purchase order; you can continue after they save.')
    showTicketDialog.value = false
    await loadPO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Could not place purchase order on hold')
  } finally {
    ticketSubmitting.value = false
  }
}

onMounted(loadPO)
</script>
