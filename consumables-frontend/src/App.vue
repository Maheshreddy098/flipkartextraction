<template>
  <FrappeUIProvider>
  <div class="min-h-screen bg-gray-50">
    <template v-if="!authStore.initialized && route.name !== 'Login'">
      <div class="flex min-h-screen items-center justify-center bg-gray-900">
        <span class="text-sm text-gray-400">Loading…</span>
      </div>
    </template>

    <template v-else-if="authStore.initialized && authStore.isAuthenticated && route.name !== 'Login'">
      <div class="flex h-screen overflow-hidden">
        <!-- Mobile overlay -->
        <div
          v-if="mobileNavOpen"
          class="fixed inset-0 z-30 bg-black/40 md:hidden"
          @click="mobileNavOpen = false"
        />

        <!-- Sidebar -->
        <aside
          class="fixed inset-y-0 left-0 z-40 flex h-full w-56 shrink-0 flex-col bg-gray-900 transition-transform duration-200 md:static md:translate-x-0"
          :class="mobileNavOpen ? 'translate-x-0' : '-translate-x-full'"
        >
          <!-- Logo -->
          <div class="flex h-14 items-center border-b border-gray-700 px-4">
            <span class="text-base font-bold tracking-wide text-white">KFL StoreOps</span>
          </div>

          <!-- Nav groups -->
          <nav class="min-h-0 flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
            <template v-for="item in navItems" :key="item.name">
              <!-- Section divider label -->
              <p
                v-if="item.divider"
                class="mt-3 mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-500"
              >
                {{ item.divider }}
              </p>

              <RouterLink
                v-else
                :to="item.path"
                class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors"
                :class="
                  isActive(item.path)
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                "
                @click="mobileNavOpen = false"
              >
                <component :is="item.icon" class="h-4 w-4 shrink-0" />
                <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>

                <!-- delivery badge -->
                <span
                  v-if="item.name === 'delivery' && deliveryBadgeCount > 0"
                  class="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-900"
                >
                  {{ deliveryBadgeCount }}
                </span>
                <!-- requests badge -->
                <span
                  v-if="item.name === 'materialRequests' && requestBadgeCount > 0"
                  class="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-900"
                >
                  {{ requestBadgeCount }}
                </span>
                <!-- procurement badge (procurement users) -->
                <span
                  v-if="item.name === 'procurement' && procurementBadgeCount > 0 && !isStoreManager"
                  class="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-900"
                >
                  {{ procurementBadgeCount }}
                </span>
                <!-- GRN pending badge (store managers) -->
                <span
                  v-if="item.name === 'procurement' && grnBadgeCount > 0 && isStoreManager"
                  class="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-900"
                >
                  {{ grnBadgeCount }}
                </span>
              </RouterLink>
            </template>
          </nav>

          <!-- User footer -->
          <div class="shrink-0 border-t border-gray-700 px-4 py-3 space-y-1">
            <p class="truncate text-xs font-medium text-gray-300">{{ authStore.fullName || authStore.user }}</p>
            <p class="truncate text-[10px] text-gray-500">{{ roleShortName }}</p>
            <button
              class="mt-1 w-full text-left text-xs text-red-400 transition-colors hover:text-red-300"
              @click="handleLogout"
            >
              Sign out
            </button>
          </div>
        </aside>

        <!-- Main -->
        <main class="flex-1 overflow-y-auto">
          <!-- Mobile top bar -->
          <div class="sticky top-0 z-20 flex items-center gap-3 border-b border-gray-200 bg-white px-4 py-2.5 md:hidden">
            <button
              type="button"
              class="rounded-md border border-gray-300 bg-white p-1.5 text-gray-600"
              @click="mobileNavOpen = !mobileNavOpen"
            >
              <Menu class="h-4 w-4" />
            </button>
            <span class="text-sm font-semibold text-gray-800 flex-1 truncate">{{ currentPageTitle }}</span>
            
            <RouterLink
              v-if="route.path !== '/dashboard'"
              to="/dashboard"
              class="rounded-md border border-gray-300 bg-white p-1.5 text-gray-600 shadow-sm active:bg-gray-50"
            >
              <Home class="h-4 w-4" />
            </RouterLink>
          </div>
          <RouterView />
        </main>
      </div>
    </template>

    <template v-else>
      <RouterView />
    </template>
  </div>
  </FrappeUIProvider>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { io } from 'socket.io-client'
