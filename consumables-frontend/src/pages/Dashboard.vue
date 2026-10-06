<template>
  <div class="min-h-full bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-4 py-4 sm:px-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-bold text-gray-900 sm:text-xl">
            Good {{ greeting }}, {{ firstName }}
          </h1>
          <p class="mt-0.5 text-xs text-gray-500">{{ roleBadge }}</p>
        </div>
        <span class="hidden rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-xs font-medium text-teal-700 sm:inline">
          {{ today }}
        </span>
      </div>
    </div>

    <div class="p-4 sm:p-6 space-y-6">

      <!-- Quick Actions -->
      <section>
        <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Quick Actions</h2>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <RouterLink
            v-for="action in quickActions"
            :key="action.label"
            :to="action.to"
            class="flex flex-col items-center gap-2 rounded-xl border border-gray-200 bg-white p-4 text-center transition-all hover:border-teal-400 hover:shadow-sm active:scale-95"
          >
            <span class="flex h-10 w-10 items-center justify-center rounded-full text-xl" :class="action.bg">
              {{ action.icon }}
            </span>
            <span class="text-xs font-medium text-gray-800 leading-tight">{{ action.label }}</span>
          </RouterLink>
        </div>
      </section>

      <!-- Action Required (Manager/Admin) -->
      <section v-if="isManagerOrAdmin && (pendingDeliveriesUnread > 0 || pendingDecisionsUnread > 0 || pendingGrnForManagerUnread > 0)">
        <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Action Required</h2>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <RouterLink
            v-if="pendingDeliveriesUnread > 0"
            to="/delivery?status=Submitted"
            class="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 hover:shadow-sm"
          >
            <span class="text-2xl">📋</span>
            <div>
              <p class="text-xl font-bold text-amber-900">{{ pendingDeliveriesUnread }}</p>
              <p class="text-xs font-semibold text-amber-700">Delivery Notes to Approve</p>
              <p class="mt-0.5 text-[10px] text-amber-600">Staff submitted these — review &amp; approve</p>
            </div>
          </RouterLink>
          <RouterLink
            v-if="pendingDecisionsUnread > 0"
            to="/material-requests?tab=decision"
            class="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 hover:shadow-sm"
          >
            <span class="text-2xl">📝</span>
            <div>
              <p class="text-xl font-bold text-blue-900">{{ pendingDecisionsUnread }}</p>
              <p class="text-xs font-semibold text-blue-700">Requests Awaiting Decision</p>
              <p class="mt-0.5 text-[10px] text-blue-600">Define the fulfillment plan for each</p>
            </div>
          </RouterLink>
          <RouterLink
            v-if="pendingCPRUnread > 0 && authStore.isProcurementUser"
            to="/procurement?status=Submitted"
            class="flex items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4 hover:shadow-sm"
          >
            <span class="text-2xl">🛒</span>
            <div>
              <p class="text-xl font-bold text-indigo-900">{{ pendingCPRUnread }}</p>
              <p class="text-xs font-semibold text-indigo-700">Purchase Orders (PO) to Raise</p>
              <p class="mt-0.5 text-[10px] text-indigo-600">Review &amp; raise PO in SAP</p>
            </div>
          </RouterLink>
          <!-- GRN pending card — for Store Managers who handle goods receipt -->
          <RouterLink
            v-if="pendingGrnForManagerUnread > 0 && isStoreManager"
            :to="{ path: '/procurement', query: { status: 'PO Raised' } }"
            class="flex items-center gap-3 rounded-xl border border-teal-300 bg-teal-50 p-4 hover:shadow-sm"
          >
            <span class="text-2xl">📦</span>
            <div>
              <p class="text-xl font-bold text-teal-900">{{ pendingGrnForManagerUnread }}</p>
              <p class="text-xs font-semibold text-teal-800">GRN Pending</p>
              <p class="mt-0.5 text-[10px] text-teal-700">Goods have arrived — record receipt in SAP</p>
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- Procurement User pending -->
      <section v-if="authStore.isProcurementUser && !isManagerOrAdmin && (pendingCPRUnread > 0 || pendingGRNUnread > 0)">
        <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Action Required</h2>
        <div class="grid grid-cols-2 gap-3">
          <RouterLink
            v-if="pendingCPRUnread > 0"
            to="/procurement?status=Submitted"
            class="flex items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4 hover:shadow-sm"
          >
            <span class="text-2xl">🛒</span>
            <div>
              <p class="text-xl font-bold text-indigo-900">{{ pendingCPRUnread }}</p>
              <p class="text-xs font-semibold text-indigo-700">Purchase Orders (PO) to Raise</p>
              <p class="mt-0.5 text-[10px] text-indigo-600">Review &amp; raise PO in SAP</p>
            </div>
          </RouterLink>
          <RouterLink
            v-if="pendingGRNUnread > 0"
            to="/procurement?status=PO Raised"
            class="flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50 p-4 hover:shadow-sm"
          >
            <span class="text-2xl">📦</span>
            <div>
              <p class="text-xl font-bold text-teal-900">{{ pendingGRNUnread }}</p>
              <p class="text-xs font-semibold text-teal-700">Goods Receipts (GRN) Pending</p>
              <p class="mt-0.5 text-[10px] text-teal-600">Enter received quantities for delivered POs</p>
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- My Recent Requests -->
      <section v-if="!authStore.isProcurementUser || isManagerOrAdmin">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-500">My Recent Requests</h2>
          <RouterLink to="/material-requests?tab=my" class="text-xs text-teal-700 hover:text-teal-800">View all →</RouterLink>
        </div>
        <div v-if="loadingRequests" class="space-y-2">
          <div v-for="i in 3" :key="i" class="h-16 rounded-xl bg-gray-100 animate-pulse" />
        </div>
        <div v-else-if="!recentRequests.length" class="rounded-xl border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500">
          No requests yet.
          <RouterLink to="/material-requests/new" class="ml-1 text-teal-700 underline">Create one →</RouterLink>
        </div>
        <div v-else class="space-y-2">
          <RouterLink
            v-for="req in recentRequests"
            :key="req.name"
            :to="`/material-requests/${req.name}`"
            class="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 hover:shadow-sm"
          >
            <div class="min-w-0">
              <p class="font-mono text-sm font-medium text-gray-900">{{ req.name }}</p>
              <p class="mt-0.5 text-xs text-gray-500">{{ req.plant_code || '—' }} · {{ fmtDate(req.requested_on || req.creation) }}</p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <span
                v-if="req.urgency === 'Critical'"
                class="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700"
              >CRITICAL</span>
              <StatusBadge :status="req.status || 'Submitted'" size="sm" />
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- Plant Cards -->
      <section v-if="authStore.plants.length">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-500">My Plants</h2>
          <RouterLink to="/inventory" class="text-xs text-teal-700 hover:text-teal-800">View all →</RouterLink>
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="plant in authStore.plants"
            :key="plant.plant_code"
            class="cursor-pointer rounded-xl border border-gray-200 bg-white p-4 transition-all hover:shadow-md"
            @click="router.push('/inventory/' + plant.plant_code)"
          >
            <div class="flex items-start justify-between">
              <div class="min-w-0">
                <h3 class="truncate text-sm font-semibold text-gray-900">{{ plant.plant_name }}</h3>
                <p class="text-xs text-gray-500">{{ plant.plant_code }}</p>
              </div>
            </div>
            <div v-if="loadingByPlant[plant.plant_code]" class="mt-3 space-y-1.5">
              <div class="h-2.5 w-28 rounded bg-gray-200 animate-pulse" />
              <div class="h-2.5 w-20 rounded bg-gray-200 animate-pulse" />
            </div>
            <div v-else class="mt-3 grid grid-cols-2 gap-2 text-center">
              <div class="rounded-lg bg-gray-50 p-2">
                <p class="text-base font-bold text-gray-900">{{ summaryFor(plant.plant_code).itemCount }}</p>
                <p class="text-[10px] text-gray-500">Items</p>
              </div>
              <div class="rounded-lg bg-gray-50 p-2">
                <p class="text-base font-bold text-gray-900">{{ summaryFor(plant.plant_code).warehouseCount }}</p>
                <p class="text-[10px] text-gray-500">Warehouses</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div v-else-if="!authStore.isProcurementUser" class="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center text-gray-500">
        <p class="font-medium">No plants assigned</p>
        <p class="mt-1 text-sm">Ask your administrator to assign you to a plant.</p>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { useInventoryStore } from '@/stores/inventory.js'
