<template>
  <div class="p-6">
    <h1 class="text-2xl font-semibold mb-4">Admin Dashboard</h1>
    <p class="text-gray-600 mb-6">Select a plant to enter its dashboard. Requires access for the selected plant.</p>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="plant in plants" :key="plant.id" class="border rounded-lg p-4 bg-white shadow">
        <h2 class="text-lg font-medium">{{ plant.name }}</h2>
        <p class="text-sm text-gray-500">{{ plant.location }}</p>
        <div class="mt-4 flex gap-2">
          <button @click="enterPlant(plant.id)" class="px-3 py-1.5 text-white bg-blue-600 rounded hover:bg-blue-700">Enter</button>
          <router-link :to="`/plant/${plant.id}/dashboard`" class="px-3 py-1.5 text-blue-700 bg-blue-50 rounded hover:bg-blue-100">View</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { APP_CONFIG } from '@/config/constants'
import { authService } from '@/core/auth/authService'
import { useRouter } from 'vue-router'

const router = useRouter()

const plants = computed(() => [
  { id: APP_CONFIG.PLANTS.MAHADEVPURA, name: 'Mahadevpura', location: 'Bangalore' },
  { id: APP_CONFIG.PLANTS.NANDI_HILLS, name: 'Nandi Hills', location: 'Karnataka' },
  { id: APP_CONFIG.PLANTS.MALUR, name: 'Malur', location: 'Karnataka' },
  { id: APP_CONFIG.PLANTS.KRISHNAGIRI, name: 'Krishnagiri', location: 'Tamil Nadu' },
  { id: APP_CONFIG.PLANTS.CHAMPAVATH, name: 'Champavath', location: 'Karnataka' },
  { id: APP_CONFIG.PLANTS.DASHBOARD, name: 'Dashboard', location: 'System' }
])

async function enterPlant(plantId) {
  try {
    await authService.switchPlant(plantId)
    router.push(`/plant/${plantId}/dashboard`)
  } catch (e) {
    alert(`Unable to enter plant ${plantId}: ${e?.message || e}`)
  }
}
</script>
