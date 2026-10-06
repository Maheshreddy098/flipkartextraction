<template>
  <div class="relative">
    <!-- User Avatar Button -->
    <button
      @click="toggleDropdown"
      class="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-100 transition-colors duration-200"
    >
      <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
        <span class="text-white text-sm font-bold">
          {{ user.name?.charAt(0) || 'U' }}
        </span>
      </div>
      <div class="text-left hidden sm:block">
        <p class="text-sm font-medium text-gray-900">{{ user.name }}</p>
        <p class="text-xs text-gray-500">{{ user.role }}</p>
      </div>
      <svg 
        :class="[
          'w-4 h-4 text-gray-500 transition-transform duration-200',
          isOpen ? 'rotate-180' : ''
        ]"
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown Menu -->
    <div
      v-if="isOpen"
      class="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50"
    >
      <!-- User Info -->
      <div class="px-4 py-3 border-b border-gray-100">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
            <span class="text-white text-sm font-bold">
              {{ user.name?.charAt(0) || 'U' }}
            </span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">{{ user.name }}</p>
            <p class="text-xs text-gray-500 truncate">{{ user.email }}</p>
            <p class="text-xs text-gray-500">{{ user.role }}</p>
          </div>
        </div>
      </div>

      <!-- Menu Items -->
      <div class="py-1">
        <button
          @click="openProfile"
          class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors duration-200 flex items-center space-x-3"
        >
          <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          <span>View Profile</span>
        </button>
        
        <button
          @click="openProfile(true)"
          class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors duration-200 flex items-center space-x-3"
        >
          <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <span>Change Password</span>
        </button>
        
        <div class="border-t border-gray-100 my-1"></div>
        
        <button
          @click="handleLogout"
          class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors duration-200 flex items-center space-x-3"
        >
          <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>Logout</span>
        </button>
      </div>
    </div>

    <!-- Profile Modal -->
    <div
      v-if="showProfileModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      @click="closeProfileModal"
    >
      <div @click.stop>
        <UserProfile 
          :plant="plant"
          @close="closeProfileModal"
          @logout="handleLogout"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'
import UserProfile from './UserProfile.vue'

// Props
const props = defineProps({
  plant: {
    type: Object,
    required: true
  }
})

// Emits
const emit = defineEmits(['logout'])

// Stores
const sessionStore = useSessionStore()

// State
const isOpen = ref(false)
const showProfileModal = ref(false)

// Computed
const user = computed(() => sessionStore.user)

// Methods
const toggleDropdown = () => {
  isOpen.value = !isOpen.value
}

const openProfile = () => {
  showProfileModal.value = true
  isOpen.value = false
}

const closeProfileModal = () => {
  showProfileModal.value = false
}

const changePassword = () => {
  // TODO: Implement change password functionality
  alert('Change password functionality will be implemented soon')
  isOpen.value = false
}

const handleLogout = () => {
  emit('logout')
  isOpen.value = false
  showProfileModal.value = false
}

const closeDropdown = (event) => {
  if (!event.target.closest('.relative')) {
    isOpen.value = false
  }
}

// Lifecycle
onMounted(() => {
  document.addEventListener('click', closeDropdown)
})

onUnmounted(() => {
  document.removeEventListener('click', closeDropdown)
})
</script>