import { useDeliveryStore } from '@/stores/delivery.js'
import { get_material_requests } from '@/core/api/material_requests.js'
import { get_purchase_requests } from '@/core/api/procurement.js'
import { get_delivery_notes } from '@/core/api/delivery.js'
import { StatusBadge } from '@/shared/components/index.js'

const router = useRouter()
const authStore = useAuthStore()
const inventoryStore = useInventoryStore()
const deliveryStore = useDeliveryStore()

const loadingByPlant = ref({})
const plantSummaries = ref({})
const loadingRequests = ref(false)
const recentRequests = ref([])
const pendingDeliveries = ref(0)
const pendingDecisions = ref(0)
const pendingCPR = ref(0)
const pendingGRN = ref(0)
const pendingDeliveriesUnread = ref(0)
const pendingDecisionsUnread = ref(0)
const pendingCPRUnread = ref(0)
const pendingGRNUnread = ref(0)
let socket = null

const isManagerOrAdmin = computed(() => authStore.isManager)
const isStoreManager = computed(() =>
  authStore.consumablesRoles.includes('Consumables Store Manager') ||
  authStore.consumablesRoles.includes('Consumables Inventory Manager')
)

const pendingGrnForManager = ref(0)
const pendingGrnForManagerUnread = ref(0)

