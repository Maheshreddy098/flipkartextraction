<template>
  <div class="max-w-5xl p-4 sm:p-6">
    <RouterLink
      to="/material-requests"
      class="mb-4 inline-block text-sm text-teal-700 hover:text-teal-800"
    >
      ← Back to material requests
    </RouterLink>

    <h1 class="mb-4 text-xl font-bold text-gray-900 sm:mb-6 sm:text-2xl">New Material Request</h1>

    <form class="space-y-6" @submit.prevent="submit">
      <div class="grid gap-4 md:grid-cols-2">
        <div>
          <label class="mb-1 block text-sm font-medium text-gray-700">Plant</label>
          <select
            v-if="authStore.isSuperAdmin"
            v-model="plantCode"
            required
            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
          >
            <option value="">Select plant</option>
            <option v-for="p in authStore.plants" :key="p.plant_code" :value="p.plant_code">
              {{ p.plant_code }} — {{ p.plant_name }}
            </option>
          </select>
          <input
            v-else
            :value="defaultPlantLabel"
            type="text"
            readonly
            class="w-full cursor-not-allowed rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-gray-700">Urgency</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="option in urgencyOptions"
              :key="option"
              type="button"
              class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm"
              :class="
                urgency === option
                  ? 'border-teal-600 bg-teal-600 text-white'
                  : 'border-gray-300 bg-white text-gray-700 hover:border-teal-400'
              "
              @click="urgency = option"
            >
              {{ option }}
            </button>
          </div>
        </div>
      </div>

      <div class="rounded-lg border border-gray-200 bg-white">
        <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <h2 class="text-sm font-semibold text-gray-800">Items</h2>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg border border-teal-300 bg-teal-50 px-3 py-1.5 text-xs font-medium text-teal-700 hover:bg-teal-100 disabled:opacity-50"
            :disabled="importing"
            @click="triggerImport"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a2 2 0 002 2h12a2 2 0 002-2v-1M8 12l4 4 4-4M12 3v13" />
            </svg>
            {{ importing ? 'Importing…' : 'Import File' }}
          </button>
          <input
            ref="fileInputRef"
            type="file"
            accept=".csv,.xlsx,.xls,.txt"
            class="hidden"
            @change="onFileChange"
          />
        </div>

        <div
          v-if="importSummary?.failed?.length"
          class="mx-3 mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3"
        >
          <div class="flex items-start justify-between">
            <p class="text-xs font-semibold text-amber-800">
              {{ importSummary.failed.length }} item{{ importSummary.failed.length > 1 ? 's' : '' }} not matched — add manually or fix file and re-import:
            </p>
            <button type="button" class="ml-2 text-amber-500 hover:text-amber-700" @click="importSummary = null">✕</button>
          </div>
          <ul class="mt-1.5 space-y-0.5">
            <li v-for="f in importSummary.failed" :key="f.raw" class="text-xs text-amber-700">
              <span class="font-medium">{{ f.raw }}</span> (qty: {{ f.quantity }}) — {{ f.reason }}
            </li>
          </ul>
        </div>

        <div class="space-y-3 p-3 sm:p-4">
          <div
            v-for="(row, idx) in lineItems"
            :key="`mr-row-${idx}`"
            class="rounded-lg border border-gray-200 p-3"
          >
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-12">
              <div class="sm:col-span-6">
                <label class="mb-1 block text-xs font-medium text-gray-600">Item</label>
                <div class="relative">
                  <input
                    :value="row._item_query || row.item_code"
                    type="text"
                    class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
                    placeholder="Search item code or name"
                    @input="onItemInput(idx, $event.target.value)"
                    @focus="openSuggestions(idx)"
                    @blur="onItemBlur(idx)"
                  />
                  <ul
                    v-if="showSuggestions(idx)"
                    class="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg"
                  >
                    <li
                      v-for="item in itemSuggestions(row)"
                      :key="item.item_code"
                      class="cursor-pointer px-3 py-2 text-sm hover:bg-gray-50"
                      @mousedown.prevent="onItemPick(idx, item)"
                    >
                      <div class="font-medium text-gray-900">{{ item.item_code }}</div>
                      <div class="text-xs text-gray-600">{{ item.item_name || '—' }}</div>
                    </li>
                    <li
                      v-if="!itemSuggestions(row).length"
                      class="px-3 py-2 text-xs text-gray-500"
                    >
                      {{ itemSearchError || 'No items found' }}
                    </li>
                  </ul>
                </div>
              </div>

              <div class="sm:col-span-2">
                <label class="mb-1 block text-xs font-medium text-gray-600">Qty</label>
                <input
                  :value="row.quantity"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
                  @input="onQtyInput(idx, $event.target.value)"
                />
              </div>

              <div class="sm:col-span-3">
                <label class="mb-1 block text-xs font-medium text-gray-600">UOM</label>
                <input
                  :value="row.uom"
                  type="text"
                  class="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700"
                  readonly
                />
              </div>

              <div class="sm:col-span-1 flex items-end">
                <button
                  type="button"
                  class="w-full rounded-lg border border-red-200 px-2.5 py-2 text-xs font-medium text-red-700 hover:bg-red-50"
                  @click="removeLine(idx)"
                >
                  Remove
                </button>
              </div>
            </div>
          </div>

          <div class="flex items-center justify-between">
            <p class="text-xs text-gray-400">Supported: CSV, Excel (.xlsx). Columns: Item Code, Item Name, Qty.</p>
            <button
              type="button"
              class="text-sm font-medium text-teal-700 hover:text-teal-800"
              @click="addLine"
            >
              + Add Item
            </button>
          </div>
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-gray-700">Remarks</label>
        <textarea
          v-model="remarks"
          rows="3"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
          placeholder="Add any remarks or notes for this request (optional)"
        />
      </div>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:gap-3">
        <button
          type="submit"
          class="w-full justify-center rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:py-2"
          :disabled="submitting || raisingPo"
        >
          {{ submitting ? 'Sending…' : 'Send Request' }}
        </button>
        <button
          type="button"
          class="w-full justify-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:py-2"
          :disabled="submitting || raisingPo"
          @click="raisePo"
        >
          {{ raisingPo ? 'Raising PO…' : 'Raise PO' }}
        </button>
        <RouterLink
          to="/material-requests"
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
import { toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { searchItemsForRequest } from '@/core/api/inventory.js'
import { raise_po_from_request } from '@/core/api/material_requests.js'
import { useAuthStore } from '@/stores/auth.js'
import { useMaterialRequestsStore } from '@/stores/material_requests.js'

const router = useRouter()
const authStore = useAuthStore()
const materialRequestsStore = useMaterialRequestsStore()

const plantCode = ref('')
const warehouseCode = ref('')
const urgency = ref('Medium')
const remarks = ref('')
const lineItems = ref([blankLine()])
const submitting = ref(false)
const raisingPo = ref(false)

const itemOptions = ref([])
const itemSearchError = ref('')
const activeSuggestIndex = ref(-1)
const urgencyOptions = ['Low', 'Medium', 'High', 'Critical']

const fileInputRef = ref(null)
const importing = ref(false)
const importSummary = ref(null)

let suggestToken = 0

function blankLine() {
  return {
    item_code: '',
    item_name: '',
    quantity: '',
    uom: '',
    _item_query: '',
    create_new_item: false,
  }
}

const defaultPlant = computed(() => {
  if (authStore.isSuperAdmin) return null
  return authStore.plants?.[0] || null
})

const defaultPlantLabel = computed(() => {
  if (!defaultPlant.value) return 'No plant assigned'
  return `${defaultPlant.value.plant_code} — ${defaultPlant.value.plant_name || defaultPlant.value.plant_code}`
})

watch(
  () => authStore.plants,
  (plants) => {
    if (authStore.isSuperAdmin) {
      if (!plantCode.value && plants?.length) plantCode.value = plants[0].plant_code
      return
    }
    plantCode.value = plants?.[0]?.plant_code || ''
  },
  { immediate: true },
)

watch(plantCode, () => {
  warehouseCode.value =
    authStore.plants?.find((p) => p.plant_code === plantCode.value)?.warehouses?.[0]?.warehouse_code || ''
  resetItems()
})

function resetItems() {
  itemOptions.value = []
  itemSearchError.value = ''
  activeSuggestIndex.value = -1
  lineItems.value = [blankLine()]
}

function addLine() {
  lineItems.value = [...lineItems.value, blankLine()]
}

function removeLine(idx) {
  if (lineItems.value.length <= 1) {
    lineItems.value = [blankLine()]
    return
  }
  lineItems.value = lineItems.value.filter((_, i) => i !== idx)
}

function normalizeItemOptions(rows) {
  const map = new Map()
  for (const row of rows || []) {
    const item_code = String(row.item_code || '').trim()
    if (!item_code || map.has(item_code)) continue
    map.set(item_code, {
      item_code,
      item_name: row.item_name || '',
      uom: row.uom || row.stock_uom || '',
    })
  }
  return [...map.values()]
}

async function loadItemSuggestions(search = '') {
  if (!plantCode.value || search.length < 2) {
    itemOptions.value = []
    itemSearchError.value = ''
    return
  }
  const token = ++suggestToken
  try {
    // Item master search, not warehouse stock — a Material Request is a request
    // for items the store doesn't have, so zero-stock items must still show up.
    const res = await searchItemsForRequest(search)
    if (token !== suggestToken) return
    const items = Array.isArray(res?.items) ? res.items : []
    itemOptions.value = normalizeItemOptions(items)
    itemSearchError.value = ''
  } catch {
    if (token !== suggestToken) return
    itemOptions.value = []
    itemSearchError.value = 'Item search failed (SAP connection/schema issue)'
  }
}

function itemSuggestions(row) {
  const q = String(row?._item_query || '').trim().toLowerCase()
  if (q.length < 2) return []
  return itemOptions.value
    .filter(
      (it) =>
        it.item_code.toLowerCase().includes(q) ||
        (it.item_name || '').toLowerCase().includes(q),
    )
    .slice(0, 20)
}

function showSuggestions(idx) {
  return activeSuggestIndex.value === idx
}

function openSuggestions(idx) {
  activeSuggestIndex.value = idx
  const q = String(lineItems.value[idx]?._item_query || '').trim()
  if (q.length >= 2) loadItemSuggestions(q)
}

function onItemInput(idx, raw) {
  const value = String(raw || '')
  const next = [...lineItems.value]
  next[idx] = {
    ...next[idx],
    _item_query: value,
    item_code: next[idx].create_new_item ? value.trim() : '',
    item_name: next[idx].create_new_item ? value.trim() : '',
    uom: next[idx].create_new_item ? next[idx].uom : '',
  }
  lineItems.value = next
  activeSuggestIndex.value = idx
  if (!next[idx].create_new_item && value.trim().length >= 2) loadItemSuggestions(value.trim())
}

function onItemPick(idx, item) {
  const next = [...lineItems.value]
  next[idx] = {
    ...next[idx],
    item_code: item.item_code,
    item_name: item.item_name || '',
    uom: item.uom || '',
    _item_query: `${item.item_code} — ${item.item_name || ''}`.trim(),
  }
  lineItems.value = next
  activeSuggestIndex.value = -1
}

function parseItemQuery(query) {
  const text = String(query || '').trim()
  if (!text) return null
  const lowered = text.toLowerCase()
  return (
    itemOptions.value.find(
      (x) =>
        x.item_code.toLowerCase() === lowered ||
        `${x.item_code} — ${x.item_name || ''}`.toLowerCase() === lowered,
    ) ||
    itemOptions.value.find((x) => x.item_code.toLowerCase().startsWith(lowered)) ||
    null
  )
}

function onItemBlur(idx) {
  setTimeout(() => {
    const row = lineItems.value[idx]
    if (!row) return
    if (row.create_new_item) {
      const text = String(row._item_query || '').trim()
      lineItems.value[idx] = { ...row, item_code: text, item_name: row.item_name || text }
      if (activeSuggestIndex.value === idx) activeSuggestIndex.value = -1
      return
    }
    const parsed = parseItemQuery(row._item_query)
    if (parsed) onItemPick(idx, parsed)
    if (activeSuggestIndex.value === idx) activeSuggestIndex.value = -1
  }, 120)
}

function onToggleNewItem(idx, checked) {
  const row = lineItems.value[idx] || blankLine()
  const text = String(row._item_query || row.item_code || '').trim()
  const next = [...lineItems.value]
  next[idx] = {
    ...row,
    create_new_item: checked,
    item_code: checked ? text : '',
    item_name: checked ? (row.item_name || text) : '',
    uom: checked ? row.uom : '',
  }
  lineItems.value = next
}

function onQtyInput(idx, raw) {
  const next = [...lineItems.value]
  next[idx] = { ...next[idx], quantity: raw }
  lineItems.value = next
}

// ---------------------------------------------------------------------------
// File import
// ---------------------------------------------------------------------------

function triggerImport() {
  if (!plantCode.value) { toast.error('Select a plant before importing'); return }
  fileInputRef.value?.click()
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  importing.value = true
  importSummary.value = null
  try {
    const ext = file.name.split('.').pop().toLowerCase()
    let rows = []
    if (ext === 'csv' || ext === 'txt') {
      rows = parseCSVText(await file.text())
    } else if (ext === 'xlsx' || ext === 'xls') {
      rows = await parseXLSXBuffer(await file.arrayBuffer())
    } else {
      toast.error('Unsupported format. Use CSV or Excel (.xlsx/.xls)')
      return
    }
    if (!rows.length) {
      toast.error('No rows with valid quantities found. Fill in the Qty column and re-import.')
      return
    }
    await processImportRows(rows)
  } catch (e) {
    toast.error('Failed to read file: ' + (e?.message || 'Unknown error'))
  } finally {
    importing.value = false
  }
}

function parseCSVText(text) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  let headerRowIdx = -1, itemCol = 0, qtyCol = -1
  for (let i = 0; i < Math.min(lines.length, 5); i++) {
    const parts = lines[i].includes('\t') ? lines[i].split('\t') : lines[i].split(',')
    for (let c = 0; c < parts.length; c++) {
      const cell = parts[c].replace(/^["']|["']$/g, '').toLowerCase().trim()
      if (/\b(qty|quantity|required|req\.?\s*qty)\b/.test(cell)) { headerRowIdx = i; qtyCol = c }
      if (/\b(item[\s_]*(no|code|number|#))\b/.test(cell)) itemCol = c
    }
    if (qtyCol !== -1) break
  }
  const rows = []
  const startIdx = headerRowIdx !== -1 ? headerRowIdx + 1 : 0
  for (let i = startIdx; i < lines.length; i++) {
    const parts = lines[i].includes('\t') ? lines[i].split('\t') : lines[i].split(',')
    const raw = (parts[itemCol] || '').replace(/^["']|["']$/g, '').trim()
    if (!raw) continue
    const qtyRaw = qtyCol !== -1 ? parts[qtyCol] : parts[1]
    const qty = parseFloat((qtyRaw || '').replace(/^["']|["']$/g, '').trim())
    if (isNaN(qty) || qty <= 0) continue
    rows.push({ raw, quantity: qty })
  }
  return rows
}

async function parseXLSXBuffer(buffer) {
  const XLSX = await import('xlsx')
  const wb = XLSX.read(buffer, { type: 'array' })
  const ws = wb.Sheets[wb.SheetNames[0]]
  const data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })

  let headerRowIdx = -1, itemCol = 0, qtyCol = -1
  for (let i = 0; i < Math.min(data.length, 10); i++) {
    const row = data[i]
    for (let c = 0; c < row.length; c++) {
      const cell = String(row[c] || '').toLowerCase().trim()
      if (/\b(qty|quantity|required|req\.?\s*qty)\b/.test(cell)) { headerRowIdx = i; qtyCol = c }
      if (/\b(item[\s_]*(no|code|number|#))\b/.test(cell)) itemCol = c
    }
    if (qtyCol !== -1) break
  }

  const rows = []
  if (qtyCol !== -1) {
    for (let i = headerRowIdx + 1; i < data.length; i++) {
      const row = data[i]
      const raw = String(row[itemCol] || '').trim()
      if (!raw) continue
      const qtyVal = row[qtyCol]
      const qty = typeof qtyVal === 'number' ? qtyVal : parseFloat(String(qtyVal || '').trim())
      if (isNaN(qty) || qty <= 0) continue
      rows.push({ raw, quantity: qty })
    }
  } else {
    for (const row of data) {
      const raw = String(row[0] || '').trim()
      if (!raw) continue
      let qty = NaN
      for (let c = 1; c < row.length; c++) {
        const v = row[c]
        if (typeof v === 'number' && v > 0) { qty = v; break }
        const s = String(v || '').trim()
        if (/^\d+(\.\d+)?$/.test(s)) { qty = parseFloat(s); break }
      }
      if (isNaN(qty) || qty <= 0) continue
      rows.push({ raw, quantity: qty })
    }
  }
  return rows
}

async function processImportRows(rows) {
  const uniqueTerms = [...new Set(rows.map((r) => r.raw))]
  const searchResults = {}
  await Promise.all(
    uniqueTerms.map(async (term) => {
      try {
        const res = await searchItemsForRequest(term)
        const items = Array.isArray(res?.items) ? res.items : []
        searchResults[term] = items.map((it) => ({
          item_code: String(it.item_code || '').trim(),
          item_name: it.item_name || '',
          uom: it.uom || it.stock_uom || '',
        })).filter((it) => it.item_code)
      } catch {
        searchResults[term] = []
      }
    }),
  )

  const added = []
  const failed = []
  for (const row of rows) {
    const candidates = searchResults[row.raw] || []
    const term = row.raw.toLowerCase()
    const match =
      candidates.find((c) => c.item_code.toLowerCase() === term) ||
      candidates.find((c) => (c.item_name || '').toLowerCase() === term) ||
      (candidates.length === 1 ? candidates[0] : null)
    if (match) {
      added.push({
        item_code: match.item_code,
        item_name: match.item_name || '',
        quantity: row.quantity,
        uom: match.uom || '',
        _item_query: `${match.item_code} — ${match.item_name || ''}`.trim(),
        create_new_item: false,
      })
    } else {
      failed.push({ raw: row.raw, quantity: row.quantity, reason: candidates.length > 1 ? 'Multiple matches — add manually' : 'Item not found in SAP' })
    }
  }

  if (added.length) {
    const current = lineItems.value
    const onlyBlank = current.length === 1 && !current[0].item_code && !current[0]._item_query
    lineItems.value = onlyBlank ? added : [...current, ...added]
    toast.success(`${added.length} item${added.length > 1 ? 's' : ''} imported`)
  }
  importSummary.value = { added: added.length, failed }
  if (failed.length) toast.warning(`${failed.length} item${failed.length > 1 ? 's' : ''} could not be matched`)
}

// ---------------------------------------------------------------------------
// Raise PO
// ---------------------------------------------------------------------------

async function raisePo() {
  if (!plantCode.value) { toast.error('Select a plant'); return }
  const rows = effectiveRows()
  if (!rows.length) { toast.error('Add at least one valid line item'); return }
  raisingPo.value = true
  try {
    const res = await raise_po_from_request({
      plant_code: plantCode.value,
      remarks: remarks.value.trim(),
      line_items: rows.map((row) => ({
        item_code: String(row.item_code || row._item_query || '').trim(),
        item_name: row.item_name || '',
        quantity: Number(row.quantity),
        uom: row.uom || '',
      })),
    })
    const name = res?.message?.name || res?.name
    toast.success(`PO request ${name || ''} raised — Procurement Manager notified`)
    router.push('/material-requests')
  } catch (e) {
    const msg = e?.messages?.[0] || e?.message || 'Could not raise PO'
    toast.error(typeof msg === 'string' ? msg : 'Could not raise PO')
  } finally {
    raisingPo.value = false
  }
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

function effectiveRows() {
  return lineItems.value.filter((row) => {
    const code = String(row.item_code || row._item_query || '').trim()
    return !!code && Number(row.quantity) > 0
  })
}

function validateClient() {
  if (!plantCode.value) { toast.error('Select a plant'); return false }
  if (!urgency.value) { toast.error('Select urgency'); return false }
  if (!effectiveRows().length) { toast.error('Add at least one valid line item'); return false }
  return true
}

async function submit() {
  if (!validateClient()) return
  submitting.value = true
  try {
    const payload = {
      plant_code: plantCode.value || undefined,
      urgency: urgency.value,
      remarks: remarks.value.trim(),
      reason: remarks.value.trim(),
      line_items: effectiveRows().map((row) => ({
        item_code: String(row.item_code || row._item_query || '').trim(),
        item_name: row.item_name || '',
        quantity: Number(row.quantity),
        uom: row.uom || '',
        create_new_item: !!row.create_new_item,
      })),
    }
    const doc = await materialRequestsStore.create(payload)
    const name = doc?.name
    if (!name) { toast.error('Created request but missing document name'); return }
    await materialRequestsStore.submit(name)
    toast.success('Your request has been sent')
    router.push({ name: 'MaterialRequestDetail', params: { name } })
  } catch (e) {
    const msg = e?.messages?.[0] || e?.message || 'Could not create material request'
    toast.error(typeof msg === 'string' ? msg : 'Could not create material request')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (!plantCode.value && authStore.plants?.length) {
    plantCode.value = authStore.plants[0].plant_code
  }
})
</script>
