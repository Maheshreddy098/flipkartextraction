<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Plant Header -->
    <PlantHeader 
      :plant="plantConfig"
      :user="currentUser"
      @logout="handleLogout"
    />

    <!-- Main Content -->
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Page Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">User Profile</h1>
        <p class="text-gray-600">Manage your account and plant access</p>
      </div>

      <!-- Profile Card -->
      <div class="bg-white rounded-lg shadow p-6 mb-8">
        <div class="flex items-center space-x-6">
          <!-- Avatar -->
          <div class="flex-shrink-0">
            <div class="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center">
              <span class="text-2xl font-bold text-white">
                {{ currentUser.name?.charAt(0) || 'U' }}
              </span>
            </div>
          </div>
          
          <!-- User Info -->
          <div class="flex-1">
            <h2 class="text-2xl font-bold text-gray-900">{{ currentUser.name }}</h2>
            <p class="text-gray-600">{{ currentUser.email }}</p>
            <p class="text-sm text-gray-500 mt-1">{{ currentUser.role }}</p>
          </div>
        </div>
      </div>

      <!-- Plant Access Information -->
      <div class="bg-white rounded-lg shadow p-6 mb-8">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Plant Access</h3>
        <div class="space-y-4">
          <div class="flex items-center justify-between p-4 border rounded-lg">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                <span class="text-green-600 text-lg">🏭</span>
              </div>
              <div>
                <h4 class="font-medium text-gray-900">{{ plantConfig.name }}</h4>
                <p class="text-sm text-gray-500">{{ plantConfig.location }}</p>
              </div>
            </div>
            <div class="text-right">
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Active
              </span>
              <p class="text-sm text-gray-500 mt-1">{{ currentUser.role }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- User Permissions -->
      <div class="bg-white rounded-lg shadow p-6 mb-8">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Permissions</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="permission in userPermissions" :key="permission" class="flex items-center space-x-3">
            <div class="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center">
              <svg class="w-3 h-3 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </div>
            <span class="text-sm font-medium text-gray-900">{{ formatPermission(permission) }}</span>
          </div>
        </div>
      </div>

      <!-- Session Information -->
      <div class="bg-white rounded-lg shadow p-6 mb-8">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Session Information</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Login Time</label>
            <p class="text-sm text-gray-900">{{ formatDate(sessionInfo.loginTime) }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Session Duration</label>
            <p class="text-sm text-gray-900">{{ sessionInfo.duration }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Last Activity</label>
            <p class="text-sm text-gray-900">{{ formatDate(sessionInfo.lastActivity) }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">IP Address</label>
            <p class="text-sm text-gray-900">{{ sessionInfo.ipAddress }}</p>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Account Actions</h3>
        <div class="flex flex-col sm:flex-row gap-4">
          <button
            @click="changePassword"
            class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
          >
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            Change Password
          </button>
          
          <button
            @click="refreshSession"
            class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
          >
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh Session
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import PlantHeader from '@/shared/components/PlantHeader.vue'

const router = useRouter()
const sessionStore = useSessionStore()

// Plant configuration
const plantConfig = computed(() => ({
  id: 'malur',
  name: 'Malur Plant',
  location: 'Malur, Karnataka',
  type: 'Processing Facility'
}))

// Current user
const currentUser = computed(() => sessionStore.user)

// User permissions
const userPermissions = computed(() => sessionStore.permissions || [])

// Session information
const sessionInfo = ref({
  loginTime: new Date(),
  lastActivity: new Date(),
  duration: '1h 45m',
  ipAddress: '192.168.1.101'
})

// Methods
const handleLogout = async () => {
  await sessionStore.logout()
  router.push('/login')
}

const formatPermission = (permission) => {
  const permissionMap = {
    'dashboard': 'Dashboard Access',
    'profile': 'Profile Management',
    'grn': 'GRN Management',
    'crate': 'Crate Management',
    'production-order': 'Production Orders',
    'department': 'Department Management',
    'admin': 'Administrative Access',
    'settings': 'System Settings',
    'reports': 'Reports Access'
  }
  return permissionMap[permission] || permission
}

const formatDate = (date) => {
  if (!date) return 'N/A'
  return new Date(date).toLocaleString()
}

const changePassword = () => {
  alert('Password change functionality will be implemented')
}

const refreshSession = async () => {
  try {
    await sessionStore.refreshToken()
    alert('Session refreshed successfully')
  } catch (error) {
    alert('Failed to refresh session')
  }
}

// Initialize session info
onMounted(() => {
  const session = sessionStore.getSession()
  if (session) {
    sessionInfo.value.loginTime = session.loginTime
    sessionInfo.value.lastActivity = new Date()
  }
})
</script>
