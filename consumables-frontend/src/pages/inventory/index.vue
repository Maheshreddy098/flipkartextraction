<template>
  <div class="p-4 sm:p-6">
    <h1 class="mb-2 text-xl font-bold text-gray-900 sm:text-2xl">Inventory</h1>
    <p class="mb-5 text-sm text-gray-500 sm:mb-6 sm:text-base">Choose a plant to view warehouses and stock.</p>

    <div v-if="authStore.isSuperAdmin && plants.length" class="mb-5">
      <p class="text-sm font-medium text-gray-700 mb-2">Select Plant</p>
      <select
        v-model="selectedPlant"
        class="w-full sm:w-80 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-800"
      >
        <option :value="SELECT_ALL_PLANTS" class="text-gray-800 bg-white">
          Select all
        </option>
        <option
          v-for="plant in plants"
          :key="plant.plant_code"
          :value="plant.plant_code"
          class="text-gray-800 bg-white"
        >
          {{ plant.plant_code }} - {{ plant.plant_name }}
        </option>
      </select>
    </div>

    <div v-if="visiblePlants.length" class="grid gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="plant in visiblePlants"
        :key="plant.plant_code"
        class="rounded-xl border border-gray-200 bg-white p-4 transition hover:border-blue-400 hover:shadow-sm sm:p-5"
      >
        <RouterLink :to="`/inventory/${plant.plant_code}`" class="block">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="text-base font-semibold text-gray-900">
                {{ plant.plant_name }} · {{ plant.plant_code }}
              </h3>
              <p class="text-xs text-gray-500 mt-1">Live warehouse summary</p>
            </div>
          </div>

          <div v-if="loadingByPlant[plant.plant_code]" class="mt-4 space-y-2">
            <div class="h-3 w-32 bg-gray-200 rounded animate-pulse" />
            <div class="h-3 w-24 bg-gray-200 rounded animate-pulse" />
          </div>
          <div v-else class="mt-4 grid grid-cols-2 gap-2 text-sm text-gray-700">
            <div>Warehouses: {{ summaryFor(plant.plant_code).warehouseCount }}</div>
            <div>Items: {{ summaryFor(plant.plant_code).itemCount }}</div>
          </div>

          <div class="mt-3 text-sm font-medium text-teal-600">View inventory →</div>
        </RouterLink>
      </div>
    </div>
    <div v-else class="rounded-xl border border-gray-200 bg-white p-4 text-gray-500">
      No plants assigned to your account.
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useInventoryStore } from '@/stores/inventory.js'
const SELECT_ALL_PLANTS = '__all__'
const authStore = useAuthStore()
const inventoryStore = useInventoryStore()

const plants = computed(() => authStore.sourcePlants || authStore.plants || [])
const selectedPlant = ref('')
const loadingByPlant = ref({})
const plantSummaries = ref({})

const visiblePlants = computed(() => {
  if (!plants.value.length) return []
  if (!authStore.isSuperAdmin) return plants.value
  if (!selectedPlant.value || selectedPlant.value === SELECT_ALL_PLANTS) return plants.value
  return plants.value.filter(p => p.plant_code === selectedPlant.value)
})

function summaryFor(plantCode) {
  return plantSummaries.value[plantCode] || { warehouseCount: 0, itemCount: 0 }
}

async function loadPlantSummary(plantCode) {
  loadingByPlant.value[plantCode] = true
  try {
    const warehouses = await inventoryStore.fetchWarehouses(plantCode)
    const warehouseCount = warehouses.length
    const itemCount = warehouses.reduce((sum, w) => sum + Number(w.item_count || 0), 0)
    plantSummaries.value[plantCode] = { warehouseCount, itemCount }
  } catch {
    plantSummaries.value[plantCode] = { warehouseCount: 0, itemCount: 0 }
  } finally {
    loadingByPlant.value[plantCode] = false
  }
}

async function loadAllSummaries() {
  const codes = visiblePlants.value.map(p => p.plant_code)
  await Promise.all(codes.map(code => loadPlantSummary(code)))
}

watch(plants, nextPlants => {
  if (authStore.isSuperAdmin && !selectedPlant.value && nextPlants.length) {
    selectedPlant.value = SELECT_ALL_PLANTS
  }
}, { immediate: true })

watch(visiblePlants, () => {
  loadAllSummaries()
}, { immediate: true })

onMounted(loadAllSummaries)
</script>
