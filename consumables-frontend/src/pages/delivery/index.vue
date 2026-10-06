<template>
  <div class="p-4 sm:p-6">
    <div class="mb-4 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div>
        <h1 class="text-xl font-bold text-gray-900 sm:text-2xl">Store Consumptions</h1>
        <p class="mt-0.5 text-xs text-gray-500">Record consumption and internal stock issues from your plant</p>
      </div>
      <RouterLink
        to="/delivery/new"
        class="inline-flex w-full justify-center rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 sm:w-auto sm:py-2"
      >
        + New Store Consumption
      </RouterLink>
    </div>

    <div class="mb-4 flex flex-wrap gap-1.5 sm:gap-2">
      <button
        v-for="tab in statusTabs"
        :key="tab.id"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors sm:px-3 sm:py-1.5 sm:text-sm"
        :class="
          activeTab === tab.id
            ? 'border-teal-600 bg-teal-600 text-white'
            : 'border-gray-300 bg-white text-gray-700 hover:border-teal-400'
        "
        @click="selectTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="mb-5 grid grid-cols-1 gap-3 sm:flex sm:flex-wrap sm:items-end sm:gap-4">
      <div v-if="authStore.isSuperAdmin" class="min-w-0 sm:w-auto">
        <label class="mb-1 block text-xs font-medium text-gray-600">Plant</label>
        <select
          v-model="plantCode"
          class="w-full min-w-0 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 sm:min-w-[12rem] sm:w-auto"
        >
          <option value="">All plants</option>
          <option
            v-for="p in authStore.plants"
            :key="p.plant_code"
            :value="p.plant_code"
          >
            {{ p.plant_code }} — {{ p.plant_name }}
          </option>
        </select>
      </div>

      <div class="min-w-0 sm:w-auto">
        <label class="mb-1 block text-xs font-medium text-gray-600">From</label>
        <input
          v-model="filterFrom"
          type="date"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 sm:w-auto"
        />
      </div>

      <div class="min-w-0 sm:w-auto">
        <label class="mb-1 block text-xs font-medium text-gray-600">To</label>
        <input
          v-model="filterTo"
          type="date"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 sm:w-auto"
        />
      </div>
    </div>

    <div
      v-if="deliveryStore.error"
      class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {{ deliveryStore.error }}
    </div>

    <div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <div v-if="deliveryStore.loading" class="flex justify-center p-12">
        <div class="h-8 w-8 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
      </div>

      <template v-else>
        <div v-if="!deliveryStore.deliveryNotes.length" class="p-12 text-center text-gray-500">
          No store consumptions match your filters.
        </div>

        <ul v-else class="divide-y divide-gray-100">
          <li
            v-for="row in deliveryStore.deliveryNotes"
            :key="row.name"
            class="cursor-pointer px-3 py-2.5 hover:bg-gray-50 sm:px-4 sm:py-3"
            @click="goToDetail(row.name)"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="min-w-0 truncate font-mono text-xs font-medium text-gray-900 sm:text-sm">{{ row.name }}</span>
              <div class="flex items-center gap-1.5">
                <span
                  v-if="isBackdated(row)"
                  class="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800"
                >
                  Backdated
                </span>
                <StatusBadge :status="row.status" size="sm" />
              </div>
            </div>
            <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-600 sm:gap-3 sm:text-sm">
              <span class="font-medium text-gray-700">{{ row.plant || '—' }}</span>
              <span class="max-w-[11rem] truncate sm:max-w-none">{{ row.purpose || '—' }}</span>
              <span class="text-gray-500">{{ itemPhrase(row) }}</span>
              <span class="ml-auto shrink-0 text-gray-500">{{ formatDate(row) }}</span>
            </div>
          </li>
        </ul>
      </template>
    </div>

    <div
      v-if="totalPages > 1 && !deliveryStore.loading"
      class="mt-4 flex flex-wrap items-center justify-center gap-1.5 sm:gap-2"
    >
      <button
        type="button"
        class="rounded-lg border px-2.5 py-1.5 text-xs disabled:opacity-40 sm:px-3 sm:text-sm"
        :disabled="page <= 1"
        @click="setPage(page - 1)"
      >
        Previous
      </button>
      <button
        v-for="p in pageNumbers"
        :key="p"
        type="button"
        class="min-w-[2rem] rounded-lg border px-1.5 py-1.5 text-xs sm:min-w-[2.25rem] sm:px-2 sm:text-sm"
        :class="p === page ? 'border-teal-600 bg-teal-600 text-white' : 'border-gray-300 bg-white text-gray-700'"
        @click="setPage(p)"
      >
        {{ p }}
      </button>
      <button
        type="button"
        class="rounded-lg border px-2.5 py-1.5 text-xs disabled:opacity-40 sm:px-3 sm:text-sm"
        :disabled="page >= totalPages"
        @click="setPage(page + 1)"
      >
        Next
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useDeliveryStore } from '@/stores/delivery.js'
import { StatusBadge } from '@/shared/components/index.js'

const PAGE_SIZE = 20

const statusTabs = [
  { id: 'all',      label: 'All',            apiStatus: null },
  { id: 'posted',   label: 'Posted to SAP',  apiStatus: 'Posted' },
  { id: 'rejected', label: 'Rejected',       apiStatus: 'Rejected' },
  { id: 'failed',   label: 'SAP Failed',     apiStatus: 'Failed' },
]

const router = useRouter()
const authStore = useAuthStore()
const deliveryStore = useDeliveryStore()

const activeTab = ref('all')
const plantCode = ref('')
const filterFrom = ref('')
const filterTo = ref('')

const page = computed({
  get: () => deliveryStore.filters.page,
  set: (v) => {
    deliveryStore.filters.page = v
  },
})

const totalPages = computed(() => Math.max(1, Math.ceil(deliveryStore.totalCount / PAGE_SIZE)))

const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = page.value
  const window = 2
  const start = Math.max(1, cur - window)
  const end = Math.min(total, cur + window)
  const nums = []
  for (let i = start; i <= end; i++) nums.push(i)
  return nums
})

function tabDef() {
  return statusTabs.find((t) => t.id === activeTab.value)
}

function itemCount(row) {
  const n =
    row.items_count ??
    row.line_items_count ??
    row.total_items ??
    row.line_items?.length ??
    row.items?.length ??
    0
  return Number(n) || 0
}

function itemPhrase(row) {
  const n = itemCount(row)
  return `${n} ${n === 1 ? 'item' : 'items'}`
}

function isBackdated(row) {
  if (!row.doc_date || !row.requested_on) return false
  return String(row.doc_date).slice(0, 10) !== String(row.requested_on).slice(0, 10)
}

function formatDate(row) {
  const raw = row.requested_on || row.approved_on || row.creation || ''
  if (!raw) return '—'
  const d = String(raw).slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return d
  return d.slice(5)
}

function goToDetail(name) {
  if (!name) return
  router.push({ name: 'DeliveryDetail', params: { name } })
}

async function fetchTable() {
  const tab = tabDef()
  await deliveryStore.fetchDeliveryNotes({
    status: tab?.apiStatus ?? null,
    page: page.value,
    page_size: PAGE_SIZE,
    from_date: filterFrom.value || null,
    to_date: filterTo.value || null,
    plant_code: authStore.isSuperAdmin ? (plantCode.value || null) : null,
  })
}

function selectTab(id) {
  activeTab.value = id
  deliveryStore.filters.page = 1
  fetchTable()
}

function setPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  fetchTable()
}

watch([plantCode, filterFrom, filterTo], () => {
  deliveryStore.filters.page = 1
  fetchTable()
})

onMounted(fetchTable)
</script>
