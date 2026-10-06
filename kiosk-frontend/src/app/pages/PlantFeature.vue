<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Plant Header -->
    <PlantHeader 
      :plant="plantConfig"
      :user="currentUser"
      @logout="handleLogout"
    />

    <!-- Main Content -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Page Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">
          {{ featureName }} - {{ plantConfig.name }}
        </h1>
        <p class="text-gray-600">{{ featureDescription }}</p>
      </div>

      <!-- Feature Content -->
      <div class="bg-white rounded-lg shadow">
        <div class="p-8 text-center">
          <div class="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <span class="text-4xl">{{ featureIcon }}</span>
          </div>
          
          <h2 class="text-2xl font-bold text-gray-900 mb-4">
            {{ featureName }}
          </h2>
          
          <p class="text-gray-600 mb-8 max-w-2xl mx-auto">
            {{ featureDescription }}
          </p>

          <!-- Feature Status -->
          <div class="mb-8">
            <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800">
              <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
              </svg>
              Coming Soon
            </span>
          </div>

          <!-- Feature Info -->
          <div class="bg-gray-50 rounded-lg p-6 mb-8">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
              <div>
                <h4 class="font-semibold text-gray-900 mb-2">Plant</h4>
                <p class="text-gray-600">{{ plantConfig.name }}</p>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-2">Feature</h4>
                <p class="text-gray-600">{{ feature }}</p>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-2">Status</h4>
                <p class="text-gray-600">In Development</p>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              @click="goBack"
              class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              Go Back to Dashboard
            </button>
            
            <button
              @click="goToDashboard"
              class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import PlantHeader from '@/shared/components/PlantHeader.vue'

// Composables
const route = useRoute()
const router = useRouter()
const sessionStore = useSessionStore()

// Reactive data
const feature = ref('')
const plantId = ref('')

// Computed
const currentUser = computed(() => sessionStore.currentUser)
const plantConfig = computed(() => sessionStore.currentPlant)

const featureName = computed(() => {
  const names = {
    'grn': 'GRN Management',
    'crate': 'Crate Assignment',
    'production-order': 'Production Order Management',
    'department': 'Department Management',
    'admin': 'Admin Dashboard',
    'settings': 'Settings'
  }
  return names[feature.value] || feature.value
})

const featureDescription = computed(() => {
  const descriptions = {
    'grn': 'Manage goods receipt notes and track incoming materials',
    'crate': 'Assign and track crates for production and shipping',
    'production-order': 'Create and manage production orders',
    'department': 'Monitor and manage department operations',
    'admin': 'Administrative functions and system management',
    'settings': 'Configure system settings and preferences'
  }
  return descriptions[feature.value] || 'Feature description not available'
})

const featureIcon = computed(() => {
  const icons = {
    'grn': '📦',
    'crate': '📋',
    'production-order': '🏭',
    'department': '🏢',
    'admin': '⚙️',
    'settings': '🔧'
  }
  return icons[feature.value] || '📄'
})

// Methods
function goBack() {
  router.back()
}

function goToDashboard() {
  // Special handling: If plant is "dashboard", go to admin
  if (plantId.value === 'dashboard') {
    router.push('/admin')
  } else {
    router.push(`/plant/${plantId.value}/dashboard`)
  }
}

async function handleLogout() {
  const { authService } = await import('@/core/auth/authService.js')
  await authService.logout()
}

// Lifecycle
onMounted(async () => {
  // Get route parameters
  feature.value = route.params.feature
  plantId.value = route.params.plantId
  
  // Special handling: If plant is "dashboard", redirect to admin
  if (plantId.value === 'dashboard') {
    router.replace('/admin')
    return
  }
})
</script>

<style scoped>
/* Custom animations */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.feature-content {
  animation: fadeInUp 0.6s ease-out;
}
</style>
