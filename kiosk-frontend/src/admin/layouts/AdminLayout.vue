<template>
  <div class="flex h-screen bg-gray-100">
    <!-- Sidebar -->
    <div 
      :class="[
        'relative bg-white shadow-lg transition-all duration-300 ease-in-out flex-shrink-0',
        isCollapsed ? 'w-16' : 'w-64'
      ]"
    >
      <!-- Admin Header -->
      <div class="p-4 border-b border-gray-200">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <span class="text-white text-sm font-bold">⚙️</span>
          </div>
          <div v-if="!isCollapsed" class="flex-1 min-w-0">
            <h2 class="text-sm font-semibold text-gray-900 truncate">Admin Panel</h2>
            <p class="text-xs text-gray-500 truncate">System Administration</p>
          </div>
        </div>
      </div>

      <!-- Navigation Menu -->
      <nav class="mt-4 px-2">
        <ul class="space-y-1">
          <li v-for="item in navigationItems" :key="item.id">
            <router-link
              :to="item.route"
              :class="[
                'group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-200',
                isActive(item.route) 
                  ? 'bg-purple-100 text-purple-700 border-r-2 border-purple-500' 
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              ]"
              @click="setActiveItem(item.id)"
            >
              <span class="text-lg mr-3 flex-shrink-0">{{ item.icon }}</span>
              <span v-if="!isCollapsed" class="truncate">{{ item.name }}</span>
            </router-link>
          </li>
        </ul>
      </nav>

      <!-- Collapse Toggle -->
      <div class="absolute bottom-4 left-4">
        <button
          @click="toggleCollapse"
          class="p-2 rounded-md bg-gray-100 hover:bg-gray-200 transition-colors duration-200"
        >
          <svg 
            :class="[
              'w-4 h-4 text-gray-600 transition-transform duration-200',
              isCollapsed ? 'rotate-180' : ''
            ]"
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="flex-1 min-w-0 flex flex-col overflow-hidden">
      <!-- Top Bar -->
      <div class="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <button
              @click="toggleCollapse"
              class="p-2 rounded-md hover:bg-gray-100 transition-colors duration-200 lg:hidden"
            >
              <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h1 class="text-xl font-semibold text-gray-900">{{ currentPageTitle }}</h1>
          </div>
          
          <!-- User Dropdown -->
          <UserDropdown 
            :plant="plantConfig"
            @logout="handleLogout"
          />
        </div>
      </div>

      <!-- Page Content -->
      <main class="flex-1 min-w-0 overflow-auto bg-gray-50">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import UserDropdown from '@/app/components/UserDropdown.vue'

const route = useRoute()
const router = useRouter()
const sessionStore = useSessionStore()

// State
const isCollapsed = ref(false)
const activeItem = ref('admin-dashboard')

// Plant configuration from session (for user dropdown)
const plantConfig = computed(() => {
  const session = sessionStore.getSession()
  return session?.plant || { name: 'Admin', location: 'System', id: 'admin' }
})

// Navigation items for Admin Panel
const navigationItems = ref([
  {
    id: 'admin-dashboard',
    name: 'Admin Dashboard',
    icon: '📊',
    route: '/admin'
  },
  {
    id: 'avalara-dashboard',
    name: 'Avalara Dashboard',
    icon: '📈',
    route: '/admin/avalara-dashboard'
  },
  {
    id: 'unicommerce-dashboard',
    name: 'Unicommerce Dashboard',
    icon: '📦',
    route: '/admin/unicommerce-dashboard'
  },
  {
    id: 'logistics-dashboard',
    name: 'POD Dashboard',
    icon: '📋',
    route: '/admin/logistics-dashboard'
  },
  {
    id: 'vendor-master-dashboard',
    name: 'Vendor Master Dashboard',
    icon: '🏦',
    route: '/admin/vendor-master-dashboard'
  }
])

// Current page title
const currentPageTitle = computed(() => {
  return route.meta?.title || 'Admin Panel'
})

// Check if route is active
function isActive(routePath) {
  if (routePath === '/admin') return route.path === '/admin'
  return route.path === routePath || route.path.startsWith(routePath + '/')
}

// Set active navigation item
function setActiveItem(itemId) {
  activeItem.value = itemId
}

// Toggle sidebar collapse
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

// Handle logout
function handleLogout() {
  sessionStore.clearSession()
  router.push('/login')
}

// Update active item when route changes
watch(() => route.path, (newPath) => {
  const item = navigationItems.value.find(item => isActive(item.route))
  if (item) {
    activeItem.value = item.id
  }
}, { immediate: true })

onMounted(() => {
  // Set initial active item
  const item = navigationItems.value.find(item => isActive(item.route))
  if (item) {
    activeItem.value = item.id
  }
})
</script>
