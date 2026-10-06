import { ref, computed } from 'vue'

// Plant configurations
const PLANT_CONFIGS = {
  'mahadevpura': {
    id: 'mahadevpura',
    name: 'Mahadevpura Plant',
    location: 'Bangalore, Karnataka',
    type: 'Primary Production Facility',
    features: ['dashboard', 'grn', 'production-order', 'quality', 'inventory-transfer']
  },
  'nandi-hills': {
    id: 'nandi-hills',
    name: 'Nandi Hills Plant',
    location: 'Kolar, Karnataka', 
    type: 'Secondary Production Facility',
    features: ['dashboard', 'grn', 'production-order', 'quality', 'inventory-transfer']
  },
  'malur': {
    id: 'malur',
    name: 'Malur Plant',
    location: 'Kolar, Karnataka',
    type: 'Secondary Production Facility', 
    features: ['dashboard', 'production-order', 'inventory-transfer']
  },
  'krishnagiri': {
    id: 'krishnagiri',
    name: 'Krishnagiri Plant',
    location: 'Krishnagiri, Tamil Nadu',
    type: 'Primary Production Facility',
    features: ['dashboard', 'grn', 'production-order', 'quality', 'inventory-transfer']
  },
  'champavath': {
    id: 'champavath', 
    name: 'Champavath Plant',
    location: 'Champavath, Karnataka',
    type: 'Secondary Production Facility',
    features: ['dashboard', 'grn', 'production-order', 'inventory-transfer']
  }
}

export function usePlantData(plantId: string) {
  const loading = ref(false)
  const error = ref('')
  const stats = ref({
    production: '-',
    quality: 0,
    efficiency: 0,
    orders: 0
  })
  const loadingStats = ref(true)
  const statsError = ref('')

  // Plant configuration
  const plantConfig = computed(() => {
    return PLANT_CONFIGS[plantId as keyof typeof PLANT_CONFIGS] || {
      id: plantId,
      name: 'Unknown Plant',
      location: 'Unknown',
      type: 'Production Facility',
      features: ['dashboard']
    }
  })

  // Available features based on plant
  const availableFeatures = computed(() => {
    const features = plantConfig.value.features
    const featureMap = {
      'dashboard': {
        id: 'dashboard',
        name: 'Dashboard',
        description: 'Overview and key metrics',
        icon: '📊'
      },
      'grn': {
        id: 'grn',
        name: 'GRN',
        description: 'Goods Receipt Note',
        icon: '📦'
      },
      'production-order': {
        id: 'production-order',
        name: 'Production Order',
        description: 'Manage production orders',
        icon: '🏭'
      },
      'quality': {
        id: 'quality',
        name: 'Quality',
        description: 'Quality control checks',
        icon: '✅'
      },
      'inventory-transfer': {
        id: 'inventory-transfer',
        name: 'Inventory Transfer',
        description: 'Transfer inventory between locations',
        icon: '📋'
      }
    }

    return features.map(feature => featureMap[feature as keyof typeof featureMap]).filter(Boolean)
  })

  // Recent activity (mock data for now)
  const recentActivity = ref([
    {
      id: 1,
      action: 'GRN #1234 created',
      time: '2 minutes ago',
      icon: '📦'
    },
    {
      id: 2,
      action: 'Quality check completed',
      time: '15 minutes ago',
      icon: '✅'
    },
    {
      id: 3,
      action: 'Production order updated',
      time: '30 minutes ago',
      icon: '🏭'
    },
    {
      id: 4,
      action: 'Inventory transfer completed',
      time: '1 hour ago',
      icon: '📋'
    }
  ])

  // Departments (mock data for now)
  const departments = ref([
    {
      id: 'production',
      name: 'Production',
      description: 'Manufacturing operations',
      icon: '🏭',
      status: 'Active',
      efficiency: 95
    },
    {
      id: 'quality',
      name: 'Quality Control',
      description: 'Quality assurance',
      icon: '✅',
      status: 'Active', 
      efficiency: 98
    },
    {
      id: 'warehouse',
      name: 'Warehouse',
      description: 'Inventory management',
      icon: '📦',
      status: 'Active',
      efficiency: 92
    },
    {
      id: 'maintenance',
      name: 'Maintenance',
      description: 'Equipment maintenance',
      icon: '🔧',
      status: 'Active',
      efficiency: 88
    }
  ])

  // Fetch plant stats
  async function fetchPlantData() {
    loading.value = true
    loadingStats.value = true
    error.value = ''
    statsError.value = ''

    try {
      // In real implementation, this would call the actual API
      // For now, we'll simulate with mock data
      await new Promise(resolve => setTimeout(resolve, 1000)) // Simulate API call

      // Mock stats based on plant
      const mockStats = {
        'mahadevpura': {
          production: '2,450 units',
          quality: 96.8,
          efficiency: 94.2,
          orders: 15
        },
        'nandi-hills': {
          production: '1,250 units', 
          quality: 97.2,
          efficiency: 91.5,
          orders: 8
        },
        'malur': {
          production: '1,850 units',
          quality: 95.5,
          efficiency: 89.3,
          orders: 12
        },
        'krishnagiri': {
          production: '2,100 units',
          quality: 98.1,
          efficiency: 92.7,
          orders: 18
        },
        'champavath': {
          production: '1,420 units',
          quality: 96.3,
          efficiency: 90.8,
          orders: 9
        }
      }

      stats.value = mockStats[plantId as keyof typeof mockStats] || {
        production: '1,000 units',
        quality: 95.0,
        efficiency: 90.0,
        orders: 5
      }

    } catch (err: any) {
      console.error('Failed to fetch plant data:', err)
      error.value = 'Failed to load plant data'
      statsError.value = 'Failed to load statistics'
    } finally {
      loading.value = false
      loadingStats.value = false
    }
  }

  return {
    loading,
    error,
    stats,
    loadingStats, 
    statsError,
    plantConfig,
    availableFeatures,
    recentActivity,
    departments,
    fetchPlantData
  }
}