function seenStorageKey() {
  return `storeops_seen_badges:${authStore.user || 'guest'}`
}

function loadSeenCounts() {
  try {
    const raw = localStorage.getItem(seenStorageKey())
    const parsed = raw ? JSON.parse(raw) : {}
    return {
      delivery: Number(parsed.delivery || 0),
      request: Number(parsed.request || 0),
      procurement: Number(parsed.procurement || 0),
      procurementGrn: Number(parsed.procurementGrn || 0),
      grn: Number(parsed.grn || 0),
    }
  } catch {
    return { delivery: 0, request: 0, procurement: 0, procurementGrn: 0, grn: 0 }
  }
}

function applySeenFilter() {
  const seen = loadSeenCounts()
  pendingDeliveriesUnread.value = Math.max(0, Number(pendingDeliveries.value || 0) - Number(seen.delivery || 0))
  pendingDecisionsUnread.value = Math.max(0, Number(pendingDecisions.value || 0) - Number(seen.request || 0))
  pendingCPRUnread.value = Math.max(0, Number(pendingCPR.value || 0) - Number(seen.procurement || 0))
  pendingGRNUnread.value = Math.max(0, Number(pendingGRN.value || 0) - Number(seen.procurementGrn || 0))
  pendingGrnForManagerUnread.value = Math.max(0, Number(pendingGrnForManager.value || 0) - Number(seen.grn || 0))
}

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
})

const firstName = computed(() => {
  const name = authStore.fullName || authStore.user || ''
  return name.split(' ')[0]
})

const roleBadge = computed(() => {
  const map = {
    'Consumables Super Admin': 'Super Admin',
    'Consumables Store Manager': 'Store Manager',
    'Consumables Inventory Manager': 'Inventory Manager',
    'Consumables Store User': 'Store User',
    'Consumables Procurement User': 'Procurement',
  }
  return map[authStore.role] || authStore.role || ''
})

const today = computed(() =>
  new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }),
)

const quickActions = computed(() => {
  const actions = []
  if (!authStore.isProcurementUser || isManagerOrAdmin.value) {
    actions.push({ label: 'New Request', to: '/material-requests/new', icon: '📝', bg: 'bg-blue-100' })
    actions.push({ label: 'New Store Consumption', to: '/delivery/new', icon: '📋', bg: 'bg-teal-100' })
  }
  if (isManagerOrAdmin.value) {
    actions.push({ label: 'View Transfers', to: '/transfers', icon: '🔄', bg: 'bg-indigo-100' })
  }
  if (authStore.isSuperAdmin || authStore.isProcurementUser) {
    actions.push({ label: 'Purchase Requests', to: '/procurement', icon: '🛒', bg: 'bg-indigo-100' })
  }
  if (isStoreManager.value && !authStore.isProcurementUser) {
    actions.push({ label: 'GRN Pending', to: { path: '/procurement', query: { status: 'PO Raised' } }, icon: '📦', bg: 'bg-teal-100' })
  }
  actions.push({ label: 'Inventory', to: '/inventory', icon: '📦', bg: 'bg-green-100' })
  return actions
})

function summaryFor(code) {
  return plantSummaries.value[code] || { warehouseCount: 0, itemCount: 0, expired: 0 }
}

function fmtDate(val) {
  if (!val) return ''
  return new Date(val).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
}

