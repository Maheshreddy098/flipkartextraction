<template>
  <div class="rounded-xl bg-neutral-100 text-neutral-900 p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold">Activity (last {{ hours }}h)</h3>
      <div class="flex items-center gap-2">
        <select v-model.number="hours" @change="reload" class="text-sm border rounded px-2 py-1">
          <option :value="6">6h</option>
          <option :value="24">24h</option>
          <option :value="72">72h</option>
        </select>
        <button class="text-sm px-3 py-1 border rounded hover:bg-neutral-200" @click="reload" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div>
        <div class="text-xs uppercase font-semibold text-neutral-500 mb-2">Scheduled Jobs</div>
        <div v-if="data.jobs.length === 0" class="text-sm text-neutral-500">No jobs in window.</div>
        <ul v-else class="space-y-1 text-xs">
          <li v-for="j in data.jobs" :key="j.name" class="flex justify-between border-b border-neutral-200 py-1">
            <span class="truncate max-w-[60%]" :title="j.scheduled_job_type">{{ j.scheduled_job_type }}</span>
            <span :class="j.status === 'Complete' ? 'text-emerald-600' : 'text-red-600'">{{ j.status }}</span>
            <span class="text-neutral-400">{{ shortTime(j.creation) }}</span>
          </li>
        </ul>
      </div>

      <div>
        <div class="text-xs uppercase font-semibold text-neutral-500 mb-2">Errors</div>
        <div v-if="data.errors.length === 0" class="text-sm text-neutral-500">No errors in window.</div>
        <ul v-else class="space-y-1 text-xs">
          <li v-for="e in data.errors" :key="e.name" class="border-b border-neutral-200 py-1">
            <div class="flex justify-between">
              <span class="font-mono truncate max-w-[70%]" :title="e.method">{{ e.method }}</span>
              <span class="text-neutral-400">{{ shortTime(e.creation) }}</span>
            </div>
            <div class="text-neutral-600 truncate" :title="e.error">{{ e.error }}</div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'

const props = defineProps({ callMethod: { type: Function, required: true } })

const API_BASE = 'khanal_tech_integrations.unicommerce.api.ops'

const hours = ref(24)
const loading = ref(false)
const data = reactive({ jobs: [], errors: [], since: '' })

function shortTime(ts) {
  if (!ts) return '-'
  return String(ts).replace('T', ' ').slice(0, 16)
}

async function reload() {
  loading.value = true
  try {
    const r = await props.callMethod(`${API_BASE}.ops_activity`, { hours: hours.value })
    data.jobs = r?.jobs || []
    data.errors = r?.errors || []
    data.since = r?.since || ''
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>
