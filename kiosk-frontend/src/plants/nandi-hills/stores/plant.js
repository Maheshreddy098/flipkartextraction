/**
 * Nandi Hills Plant Store
 * Plant-specific state management for Nandi Hills Plant
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'

export const usePlantStore = defineStore('nandi-hills-plant', () => {
  // State
  const plantId = ref('nandi-hills')
  const plantData = ref({
    id: 'nandi-hills',
    name: 'Nandi Hills Plant',
    location: 'Kolar, Karnataka',
    type: 'Secondary Production Facility',
    status: 'Active',
    established: '2020',
    capacity: '15,000L/day'
  })

  const departments = ref([
    {
      id: 1,
      name: 'Milk Processing',
      description: 'Primary milk processing operations',
      icon: '🥛',
      status: 'Active',
      efficiency: 94,
      manager: 'Rajesh Kumar',
      employees: 12
    },
    {
      id: 2,
      name: 'Yogurt Production',
      description: 'Yogurt manufacturing and packaging',
      icon: '🍶',
      status: 'Active',
      efficiency: 89,
      manager: 'Priya Sharma',
      employees: 8
    },
    {
      id: 3,
      name: 'Cheese Making',
      description: 'Artisan cheese production',
      icon: '🧀',
      status: 'Active',
      efficiency: 93,
      manager: 'Amit Patel',
      employees: 6
    },
    {
      id: 4,
      name: 'Packaging',
      description: 'Final packaging and quality control',
      icon: '📦',
      status: 'Active',
      efficiency: 96,
      manager: 'Sunita Reddy',
      employees: 10
    }
  ])

  const productionStats = ref({
    daily: {
      milk: '12,500L',
      yogurt: '8,200L',
      cheese: '450kg',
      packaging: '2,100 units'
    },
    weekly: {
      milk: '87,500L',
      yogurt: '57,400L',
      cheese: '3,150kg',
      packaging: '14,700 units'
    },
    monthly: {
      milk: '375,000L',
      yogurt: '246,000L',
      cheese: '13,500kg',
      packaging: '63,000 units'
    }
  })

  const qualityMetrics = ref({
    overall: 97.2,
    milk: 98.1,
    yogurt: 96.8,
    cheese: 97.5,
    packaging: 98.0
  })

  const equipment = ref([
    {
      id: 1,
      name: 'Milk Pasteurizer #1',
      type: 'Pasteurization',
      status: 'Operational',
      efficiency: 95,
      lastMaintenance: '2024-01-15',
      nextMaintenance: '2024-02-15'
    },
    {
      id: 2,
      name: 'Yogurt Incubator #2',
      type: 'Incubation',
      status: 'Operational',
      efficiency: 92,
      lastMaintenance: '2024-01-10',
      nextMaintenance: '2024-02-10'
    },
    {
      id: 3,
      name: 'Cheese Press #1',
      type: 'Pressing',
      status: 'Operational',
      efficiency: 88,
      lastMaintenance: '2024-01-20',
      nextMaintenance: '2024-02-20'
    },
    {
      id: 4,
      name: 'Packaging Line #1',
      type: 'Packaging',
      status: 'Operational',
      efficiency: 96,
      lastMaintenance: '2024-01-12',
      nextMaintenance: '2024-02-12'
    }
  ])

  const recentActivities = ref([
    {
      id: 1,
      type: 'production',
      title: 'Daily production target achieved',
      description: 'Milk processing completed 12,500L',
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
      user: 'Rajesh Kumar',
      department: 'Milk Processing'
    },
    {
      id: 2,
      type: 'quality',
      title: 'Quality check passed',
      description: 'All products meet quality standards',
      timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), // 4 hours ago
      user: 'Priya Sharma',
      department: 'Quality Control'
    },
    {
      id: 3,
      type: 'maintenance',
      title: 'Equipment maintenance completed',
      description: 'Cheese Press #1 maintenance completed',
      timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000), // 6 hours ago
      user: 'Amit Patel',
      department: 'Maintenance'
    }
  ])

  // Getters
  const isActive = computed(() => plantData.value.status === 'Active')
  
  const totalEmployees = computed(() => 
    departments.value.reduce((total, dept) => total + dept.employees, 0)
  )

  const averageEfficiency = computed(() => 
    departments.value.reduce((total, dept) => total + dept.efficiency, 0) / departments.value.length
  )

  const activeDepartments = computed(() => 
    departments.value.filter(dept => dept.status === 'Active')
  )

  const operationalEquipment = computed(() => 
    equipment.value.filter(eq => eq.status === 'Operational')
  )

  // Actions
  const initializePlant = (plantId) => {
    // Load plant-specific data
    loadPlantData()
    loadProductionStats()
    loadQualityMetrics()
  }

  const loadPlantData = async () => {
    try {
      // In a real application, this would fetch from API
    } catch (error) {
      console.error('Error loading plant data:', error)
    }
  }

  const loadProductionStats = async () => {
    try {
      // In a real application, this would fetch from API
    } catch (error) {
      console.error('Error loading production stats:', error)
    }
  }

  const loadQualityMetrics = async () => {
    try {
      // In a real application, this would fetch from API
    } catch (error) {
      console.error('Error loading quality metrics:', error)
    }
  }

  const updateDepartmentEfficiency = (departmentId, efficiency) => {
    const department = departments.value.find(dept => dept.id === departmentId)
    if (department) {
      department.efficiency = efficiency
    }
  }

  const addActivity = (activity) => {
    recentActivities.value.unshift({
      id: Date.now(),
      timestamp: new Date(),
      ...activity
    })
    
    // Keep only last 50 activities
    if (recentActivities.value.length > 50) {
      recentActivities.value = recentActivities.value.slice(0, 50)
    }
  }

  const updateEquipmentStatus = (equipmentId, status) => {
    const equipmentItem = equipment.value.find(eq => eq.id === equipmentId)
    if (equipmentItem) {
      equipmentItem.status = status
    }
  }

  const getDepartmentById = (id) => {
    return departments.value.find(dept => dept.id === id)
  }

  const getEquipmentById = (id) => {
    return equipment.value.find(eq => eq.id === id)
  }

  return {
    // State
    plantId,
    plantData,
    departments,
    productionStats,
    qualityMetrics,
    equipment,
    recentActivities,

    // Getters
    isActive,
    totalEmployees,
    averageEfficiency,
    activeDepartments,
    operationalEquipment,

    // Actions
    initializePlant,
    loadPlantData,
    loadProductionStats,
    loadQualityMetrics,
    updateDepartmentEfficiency,
    addActivity,
    updateEquipmentStatus,
    getDepartmentById,
    getEquipmentById
  }
})
