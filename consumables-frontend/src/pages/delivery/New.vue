<template>
  <div class="max-w-5xl p-4 sm:p-6">
    <RouterLink to="/delivery" class="mb-4 inline-block text-sm text-teal-700 hover:text-teal-800">
      ← Back to Store Consumptions
    </RouterLink>

    <h1 class="mb-4 text-xl font-bold text-gray-900 sm:mb-6 sm:text-2xl">New Store Consumption</h1>

    <form class="space-y-6" @submit.prevent="submit">
      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Plant</label>
            <div v-if="!authStore.isSuperAdmin || authStore.plants.length <= 1" class="rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-800">
              {{ currentPlantLabel }}
            </div>
            <select
              v-else
              v-model="plantCode"
              class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
            >
              <option value="">Select plant</option>
              <option v-for="p in authStore.plants" :key="p.plant_code" :value="p.plant_code">
                {{ p.plant_code }} — {{ p.plant_name || p.plant_code }}
              </option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Warehouse</label>
            <div class="rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-800">
              {{ warehouseCode || 'No warehouse configured' }}
            </div>
          </div>
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-gray-700">Purpose</label>
        <input
          v-model="purpose"
          type="text"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
          placeholder="Comments for SAP"
        />
      </div>

      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <label class="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input v-model="isBackdated" type="checkbox" class="rounded border-gray-300 text-teal-600" />
          Backdate this delivery
        </label>
        <div v-if="isBackdated" class="mt-3 grid gap-4 md:grid-cols-2">
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Delivery Date</label>
            <input
              v-model="docDate"
              type="date"
              :min="minDate"
              :max="maxDate"
              class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Reason for backdating</label>
            <input
              v-model="backdateReason"
              type="text"
              class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
              placeholder="Why is this backdated?"
            />
          </div>
        </div>
      </div>

      <BatchPicker
        v-model="lineItems"
        :plant-code="plantCode"
        :warehouse-code="warehouseCode"
        :show-uom="true"
      />

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:gap-3">
        <button
          type="submit"
          class="w-full justify-center rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:py-2"
          :disabled="submitting"
        >
          {{ submitting ? 'Posting…' : 'Post to SAP' }}
        </button>
        <RouterLink
          to="/delivery"
          class="flex w-full items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:w-auto sm:py-2"
        >
          Cancel
        </RouterLink>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'frappe-ui'
import { useAuthStore } from '@/stores/auth.js'
import { useDeliveryStore } from '@/stores/delivery.js'
import { BatchPicker } from '@/shared/components/index.js'

const router = useRouter()
const authStore = useAuthStore()
const deliveryStore = useDeliveryStore()

const BACKDATE_MAX_DAYS = 30

const plantCode = ref('')
const warehouseCode = ref('')
const purpose = ref('')
const lineItems = ref([blankLine()])
const submitting = ref(false)

const isBackdated = ref(false)
const docDate = ref(toDateStr(new Date()))
const backdateReason = ref('')

function toDateStr(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const maxDate = toDateStr(new Date())
const minDate = toDateStr(new Date(Date.now() - BACKDATE_MAX_DAYS * 24 * 60 * 60 * 1000))

watch(isBackdated, (value) => {
  if (!value) {
    docDate.value = maxDate
    backdateReason.value = ''
  }
})

const currentPlant = computed(() => {
  const selected = authStore.plants?.find((p) => p.plant_code === plantCode.value)
  return selected || authStore.plants?.[0] || null
})

const currentPlantLabel = computed(() => {
  if (!currentPlant.value) return 'No plant assigned'
  return `${currentPlant.value.plant_code} — ${currentPlant.value.plant_name || currentPlant.value.plant_code}`
})

const currentWarehouseOptions = computed(() => {
  if (!currentPlant.value) return []
  return (currentPlant.value.warehouses || [])
    .filter((w) => w.is_active !== false)
    .map((w) => ({
      warehouse_code: w.warehouse_code || w.name,
      warehouse_name: w.warehouse_name || '',
    }))
})

watch(
  () => authStore.plants,
  () => {
    plantCode.value = currentPlant.value?.plant_code || ''
  },
  { immediate: true },
)

watch(
  currentPlant,
  () => {
    warehouseCode.value = currentWarehouseOptions.value[0]?.warehouse_code || ''
    resetItems()
  },
  { immediate: true },
)

watch(warehouseCode, resetItems)

function blankLine() {
  return {
    item_code: '',
    item_name: '',
    batch_number: '',
    quantity: 0,
    uom: '',
    available_quantity: 0,
    _item_query: '',
  }
}

function resetItems() {
  lineItems.value = [blankLine()]
}

function effectiveRows() {
  return lineItems.value.filter((row) => {
    const hasItem = !!String(row.item_code || '').trim()
    const hasQty = Number(row.quantity) > 0
    return hasItem || hasQty
  })
}

function validateClient() {
  if (!plantCode.value) {
    toast.error('No plant selected for store consumption')
    return false
  }
  if (!warehouseCode.value) {
    toast.error('No warehouse selected for store consumption')
    return false
  }
  if (!purpose.value.trim()) {
    toast.error('Purpose is required')
    return false
  }
  const rows = effectiveRows()
  if (!rows.length) {
    toast.error('Add at least one line item')
    return false
  }

  if (isBackdated.value) {
    if (!docDate.value) {
      toast.error('Delivery date is required when backdating')
      return false
    }
    if (docDate.value > maxDate) {
      toast.error('Delivery date cannot be in the future')
      return false
    }
    if (docDate.value < minDate) {
      toast.error(`Delivery date cannot be more than ${BACKDATE_MAX_DAYS} days in the past`)
      return false
    }
    if (!backdateReason.value.trim()) {
      toast.error('Reason is required when backdating a delivery note')
      return false
    }
  }

  for (const row of rows) {
    if (!String(row.item_code || '').trim()) {
      toast.error('Each line item requires a valid item code')
      return false
    }
    const qty = Number(row.quantity)
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error('Each line item requires quantity greater than zero')
      return false
    }
    const max = Number(row.available_quantity)
    if (Number.isFinite(max) && qty > max) {
      toast.error(
        max === 0
          ? `${row.item_code} is out of stock`
          : `Quantity cannot exceed available stock (${max}) for ${row.item_code}`
      )
      return false
    }
  }

  return true
}

async function submit() {
  if (!validateClient()) return
  submitting.value = true

  try {
    const rows = effectiveRows()
    const payload = {
      plant_code: plantCode.value,
      warehouse_code: warehouseCode.value,
      purpose: purpose.value.trim(),
      line_items: rows.map((row) => ({
        item_code: row.item_code,
        item_name: row.item_name || '',
        requested_quantity: Number(row.quantity),
        uom: row.uom || '',
      })),
    }

    if (isBackdated.value) {
      payload.doc_date = docDate.value
      payload.remarks = backdateReason.value.trim()
    }

    const doc = await deliveryStore.postDeliveryNote(payload)
    const name = doc?.name
    if (!name) {
      toast.error('Posted store consumption but missing document name')
      return
    }
    if (doc.status !== 'Posted') {
      throw new Error(doc.sap_last_error || 'Delivery note was not posted to SAP')
    }

    toast.success('Delivery note posted to SAP')
    router.push({ name: 'DeliveryDetail', params: { name } })
  } catch (e) {
    const msg =
      e?.messages?.[0] ||
      e?.exc ||
      e?.message ||
      'Could not post store consumption to SAP'
    toast.error(typeof msg === 'string' ? msg : String(msg))
  } finally {
    submitting.value = false
  }
}
</script>
