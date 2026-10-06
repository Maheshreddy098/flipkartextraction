<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <label class="text-sm font-medium text-gray-700">Line items</label>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-lg border border-teal-300 bg-teal-50 px-3 py-1.5 text-xs font-medium text-teal-700 hover:bg-teal-100 disabled:opacity-50"
        :disabled="importing || !plantCode || !warehouseCode"
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
      class="rounded-lg border border-amber-200 bg-amber-50 p-3"
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
    <p class="text-xs text-gray-400">Supported: CSV, Excel (.xlsx). Columns: Item Code, Qty.</p>

    <p v-if="loadError" class="text-sm text-red-600">{{ loadError }}</p>
    <p v-else-if="loading" class="text-sm text-gray-500">Loading stock…</p>
    <p v-else-if="!plantCode || !warehouseCode" class="text-sm text-gray-500">
      Select source warehouse first.
    </p>

    <div class="overflow-visible rounded-lg border border-gray-200">
      <div
        class="-mx-1 sm:mx-0"
        :class="hasOpenSuggestions ? 'overflow-visible' : 'overflow-x-auto'"
      >
      <table class="min-w-[22rem] text-sm">
        <thead class="bg-gray-50 text-gray-700">
          <tr>
            <th class="text-left px-3 py-2 font-medium">Item Code</th>
            <th class="text-left px-3 py-2 font-medium">Item Name</th>
            <th class="text-left px-3 py-2 font-medium w-36">Qty</th>
            <th v-if="showUom" class="text-left px-3 py-2 font-medium w-16">UOM</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(line, idx) in modelValue" :key="idx" class="border-t border-gray-100">
            <td class="px-3 py-2 align-top relative">
              <div class="relative">
                <input
                  :value="line._item_query || itemDisplayValue(line.item_code)"
                  placeholder="Search item code or name"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800"
                  @input="onItemInput(idx, $event.target.value)"
                  @focus="openSuggestions(idx)"
                  @blur="onItemBlur(idx)"
                />
                <ul
                  v-if="showSuggestions(idx)"
                  class="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg"
                >
                  <li
                    v-for="it in itemSuggestions(line)"
                    :key="it.item_code"
                    class="cursor-pointer px-3 py-2 text-sm hover:bg-gray-50"
                    @mousedown.prevent="onItemPick(idx, it.item_code)"
                  >
                    <div class="font-medium text-gray-900">{{ it.item_code }}</div>
                    <div class="text-xs text-gray-600">{{ it.item_name || '—' }}</div>
                  </li>
                  <li
                    v-if="!itemSuggestions(line).length"
                    class="px-3 py-2 text-xs text-gray-500"
                  >
                    No items found
                  </li>
                </ul>
              </div>
            </td>
            <td class="px-3 py-2 align-top text-xs text-gray-700">
              <div class="rounded-lg border border-gray-300 bg-gray-50 px-2 py-2 min-h-[2.5rem]">
                {{ line.item_name || 'Item name will populate once code is selected' }}
              </div>
            </td>
            <td class="px-3 py-2 align-top">
              <input
                :value="line.quantity"
                type="number"
                min="0"
                step="any"
                class="w-full rounded px-2 py-1.5 text-xs bg-white"
                :class="isOverStock(line) ? 'border-2 border-red-500 text-red-700' : 'border border-gray-300 text-gray-800'"
                @input="onQty(idx, $event.target.value)"
              />
              <p
                v-if="line.item_code"
                class="mt-0.5 text-[10px]"
                :class="isOverStock(line) ? 'font-semibold text-red-600' : 'text-gray-400'"
              >
                avail: {{ fmtQty(line.available_quantity) }}
                <span v-if="batchLoading"> (loading…)</span>
                <span v-if="Number(line.available_quantity) === 0"> — out of stock</span>
                <span v-else-if="isOverStock(line)"> — exceeds available stock</span>
              </p>
            </td>
            <td v-if="showUom" class="px-3 py-2 text-gray-600 text-xs">{{ line.uom || '—' }}</td>
            <td class="px-2 py-2 align-top">
              <button type="button" class="text-red-600 text-xs hover:underline" @click="removeLine(idx)">
                ✕
              </button>
            </td>
          </tr>
          <tr v-if="!plantCode || !warehouseCode" class="border-t border-gray-100">
            <td :colspan="showUom ? 4 : 3" class="px-3 py-3 text-xs text-gray-500">
              Select source warehouse first.
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <div class="flex justify-end">
      <button
        type="button"
        class="text-sm font-medium text-teal-700 hover:text-teal-800 disabled:opacity-40"
        :disabled="loading"
        @click="addLine"
      >
        + Add line
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import { fetchBatchDetail, fetchInventory } from '@/core/api/inventory.js'

const props = defineProps({
  plantCode: { type: String, default: '' },
  warehouseCode: { type: String, default: '' },
  modelValue: { type: Array, default: () => [] },
  showUom: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])

