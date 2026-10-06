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
        <p class="text-gray-600">Manage your account settings and preferences</p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Profile Information -->
        <div class="lg:col-span-2 space-y-6">
          <!-- User Information Card -->
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-medium text-gray-900">User Information</h3>
            </div>
            <div class="p-6">
              <div class="flex items-center space-x-6">
                <!-- Avatar -->
                <div class="flex-shrink-0">
                  <div class="w-20 h-20 bg-blue-500 rounded-full flex items-center justify-center">
                    <span class="text-white text-2xl font-bold">
                      {{ currentUser.name?.charAt(0) || 'U' }}
                    </span>
                  </div>
                </div>
                
                <!-- User Details -->
                <div class="flex-1">
                  <h4 class="text-xl font-semibold text-gray-900">{{ currentUser.name }}</h4>
                  <p class="text-gray-600">{{ currentUser.email }}</p>
                  <p class="text-sm text-gray-500">{{ currentUser.role }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Plant Access Information -->
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-medium text-gray-900">Plant Access</h3>
            </div>
            <div class="p-6">
              <div class="flex items-center space-x-4">
                <div class="text-4xl">{{ plantConfig.icon }}</div>
                <div>
                  <h4 class="text-lg font-semibold text-gray-900">{{ plantConfig.name }}</h4>
                  <p class="text-gray-600">{{ plantConfig.location }}</p>
                  <p class="text-sm text-gray-500">{{ plantConfig.type }}</p>
                </div>
              </div>
              
              <!-- Permissions -->
              <div class="mt-6">
                <h5 class="text-sm font-medium text-gray-700 mb-3">Your Permissions</h5>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="permission in userPermissions"
                    :key="permission"
                    class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800"
                  >
                    {{ formatPermission(permission) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Session Information -->
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-medium text-gray-900">Session Information</h3>
            </div>
            <div class="p-6">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p class="text-sm font-medium text-gray-500">Login Time</p>
                  <p class="text-gray-900">{{ formatDateTime(sessionInfo.loginTime) }}</p>
                </div>
                <div>
                  <p class="text-sm font-medium text-gray-500">Session Duration</p>
                  <p class="text-gray-900">{{ formatDuration(sessionInfo.sessionDuration) }}</p>
                </div>
                <div>
                  <p class="text-sm font-medium text-gray-500">Last Activity</p>
                  <p class="text-gray-900">{{ formatDateTime(sessionInfo.lastActivity) }}</p>
                </div>
                <div>
                  <p class="text-sm font-medium text-gray-500">Session Status</p>
                  <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                        :class="sessionInfo.isSessionValid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
                    {{ sessionInfo.isSessionValid ? 'Active' : 'Expired' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Sidebar -->
        <div class="space-y-6">
          <!-- Password Change Card -->
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-medium text-gray-900">Change Password</h3>
            </div>
            <div class="p-6">
              <form @submit.prevent="handlePasswordChange" class="space-y-4">
                <div>
                  <label for="currentPassword" class="block text-sm font-medium text-gray-700 mb-1">
                    Current Password
                  </label>
                  <input
                    id="currentPassword"
                    v-model="passwordForm.currentPassword"
                    type="password"
                    required
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    :disabled="passwordLoading"
                  />
                </div>
                
                <div>
                  <label for="newPassword" class="block text-sm font-medium text-gray-700 mb-1">
                    New Password
                  </label>
                  <input
                    id="newPassword"
                    v-model="passwordForm.newPassword"
                    type="password"
                    required
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    :disabled="passwordLoading"
                  />
                </div>
                
                <div>
                  <label for="confirmPassword" class="block text-sm font-medium text-gray-700 mb-1">
                    Confirm New Password
                  </label>
                  <input
                    id="confirmPassword"
                    v-model="passwordForm.confirmPassword"
                    type="password"
                    required
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    :disabled="passwordLoading"
                  />
                </div>

                <!-- Error Message -->
                <div v-if="passwordError" class="bg-red-50 border border-red-200 rounded-md p-3">
                  <p class="text-sm text-red-600">{{ passwordError }}</p>
                </div>

                <!-- Success Message -->
                <div v-if="passwordSuccess" class="bg-green-50 border border-green-200 rounded-md p-3">
                  <p class="text-sm text-green-600">{{ passwordSuccess }}</p>
                </div>

                <button
                  type="submit"
                  :disabled="passwordLoading || !isPasswordFormValid"
                  class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded-md transition-colors"
                >
                  <span v-if="passwordLoading">Changing...</span>
                  <span v-else>Change Password</span>
                </button>
              </form>
            </div>
          </div>

          <!-- Quick Actions -->
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-medium text-gray-900">Quick Actions</h3>
            </div>
            <div class="p-6 space-y-3">
              <button
                @click="refreshSession"
                class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-md transition-colors"
              >
                🔄 Refresh Session
              </button>
              <button
                @click="viewActivityLog"
                class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-md transition-colors"
              >
                📊 View Activity Log
              </button>
              <button
                @click="exportData"
                class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-md transition-colors"
              >
                📥 Export Data
              </button>
            </div>
          </div>

          <!-- System Information -->
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-medium text-gray-900">System Info</h3>
            </div>
            <div class="p-6 space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-500">App Version:</span>
                <span class="text-gray-900">1.0.0</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Browser:</span>
                <span class="text-gray-900">{{ systemInfo.browser }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Screen:</span>
                <span class="text-gray-900">{{ systemInfo.screen }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Last Update:</span>
                <span class="text-gray-900">{{ systemInfo.lastUpdate }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import { authService } from '@/core/auth/authService.js'
import PlantHeader from '@/shared/components/PlantHeader.vue'

// Composables
const router = useRouter()
const sessionStore = useSessionStore()

// Reactive data
const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const passwordLoading = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')

// Computed
const currentUser = computed(() => sessionStore.currentUser)
const plantConfig = computed(() => sessionStore.currentPlant)
const userPermissions = computed(() => sessionStore.userPermissions)
const sessionInfo = computed(() => sessionStore.getSessionInfo())

const isPasswordFormValid = computed(() => {
  return passwordForm.value.currentPassword &&
         passwordForm.value.newPassword &&
         passwordForm.value.confirmPassword &&
         passwordForm.value.newPassword === passwordForm.value.confirmPassword &&
         passwordForm.value.newPassword.length >= 8
})

const systemInfo = computed(() => ({
  browser: navigator.userAgent.split(' ').slice(-2).join(' '),
  screen: `${screen.width}x${screen.height}`,
  lastUpdate: new Date().toLocaleDateString()
}))

// Methods
async function handlePasswordChange() {
  if (!isPasswordFormValid.value) return
  
  passwordLoading.value = true
  passwordError.value = ''
  passwordSuccess.value = ''

  try {
    await authService.changePassword(
      passwordForm.value.currentPassword,
      passwordForm.value.newPassword
    )

    passwordSuccess.value = 'Password changed successfully!'
    passwordForm.value = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    }

    // Log password change
      user: currentUser.value.email,
      plant: plantConfig.value.id
    })

  } catch (error) {
    passwordError.value = error.message
    
    // Log failed password change
      user: currentUser.value.email,
      plant: plantConfig.value.id,
      error: error.message
    })
  } finally {
    passwordLoading.value = false
  }
}

async function refreshSession() {
  try {
    await authService.refreshToken()
    passwordSuccess.value = 'Session refreshed successfully!'
    
    // Log session refresh
      user: currentUser.value.email,
      plant: plantConfig.value.id
    })
  } catch (error) {
    passwordError.value = 'Failed to refresh session'
  }
}

function viewActivityLog() {
  // Navigate to activity log page
  router.push(`/plant/${plantConfig.value.id}/activity-log`)
}

async function exportData() {
  try {
    // Export user data
    const data = {
      user: currentUser.value,
      plant: plantConfig.value,
      session: sessionInfo.value,
      exportDate: new Date().toISOString()
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `user-data-${currentUser.value.email}-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)

    // Log data export
      user: currentUser.value.email,
      plant: plantConfig.value.id
    })

  } catch (error) {
    passwordError.value = 'Failed to export data'
  }
}

async function handleLogout() {
  await authService.logout()
}

function formatPermission(permission) {
  return permission.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

function formatDateTime(timestamp) {
  if (!timestamp) return 'N/A'
  return new Date(timestamp).toLocaleString()
}

function formatDuration(duration) {
  if (!duration) return 'N/A'
  
  const hours = Math.floor(duration / (1000 * 60 * 60))
  const minutes = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60))
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

// Lifecycle
onMounted(async () => {
  // Log page view
  
  // Start page tracking
})
</script>

<style scoped>
/* Custom animations */
@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.profile-card {
  animation: slideInUp 0.6s ease-out;
}
</style>
