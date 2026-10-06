<template>
  <div class="p-6 w-full">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">
          {{ order?.dispatch_order_name || `Dispatch Order: ${order?.name || orderId}` }}
        </h1>
        <p v-if="order?.name" class="text-sm text-gray-500 mt-0.5">{{ order.name }}</p>
      </div>
      <router-link to="/warehouse/dispatch-orders" class="text-sm text-gray-500 hover:text-gray-700">&larr; Back</router-link>
    </div>

    <div v-if="loading" class="text-gray-400">Loading...</div>

    <div v-else-if="order" class="space-y-6">
      <div class="bg-white rounded-xl shadow-sm border p-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><span class="text-gray-500 block">Status</span><StatusBadge :status="order.status" /></div>
          <div><span class="text-gray-500 block">Customer</span>{{ order.card_code }} – {{ order.card_name }}</div>
          <div><span class="text-gray-500 block">Doc Date</span>{{ order.doc_date }}</div>
          <div><span class="text-gray-500 block">Due Date</span>{{ order.doc_due_date || '—' }}</div>
          <div><span class="text-gray-500 block">Accepted By</span>{{ order.accepted_by || '—' }}</div>
          <div v-if="order.mobile_number"><span class="text-gray-500 block">Mobile</span>{{ order.mobile_number }}</div>
          <div v-if="order.dispatched_at"><span class="text-gray-500 block">Dispatched At</span>{{ order.dispatched_at }}</div>
        </div>
        <p v-if="order.comments" class="mt-3 text-sm text-gray-600">{{ order.comments }}</p>
        <p
          v-if="order.status === 'Error' && order.sap_sync_error"
          class="mt-3 text-sm text-red-600"
        >
          {{ order.sap_sync_error }}. This dispatch order has a SAP error and is being reviewed by the KhanalFoods team.
        </p>
        <div
          v-if="order.warehouse_awaiting_kf"
          class="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900"
        >
          <strong>On hold.</strong> KhanalFoods is updating this dispatch order after your ticket. You can continue as soon as they save.
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border">
        <div class="px-6 py-4 border-b">
          <h2 class="text-lg font-semibold text-gray-800">Line Items</h2>
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
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase w-24">Unit Price</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in groupedItems" :key="idx" class="border-b border-gray-100">
                <td class="px-4 py-2.5">
                  <span class="font-medium text-gray-800">{{ item.item_code }}</span>
                  <span v-if="item.item_name" class="block text-gray-500 text-xs">{{ item.item_name }}</span>
                </td>
                <td class="px-4 py-2.5 font-medium">{{ item.quantity }}</td>
                <td class="px-4 py-2.5">{{ item.uom || 'Nos' }}</td>
                <td class="px-4 py-2.5">{{ item.number_of_units_per_box ?? '—' }}</td>
                <td class="px-4 py-2.5">{{ item.number_of_boxes ?? '—' }}</td>
                <td class="px-4 py-2.5">{{ item.unit_price }}</td>
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
          {{ processing ? 'Accepting...' : 'Accept Order' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'Accepted'"
          @click="handleStartPreparation"
          :disabled="processing"
          class="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Starting...' : 'Start Preparation' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && order.status === 'In Preparation'"
          @click="handleDispatch"
          :disabled="processing"
          class="px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Dispatching...' : 'Mark Dispatched' }}
        </button>
        <button
          v-if="order.sap_doc_entry && ['Approved', 'Error'].includes(order.status)"
          @click="handleReconcileStatus"
          :disabled="processing"
          class="px-6 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 text-sm font-medium"
        >
          {{ processing ? 'Fixing...' : 'Fix Status' }}
        </button>
        <button
          v-if="!order.warehouse_awaiting_kf && ['Approved', 'Accepted', 'In Preparation', 'Error'].includes(order.status)"
          type="button"
          @click="showTicketDialog = true"
          class="px-6 py-2.5 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium"
        >
          Raise Ticket for KhanalFoods
        </button>
      </div>
      <KFAttachments
        doctype="WowPets Dispatch Order"
        :docname="orderId"
        :readonly="true"
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useNotificationStore } from '@/core/stores/notifications.js'
import {
  fetchDispatchOrder,
  acceptDispatchOrder,
  startPreparationDispatchOrder,
  dispatchDispatchOrder,
  warehouseRequestKfAssistanceDispatch,
  reconcileDispatchStatus,
} from '@/core/api/dispatchOrders.js'
import StatusBadge from '@/components/common/StatusBadge.vue'
import TicketDialog from '@/components/common/TicketDialog.vue'
import KFAttachments from '@/components/common/KFAttachments.vue'
import { createTicket, addTicketAttachment } from '@/core/api/tickets.js'

const props = defineProps({ id: String })
const route = useRoute()
const notify = useNotificationStore()

const orderId = props.id || route.params.id
const loading = ref(true)
const processing = ref(false)
const order = ref(null)
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

const groupedItems = computed(() => {
  const items = order.value?.items || []
  if (!items.length) return []

  const map = new Map()

  for (const row of items) {
    const key = [
      row.item_code || '',
      row.item_name || '',
      row.uom || 'Nos',
      row.number_of_units_per_box ?? '',
      row.unit_price ?? '',
    ].join('::')

    const existing = map.get(key) || {
      item_code: row.item_code,
      item_name: row.item_name,
      uom: row.uom || 'Nos',
      number_of_units_per_box: row.number_of_units_per_box,
      unit_price: row.unit_price,
      quantity: 0,
      number_of_boxes: 0,
    }

    existing.quantity += Number(row.quantity || 0)
    existing.number_of_boxes += Number(row.number_of_boxes || 0)

    map.set(key, existing)
  }

  return Array.from(map.values())
})

async function loadOrder() {
  loading.value = true
  try {
    order.value = await fetchDispatchOrder(orderId)
  } catch {
    notify.error('Failed to load dispatch order')
  } finally {
    loading.value = false
  }
}

async function handleAccept() {
  processing.value = true
  try {
    await acceptDispatchOrder(orderId)
    notify.success('Order accepted')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to accept')
  } finally {
    processing.value = false
  }
}

async function handleStartPreparation() {
  processing.value = true
  try {
    await startPreparationDispatchOrder(orderId)
    notify.success('Preparation started')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to start preparation')
  } finally {
    processing.value = false
  }
}

async function handleDispatch() {
  processing.value = true
  try {
    await dispatchDispatchOrder(orderId)
    notify.success('Order marked as dispatched')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to dispatch')
  } finally {
    processing.value = false
  }
}

async function handleReconcileStatus() {
  processing.value = true
  try {
    await reconcileDispatchStatus(orderId)
    notify.success('Status fixed')
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to fix status')
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
    await warehouseRequestKfAssistanceDispatch(orderId)
    const { ticket, attachment } = payload
    try {
      const created = await createTicket(ticket)
      if (attachment && created?.name) {
        await addTicketAttachment(created.name, attachment.file_name, attachment.filedata)
      }
    } catch (te) {
      notify.success('Dispatch order is on hold for KhanalFoods.')
      notify.error(
        (te.response?.data?.message || 'Could not create ticket') +
          '. Add one from Tickets and link this dispatch order if needed.',
      )
      showTicketDialog.value = false
      await loadOrder()
      return
    }
    notify.success('On hold. KhanalFoods will update this dispatch order; you can continue after they save.')
    showTicketDialog.value = false
    await loadOrder()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Could not place dispatch order on hold')
  } finally {
    ticketSubmitting.value = false
  }
}

onMounted(loadOrder)
</script>