const inventoryRows = ref([])
const itemOptions = ref([])
const batchRowsByItem = ref({})
const loading = ref(false)
const batchLoading = ref(false)
const loadError = ref('')
const activeSuggestIndex = ref(-1)
const fileInputRef = ref(null)
const importing = ref(false)
const importSummary = ref(null)
let suggestRequestToken = 0
let batchRequestToken = 0

const hasOpenSuggestions = computed(() => activeSuggestIndex.value >= 0)

const distinctItems = computed(() => {
  const m = new Map()
  for (const r of [...inventoryRows.value, ...itemOptions.value]) {
    const code = (r.item_code || '').trim()
    if (!code) continue
    if (!m.has(code)) {
      m.set(code, {
        item_code: code,
        item_name: r.item_name || '',
        uom: r.uom || '',
      })
    }
  }
  return [...m.values()].sort((a, b) => a.item_code.localeCompare(b.item_code))
})

const allItemOptions = computed(() => {
  return distinctItems.value
})

function itemOptionValue(it) {
  return `${it.item_code} — ${it.item_name || ''}`.trim()
}

function itemDisplayValue(itemCode) {
  const it = allItemOptions.value.find(x => x.item_code === itemCode)
  return it ? itemOptionValue(it) : itemCode || ''
}

function fmtQty(q) {
  const n = Number(q)
  return Number.isFinite(n) ? n : q
}

async function loadInventory() {
  loadError.value = ''
  inventoryRows.value = []
  itemOptions.value = []
  batchRowsByItem.value = {}
  if (!props.plantCode || !props.warehouseCode) return
  loading.value = true
  try {
    const payload = await fetchInventory(props.plantCode, props.warehouseCode, {
      paginate_by_item: 0,
      page: 1,
      page_size: 50000,
    })
    inventoryRows.value = payload.items || []
  } catch (e) {
    loadError.value = e?.messages?.[0] || e?.message || 'Could not load inventory'
  } finally {
    loading.value = false
  }
}

async function loadItemSuggestions(search) {
  const q = String(search || '').trim()
  if (!props.plantCode || !props.warehouseCode || !q) {
    itemOptions.value = []
    return
  }

  const token = ++suggestRequestToken
  try {
    const payload = await fetchInventory(props.plantCode, props.warehouseCode, {
      search: q,
      paginate_by_item: 1,
      page: 1,
      page_size: 25,
    })
    if (token !== suggestRequestToken) return
    itemOptions.value = payload.items || []
  } catch (e) {
    if (token !== suggestRequestToken) return
    itemOptions.value = []
    loadError.value = e?.messages?.[0] || e?.message || 'Could not load item suggestions'
  }
}

async function loadBatchesForItem(itemCode) {
  const code = String(itemCode || '').trim()
  if (!props.plantCode || !props.warehouseCode || !code) return []
  if (Array.isArray(batchRowsByItem.value[code])) return batchRowsByItem.value[code]

  const token = ++batchRequestToken
  batchLoading.value = true
  try {
    const payload = await fetchBatchDetail(props.plantCode, props.warehouseCode, code)
    const rows = (payload.batches || []).map((row) => ({ ...row, item_code: row.item_code || code }))
    if (token !== batchRequestToken) return rows
    batchRowsByItem.value = {
      ...batchRowsByItem.value,
      [code]: rows,
    }
    return rows
  } catch (e) {
    loadError.value = e?.messages?.[0] || e?.message || 'Could not load batches'
    return []
  } finally {
    if (token === batchRequestToken) batchLoading.value = false
  }
}

watch(
  () => [props.plantCode, props.warehouseCode],
  () => {
    loadInventory()
    emit('update:modelValue', [blankLine()])
  },
  { immediate: true },
)

function sync(lines) {
  emit('update:modelValue', lines)
}

function blankLine() {
  return {
    item_code: '',
    item_name: '',
    quantity: 0,
    uom: '',
    available_quantity: 0,
    _item_query: '',
  }
}

function addLine() {
  sync([
    ...props.modelValue,
    blankLine(),
  ])
}

function removeLine(idx) {
  if (props.modelValue.length <= 1) {
    sync([blankLine()])
    return
  }
  sync(props.modelValue.filter((_, i) => i !== idx))
}

async function onItemChange(idx, itemCode) {
  const it = allItemOptions.value.find(x => x.item_code === itemCode)
  const fetchedBatches = await loadBatchesForItem(itemCode)
  const firstBatch = fetchedBatches[0]
  const total = fetchedBatches.reduce((sum, b) => sum + (Number(b.quantity) || 0), 0)
  const lines = props.modelValue.map((line, i) => {
    if (i !== idx) return line
    return {
      ...line,
      item_code: itemCode,
      item_name: it?.item_name || '',
      quantity: 0,
      uom: firstBatch?.uom || it?.uom || '',
      available_quantity: total,
      _item_query: it ? itemOptionValue(it) : '',
    }
  })
  sync(lines)
}

