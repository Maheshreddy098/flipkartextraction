<template>
  <div class="space-y-4">
    <!-- Health strip -->
    <div class="rounded-xl bg-neutral-100 text-neutral-900 p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
      <div>
        <div class="text-xs uppercase text-neutral-500 font-semibold">SAP Login</div>
        <div :class="overview.health?.sap_login?.ok ? 'text-emerald-600' : 'text-red-600'" class="text-lg font-medium">
          {{ overview.health?.sap_login?.ok ? 'Healthy' : 'Down' }}
        </div>
        <div class="text-xs text-neutral-500 truncate">{{ overview.health?.sap_login?.message || '-' }}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-neutral-500 font-semibold">UC Login</div>
        <div :class="overview.health?.uc_login?.ok ? 'text-emerald-600' : 'text-red-600'" class="text-lg font-medium">
          {{ overview.health?.uc_login?.ok ? 'Healthy' : 'Down' }}
        </div>
        <div class="text-xs text-neutral-500 truncate">{{ overview.health?.uc_login?.message || '-' }}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-neutral-500 font-semibold">Recon Gaps</div>
        <div class="text-2xl font-semibold">{{ overview.recon_summary?.gap_count ?? 0 }}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-neutral-500 font-semibold">Last Generated</div>
        <div class="text-xs">{{ overview.generated_at || '-' }}</div>
        <button class="mt-1 text-xs px-2 py-1 border rounded hover:bg-neutral-200" @click="reloadOverview" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Stage counts -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <StageCard title="Orders" :counts="overview.counts?.orders" :status-keys="orderStatuses" />
      <StageCard title="Credit Notes" :counts="overview.counts?.credit_notes" :status-keys="cnStatuses" />
      <StageCard title="Inventory Sync" :counts="overview.counts?.inventory" :status-keys="invStatuses" />
    </div>

    <!-- Sub-tabs -->
    <div class="rounded-xl bg-neutral-900 p-2">
      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in subTabs"
          :key="t.id"
          @click="subTab = t.id"
          class="px-4 py-2 rounded-lg text-sm border"
          :class="subTab === t.id ? 'bg-neutral-100 text-neutral-900 border-neutral-100' : 'border-neutral-700 text-neutral-300 hover:border-neutral-500'">
          {{ t.label }}
        </button>
      </div>
    </div>

    <FailuresTable v-if="subTab === 'failures'" :call-method="callMethod" />
    <ActivityLog v-if="subTab === 'activity'" :call-method="callMethod" />
    <AlertRecipientsCard v-if="subTab === 'alerts'" :call-method="callMethod" />
  </div>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref } from 'vue'
import FailuresTable from './FailuresTable.vue'
import ActivityLog from './ActivityLog.vue'
import AlertRecipientsCard from './AlertRecipientsCard.vue'

const props = defineProps({ callMethod: { type: Function, required: true } })

const API_BASE = 'khanal_tech_integrations.unicommerce.api.ops'

const overview = reactive({
  health: { sap_login: { ok: false, message: '' }, uc_login: { ok: false, message: '' } },
  counts: { orders: {}, credit_notes: {}, inventory: {} },
  recon_summary: { gap_count: 0 },
  generated_at: '',
})
const loading = ref(false)
const subTab = ref('failures')
const subTabs = [
  { id: 'failures', label: 'Failures' },
  { id: 'activity', label: 'Activity' },
  { id: 'alerts', label: 'Alert Recipients' },
]

const orderStatuses = ['pending', 'ready', 'posting', 'posted', 'verify', 'failed', 'dead', 'batch_hold']
const cnStatuses = ['pending', 'posting', 'posted', 'failed', 'dead']
const invStatuses = ['Pending', 'Synced', 'Failed', 'Partial']

async function reloadOverview() {
  loading.value = true
  try {
    const data = await props.callMethod(`${API_BASE}.ops_overview`)
    Object.assign(overview, data || {})
  } catch (e) {
    console.error('ops_overview failed', e)
  } finally {
    loading.value = false
  }
}

const StageCard = defineComponent({
  props: {
    title: { type: String, required: true },
    counts: { type: Object, default: () => ({}) },
    statusKeys: { type: Array, default: () => [] },
  },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-xl bg-neutral-100 text-neutral-900 p-4' }, [
        h('div', { class: 'flex justify-between items-center mb-2' }, [
          h('h3', { class: 'font-semibold' }, props.title),
          h('span', { class: 'text-2xl font-semibold' }, props.counts?._total ?? 0),
        ]),
        h(
          'div',
          { class: 'space-y-1 text-xs' },
          props.statusKeys.map((k) =>
            h('div', { class: 'flex justify-between border-b border-neutral-200 py-1' }, [
              h('span', { class: 'text-neutral-600' }, k),
              h(
                'span',
                {
                  class:
                    k === 'failed' || k === 'dead' || k === 'Failed'
                      ? 'text-red-600 font-medium'
                      : k === 'posted' || k === 'Synced'
                      ? 'text-emerald-600'
                      : 'text-neutral-700',
                },
                String(props.counts?.[k] ?? 0)
              ),
            ])
          )
        ),
      ])
  },
})

onMounted(reloadOverview)
</script>
