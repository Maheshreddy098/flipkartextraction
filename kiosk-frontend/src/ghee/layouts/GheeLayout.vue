<template>
  <div class="flex h-screen bg-gray-100">
    <!-- Sidebar -->
    <div
      :class="[
        'relative bg-white shadow-lg transition-all duration-300 ease-in-out flex-shrink-0',
        collapsed ? 'w-16' : 'w-60'
      ]"
    >
      <!-- Header -->
      <div class="p-4 border-b border-gray-200">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 bg-yellow-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <span class="text-white text-sm font-bold">G</span>
          </div>
          <div v-if="!collapsed" class="flex-1 min-w-0">
            <h2 class="text-sm font-semibold text-gray-900 truncate">Ghee Production</h2>
            <p class="text-xs text-gray-500 truncate">KhanalFoods</p>
          </div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="mt-4 px-2">
        <ul class="space-y-1">
          <li v-for="item in navItems" :key="item.id">
            <router-link
              :to="item.route"
              :class="[
                'group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-200',
                isActive(item)
                  ? 'bg-yellow-100 text-yellow-800 border-r-2 border-yellow-500'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              ]"
            >
              <span class="text-lg mr-3 flex-shrink-0">{{ item.icon }}</span>
              <span v-if="!collapsed" class="truncate">{{ item.name }}</span>
            </router-link>
          </li>
        </ul>
      </nav>

      <!-- Collapse toggle -->
      <div class="absolute bottom-4 left-4">
        <button
          @click="collapsed = !collapsed"
          class="p-2 rounded-md bg-gray-100 hover:bg-gray-200 transition-colors"
        >
          <svg
            :class="['w-4 h-4 text-gray-600 transition-transform duration-200', collapsed ? 'rotate-180' : '']"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Main content -->
    <div class="flex-1 min-w-0 flex flex-col overflow-hidden">
      <!-- Top bar -->
      <div class="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
        <div class="flex items-center justify-between">
          <h1 class="text-xl font-semibold text-gray-900">{{ pageTitle }}</h1>
          <div class="flex items-center gap-3">
            <span class="text-sm text-gray-500">{{ userEmail }}</span>
            <button
              @click="logout"
              class="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      <!-- Page content -->
      <main class="flex-1 min-w-0 overflow-auto bg-gray-50">
        <!-- Inline error panel — keeps sidebar/topbar intact -->
        <div v-if="pageError" class="p-6">
          <div class="bg-red-50 border border-red-300 rounded-xl p-6 max-w-2xl">
            <div class="flex items-start gap-3">
              <div class="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
                <svg class="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L4.35 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div class="flex-1">
                <h3 class="text-sm font-semibold text-red-800">Something went wrong on this page</h3>
                <p class="text-sm text-red-600 mt-1">{{ pageError.message }}</p>
                <div class="mt-4 flex gap-3">
                  <button
                    @click="retryPage"
                    class="px-4 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors"
                  >Try Again</button>
                  <button
                    @click="pageError = null"
                    class="px-4 py-1.5 bg-white border border-red-300 text-red-700 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
                  >Dismiss</button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <router-view v-else />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onErrorCaptured } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

// Catch page-level errors inline — prevents App ErrorBoundary full-page takeover
const pageError = ref(null)

onErrorCaptured((err) => {
  console.error('[GheeLayout] caught:', err)
  pageError.value = err
  return false // stop propagation to App-level ErrorBoundary
})

function retryPage() {
  pageError.value = null
  router.go(0)
}

const navItems = [
  { id: 'dashboard',             name: 'Dashboard',        icon: '📋', route: '/ghee-production-order',      exact: true },
  { id: 'ghee-production-order', name: 'New Order',        icon: '🏭', route: '/ghee-production-order/new'               },
]

const isActive = (item) => item.exact
  ? route.path === item.route
  : route.path.startsWith(item.route)

const pageTitle = computed(() => {
  const match = navItems.find(n => isActive(n))
  return match ? match.name : 'Ghee Production'
})

const userEmail = computed(() => window.session_user || (window.boot && window.boot.session_user) || '')

const logout = async () => {
  try {
    await fetch('/api/method/logout', { method: 'POST', credentials: 'include' })
  } catch {
    // ignore
  }
  window.location.href = '/login'
}
</script>