function parseItemCode(raw) {
  const value = String(raw || '').trim()
  if (!value) return ''
  const marker = ' — '
  if (value.includes(marker)) return value.split(marker)[0].trim()
  const exact = allItemOptions.value.find(
    x => x.item_code.toLowerCase() === value.toLowerCase(),
  )
  if (exact) return exact.item_code
  const byNamePrefix = allItemOptions.value.find(
    x => (x.item_name || '').toLowerCase().startsWith(value.toLowerCase()),
  )
  return byNamePrefix?.item_code || ''
}

function onItemInput(idx, raw) {
  const value = String(raw || '')
  const lines = props.modelValue.map((line, i) => {
    if (i !== idx) return line
    return {
      ...line,
      item_code: '',
      item_name: '',
      quantity: 0,
      uom: '',
      available_quantity: 0,
      _item_query: value,
    }
  })
  sync(lines)
  activeSuggestIndex.value = idx
  loadItemSuggestions(value)
}

function openSuggestions(idx) {
  activeSuggestIndex.value = idx
  const value = props.modelValue[idx]?._item_query || props.modelValue[idx]?.item_code || ''
  loadItemSuggestions(value)
}

function onItemBlur(idx) {
  setTimeout(() => {
    if (activeSuggestIndex.value === idx) activeSuggestIndex.value = -1
    const line = props.modelValue[idx]
    if (!line) return
    const parsed = parseItemCode(line._item_query || '')
    if (parsed) onItemChange(idx, parsed)
  }, 120)
}

function showSuggestions(idx) {
  return activeSuggestIndex.value === idx
}

function itemSuggestions(line) {
  const q = String(line?._item_query || '').trim().toLowerCase()
  const source = allItemOptions.value
  if (!source.length) return []
  if (!q.length) return []
  const startsWith = []
  const contains = []
  for (const it of source) {
    const code = it.item_code.toLowerCase()
    const name = (it.item_name || '').toLowerCase()
    if (code.startsWith(q) || name.startsWith(q)) startsWith.push(it)
    else if (code.includes(q) || name.includes(q)) contains.push(it)
  }
  return [...startsWith, ...contains]
    .slice(0, 25)
}

function onItemPick(idx, itemCode) {
  onItemChange(idx, itemCode)
  activeSuggestIndex.value = -1
}

function isOverStock(line) {
  if (!line?.item_code) return false
  const available = Number(line.available_quantity)
  const qty = Number(line.quantity)
  if (!Number.isFinite(available) || !Number.isFinite(qty)) return false
  return qty > available
}

function onQty(idx, raw) {
  const q = parseFloat(raw)
  const lines = props.modelValue.map((line, i) => {
    if (i !== idx) return line
    const qty = Number.isFinite(q) ? q : 0
    return { ...line, quantity: qty }
  })
  sync(lines)
}

// ---------------------------------------------------------------------------
// Bulk file import
// ---------------------------------------------------------------------------

function triggerImport() {
  if (!props.plantCode || !props.warehouseCode) {
    toast.error('Select source warehouse before importing')
    return
  }
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

function matchItem(raw) {
  const term = String(raw || '').trim().toLowerCase()
  if (!term) return { match: null, multiple: false }
  const source = allItemOptions.value
  const exact = source.filter(
    (it) => it.item_code.toLowerCase() === term || (it.item_name || '').toLowerCase() === term,
  )
  if (exact.length) return { match: exact[0], multiple: exact.length > 1 }
  const contains = source.filter(
    (it) => it.item_code.toLowerCase().includes(term) || (it.item_name || '').toLowerCase().includes(term),
  )
  if (contains.length === 1) return { match: contains[0], multiple: false }
  if (contains.length > 1) return { match: null, multiple: true }
  return { match: null, multiple: false }
}

async function buildImportedLine(it, quantity) {
  const fetchedBatches = await loadBatchesForItem(it.item_code)
  const firstBatch = fetchedBatches[0]
  const total = fetchedBatches.reduce((sum, b) => sum + (Number(b.quantity) || 0), 0)
  return {
    item_code: it.item_code,
    item_name: it.item_name || '',
    quantity,
    uom: firstBatch?.uom || it.uom || '',
    available_quantity: total,
    _item_query: itemOptionValue(it),
  }
}

async function processImportRows(rows) {
  const failed = []
  const pending = []
  for (const row of rows) {
    const { match, multiple } = matchItem(row.raw)
    if (match) {
      pending.push(buildImportedLine(match, row.quantity))
    } else {
      failed.push({
        raw: row.raw,
        quantity: row.quantity,
        reason: multiple ? 'Multiple matches — add manually' : 'Item not found in this warehouse',
      })
    }
  }

  const added = await Promise.all(pending)

  if (added.length) {
    const current = props.modelValue
    const onlyBlank = current.length === 1 && !current[0].item_code && !current[0]._item_query
    sync(onlyBlank ? added : [...current, ...added])
    toast.success(`${added.length} item${added.length > 1 ? 's' : ''} imported`)
  }
  importSummary.value = { added: added.length, failed }
  if (failed.length) toast.warning(`${failed.length} item${failed.length > 1 ? 's' : ''} could not be matched`)
}
</script>
