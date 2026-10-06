<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-64 bg-gray-900 text-white flex flex-col flex-shrink-0">
      <div class="px-6 py-5 border-b border-gray-800">
        <h2 class="text-lg font-bold">WowPets 3PL</h2>
        <p class="text-xs text-gray-400 mt-1">{{ teamLabel }}</p>
        <div
          v-if="sessionStore.team === 'khanalfoods' || sessionStore.team === 'procurement'"
          class="mt-3 flex items-center justify-between gap-2 text-[11px]"
        >
          <button
            type="button"
            class="flex items-center gap-1.5 text-gray-300 hover:text-white transition"
            @click="refreshSapHealth"
          >
            <span
              class="inline-flex w-2.5 h-2.5 rounded-full"
              :class="{
                'bg-emerald-400': sapStatus === 'connected',
                'bg-yellow-400': sapStatus === 'checking',
                'bg-red-500': sapStatus === 'disconnected' || sapStatus === 'error',
              }"
            />
            <span>
              SAP
              <span v-if="sapStatus === 'connected'">Connected</span>
              <span v-else-if="sapStatus === 'checking'">Checking…</span>
              <span v-else>Issue</span>
            </span>
          </button>
          <button
            type="button"
            @click="renewSapSession"
            :disabled="sapLoading"
            class="px-2 py-1 rounded border border-gray-700 text-[11px] text-gray-200 hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {{ sapLoading ? 'Renewing…' : 'Renew Session' }}
          </button>
        </div>
      </div>

      <nav class="flex-1 py-4 overflow-y-auto">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-6 py-3 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition"
          active-class="bg-gray-800 text-white border-r-2 border-blue-500"
        >
          <component :is="item.icon" class="w-5 h-5" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="px-6 py-4 border-t border-gray-800">
        <div class="text-sm text-gray-300 truncate">{{ sessionStore.fullName }}</div>
        <div class="text-xs text-gray-500 truncate">{{ sessionStore.userEmail }}</div>
        <button
          @click="handleLogout"
          class="mt-3 w-full text-left text-sm text-red-400 hover:text-red-300 transition"
        >
          Sign Out
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-y-auto bg-gray-50">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'
import { logout } from '@/core/auth/authService.js'
import {
  LayoutDashboard, ShoppingCart, Factory, PackageCheck,
  RotateCcw, Warehouse, ArrowLeftRight, Package, Truck, Ticket,
} from 'lucide-vue-next'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { getSapHealth, initiateSapSession } from '@/core/api/sapMaster.js'

const sessionStore = useSessionStore()
const notify = useNotificationStore()

const sapStatus = ref('checking') // 'checking' | 'connected' | 'disconnected' | 'error'
const sapLoading = ref(false)

const teamLabel = computed(() => {
  if (sessionStore.team === 'warehouse') return 'WowPets Warehouse'
  if (sessionStore.team === 'procurement') return 'Procurement Team'
  return 'KhanalFoods Team'
})

const kfMenu = [
  { path: '/khanalfoods/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/khanalfoods/purchase-orders', label: 'Purchase Orders', icon: ShoppingCart },
  { path: '/khanalfoods/orders', label: 'FBA Transfers', icon: Package },
  { path: '/khanalfoods/dispatch-orders', label: 'Dispatch Orders', icon: Truck },
  { path: '/khanalfoods/shiphero-transfers', label: 'Shiphero Transfers', icon: ArrowLeftRight },
  { path: '/khanalfoods/work-orders', label: 'Work Orders', icon: Factory },
  { path: '/khanalfoods/inventory', label: 'Inventory', icon: PackageCheck },
  { path: '/khanalfoods/returns', label: 'Returns', icon: RotateCcw },
  { path: '/khanalfoods/tickets', label: 'Tickets', icon: Ticket },
]

const whMenu = [
  { path: '/warehouse/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/warehouse/purchase-orders', label: 'Purchase Orders', icon: ShoppingCart },
  { path: '/warehouse/orders', label: 'FBA Transfers', icon: Package },
  { path: '/warehouse/dispatch-orders', label: 'Dispatch Orders', icon: Truck },
  { path: '/warehouse/shiphero-transfers', label: 'Shiphero Transfers', icon: ArrowLeftRight },
  { path: '/warehouse/work-orders', label: 'Work Orders', icon: Factory },
  { path: '/warehouse/inventory', label: 'Inventory', icon: PackageCheck },
  { path: '/warehouse/returns', label: 'Returns', icon: RotateCcw },
  { path: '/warehouse/tickets', label: 'Tickets', icon: Ticket },
]

const menuItems = computed(() =>
  sessionStore.team === 'warehouse' ? whMenu : kfMenu
)

async function refreshSapHealth() {
  if (sessionStore.team === 'warehouse') return
  sapStatus.value = 'checking'
  try {
    const res = await getSapHealth()
    if (res?.ok && res.status === 'connected') {
      sapStatus.value = 'connected'
    } else {
      sapStatus.value = res?.status || 'disconnected'
    }
  } catch {
    sapStatus.value = 'error'
  }
}

async function renewSapSession() {
  if (sessionStore.team === 'warehouse' || sapLoading.value) return
  sapLoading.value = true
  try {
    const res = await initiateSapSession()
    if (res?.ok) {
      notify.success('SAP session renewed for KhanalFoods')
      await refreshSapHealth()
    } else {
      sapStatus.value = 'error'
      notify.error(res?.error || 'Failed to renew SAP session')
    }
  } catch (e) {
    sapStatus.value = 'error'
    notify.error(e.response?.data?.message || 'Failed to renew SAP session')
  } finally {
    sapLoading.value = false
  }
}

function handleLogout() {
  logout()
}

onMounted(() => {
  if (sessionStore.team !== 'warehouse') {
    refreshSapHealth()
  }
})
</script>