async function loadPlantSummary(plantCode) {
  loadingByPlant.value[plantCode] = true
  try {
    const warehouses = await inventoryStore.fetchWarehouses(plantCode)
    plantSummaries.value[plantCode] = {
      warehouseCount: warehouses.length,
      itemCount: warehouses.reduce((s, w) => s + Number(w.item_count || 0), 0),
      expired: warehouses.reduce((s, w) => s + Number(w.expiring_soon || 0), 0),
    }
  } catch {
    plantSummaries.value[plantCode] = { warehouseCount: 0, itemCount: 0, expired: 0 }
  } finally {
    loadingByPlant.value[plantCode] = false
  }
}

async function loadRecentRequests() {
  if (authStore.isProcurementUser && !isManagerOrAdmin.value) return
  loadingRequests.value = true
  try {
    const res = await get_material_requests({ page: 1, page_size: 50 })
    const data = res?.message ?? res ?? {}
    const list = data?.material_requests || data?.data || []
    const mine = list.filter(r => (r.requested_by || r.owner || '') === authStore.user)
    recentRequests.value = mine.slice(0, 5)
  } catch {
    recentRequests.value = []
  } finally {
    loadingRequests.value = false
  }
}

async function loadCounters() {
  try {
    if (isManagerOrAdmin.value) {
      const [deliveryRes, mrRes] = await Promise.all([
        get_delivery_notes({ status: 'Submitted', page: 1, page_size: 1 }),
        get_material_requests({ page: 1, page_size: 200 }),
      ])
      const dp = deliveryRes?.message ?? deliveryRes ?? {}
      pendingDeliveries.value = Number(dp.total || 0)
      const mrp = mrRes?.message ?? mrRes ?? {}
      const mrList = mrp?.material_requests || mrp?.data || []
      pendingDecisions.value = mrList.filter(r => ['submitted', 'under review'].includes((r.status || '').toLowerCase())).length
    }
    if (authStore.isProcurementUser) {
      const [cprRes] = await Promise.all([get_purchase_requests({ status: 'Submitted', page: 1, page_size: 1 })])
      const cprp = cprRes?.message ?? cprRes ?? {}
      pendingCPR.value = Number(cprp.total || 0)

      const grnRes = await get_purchase_requests({ status: 'PO Raised', page: 1, page_size: 1 })
      const grnp = grnRes?.message ?? grnRes ?? {}
      pendingGRN.value = Number(grnp.total || 0)
    } else {
      pendingCPR.value = 0
      pendingGRN.value = 0
    }

    if (isStoreManager.value && !authStore.isProcurementUser) {
      const res = await get_purchase_requests({ status: 'PO Raised', page: 1, page_size: 1 })
      pendingGrnForManager.value = Number((res?.message ?? res ?? {}).total || 0)
    } else {
      pendingGrnForManager.value = 0
    }

  } catch {
    /* best effort */
  } finally {
    applySeenFilter()
  }
}

function resolveSocketPort() {
  if (import.meta.env.VITE_SOCKETIO_PORT) return import.meta.env.VITE_SOCKETIO_PORT
  if (window.socketio_port) return String(window.socketio_port)
  const webPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80')
  const webPortNum = parseInt(webPort)
  if (webPortNum === 80 || webPortNum === 443) return webPort
  if (webPortNum >= 8000 && webPortNum < 9000) return String(webPortNum + 1000)
  return webPort
}

function connectRealtime() {
  try {
    const port = resolveSocketPort()
    const hostname = window.location.hostname
    const protocol = window.location.protocol
    const site = window.frappe?.boot?.sitename || import.meta.env.VITE_FRAPPE_SITE || hostname
    socket = (window.io || null)?.(
      `${protocol}//${hostname}:${port}/${site}`,
      { path: '/socket.io', withCredentials: true, transports: ['websocket', 'polling'] },
    )
    socket?.on('storeops_update', () => {
      loadCounters()
      loadRecentRequests()
    })
  } catch { /* ignore */ }
}

onMounted(async () => {
  const plants = (authStore.plants || []).map(p => p.plant_code)
  await Promise.all([
    ...plants.map(loadPlantSummary),
    loadRecentRequests(),
    loadCounters(),
  ])
  connectRealtime()
})

onUnmounted(() => {
  try { socket?.disconnect() } catch { /* ignore */ }
  socket = null
})
</script>
