<template>
  <div class="p-6 w-full">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ order?.fba_transfer_name || `FBA Transfer: ${orderId}` }}
      </h1>
      <router-link to="/warehouse/orders" class="text-sm text-gray-500 hover:text-gray-700">&larr; Back</router-link>
    </div>

    <div v-if="loading" class="text-gray-400">Loading...</div>

    <div v-else-if="order" class="space-y-6">
      <div class="bg-white rounded-xl shadow-sm border p-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><span class="text-gray-500 block">Status</span><StatusBadge :status="order.status === 'Sent to SAP' ? 'Completed' : order.status" /></div>
          <div><span class="text-gray-500 block">Doc Date</span>{{ order.doc_date }}</div>
          <div><span class="text-gray-500 block">To Warehouse</span>{{ order.to_warehouse }}</div>
          <div><span class="text-gray-500 block">Accepted By</span>{{ order.accepted_by || '—' }}</div>
          <p v-if="order.sap_sync_error" class="col-span-2 text-sm text-red-600">{{ order.sap_sync_error }}</p>
        </div>
        <div
          v-if="order.warehouse_awaiting_kf"
          class="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900"
        >
          <strong>On hold.</strong> KhanalFoods is updating this order after your ticket. You can continue as soon as they save.
        </div>
      </div>

      <div v-if="order.address_line1 || order.city || order.state || order.zip_code" class="bg-white rounded-xl shadow-sm border p-6">
        <h2 class="text-base font-semibold text-gray-800 mb-3">Address (USA)</h2>
        <div class="text-sm text-gray-700 space-y-1">
          <p>{{ order.address_line1 }}</p>
          <p v-if="order.address_line2">{{ order.address_line2 }}</p>
          <p>{{ [order.city, order.state, order.zip_code].filter(Boolean).join(', ') }}</p>
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border">
        <div class="px-6 py-4 border-b">
          <h2 class="text-lg font-semibold text-gray-800">Line Items</h2>
          <p class="text-xs text-gray-500 mt-1">Fill Units per box and Number of boxes. Green tick when they match quantity — then you can dispatch.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase">Item</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Quantity</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-20">UOM</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-28">Units/Box</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">No. Boxes</th>
                <th class="px-4 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-16">OK</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in lineItems" :key="idx" class="border-b border-gray-100">
                <td class="px-4 py-2.5">
                  <span class="font-medium text-gray-800">{{ item.item_code }}</span>
                  <span v-if="item.item_name" class="block text-gray-500 text-xs">{{ item.item_name }}</span>
                </td>
                <td class="px-4 py-2.5 font-medium">{{ item.quantity }}</td>
                <td class="px-4 py-2.5">{{ item.uom || 'Nos' }}</td>
                <td class="px-4 py-2.5">
                  <input
                    v-if="order.status === 'Packaging'"
                    v-model.number="item.number_of_units_per_box"
                    type="number"
                    min="0"
                    class="input-field-sm w-20"
                    @input="onUnitsPerBoxChange(item)"
                  />
                  <span v-else>{{ item.number_of_units_per_box ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <input
                    v-if="order.status === 'Packaging'"
                    v-model.number="item.number_of_boxes"
                    type="number"
                    min="0"
                    class="input-field-sm w-20"
                  />
                  <span v-else>{{ item.number_of_boxes ?? '—' }}</span>
                </td>
                <td class="px-4 py-2.5 text-center">
                  <span v-if="lineValid(item)" class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600" title="Units × Boxes = Quantity">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                  </span>
                  <span v-else class="text-gray-300">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'Approved'"
          @click="handleAccept"
          :disabled="processing"
          class="px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Accepting...' : 'Accept FBA Transfer' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'Accepted'"
          @click="handleStartPackaging"
          :disabled="processing"
          class="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Starting...' : 'Start Packaging' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'Accepted' && !order.sap_request_doc_entry"
          @click="handleRetrySapRequest"
          :disabled="processing"
          class="px-6 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Creating...' : 'Retry SAP Request' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'Packaging'"
          @click="handleComplete"
          :disabled="processing || !allLinesValid"
          class="px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
          :title="allLinesValid ? 'Dispatch order in the system' : 'Fill Units/Box so every line shows green tick'"
        >
          {{ processing ? 'Dispatching...' : 'Dispatch' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'Error'"
          @click="handleRetrySap"
          :disabled="processing"
          class="px-6 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Retrying...' : 'Retry sync' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && ['Approved', 'Accepted', 'Packaging', 'Error'].includes(order.status)"
          type="button"
          @click="showTicketDialog = true"
          class="px-6 py-2.5 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium"
        >
          Raise Ticket for KhanalFoods
        </button>
      </div>
      <KFAttachments
        doctype="WowPets Order"
        :docname="orderId"
        :readonly="true"
      />

      <TicketDialog
        :visible="showTicketDialog"
        title="Raise Ticket for FBA Transfer"
        section="FBA Transfer"
        reference-doctype="WowPets Order"
        :reference-name="orderId"
        :submitting="ticketSubmitting"
        @submit="handleTicketSubmit"
        @cancel="showTicketDialog = false"
      />
      <p v-if="order.status === 'Packaging' && !allLinesValid" class="text-sm text-amber-600">
        Fill <strong>Units per box</strong> and <strong>Number of boxes</strong> for each line so that (Units per box × Number of boxes) = Quantity. When all lines show a green tick, you can dispatch the order.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  fetchOrder,
  acceptOrder,
  startPackagingOrder,
  completeOrder,
  sendOrderToSap,
  retryOrderSapRequest,
  warehouseRequestKfAssistanceOrder,
} from '@/core/api/orders.js'
import StatusBadge from '@/components/common/StatusBadge.vue'
import TicketDialog from '@/components/common/TicketDialog.vue'
import KFAttachments from '@/components/common/KFAttachments.vue'
import { createTicket, addTicketAttachment } from '@/core/api/tickets.js'

const props = defineProps({ id: String })
const route = useRoute()
const session = useSessionStore()
const notify = useNotificationStore()

const orderId = props.id || route.params.id
const loading = ref(true)
const processing = ref(false)
const order = ref(null)
const lineItems = ref([])
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

function onUnitsPerBoxChange(item) {
  const qty = Number(item.quantity) || 0
  const upb = Number(item.number_of_units_per_box) || 0
  if (upb > 0 && qty > 0) item.number_of_boxes = Math.round(qty / upb)
}

function lineValid(item) {
  const qty = Number(item.quantity) || 0
  const upb = parseInt(item.number_of_units_per_box, 10) || 0
  const boxes = parseInt(item.number_of_boxes, 10) || 0
  if (qty <= 0) return false
  return upb > 0 && boxes > 0 && upb * boxes === qty
}

const allLinesValid = computed(() => {
  if (!order.value || order.value.status !== 'Packaging' || !lineItems.value.length) return false
  return lineItems.value.every((item) => lineValid(item))
})

async function loadOrder() {
  loading.value = true
  try {
    const data = await fetchOrder(orderId)
    order.value = data
    lineItems.value = (data.items || []).map((i) => ({
      item_code: i.item_code,
      item_name: i.item_name,
      quantity: i.quantity,
      uom: i.uom || 'Nos',
      number_of_units_per_box: i.number_of_units_per_box ?? 0,
      number_of_boxes: i.number_of_boxes ?? 0,
      batch_number: i.batch_number || '',
    }))
  } catch {
    notify.error('Failed to load order')
  }
  loading.value = false
}

async function handleAccept() {
  processing.value = true
  try {
    await acceptOrder(orderId)
    notify.success('FBA Transfer accepted. You can start packaging.')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Accept failed')
  } finally {
    processing.value = false
  }
}

async function handleStartPackaging() {
  processing.value = true
  try {
    await startPackagingOrder(orderId)
    notify.success('Packaging started. Fill units per box and number of boxes for each line.')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Start packaging failed')
  } finally {
    processing.value = false
  }
}

async function handleComplete() {
  if (!allLinesValid.value) {
    notify.error('All lines must show green tick (Units per box × Number of boxes = Quantity)')
    return
  }
  processing.value = true
  try {
    const payload = { items: lineItems.value.map((i) => ({
      item_code: i.item_code,
      item_name: i.item_name,
      quantity: Number(i.quantity),
      uom: i.uom || 'Nos',
      number_of_units_per_box: parseInt(i.number_of_units_per_box, 10) || 0,
      number_of_boxes: parseInt(i.number_of_boxes, 10) || 0,
      batch_number: (i.batch_number || '').trim() || undefined,
    })) }
    const updated = await completeOrder(orderId, payload)
    if (updated && updated.status === 'Error') {
      notify.error('FBA Transfer was dispatched, but there was a sync issue. Use Retry below.')
    } else {
      notify.success('FBA Transfer dispatched and synced.')
    }
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Complete failed')
  } finally {
    processing.value = false
  }
}

async function handleRetrySap() {
  processing.value = true
  try {
    await sendOrderToSap(orderId)
    notify.success('FBA Transfer sync retried.')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Retry failed')
  } finally {
    processing.value = false
  }
}

async function handleRetrySapRequest() {
  processing.value = true
  try {
    await retryOrderSapRequest(orderId)
    notify.success('SAP Transfer Request created successfully')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'SAP Transfer Request failed')
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
    await warehouseRequestKfAssistanceOrder(orderId)
    const { ticket, attachment } = payload
    try {
      const created = await createTicket(ticket)
      if (attachment && created?.name) {
        await addTicketAttachment(created.name, attachment.file_name, attachment.filedata)
      }
    } catch (te) {
      notify.success('FBA Transfer is on hold for KhanalFoods.')
      notify.error(
        (te.response?.data?.message || 'Could not create ticket') +
          '. Add one from Tickets and link this order if needed.',
      )
      showTicketDialog.value = false
      await loadOrder()
      return
    }
    notify.success('On hold. KhanalFoods will update this order; you can continue after they save.')
    showTicketDialog.value = false
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Could not place order on hold')
  } finally {
    ticketSubmitting.value = false
  }
}

onMounted(loadOrder)
</script>

<style scoped>
.input-field-sm {
  @apply w-full px-2.5 py-1.5 border border-gray-200 rounded-md text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white transition;
}
</style>
