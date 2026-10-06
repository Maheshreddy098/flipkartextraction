<template>
  <div class="p-6 w-full">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ wo?.work_order_name || `Work Order: ${woId}` }}
      </h1>
      <router-link to="/warehouse/work-orders" class="text-sm text-gray-500 hover:text-gray-700">&larr; Back</router-link>
    </div>

    <div v-if="loading" class="text-gray-400">Loading...</div>

    <div v-else-if="wo" class="space-y-6">
      <div class="bg-white rounded-xl shadow-sm border p-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><span class="text-gray-500 block">Status</span><StatusBadge :status="wo.status" /></div>
          <div><span class="text-gray-500 block">Finished Item</span>{{ wo.finished_item_code }}<span v-if="wo.finished_item_name" class="block text-gray-700 text-xs mt-0.5">{{ wo.finished_item_name }}</span></div>
          <div><span class="text-gray-500 block">Qty to Produce</span>{{ wo.qty_to_produce }}</div>
          <div><span class="text-gray-500 block">Produced</span>{{ wo.produced_qty || 0 }}</div>
          <div><span class="text-gray-500 block">Finished goods batch</span>{{ wo.finished_goods_batch || '—' }}</div>
          <div><span class="text-gray-500 block">BOM No</span>{{ wo.bom_no || '-' }}</div>
          <div><span class="text-gray-500 block">Warehouse</span>{{ wo.warehouse || 'WowPets Warehouse' }}</div>
          <div><span class="text-gray-500 block">Created By</span>{{ wo.created_by_user }}</div>
          <div><span class="text-gray-500 block">Date</span>{{ wo.posting_date }}</div>
        </div>
        <div
          v-if="wo.warehouse_awaiting_kf"
          class="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900"
        >
          <strong>On hold.</strong> KhanalFoods is updating this work order after your ticket. You can continue as soon as they save.
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border p-6">
        <h2 class="text-lg font-semibold mb-4">Raw Materials / Components</h2>
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2 text-left">Item Code</th>
              <th class="px-3 py-2 text-left min-w-[200px]">Item Name</th>
              <th class="px-3 py-2 text-left">Required Qty</th>
              <template v-if="isCompletedWO">
                <th class="px-3 py-2 text-left">Consumed Qty</th>
              </template>
              <template v-else>
                <th class="px-3 py-2 text-left">Available Qty</th>
                <th class="px-3 py-2 text-left">Status</th>
              </template>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in displayItems" :key="row.item_code" class="border-b">
              <td class="px-3 py-2 font-medium">{{ row.item_code }}</td>
              <td class="px-3 py-2 whitespace-normal break-words">{{ row.item_name }}</td>
              <td class="px-3 py-2">{{ row.required_qty }}</td>
              <template v-if="isCompletedWO">
                <td class="px-3 py-2 text-gray-800 font-medium">{{ row.consumed_qty }}</td>
              </template>
              <template v-else>
                <td class="px-3 py-2" :class="(row.current_available || 0) < row.required_qty ? 'text-red-600 font-semibold' : 'text-green-600'">
                  {{ row.current_available ?? row.available_qty ?? 0 }}
                </td>
                <td class="px-3 py-2">
                  <span v-if="(row.current_available ?? 0) >= row.required_qty" class="text-green-600 text-xs font-medium">Available</span>
                  <span v-else class="text-red-600 text-xs font-medium">Insufficient</span>
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex flex-wrap gap-3 items-center">
        <button
          v-if="!wo.warehouse_awaiting_kf && wo.status === 'Approved'"
          @click="handleStart"
          :disabled="processing"
          class="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm"
        >{{ processing ? 'Starting...' : 'Start (Accept Work Order)' }}</button>
        <button
          v-if="!wo.warehouse_awaiting_kf && wo.status === 'In Progress' && !wo.warehouse_consumed"
          @click="handleMarkConsumed"
          :disabled="processing"
          class="px-6 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 text-sm"
        >{{ processing ? 'Processing...' : 'Mark Consumed' }}</button>
        <button
          v-if="!wo.warehouse_awaiting_kf && wo.status === 'In Progress' && wo.warehouse_consumed && !wo.warehouse_completed"
          @click="handleWarehouseComplete"
          :disabled="processing"
          class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm"
        >{{ processing ? 'Processing...' : 'Complete (FG ready)' }}</button>
        <button
          v-if="showRaiseTicket"
          type="button"
          @click="showTicketDialog = true"
          class="px-6 py-2 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 text-sm font-medium"
        >
          Raise ticket for KhanalFoods
        </button>
      </div>
      <KFAttachments
        doctype="WowPets Work Order"
        :docname="woId"
        :readonly="true"
      />

      <TicketDialog
        :visible="showTicketDialog"
        title="Raise ticket for Work Order"
        section="Work Order"
        reference-doctype="WowPets Work Order"
        :reference-name="woId"
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
  fetchWorkOrder,
  startProcessingWO,
  warehouseMarkConsumedWO,
  warehouseCompleteWO,
  warehouseRequestKfAssistance,
} from '@/core/api/workOrders.js'
import StatusBadge from '@/components/common/StatusBadge.vue'
import TicketDialog from '@/components/common/TicketDialog.vue'
import KFAttachments from '@/components/common/KFAttachments.vue'
import { createTicket, addTicketAttachment } from '@/core/api/tickets.js'

