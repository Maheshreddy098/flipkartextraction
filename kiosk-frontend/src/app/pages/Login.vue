<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
    <div class="max-w-md w-full">
      <!-- App Header -->
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Khanal Foods Production Kiosk Tool</h1>
      </div>

      <!-- Login Form -->
      <div class="bg-white rounded-xl shadow-lg p-8">
        <h2 class="text-2xl font-bold text-gray-900 mb-6 text-center">
          Sign In
        </h2>

        <form @submit.prevent="handleLogin" class="space-y-6">
          <!-- Email Field -->
          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 mb-2">
              Email Address
            </label>
            <input
              id="email"
              v-model="form.email"
              type="email"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors text-gray-900 placeholder-gray-400 bg-white caret-blue-600 appearance-none"
              placeholder="Enter your email"
              :disabled="loading"
            />
          </div>

          <!-- Password Field -->
          <div>
            <label for="password" class="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <div class="relative">
              <input
                id="password"
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                required
                class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors pr-12 text-gray-900 placeholder-gray-400 bg-white caret-blue-600 appearance-none"
                placeholder="Enter your password"
                :disabled="loading"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg v-if="showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                </svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </button>
            </div>
          </div>

          <!-- Plant Selector -->
          <div>
            <label for="plant" class="block text-sm font-medium text-gray-700 mb-2">
              Select Plant
            </label>
            <select
              id="plant"
              v-model="selectedPlantId"
              @change="onPlantChange"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors bg-white text-gray-900"
              required
            >
              <option value="" disabled>Select a plant</option>
              <option v-for="p in plants" :key="p.id" :value="p.id">
                {{ p.name }} — {{ p.location }}
              </option>
            </select>
          </div>

          <!-- Error Message -->
          <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4">
            <div class="flex">
              <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
              <p class="text-sm text-red-600">{{ error }}</p>
            </div>
          </div>

          <!-- Login Button -->
          <button
            type="submit"
            :disabled="loading || !form.email || !form.password || !selectedPlantId"
            class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center"
          >
            <svg v-if="loading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span v-if="loading">Signing In...</span>
            <span v-else>Sign In</span>
          </button>
        </form>

        <!-- Forgot Password -->
        <div class="mt-6 text-center">
          <button
            @click="showForgotPassword = true"
            class="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            Forgot your password?
          </button>
        </div>

        <!-- No back link when using dropdown -->
      </div>

      <!-- Forgot Password Modal -->
      <div v-if="showForgotPassword" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg p-6 max-w-md w-full">
          <h3 class="text-xl font-bold text-gray-900 mb-4">Reset Password</h3>
          <p class="text-gray-600 mb-4">
            Enter your email address and we'll send you a link to reset your password.
          </p>
          
          <form @submit.prevent="handleForgotPassword" class="space-y-4">
            <input
              v-model="forgotPasswordEmail"
              type="email"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter your email"
            />
            
            <div class="flex space-x-3">
              <button
                type="button"
                @click="showForgotPassword = false"
                class="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="loading"
                class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
              >
                Send Reset Link
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authService } from '@/core/auth/authService.js'
import { plantService } from '@/core/api/plantService.js'

// Composables
const route = useRoute()
const router = useRouter()

// Reactive data
const form = ref({
  email: '',
  password: ''
})
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const showForgotPassword = ref(false)
const forgotPasswordEmail = ref('')
const plants = ref([])
const selectedPlantId = ref('')
const selectedPlant = ref(null)

// Computed
const plantId = computed(() => route.params.plantId || selectedPlantId.value)

// Helper to sync selectedPlant object from list
function syncSelectedPlant() {
  selectedPlant.value = plants.value.find(p => p.id === plantId.value) || null
}

function onPlantChange() {
  syncSelectedPlant()
  if (selectedPlantId.value) {
    // update URL without leaving page
    const base = '/login/' + selectedPlantId.value
    if (route.params.plantId !== selectedPlantId.value) router.replace(base)
  }
}

// Methods
async function handleLogin() {
  if (loading.value) return
  
  loading.value = true
  error.value = ''

  try {
    // Authenticate with plant-specific access control
    const result = await authService.authenticate(
      form.value.email,
      form.value.password,
      plantId.value
    )

    if (result.success) {
      // Special handling for Dashboard plant - redirect to admin
      if (plantId.value === 'dashboard') {
        try {
          await router.replace('/admin')
        } catch (e) {
          window.location.href = '/kiosk/admin'
        }
      } else {
        // Navigate to plant dashboard (ensure base '/kiosk/' works as well)
        try {
          await router.replace(`/plant/${plantId.value}/dashboard`)
        } catch (e) {
          const { APP_CONFIG } = await import('@/config/constants.js')
          window.location.href = APP_CONFIG.ROUTES.plantDashboard(plantId.value)
        }
      }
    }

  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function handleForgotPassword() {
  if (!forgotPasswordEmail.value) return
  
  loading.value = true
  
  try {
    await authService.requestPasswordReset(forgotPasswordEmail.value, plantId.value)
    
    // Show success message
    alert('Password reset link sent to your email')
    showForgotPassword.value = false
    forgotPasswordEmail.value = ''
    
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

// no back link

// Lifecycle
onMounted(async () => {
  try {
    plants.value = await plantService.getPlants()
    // Dashboard plant should come from Plant doctype, no need to add hardcoded one
    // The normalizePlant function will convert "Dashboard" to "dashboard" (lowercase)
  } catch (e) {
    plants.value = []
  }

  // Determine initial selection
  if (route.params.plantId) {
    selectedPlantId.value = String(route.params.plantId)
  } else if (plants.value.length) {
    selectedPlantId.value = plants.value[0].id
  }
  syncSelectedPlant()

  sessionStorage.removeItem('selected-plant')
})
</script>

<style scoped>
/* Custom animations */
@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-form {
  animation: slideInUp 0.6s ease-out;
}
</style>
