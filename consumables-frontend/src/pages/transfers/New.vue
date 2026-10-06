<template>
  <div class="max-w-4xl p-4 sm:p-6">
    <RouterLink to="/transfers" class="text-sm text-teal-700 hover:text-teal-800 mb-4 inline-block">
      ← Back to transfers
    </RouterLink>

    <h1 class="mb-4 text-xl font-bold text-gray-900 sm:mb-6 sm:text-2xl">New Transfer Request</h1>

    <form class="space-y-6" @submit.prevent="submit">
      <div class="grid gap-4 md:grid-cols-2">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">From Warehouse</label>
          <select
            v-model="fromKey"
            required
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-800"
          >
            <option value="">Select warehouse</option>
            <option v-for="o in fromWarehouseOptions" :key="o.value" :value="o.value">
              {{ o.label }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">To Plant</label>
          <select
            v-model="toPlantCode"
            required
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-800"
            :disabled="loadingDestinations"
          >
            <option value="">Select plant</option>
            <option v-for="p in destinationPlants" :key="p.plant_code" :value="p.plant_code">
              {{ p.plant_code }} — {{ p.plant_name }}
            </option>
          </select>
          <p v-if="!loadingDestinations && !destinationPlants.length" class="text-xs text-amber-700 mt-1">
            No eligible destination plants (you may already have access to all plants).
          </p>
        </div>

      </div>

      <BatchPicker
        v-model="lineItems"
        :plant-code="fromPlantCode"
        :warehouse-code="fromWarehouseCode"
      />

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Remarks (optional)</label>
        <textarea
          v-model="remarks"
          rows="3"
          class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-800"
          placeholder="Notes for approvers…"
        />
      </div>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:gap-3">
        <button
          type="submit"
          class="w-full justify-center rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:py-2"
          :disabled="submitting"
        >
          {{ submitting ? 'Creating…' : 'Create draft' }}
        </button>
        <RouterLink
          to="/transfers"
          class="flex w-full items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:w-auto sm:py-2"
        >
          Cancel
        </RouterLink>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'frappe-ui'
import { useAuthStore } from '@/stores/auth.js'
import { useTransfersStore } from '@/stores/transfers.js'
import { get_destination_plants } from '@/core/api/transfers.js'
import { BatchPicker } from '@/shared/components/index.js'

const router = useRouter()
const authStore = useAuthStore()
const transfersStore = useTransfersStore()

const fromKey = ref('')
const toPlantCode = ref('')
const remarks = ref('')
const lineItems = ref([])
const submitting = ref(false)

const destinationPlants = ref([])
const loadingDestinations = ref(false)

const fromWarehouseOptions = computed(() => {
  const opts = []
  for (const p of authStore.plants || []) {
    const pname = p.plant_name || p.plant_code
    for (const w of p.warehouses || []) {
      if (w.is_active === false) continue
      const wc = w.warehouse_code || w.name
      if (!wc) continue
      opts.push({
        value: `${p.plant_code}::${wc}`,
        label: `${wc} — ${pname} (${p.plant_code})`,
        plant_code: p.plant_code,
        warehouse_code: wc,
      })
    }
  }
  return opts
})

const fromPlantCode = computed(() => {
  const o = fromWarehouseOptions.value.find(x => x.value === fromKey.value)
  return o?.plant_code || ''
})

const fromWarehouseCode = computed(() => {
  const o = fromWarehouseOptions.value.find(x => x.value === fromKey.value)
  return o?.warehouse_code || ''
})

async function loadDestinations() {
  loadingDestinations.value = true
  try {
    const res = await get_destination_plants(fromPlantCode.value || '')
    destinationPlants.value = Array.isArray(res) ? res : []
  } catch {
    destinationPlants.value = []
    toast.error('Could not load destination plants')
  } finally {
    loadingDestinations.value = false
  }
}

watch(fromKey, () => {
  toPlantCode.value = ''
  loadDestinations()
})

function effectiveLineItems() {
  return lineItems.value.filter(row => {
    const hasItem = !!String(row.item_code || '').trim()
    const hasBatch = !!String(row.batch_number || '').trim()
    const hasQty = Number(row.quantity) > 0
    return hasItem || hasBatch || hasQty
  })
}

function validateClient() {
  if (!fromPlantCode.value || !fromWarehouseCode.value) {
    toast.error('Select a source warehouse')
    return false
  }
  if (!toPlantCode.value) {
    toast.error('Select a destination plant')
    return false
  }
  const rows = effectiveLineItems()
  if (!rows.length) {
    toast.error('Add at least one line item')
    return false
  }
  for (const row of rows) {
    if (!row.item_code || !String(row.batch_number || '').trim()) {
      toast.error('Each line needs an item and batch')
      return false
    }
    const qty = Number(row.quantity)
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error('Each line needs a quantity greater than zero')
      return false
    }
    const max = Number(row.available_quantity)
    if (Number.isFinite(max) && qty > max) {
      toast.error(
        max === 0
          ? `${row.item_code} is out of stock`
          : `Quantity cannot exceed available (${max}) for ${row.item_code}`
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
    const rows = effectiveLineItems()
    const payload = {
      from_plant: fromPlantCode.value,
      from_warehouse: fromWarehouseCode.value,
      to_plant: toPlantCode.value,
      remarks: remarks.value.trim(),
      line_items: rows.map(r => ({
        item_code: r.item_code,
        item_name: r.item_name || '',
        batch_number: r.batch_number,
        quantity: Number(r.quantity),
        uom: r.uom || '',
        available_quantity: Number(r.available_quantity) || 0,
      })),
    }
    const doc = await transfersStore.createTransfer(payload)
    const name = doc?.name
    if (!name) {
      toast.error('Created transfer but missing document name')
      return
    }
    toast.success('Transfer request created')
    router.push({ name: 'TransferDetail', params: { name } })
  } catch (e) {
    const msg = e?.messages?.[0] || e?.message || 'Could not create transfer'
    toast.error(typeof msg === 'string' ? msg : 'Could not create transfer')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadDestinations()
})
</script>