const props = defineProps({ id: String })
const route = useRoute()
const notify = useNotificationStore()

const woId = computed(() => props.id || route.params.id)
const loading = ref(true)
const processing = ref(false)
const wo = ref(null)
const showTicketDialog = ref(false)
const ticketSubmitting = ref(false)

const isCompletedWO = computed(() => wo.value?.status === 'Completed')

const showRaiseTicket = computed(() => {
  const w = wo.value
  if (!w || w.warehouse_awaiting_kf) return false
  if (w.status === 'Approved' || w.status === 'In Progress') return true
  if (w.status === 'Completed' && !w.sap_receipt_doc_entry) return true
  return false
})

/** One row per item (merge by item_code); batch numbers hidden for warehouse. */
const displayItems = computed(() => {
  const items = wo.value?.items || []
  if (!items.length) return []
  const byCode = new Map()
  for (const i of items) {
    const code = (i.item_code || '').trim()
    if (!code) continue
    const key = code.toLowerCase()
    if (!byCode.has(key)) {
      byCode.set(key, {
        item_code: i.item_code,
        item_name: i.item_name || '',
        required_qty: 0,
        allocated_sum: 0,
        current_available: i.current_available ?? i.available_qty ?? 0,
        available_qty: i.available_qty ?? i.current_available ?? 0,
      })
    }
    const row = byCode.get(key)
    row.required_qty += Number(i.required_qty) || 0
    row.allocated_sum += Number(i.allocated_qty) || 0
  }
  return Array.from(byCode.values()).map((row) => ({
    ...row,
    /** Consumed = allocated total per line; if not tracked, fall back to required (completed WO). */
    consumed_qty: row.allocated_sum > 0 ? row.allocated_sum : row.required_qty,
  }))
})

async function loadWO() {
  try { wo.value = await fetchWorkOrder(woId.value) }
  catch { notify.error('Failed to load work order') }
  loading.value = false
}

async function handleStart() {
  processing.value = true
  try {
    const data = await startProcessingWO(woId.value)
    if (data && data.sap_sync_error) {
      notify.success('Work order accepted. If posting is delayed, the office team will follow up.')
    } else {
      notify.success('Work order accepted.')
    }
    await loadWO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to start')
  } finally {
    processing.value = false
  }
}

async function handleMarkConsumed() {
  processing.value = true
  try {
    const data = await warehouseMarkConsumedWO(woId.value)
    if (data && data.sap_sync_error) {
      notify.success('Components marked consumed. If posting is delayed, the office team will follow up.')
    } else {
      notify.success('Components marked consumed.')
    }
    await loadWO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to mark consumed')
  } finally {
    processing.value = false
  }
}

async function handleWarehouseComplete() {
  processing.value = true
  try {
    const data = await warehouseCompleteWO(woId.value)
    if (data && data.sap_sync_error) {
      notify.success('Work order completed. If posting is delayed, the office team will follow up.')
    } else {
      notify.success('Work order completed.')
    }
    await loadWO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to complete')
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
    await warehouseRequestKfAssistance(woId.value)
    const { ticket, attachment } = payload
    try {
      const created = await createTicket(ticket)
      if (attachment && created?.name) {
        await addTicketAttachment(created.name, attachment.file_name, attachment.filedata)
      }
    } catch (te) {
      notify.success('Work order is on hold for KhanalFoods.')
      notify.error(
        (te.response?.data?.message || 'Could not create ticket') +
          '. Add one from Tickets and link this work order if needed.',
      )
      showTicketDialog.value = false
      await loadWO()
      return
    }
    notify.success('On hold. KhanalFoods will update this work order; you can continue after they save.')
    showTicketDialog.value = false
    await loadWO()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Could not place work order on hold')
  } finally {
    ticketSubmitting.value = false
  }
}

onMounted(loadWO)
</script>
