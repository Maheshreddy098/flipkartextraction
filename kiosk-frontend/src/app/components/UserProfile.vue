<template>
  <div class="bg-white rounded-lg shadow-lg border border-gray-200 p-6 max-w-md w-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-xl font-semibold text-gray-900">User Profile</h2>
      <button
        @click="$emit('close')"
        class="p-2 hover:bg-gray-100 rounded-full transition-colors duration-200"
      >
        <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- User Info -->
    <div class="mb-6">
      <div class="flex items-center space-x-4 mb-4">
        <div class="w-16 h-16 bg-blue-500 rounded-full flex items-center justify-center">
          <span class="text-white text-xl font-bold">
            {{ user.name?.charAt(0) || 'U' }}
          </span>
        </div>
        <div>
          <h3 class="text-lg font-medium text-gray-900">{{ user.name }}</h3>
          <p class="text-sm text-gray-500">{{ user.email }}</p>
          <p class="text-sm text-gray-500">{{ user.role }}</p>
        </div>
      </div>
    </div>

    <!-- Plant Info -->
    <div class="mb-6 p-4 bg-gray-50 rounded-lg">
      <h4 class="text-sm font-medium text-gray-900 mb-2">Current Plant</h4>
      <div class="flex items-center space-x-3">
        <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
          <span class="text-white text-sm font-bold">🏭</span>
        </div>
        <div>
          <p class="text-sm font-medium text-gray-900">{{ plant.name }}</p>
          <p class="text-xs text-gray-500">{{ plant.location }}</p>
        </div>
      </div>
    </div>

    <!-- User Permissions -->
    <div class="mb-6">
      <h4 class="text-sm font-medium text-gray-900 mb-3">Permissions</h4>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="permission in userPermissions"
          :key="permission"
          class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
        >
          {{ permission }}
        </span>
      </div>
    </div>

    <!-- Session Info -->
    <div class="mb-6 p-4 bg-gray-50 rounded-lg">
      <h4 class="text-sm font-medium text-gray-900 mb-2">Session Information</h4>
      <div class="space-y-1 text-sm text-gray-600">
        <p><span class="font-medium">Login Time:</span> {{ formatTime(loginTime) }}</p>
        <p><span class="font-medium">Session Duration:</span> {{ sessionDuration }}</p>
        <p><span class="font-medium">Last Activity:</span> {{ formatTime(lastActivity) }}</p>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex space-x-3">
      <button
        @click="handleChangePassword"
        class="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200"
      >
        Change Password
      </button>
      <button
        @click="handleLogout"
        class="flex-1 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200"
      >
        Logout
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'
import { useRouter } from 'vue-router'

// Props
const props = defineProps({
  plant: {
    type: Object,
    required: true
  }
})

// Emits
const emit = defineEmits(['close', 'logout'])

// Stores and Router
const sessionStore = useSessionStore()
const router = useRouter()

// State
const lastActivity = ref(new Date())
const activityInterval = ref(null)

// Computed
const user = computed(() => sessionStore.user)
const userPermissions = computed(() => sessionStore.permissions || [])
const loginTime = computed(() => sessionStore.loginTime)

const sessionDuration = computed(() => {
  if (!loginTime.value) return 'Unknown'
  
  const now = new Date()
  const login = new Date(loginTime.value)
  const diff = now - login
  
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
})

// Methods
const formatTime = (timestamp) => {
  if (!timestamp) return 'Unknown'
  return new Date(timestamp).toLocaleString()
}

import { useAuthService } from '@/core/composables/useAuthService.js'

const changing = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordError = ref('')
const passwordSuccess = ref('')
const auth = useAuthService()

const handleChangePassword = async () => {
  passwordError.value = ''
  passwordSuccess.value = ''
  if (!currentPassword.value || !newPassword.value) {
    passwordError.value = 'Please fill all fields'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'Passwords do not match'
    return
  }
  changing.value = true
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    passwordSuccess.value = 'Password changed successfully'
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e) {
    passwordError.value = e.message || 'Failed to change password'
  } finally {
    changing.value = false
  }
}

const handleLogout = () => {
  emit('logout')
}

const updateLastActivity = () => {
  lastActivity.value = new Date()
}

// Lifecycle
onMounted(() => {
  // Update last activity every minute
  activityInterval.value = setInterval(updateLastActivity, 60000)
  
  // Track user activity
  document.addEventListener('click', updateLastActivity)
  document.addEventListener('keypress', updateLastActivity)
})

onUnmounted(() => {
  if (activityInterval.value) {
    clearInterval(activityInterval.value)
  }
  document.removeEventListener('click', updateLastActivity)
  document.removeEventListener('keypress', updateLastActivity)
})
</script>
