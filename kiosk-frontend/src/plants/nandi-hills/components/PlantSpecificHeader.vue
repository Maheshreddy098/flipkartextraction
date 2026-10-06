<template>
  <div class="bg-white shadow-sm border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center py-4">
        <!-- Plant Info -->
        <div class="flex items-center space-x-4">
          <div class="flex-shrink-0">
            <div class="w-10 h-10 bg-gradient-to-r from-blue-500 to-green-500 rounded-lg flex items-center justify-center">
              <span class="text-white text-lg font-bold">🏔️</span>
            </div>
          </div>
          <div>
            <h1 class="text-xl font-bold text-gray-900">{{ plantConfig.name }}</h1>
            <p class="text-sm text-gray-500">{{ plantConfig.location }}</p>
          </div>
        </div>

        <!-- Plant Status -->
        <div class="flex items-center space-x-4">
          <div class="text-right">
            <div class="flex items-center space-x-2">
              <div class="w-2 h-2 bg-green-400 rounded-full"></div>
              <span class="text-sm font-medium text-gray-900">Operational</span>
            </div>
            <p class="text-xs text-gray-500">Efficiency: {{ plantStats.efficiency }}%</p>
          </div>
          
          <!-- Weather Info -->
          <div class="flex items-center space-x-2 text-sm text-gray-600">
            <span>{{ weather.icon }}</span>
            <span>{{ weather.temperature }}</span>
          </div>
        </div>

        <!-- User Info -->
        <div class="flex items-center space-x-4">
          <div class="text-right">
            <p class="text-sm font-medium text-gray-900">{{ currentUser.name }}</p>
            <p class="text-xs text-gray-500">{{ currentUser.role }}</p>
          </div>
          <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
            <span class="text-white text-sm font-bold">
              {{ currentUser.name?.charAt(0) || 'U' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'
import { getPlantWeather } from '../utils/plantUtils.js'

const sessionStore = useSessionStore()

// Props
const props = defineProps({
  plantConfig: {
    type: Object,
    required: true
  }
})

// Emits
const emit = defineEmits(['logout'])

// State
const weather = ref({
  temperature: '28°C',
  humidity: '65%',
  condition: 'Partly Cloudy',
  windSpeed: '12 km/h',
  icon: '⛅'
})

const plantStats = ref({
  efficiency: 91,
  production: '12,500L',
  quality: 97.2
})

// Computed
const currentUser = computed(() => sessionStore.user)

// Methods
const handleLogout = () => {
  emit('logout')
}

// Initialize
onMounted(() => {
  weather.value = getPlantWeather()
})
</script>