import {
  LayoutDashboard, Menu, Package, ArrowLeftRight,
  ClipboardList, FileText, ShoppingCart, Settings, PlusCircle, Home
} from 'lucide-vue-next'
import { FrappeUIProvider } from 'frappe-ui'
import { useAuthStore } from './stores/auth.js'
import { useDeliveryStore } from './stores/delivery.js'
import { get_material_requests } from './core/api/material_requests.js'
import { get_purchase_requests } from './core/api/procurement.js'
import { logout } from './core/auth/index.js'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const deliveryStore = useDeliveryStore()
const mobileNavOpen = ref(false)
const deliveryBadgeCount = ref(0)
const requestBadgeCount = ref(0)
const procurementBadgeCount = ref(0)
const grnBadgeCount = ref(0)
const deliveryUnread = ref(0)
const requestUnread = ref(0)
const procurementUnread = ref(0)
const procurementGrnUnread = ref(0)
const grnUnread = ref(0)
const seenCounts = ref({ delivery: 0, request: 0, transfer: 0, procurement: 0, procurementGrn: 0, grn: 0 })

const isStoreManager = computed(() =>
  authStore.consumablesRoles.includes('Consumables Store Manager') ||
  authStore.consumablesRoles.includes('Consumables Inventory Manager')
)
let socket = null

const isManagerOrAdmin = computed(() => authStore.isManager)

const roleShortName = computed(() => {
  const map = {
    'Consumables Super Admin': 'Super Admin',
    'Consumables Store Manager': 'Store Manager',
    'Consumables Inventory Manager': 'Inventory Manager',
    'Consumables Store User': 'Store User',
    'Consumables Procurement User': 'Procurement',
  }
  return map[authStore.role] || authStore.role || ''
})

const currentPageTitle = computed(() => {
  const nameMap = {
    'Dashboard': 'Dashboard',
    'InventoryIndex': 'Inventory',
    'PlantDetail': 'Inventory',
    'TransfersIndex': 'Transfers',
    'TransferNew': 'New Transfer',
    'TransferDetail': 'Transfer',
    'DeliveryIndex': 'Delivery Notes',
    'DeliveryNew': 'New Delivery Note',
    'DeliveryDetail': 'Delivery Note',
    'MaterialRequestsIndex': 'Requests',
    'MaterialRequestNew': 'New Request',
    'MaterialRequestDetail': 'Request',
    'ProcurementIndex': 'Procurement',
    'ProcurementDetail': 'Purchase Request',
    'AdminIndex': 'Admin',
  }
  return nameMap[route.name] || 'StoreOps'
})

// Nav items — fully reactive computed so label/path update after auth loads
const navItems = computed(() => {
  const grnMode = isStoreManager.value && !authStore.isProcurementUser

  const allItems = [
    { divider: 'Main' },
    { name: 'dashboard', label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, show: true },
    { name: 'inventory', label: 'Inventory', path: '/inventory', icon: Package, show: true },

    { divider: 'Consumables' },
    { name: 'materialRequests', label: 'Material Requests', path: '/material-requests', icon: FileText,
      show: !authStore.isProcurementUser || isManagerOrAdmin.value },
    { name: 'transfers', label: 'Transfers', path: '/transfers', icon: ArrowLeftRight,
      show: !authStore.isProcurementUser || isManagerOrAdmin.value },
    { name: 'delivery', label: 'Store Consumptions', path: '/delivery', icon: ClipboardList,
      show: !authStore.isProcurementUser || isManagerOrAdmin.value },

    { divider: 'Procurement' },
    { name: 'procurement',
      label: grnMode ? 'GRN Pending' : 'Purchase Requests',
      path: grnMode ? { path: '/procurement', query: { status: 'PO Raised' } } : '/procurement',
      icon: ShoppingCart,
      show: authStore.isSuperAdmin || authStore.isProcurementUser || isStoreManager.value },

    { divider: 'Admin' },
    { name: 'admin', label: 'Admin Setup', path: '/admin', icon: Settings,
      show: authStore.isSuperAdmin },
  ]

  const out = []
  let pendingDivider = null
  for (const item of allItems) {
    if (item.divider) {
      pendingDivider = item
      continue
    }
    if (!item.show) continue
    if (pendingDivider) { out.push(pendingDivider); pendingDivider = null }
    out.push(item)
  }
  return out
})

function isActive(path) {
  const cleanPath = (typeof path === 'object' ? path.path : path).split('?')[0]
  return route.path === cleanPath || route.path.startsWith(cleanPath + '/')
}

function seenStorageKey() {
  return `storeops_seen_badges:${authStore.user || 'guest'}`
}

function loadSeenCounts() {
  try {
    const raw = localStorage.getItem(seenStorageKey())
    const parsed = raw ? JSON.parse(raw) : {}
    seenCounts.value = {
      delivery: Number(parsed.delivery || 0),
      request: Number(parsed.request || 0),
      transfer: Number(parsed.transfer || 0),
      procurement: Number(parsed.procurement || 0),
      procurementGrn: Number(parsed.procurementGrn || 0),
      grn: Number(parsed.grn || 0),
    }
  } catch {
    seenCounts.value = { delivery: 0, request: 0, transfer: 0, procurement: 0, procurementGrn: 0, grn: 0 }
  }
}

