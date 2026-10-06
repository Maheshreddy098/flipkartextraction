<template>
  <div class="rounded-xl bg-neutral-100 text-neutral-900 p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold">Failures</h3>
      <div class="flex items-center gap-2">
        <select v-model="stage" @change="reload" class="text-sm border rounded px-2 py-1">
          <option value="all">All stages</option>
          <option value="orders">Orders</option>
          <option value="credit_notes">Credit Notes</option>
          <option value="inventory">Inventory</option>
        </select>
        <button class="text-sm px-3 py-1 border rounded hover:bg-neutral-200" @click="reload" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div v-if="rows.length === 0" class="text-sm text-neutral-500 py-6 text-center">
      No failures in this view.
    </div>

    <div v-else class="overflow-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-neutral-500 border-b">
            <th class="py-2">Stage</th>
            <th>Record</th>
            <th>Status</th>
            <th>Last Error</th>
            <th>Modified</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.doctype + row.name" class="border-b border-neutral-200">
            <td class="py-2">{{ row.stage }}</td>
            <td class="font-mono text-xs">{{ row.external_id || row.name }}</td>
            <td>
              <span class="px-2 py-0.5 rounded text-xs"
                :class="row.status === 'dead' || row.status === 'Failed' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'">
                {{ row.status }}
              </span>
            </td>
            <td class="text-xs text-neutral-600 max-w-md truncate" :title="row.last_error">{{ row.last_error || '-' }}</td>
            <td class="text-xs text-neutral-500">{{ shortTime(row.modified) }}</td>
            <td>
              <div class="flex gap-1">
                <button
                  class="text-xs px-2 py-1 rounded border border-neutral-300 hover:bg-neutral-200 disabled:opacity-50"
                  :disabled="busyKey === rowKey(row)"
                  @click="retry(row, 'queue')">
                  Queue Retry
                </button>
                <button
                  class="text-xs px-2 py-1 rounded bg-neutral-900 text-white hover:bg-neutral-800 disabled:opacity-50"
                  :disabled="busyKey === rowKey(row)"
                  @click="retry(row, 'now')">
                  Run Now
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 flex items-center justify-between text-xs text-neutral-500">
      <span>Page {{ page }}</span>
      <div class="flex gap-2">
        <button class="px-2 py-1 border rounded" :disabled="page === 1 || loading" @click="prev">Prev</button>
        <button class="px-2 py-1 border rounded" :disabled="rows.length < pageSize || loading" @click="next">Next</button>
      </div>
    </div>

    <pre v-if="lastResult" class="mt-3 text-xs bg-neutral-900 text-emerald-300 rounded p-3 max-h-40 overflow-auto">{{ lastResult }}</pre>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  callMethod: { type: Function, required: true },
})

const API_BASE = 'khanal_tech_integrations.unicommerce.api.ops'

const stage = ref('all')
const page = ref(1)
const pageSize = 25
const rows = ref([])
const loading = ref(false)
const busyKey = ref('')
const lastResult = ref('')

function rowKey(r) {
  return `${r.doctype}::${r.name}`
}

function shortTime(ts) {
  if (!ts) return '-'
  return String(ts).replace('T', ' ').slice(0, 16)
}

async function reload() {
  loading.value = true
  try {
    const data = await props.callMethod(`${API_BASE}.ops_failures`, {
      stage: stage.value,
      page: page.value,
      page_size: pageSize,
    })
    rows.value = data?.rows || []
  } catch (e) {
    lastResult.value = `Load error: ${e?.message || e}`
  } finally {
    loading.value = false
  }
}

async function retry(row, mode) {
  busyKey.value = rowKey(row)
  try {
    const result = await props.callMethod(`${API_BASE}.ops_retry`, {
      doctype: row.doctype,
      name: row.name,
      mode,
    })
    lastResult.value = `[${new Date().toLocaleString()}] retry ${mode} → ${row.name}\n${JSON.stringify(result, null, 2)}`
    await reload()
  } catch (e) {
    lastResult.value = `Retry error for ${row.name}: ${e?.message || e}`
  } finally {
    busyKey.value = ''
  }
}

function prev() {
  if (page.value > 1) {
    page.value--
    reload()
  }
}

function next() {
  page.value++
  reload()
}

onMounted(reload)
</script>
