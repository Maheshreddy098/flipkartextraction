/**
 * Malur Plant Store
 * Plant-specific state management for Malur Plant
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePlantStore = defineStore('malur-plant', () => {
  // State
  const plantId = ref('malur')
  const plantData = ref({
    id: 'malur',
    name: 'Malur Plant',
    location: 'Malur, Karnataka',
    type: 'Processing Facility',
    status: 'Active',
    established: '2019',
    capacity: '10,000L/day'
  })

  const departments = ref([
    {
      id: 1,
      name: 'Raw Material Processing',
      description: 'Initial processing of raw materials',
      icon: '🌾',
      status: 'Active',
      efficiency: 89,
      manager: 'Vikram Singh',
      employees: 10
    },
    {
      id: 2,
      name: 'Quality Control',
      description: 'Quality testing and validation',
      icon: '🔬',
      status: 'Active',
      efficiency: 92,
      manager: 'Anita Desai',
      employees: 6
    },
    {
      id: 3,
      name: 'Packaging',
      description: 'Final packaging operations',
      icon: '📦',
      status: 'Active',
      efficiency: 85,
      manager: 'Ravi Kumar',
      employees: 8
    },
    {
      id: 4,
      name: 'Storage',
      description: 'Warehouse and storage management',
      icon: '🏪',
      status: 'Active',
      efficiency: 88,
      manager: 'Sushma Reddy',
      employees: 5
    }
  ])

  const productionStats = ref({
    daily: {
      processed: '8,750L',
      packaged: '7,200L',
      quality: '95.8%',
      efficiency: '87%'
    }
  })

  // Getters
  const isActive = computed(() => plantData.value.status === 'Active')
  const totalEmployees = computed(() => 
    departments.value.reduce((total, dept) => total + dept.employees, 0)
  )

  // Actions
  const initializePlant = (plantId) => {
  }

  return {
    plantId,
    plantData,
    departments,
    productionStats,
    isActive,
    totalEmployees,
    initializePlant
  }
})
