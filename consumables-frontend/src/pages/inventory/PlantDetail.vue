<template>
  <div class="p-4 sm:p-6">
    <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0">
        <RouterLink to="/inventory" class="text-sm text-teal-700 hover:text-teal-800">← Back to Inventory</RouterLink>
        <h1 class="break-words text-xl font-bold text-gray-900 sm:text-2xl">Plant: {{ plantCode }}</h1>
        <p class="text-sm text-gray-500">Warehouses and inventory</p>
      </div>

      <div class="flex w-full gap-2 sm:w-auto sm:shrink-0">
        <button
          class="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 disabled:text-gray-500 sm:flex-none"
          @click="refreshCurrent"
        >
          Refresh
        </button>
        <button
          class="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white disabled:text-white disabled:opacity-50 sm:flex-none"
          @click="exportCsv"
          :disabled="!selectedWarehouse || exportLoading"
        >
          {{ exportLoading ? 'Exporting...' : 'Export CSV' }}
        </button>
      </div>
    </div>

    <p v-if="inventoryStore.error" class="text-red-600 mb-3">
      {{ inventoryStore.error }}
    </p>

    <div v-if="inventoryStore.warehousesLoading" class="rounded-xl border border-gray-200 bg-white p-4 text-blue-600">
      Loading warehouses...
    </div>

    <div v-else-if="warehouses.length === 1" class="mb-4">
      <p class="text-sm text-gray-500">Warehouse</p>
      <p class="text-base font-medium text-gray-900 mt-0.5">{{ warehouseCode(warehouses[0]) }}</p>
    </div>

    <div v-else-if="warehouses.length > 1" class="mb-4">
      <label class="block text-sm text-gray-700 mb-2">Warehouse</label>
      <select
        v-model="selectedWarehouse"
        class="w-full sm:w-80 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-800"
      >
        <option :value="SHOW_ALL_WAREHOUSES" class="text-gray-800 bg-white">Show all</option>
        <option
          v-for="wh in warehouses"
          :key="wh.warehouse_code || wh.name"
          :value="warehouseCode(wh)"
          class="text-gray-800 bg-white"
        >
          {{ warehouseCode(wh) }}
        </option>
      </select>
    </div>

    <div class="mb-4">
      <input
        v-model="searchInput"
        type="text"
        class="w-full max-w-xl border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-800 placeholder-gray-400"
        placeholder="Search by item code/name/batch"
      />
    </div>

    <div class="rounded-xl border border-gray-200 bg-white">
      <div class="p-4 border-b border-gray-100">
        <h2 class="font-semibold text-gray-900">
          {{
            warehouses.length === 1
              ? `Inventory — ${warehouseCode(warehouses[0])}`
              : selectedWarehouse && selectedWarehouse !== SHOW_ALL_WAREHOUSES
                ? `Warehouse: ${selectedWarehouse}`
                : 'Inventory (All Warehouses)'
          }}
        </h2>
      </div>

      <div v-if="inventoryStore.inventoryLoading" class="p-4 text-blue-600">Loading inventory...</div>
      <div v-else-if="groupedItems.length" class="overflow-x-auto">
        <table class="min-w-full text-sm text-gray-800">
          <thead class="bg-gray-50 text-gray-700">
            <tr>
              <th class="text-left px-4 py-2 font-medium">Item Code</th>
              <th class="text-left px-4 py-2 font-medium">Item Name</th>
              <th class="text-left px-4 py-2 font-medium">Batch</th>
              <th class="text-left px-4 py-2 font-medium">Warehouse Code</th>
              <th class="text-left px-4 py-2 font-medium">Total Qty</th>
              <th class="text-left px-4 py-2 font-medium">UOM</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="groupedRow in groupedItems"
              :key="groupedRowKey(groupedRow)"
              class="border-t border-gray-100 text-gray-800"
            >
              <td class="px-4 py-2 text-gray-800">{{ groupedRow.item_code || '-' }}</td>
              <td class="px-4 py-2 text-gray-800">{{ groupedRow.item_name || '-' }}</td>
              <td class="px-4 py-2 text-gray-800">
                <select
                  v-if="groupedRow.batches.length > 1"
                  v-model="batchSelectionByItem[itemSelectionKey(groupedRow)]"
                  class="w-full border border-gray-300 rounded px-2 py-1 text-sm bg-white text-gray-800"
                >
                  <option
                    v-for="batch in groupedRow.batches"
                    :key="rowKey(batch)"
                    :value="batchLabel(batch)"
                    class="text-gray-800 bg-white"
                  >
                    {{ batchOptionLabel(batch) }}
                  </option>
                </select>
                <span v-else>{{ batchOptionLabel(groupedRow.batches[0] || {}) }}</span>
              </td>
              <td class="px-4 py-2 text-gray-800">{{ groupedRow.warehouse_code || '-' }}</td>
              <td class="px-4 py-2 text-gray-800">
                {{ totalQty(groupedRow) }}
              </td>
              <td class="px-4 py-2 text-gray-800">{{ getSelectedBatch(groupedRow).uom || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="p-4 text-gray-500">
        No inventory found for selected warehouse.
      </div>

      <div class="p-4 border-t border-gray-100 flex items-center justify-between text-sm text-gray-800">
        <button
          type="button"
          class="px-3 py-1.5 rounded border border-gray-300 text-gray-800 bg-white disabled:opacity-50 disabled:text-gray-500"
          :disabled="page <= 1 || inventoryStore.inventoryLoading"
          @click="page -= 1"
        >
          &lt; Prev
        </button>
        <span>Page {{ page }} of {{ totalPages }} • Items (distinct): {{ footerDistinctTotal }}</span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded border border-gray-300 text-gray-800 bg-white disabled:opacity-50 disabled:text-gray-500"
            :disabled="page >= totalPages || inventoryStore.inventoryLoading"
            @click="page += 1"
          >
            Next &gt;
          </button>
          <select
            v-model.number="pageSize"
            class="border border-gray-300 rounded px-2 py-1.5 bg-white text-gray-800"
            title="Items per page"
          >
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="30">30</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useInventoryStore } from '@/stores/inventory'

const route = useRoute()
const inventoryStore = useInventoryStore()
const pageSize = ref(10)
const SHOW_ALL_WAREHOUSES = '__all__'

const plantCode = computed(() => {
  const value = route.params.plant_code
  return typeof value === 'string' ? value : ''
})

const warehouses = computed(() => {
  return inventoryStore.warehouses[plantCode.value] || []
})

const selectedWarehouse = ref('')
const page = ref(1)
const searchInput = ref('')
const search = ref('')
const exportLoading = ref(false)
const batchSelectionByItem = ref({})
const allWarehouseInventory = ref({ items: [], total: 0, total_distinct_items: 0, page: 1, page_size: pageSize.value })
let searchTimer

const inventoryKey = computed(() => {
  if (!plantCode.value || !selectedWarehouse.value) return ''
  if (selectedWarehouse.value === SHOW_ALL_WAREHOUSES) return `${plantCode.value}:${SHOW_ALL_WAREHOUSES}`
  return `${plantCode.value}:${selectedWarehouse.value}`
})

const currentInventory = computed(() => {
  if (!inventoryKey.value) return { items: [], total: 0, page: page.value, page_size: pageSize.value }
  if (selectedWarehouse.value === SHOW_ALL_WAREHOUSES) return allWarehouseInventory.value
  return inventoryStore.inventory[inventoryKey.value] || { items: [], total: 0, page: page.value, page_size: pageSize.value }
})

const currentItems = computed(() => currentInventory.value.items || [])
const groupedItems = computed(() => {
  const groups = {}
  for (const row of currentItems.value) {
    const itemCode = row.item_code || ''
    const itemName = row.item_name || ''
    const warehouseCodeValue = row.warehouse_code || ''
    const key = `${warehouseCodeValue}::${itemCode}::${itemName}`
    if (!groups[key]) {
      groups[key] = {
        warehouse_code: warehouseCodeValue,
        item_code: itemCode,
        item_name: itemName,
        batches: []
      }
    }
    groups[key].batches.push(row)
  }
  return Object.values(groups)
})
const totalPages = computed(() => {
  const total = Number(currentInventory.value.total || 0)
  return Math.max(1, Math.ceil(total / pageSize.value))
})

const footerDistinctTotal = computed(() => {
  const distinct = Number(currentInventory.value.total_distinct_items || 0)
  if (distinct) return distinct
  return groupedItems.value.length
})

function warehouseCode(wh) {
  return wh.warehouse_code || wh.name || ''
}

/** Paginate flat batch rows by distinct (warehouse, item_code, item_name); matches server grouping. */
function sliceInventoryRowsByItemPage(allRows, page, pageSize) {
  const orderKeys = []
  const groups = new Map()
  for (const row of allRows) {
    const wh = String(row.warehouse_code || '').trim()
    const ic = String(row.item_code || '').trim()
    const nm = String(row.item_name || '').trim()
    const key = `${wh}::${ic}::${nm}`
    if (!groups.has(key)) {
      orderKeys.push(key)
      groups.set(key, [])
    }
    groups.get(key).push(row)
  }
  const start = (page - 1) * pageSize
  const pageKeys = orderKeys.slice(start, start + pageSize)
  const items = pageKeys.flatMap(k => groups.get(k) || [])
  return { items, total: orderKeys.length }
}

function rowKey(row) {
  return `${row.item_code || ''}:${row.batch_number || row.batch || ''}:${row.expiry_date || ''}`
}

function groupedRowKey(groupedRow) {
  return `${groupedRow.item_code || ''}:${groupedRow.item_name || ''}`
}

function batchLabel(batch) {
  return batch.batch_number || batch.batch || '-'
}

function batchQty(batch) {
  return Number(batch.quantity || batch.qty || 0)
}

function batchOptionLabel(batch) {
  return `${batchLabel(batch)} (Qty: ${batchQty(batch)})`
}

function totalQty(groupedRow) {
  return groupedRow.batches.reduce((sum, batch) => sum + batchQty(batch), 0)
}

function itemSelectionKey(groupedRow) {
  return `${groupedRow.item_code || ''}::${groupedRow.item_name || ''}`
}

function getSelectedBatch(groupedRow) {
  const key = itemSelectionKey(groupedRow)
  const selectedLabel = batchSelectionByItem.value[key]
  if (selectedLabel) {
    const selected = groupedRow.batches.find(b => batchLabel(b) === selectedLabel)
    if (selected) return selected
  }

  const fallback = groupedRow.batches[0] || {}
  batchSelectionByItem.value[key] = batchLabel(fallback)
  return fallback
}

async function loadWarehouses() {
  if (!plantCode.value) return
  try {
    const result = await inventoryStore.fetchWarehouses(plantCode.value)
    if (result.length === 1) {
      selectedWarehouse.value = warehouseCode(result[0])
    } else if (result.length > 1) {
      const codes = new Set(result.map(warehouseCode).filter(Boolean))
      const current = selectedWarehouse.value
      if (
        !current ||
        (current !== SHOW_ALL_WAREHOUSES && !codes.has(current))
      ) {
        selectedWarehouse.value = SHOW_ALL_WAREHOUSES
      }
    } else {
      selectedWarehouse.value = ''
    }
  } catch {
    // Error state is already populated by the store.
  }
}

async function loadInventory({ force = false } = {}) {
  if (!plantCode.value || !selectedWarehouse.value) return
  try {
    if (selectedWarehouse.value === SHOW_ALL_WAREHOUSES) {
      const allRows = []
      for (const wh of warehouses.value) {
        const code = warehouseCode(wh)
        if (!code) continue
        const data = await inventoryStore.fetchInventory(
          plantCode.value,
          code,
          {
            search: search.value,
            page: 1,
            page_size: 1,
            paginate_by_item: false,
            force
          }
        )
        allRows.push(...(data?.items || []))
      }

      const { items, total } = sliceInventoryRowsByItemPage(
        allRows,
        page.value,
        pageSize.value
      )
      allWarehouseInventory.value = {
        items,
        total,
        total_distinct_items: total,
        page: page.value,
        page_size: pageSize.value
      }
      return
    }

    await inventoryStore.fetchInventory(
      plantCode.value,
      selectedWarehouse.value,
      {
        search: search.value,
        page: page.value,
        page_size: pageSize.value,
        paginate_by_item: true,
        force
      }
    )
  } catch {
    // Error state is already populated by the store.
  }
}

async function refreshCurrent() {
  if (!plantCode.value) return
  inventoryStore.invalidateCache(plantCode.value)
  await loadWarehouses()
  await loadInventory({ force: true })
}

async function exportCsv() {
  if (!plantCode.value || !selectedWarehouse.value) return
  exportLoading.value = true
  let allItems = []
  try {
    if (selectedWarehouse.value === SHOW_ALL_WAREHOUSES) {
      for (const wh of warehouses.value) {
        const code = warehouseCode(wh)
        if (!code) continue
        const data = await inventoryStore.fetchInventory(
          plantCode.value,
          code,
          {
            search: search.value,
            page: 1,
            page_size: 1,
            paginate_by_item: false,
            force: true
          }
        )
        allItems = allItems.concat(data?.items || [])
      }
      if (!allItems.length) return
    } else {
      const data = await inventoryStore.fetchInventory(
        plantCode.value,
        selectedWarehouse.value,
        {
          search: search.value,
          page: 1,
          page_size: 1,
          paginate_by_item: false,
          force: true
        }
      )
      allItems = data?.items || []
    }
  } finally {
    exportLoading.value = false
  }

  if (!allItems.length) return

  const header = ['Item Code', 'Item Name', 'Batch Number', 'Warehouse Code', 'Quantity', 'UOM']
  const rows = allItems.map(row => ([
    row.item_code || '',
    row.item_name || '',
    row.batch_number || row.batch || '',
    row.warehouse_code || '',
    row.quantity || row.qty || 0,
    row.uom || ''
  ]))

  const csv = [header, ...rows]
    .map(cols => cols.map(col => `"${String(col).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `${plantCode.value}_${selectedWarehouse.value}_inventory.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

watch(searchInput, value => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    search.value = value
    page.value = 1
  }, 300)
})

watch(selectedWarehouse, () => {
  page.value = 1
  loadInventory()
})

watch([page, search], () => {
  loadInventory()
})

watch(pageSize, () => {
  page.value = 1
  loadInventory({ force: true })
})

onMounted(loadWarehouses)
watch(plantCode, loadWarehouses)
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>