function persistSeenCounts() {
  try {
    localStorage.setItem(seenStorageKey(), JSON.stringify(seenCounts.value))
  } catch {
    /* ignore storage errors */
  }
}

function refreshUnreadBadges() {
  deliveryBadgeCount.value = Math.max(0, Number(deliveryUnread.value || 0) - Number(seenCounts.value.delivery || 0))
  requestBadgeCount.value = Math.max(0, Number(requestUnread.value || 0) - Number(seenCounts.value.request || 0))
  procurementBadgeCount.value = Math.max(0, Number(procurementUnread.value || 0) - Number(seenCounts.value.procurement || 0))
  grnBadgeCount.value = Math.max(0, Number(grnUnread.value || 0) - Number(seenCounts.value.grn || 0))
}

function markCurrentSectionAsSeen() {
  let changed = false
  if (route.path.startsWith('/delivery')) {
    seenCounts.value.delivery = Number(deliveryUnread.value || 0)
    changed = true
  }
  if (route.path.startsWith('/material-requests')) {
    seenCounts.value.request = Number(requestUnread.value || 0)
    changed = true
  }
  if (route.path.startsWith('/procurement')) {
    seenCounts.value.procurement = Number(procurementUnread.value || 0)
    seenCounts.value.procurementGrn = Number(procurementGrnUnread.value || 0)
    seenCounts.value.grn = Number(grnUnread.value || 0)
    changed = true
  }
  if (changed) {
    persistSeenCounts()
    refreshUnreadBadges()
  }
}

async function handleLogout() {
  try { await logout() } finally {
    authStore.clearAuth()
    router.push({ name: 'Login' })
  }
}

async function loadBadges() {
  try {
    if (isManagerOrAdmin.value) {
      await deliveryStore.fetchDeliveryNotes({ status: 'Submitted', page: 1, page_size: 100 })
      deliveryUnread.value = Number(deliveryStore.pendingApprovalCount || 0)
    } else {
      deliveryUnread.value = 0
    }
    // Requests badge — submitted requests for managers
    if (isManagerOrAdmin.value) {
      const res = await get_material_requests({ status: 'Submitted', page: 1, page_size: 1 })
      const p = res?.message ?? res ?? {}
      requestUnread.value = Number(p.total || 0)
    } else {
      requestUnread.value = 0
    }

    // Procurement badge — submitted CPRs (pending PO raise)
    if (authStore.isSuperAdmin || authStore.isProcurementUser) {
      const res = await get_purchase_requests({ status: 'Submitted', page: 1, page_size: 1 })
      const p = res?.message ?? res ?? {}
      procurementUnread.value = Number(p.total || 0)
      const grnRes = await get_purchase_requests({ status: 'PO Raised', page: 1, page_size: 1 })
      const grnp = grnRes?.message ?? grnRes ?? {}
      procurementGrnUnread.value = Number(grnp.total || 0)
    } else {
      procurementUnread.value = 0
      procurementGrnUnread.value = 0
    }

    // GRN badge for Store Managers — all PO Raised CPRs (backend scopes to their accessible plants)
    if (isStoreManager.value && !authStore.isProcurementUser) {
      const res = await get_purchase_requests({ status: 'PO Raised', page: 1, page_size: 1 })
      const p = res?.message ?? res ?? {}
      grnUnread.value = Number(p.total || 0)
    } else {
      grnUnread.value = 0
    }

    refreshUnreadBadges()
    markCurrentSectionAsSeen()
  } catch { /* best effort */ }
}

async function loadPendingDeliveryApprovals() {
  if (!isManagerOrAdmin.value) return
  try {
    await deliveryStore.fetchDeliveryNotes({ status: 'Submitted', page: 1, page_size: 100 })
    deliveryUnread.value = Number(deliveryStore.pendingApprovalCount || 0)
    refreshUnreadBadges()
  } catch { /* ignore */ }
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
    socket = io(`${protocol}//${hostname}:${port}/${site}`, {
      path: '/socket.io', withCredentials: true, transports: ['websocket', 'polling'],
    })
    socket.on('storeops_update', () => {
      loadPendingDeliveryApprovals()
      loadBadges()
    })
  } catch { /* ignore */ }
}

watch(
  () => [authStore.initialized, authStore.role, authStore.consumablesRoles, authStore.isSuperAdmin, route.fullPath],
  () => {
    mobileNavOpen.value = false
    if (authStore.initialized) {
      loadSeenCounts()
      markCurrentSectionAsSeen()
      loadPendingDeliveryApprovals()
      loadBadges()
    }
  },
  { immediate: true },
)

onMounted(() => {
  loadPendingDeliveryApprovals()
  loadBadges()
  connectRealtime()
})

onUnmounted(() => {
  try { socket?.off('storeops_update'); socket?.disconnect() } catch { /* ignore */ }
  socket = null
})
</script>
