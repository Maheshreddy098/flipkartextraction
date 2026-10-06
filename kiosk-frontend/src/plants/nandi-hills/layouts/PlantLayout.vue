<template>
  <div class="flex h-screen bg-gray-100">
    <!-- Sidebar -->
    <div 
      :class="[
        'bg-white shadow-lg transition-all duration-300 ease-in-out',
        isCollapsed ? 'w-16' : 'w-64'
      ]"
    >
      <!-- Plant Header -->
      <div class="p-4 border-b border-gray-200">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <span class="text-white text-sm font-bold">🏔️</span>
          </div>
          <div v-if="!isCollapsed" class="flex-1 min-w-0">
            <h2 class="text-sm font-semibold text-gray-900 truncate">{{ plantConfig.name }}</h2>
            <p class="text-xs text-gray-500 truncate">{{ plantConfig.location }}</p>
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
                  ? 'bg-green-100 text-green-700 border-r-2 border-green-500' 
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
    <div class="flex-1 flex flex-col overflow-hidden">
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
      <main class="flex-1 overflow-auto bg-gray-50">
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
const activeItem = ref('dashboard')

// Plant configuration from session
const plantConfig = computed(() => {
  const session = sessionStore.getSession()
  return session?.plant || { name: 'Nandi Hills Plant', location: 'Secondary Production Facility', id: 'nandi-hills' }
})

// Navigation items for Nandi Hills (removed profile)
const navigationItems = ref([
  {
    id: 'dashboard',
    name: 'Dashboard',
    icon: '📊',
    route: '/plant/nandi-hills/dashboard'
  },
  {
    id: 'grn',
    name: 'GRN',
    icon: '📦',
    route: '/plant/nandi-hills/grn'
  },
  {
    id: 'production-order',
    name: 'Production Order',
    icon: '🏭',
    route: '/plant/nandi-hills/production-order'
  },
  {
    id: 'quality',
    name: 'Quality',
    icon: '✅',
    route: '/plant/nandi-hills/quality'
  },
  {
    id: 'inventory-transfer',
    name: 'Inventory Transfer',
    icon: '🔄',
    route: '/plant/nandi-hills/inventory-transfer'
  },
  {
    id: 'disassembly',
    name: 'Disassembly',
    icon: '📋',
    route: '/plant/nandi-hills/disassembly'
  }
])

// Computed
const currentUser = computed(() => sessionStore.user)

const currentPageTitle = computed(() => {
  const currentItem = navigationItems.value.find(item => item.route === route.path)
  return currentItem ? currentItem.name : (plantConfig.value?.name || 'Plant')
})

// Methods
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  saveNavigationState()
}

const setActiveItem = (itemId) => {
  activeItem.value = itemId
  saveNavigationState()
}

const isActive = (routePath) => {
  return route.path === routePath
}

const handleLogout = () => {
  try {
    // Call logout resource submit method
    sessionStore.logout.submit()
    // No need to wait - onSuccess handler will redirect
  } catch (error) {
    console.error('Logout error:', error)
    // Force logout even if anything fails
    window.location.href = '/kiosk/login'
  }
}

const saveNavigationState = () => {
  const state = {
    isCollapsed: isCollapsed.value,
    activeItem: activeItem.value,
    plant: 'nandi-hills'
  }
  localStorage.setItem('nandi-hills-nav-state', JSON.stringify(state))
}

const loadNavigationState = () => {
  try {
    const saved = localStorage.getItem('nandi-hills-nav-state')
    if (saved) {
      const state = JSON.parse(saved)
      if (state.plant === 'nandi-hills') {
        isCollapsed.value = state.isCollapsed || false
        activeItem.value = state.activeItem || 'dashboard'
      }
    }
  } catch (error) {
    console.error('Error loading navigation state:', error)
  }
}

// Watch for route changes
watch(route, (newRoute) => {
  const currentItem = navigationItems.value.find(item => item.route === newRoute.path)
  if (currentItem) {
    activeItem.value = currentItem.id
    saveNavigationState()
  }
}, { immediate: true })

// Initialize
onMounted(() => {
  loadNavigationState()
})
</script>
