<template>
  <div class="p-6">
    <!-- Welcome Section -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">
        Welcome to {{ plantConfig.name }}
      </h1>
      <p class="text-gray-600">
        {{ currentUser?.name }} - {{ currentUser?.role }}
      </p>
    </div>

    <!-- Quick Stats -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div v-if="statsError" class="md:col-span-2 lg:col-span-4 bg-red-50 border border-red-200 text-red-700 rounded p-3">
        {{ statsError }}
      </div>
      
      <StatsCard
        v-for="stat in statsCards"
        :key="stat.id"
        :title="stat.title"
        :value="stat.value"
        :icon="stat.icon"
        :color="stat.color"
        :loading="loadingStats"
      />
    </div>

    <!-- Quick Actions -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
      <!-- Available Features -->
      <div class="bg-white rounded-lg shadow">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-medium text-gray-900">Quick Actions</h3>
        </div>
        <div class="p-6">
          <div class="grid grid-cols-2 gap-4">
            <ActionButton
              v-for="feature in availableFeatures"
              :key="feature.id"
              :feature="feature"
              @click="navigateToFeature(feature.id)"
            />
          </div>
        </div>
      </div>

      <!-- Recent Activity -->
      <div class="bg-white rounded-lg shadow">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-medium text-gray-900">Recent Activity</h3>
        </div>
        <div class="p-6">
          <ActivityList :activities="recentActivity" />
        </div>
      </div>
    </div>

    <!-- Departments -->
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200">
        <h3 class="text-lg font-medium text-gray-900">Departments</h3>
      </div>
      <div class="p-6">
        <DepartmentGrid 
          :departments="departments" 
          @department-click="navigateToDepartment"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session.js'
import StatsCard from './StatsCard.vue'
import ActionButton from './ActionButton.vue'
import ActivityList from './ActivityList.vue'
import DepartmentGrid from './DepartmentGrid.vue'
import { usePlantData } from '@/shared/composables/usePlantData'

const props = defineProps({
  plantId: {
    type: String,
    required: true
  }
})

const router = useRouter()
const sessionStore = useSessionStore()

// Use composable for plant-specific data
const {
  plantConfig,
  stats,
  loadingStats,
  statsError,
  availableFeatures,
  recentActivity,
  departments,
  fetchPlantData
} = usePlantData(props.plantId)

const currentUser = computed(() => sessionStore.user)

const statsCards = computed(() => [
  {
    id: 'production',
    title: 'Production Today',
    value: stats.value.production,
    icon: 'factory',
    color: 'blue'
  },
  {
    id: 'quality',
    title: 'Quality Score',
    value: `${stats.value.quality}%`,
    icon: 'check-circle',
    color: 'green'
  },
  {
    id: 'efficiency',
    title: 'Efficiency',
    value: `${stats.value.efficiency}%`,
    icon: 'clock',
    color: 'yellow'
  },
  {
    id: 'orders',
    title: 'Active Orders',
    value: stats.value.orders,
    icon: 'clipboard-list',
    color: 'purple'
  }
])

const navigateToFeature = (featureId) => {
  router.push(`/plant/${props.plantId}/${featureId}`)
}

const navigateToDepartment = (departmentId) => {
  // Implement department navigation logic
}

onMounted(() => {
  fetchPlantData()
})
</script>