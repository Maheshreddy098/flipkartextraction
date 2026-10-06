<template>
  <header class="bg-white shadow-sm border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <!-- Left side - Plant info -->
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-3">
            <div class="text-2xl">{{ plant?.icon }}</div>
            <div>
              <h1 class="text-lg font-semibold text-gray-900">{{ plant?.name }}</h1>
              <p class="text-sm text-gray-500">{{ plant?.location }}</p>
            </div>
          </div>
        </div>

        <!-- Center - removed extra tabs (Dashboard/Profile) to avoid duplication -->
        <div class="hidden md:flex items-center space-x-8"></div>

        <!-- Right side - User info and actions -->
        <div class="flex items-center space-x-4">
          <!-- User info -->
          <div class="hidden sm:flex items-center space-x-3">
            <div class="text-right">
              <p class="text-sm font-medium text-gray-900">{{ user?.name }}</p>
              <p class="text-xs text-gray-500">{{ user?.role }}</p>
            </div>
            <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm font-bold">
                {{ user?.name?.charAt(0) || 'U' }}
              </span>
            </div>
          </div>

          <!-- Mobile menu button -->
          <div class="md:hidden">
            <button
              @click="showMobileMenu = !showMobileMenu"
              class="text-gray-600 hover:text-gray-900 p-2 rounded-md"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>

          <!-- Logout button -->
          <button
            @click="handleLogout"
            class="hidden sm:inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 transition-colors"
          >
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logout
          </button>
        </div>
      </div>

      <!-- Mobile menu -->
      <div v-if="showMobileMenu" class="md:hidden border-t border-gray-200 py-4">
        <div class="space-y-2">
          <!-- Removed mobile Dashboard/Profile quick links to avoid duplication -->
          
          <!-- Mobile user info -->
          <div class="px-3 py-2 border-t border-gray-200 mt-4">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
                <span class="text-white font-bold">
                  {{ user?.name?.charAt(0) || 'U' }}
                </span>
              </div>
              <div>
                <p class="text-sm font-medium text-gray-900">{{ user?.name }}</p>
                <p class="text-xs text-gray-500">{{ user?.role }}</p>
              </div>
            </div>
          </div>

          <!-- Mobile logout button -->
          <button
            @click="handleLogout"
            class="w-full text-left px-3 py-2 text-red-600 hover:text-red-700 rounded-md text-base font-medium transition-colors"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authService } from '@/core/auth/authService.js'

// Props
defineProps({
  plant: {
    type: Object,
    required: true
  },
  user: {
    type: Object,
    required: true
  }
})

// Emits
const emit = defineEmits(['logout'])

// Composables
const router = useRouter()

// Reactive data
const showMobileMenu = ref(false)

// Methods
async function handleLogout() {
  try {

    // Emit logout event
    emit('logout')
    
    // Perform logout
    await authService.logout()
    
  } catch (error) {
    console.error('Logout error:', error)
    // Still perform logout even if logging fails
    await authService.logout()
  }
}
</script>

<style scoped>
/* Custom styles for header */
.router-link-active {
  @apply text-blue-600 bg-blue-50;
}

/* Mobile menu animation */
.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition: all 0.3s ease;
}

.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
