/**
 * Main Router Configuration
 * Handles plant-specific routing with authentication guards
 */

import { createRouter, createWebHistory } from 'vue-router'
import { useSessionStore } from './core/stores/session.js'
import { APP_CONFIG } from '@/config/constants.js'

// Import pages
import Login from './app/pages/Login.vue'
import NotFound from './app/pages/NotFound.vue'
import Unauthorized from './app/pages/Unauthorized.vue'
import PlantFeature from './app/pages/PlantFeature.vue'
import ResetPassword from './app/pages/ResetPassword.vue'
const BatchNumberGenerator = () => import('./pages/BatchNumberGenerator.vue')

// Plant-specific layouts (lazy loaded)
const MahadevpuraLayout = () => import('./plants/mahadevpura/layouts/PlantLayout.vue')
const NandiHillsLayout = () => import('./plants/nandi-hills/layouts/PlantLayout.vue')
const MalurLayout = () => import('./plants/malur/layouts/PlantLayout.vue')
const KrishnagiriLayout = () => import('./plants/krishnagiri/layouts/PlantLayout.vue')
const ChampavathLayout = () => import('./plants/champavath/layouts/PlantLayout.vue')

// Plant-specific pages (lazy loaded)
const MahadevpuraDashboard = () => import('./plants/mahadevpura/pages/Dashboard.vue')
const MahadevpuraGRN = () => import('./plants/mahadevpura/pages/GRN.vue')
const MahadevpuraProductionOrder = () => import('./plants/mahadevpura/pages/ProductionOrder.vue')
const MahadevpuraQuality = () => import('./plants/mahadevpura/pages/Quality.vue')
const MahadevpuraInventoryTransfer = () => import('./plants/mahadevpura/pages/InventoryTransfer.vue')

const NandiHillsDashboard = () => import('./plants/nandi-hills/pages/Dashboard.vue')
const NandiHillsGRN = () => import('./plants/nandi-hills/pages/GRN.vue')
const NandiHillsProductionOrder = () => import('./plants/nandi-hills/pages/ProductionOrder.vue')
const NandiHillsQuality = () => import('./plants/nandi-hills/pages/Quality.vue')
const NandiHillsInventoryTransfer = () => import('./plants/nandi-hills/pages/InventoryTransfer.vue')
const NandiHillsDisassembly = () => import('./plants/nandi-hills/pages/Disassembly.vue')

const MalurDashboard = () => import('./plants/malur/pages/Dashboard.vue')
const MalurGRN = () => import('./plants/malur/pages/GRN.vue')
const MalurProductionOrder = () => import('./plants/malur/pages/ProductionOrder.vue')
const MalurInventoryTransfer = () => import('./plants/malur/pages/InventoryTransfer.vue')

const KrishnagiriDashboard = () => import('./plants/krishnagiri/pages/Dashboard.vue')
const KrishnagiriGRN = () => import('./plants/krishnagiri/pages/GRN.vue')
const KrishnagiriProductionOrder = () => import('./plants/krishnagiri/pages/ProductionOrder.vue')
const KrishnagiriQuality = () => import('./plants/krishnagiri/pages/Quality.vue')
const KrishnagiriInventoryTransfer = () => import('./plants/krishnagiri/pages/InventoryTransfer.vue')

const ChampavathDashboard = () => import('./plants/champavath/pages/Dashboard.vue')
const ChampavathGRN = () => import('./plants/champavath/pages/GRN.vue')
const ChampavathProductionOrder = () => import('./plants/champavath/pages/ProductionOrder.vue')
const ChampavathInventoryTransfer = () => import('./plants/champavath/pages/InventoryTransfer.vue')

const routes = [
  // Root redirect
  {
    path: '/',
    redirect: '/login',
    name: 'Root'
  },


  // Plant-specific Login
  {
    path: '/login/:plantId',
    name: 'Login',
    component: Login,
    meta: {
      title: 'Login',
      requiresAuth: false,
      layout: 'public'
    }
  },

  // Generic Login (with plant dropdown)
  {
    path: '/login',
    name: 'LoginGeneric',
    component: Login,
    meta: {
      title: 'Login',
      requiresAuth: false,
      layout: 'public'
    }
  },

  // Reset Password (public)
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: ResetPassword,
    meta: {
      title: 'Reset Password',
      requiresAuth: false,
      layout: 'public'
    }
  },


  // Mahadevpura Plant Routes
  {
    path: '/plant/mahadevpura',
    component: MahadevpuraLayout,
    meta: {
      requiresAuth: true,
      requiresPlant: 'mahadevpura'
    },
    children: [
      {
        path: '',
        redirect: 'dashboard',
        name: 'MahadevpuraRoot'
      },
      {
        path: 'dashboard',
        name: 'MahadevpuraDashboard',
        component: MahadevpuraDashboard,
        meta: {
          title: 'Dashboard - Mahadevpura'
        }
      },
      {
        path: 'grn',
        name: 'MahadevpuraGRN',
        component: MahadevpuraGRN,
        meta: {
          title: 'GRN - Mahadevpura'
        }
      },
      {
        path: 'production-order',
        name: 'MahadevpuraProductionOrder',
        component: MahadevpuraProductionOrder,
        meta: {
          title: 'Production Order - Mahadevpura'
        }
      },
      {
        path: 'quality',
        name: 'MahadevpuraQuality',
        component: MahadevpuraQuality,
        meta: {
          title: 'Quality - Mahadevpura'
        }
      },
      {
        path: 'inventory-transfer',
        name: 'MahadevpuraInventoryTransfer',
        component: MahadevpuraInventoryTransfer,
        meta: {
          title: 'Inventory Transfer - Mahadevpura'
        }
      },
    ]
  },

  // Nandi Hills Plant Routes (accepts both nandihills and nandi-hills)
  {
    path: '/plant/:nandiPlantId(nandihills|nandi-hills)',
    component: NandiHillsLayout,
    meta: {
      requiresAuth: true,
      requiresPlant: 'nandihills'  // Must match normalized plant ID from database
    },
    children: [
      {
        path: '',
        redirect: 'dashboard',
        name: 'NandiHillsRoot'
      },
      {
        path: 'dashboard',
        name: 'NandiHillsDashboard',
        component: NandiHillsDashboard,
        meta: {
          title: 'Dashboard - Nandi Hills'
        }
      },
      {
        path: 'grn',
        name: 'NandiHillsGRN',
        component: NandiHillsGRN,
        meta: {
          title: 'GRN - Nandi Hills'
        }
      },
      {
        path: 'production-order',
        name: 'NandiHillsProductionOrder',
        component: NandiHillsProductionOrder,
        meta: {
          title: 'Production Order - Nandi Hills'
        }
      },
      {
        path: 'quality',
        name: 'NandiHillsQuality',
        component: NandiHillsQuality,
        meta: {
          title: 'Quality - Nandi Hills'
        }
      },
      {
        path: 'inventory-transfer',
        name: 'NandiHillsInventoryTransfer',
        component: NandiHillsInventoryTransfer,
        meta: {
          title: 'Inventory Transfer - Nandi Hills'
        }
      },
      {
        path: 'disassembly',
        name: 'NandiHillsDisassembly',
        component: NandiHillsDisassembly,
        meta: {
          title: 'Disassembly Report - Nandi Hills'
        }
      },
    ]
  },

  // Malur Plant Routes
  {
    path: '/plant/malur',
    component: MalurLayout,
    meta: {
      requiresAuth: true,
      requiresPlant: 'malur'
    },
    children: [
      {
        path: '',
        redirect: 'dashboard',
        name: 'MalurRoot'
      },
      {
        path: 'dashboard',
        name: 'MalurDashboard',
        component: MalurDashboard,
        meta: {
          title: 'Dashboard - Malur'
        }
      },
      {
        path: 'grn',
        name: 'MalurGRN',
        component: MalurGRN,
        meta: {
          title: 'GRN - Malur'
        }
      },
      {
        path: 'production-order',
        name: 'MalurProductionOrder',
        component: MalurProductionOrder,
        meta: {
          title: 'Production Order - Malur'
        }
      },
      {
        path: 'inventory-transfer',
        name: 'MalurInventoryTransfer',
        component: MalurInventoryTransfer,
        meta: {
          title: 'Inventory Transfer - Malur'
        }
      },
    ]
  },

  // Krishnagiri Plant Routes
  {
    path: '/plant/krishnagiri',
    component: KrishnagiriLayout,
    meta: {
      requiresAuth: true,
      requiresPlant: 'krishnagiri'
    },
    children: [
      {
        path: '',
        redirect: 'dashboard',
        name: 'KrishnagiriRoot'
      },
      {
        path: 'dashboard',
        name: 'KrishnagiriDashboard',
        component: KrishnagiriDashboard,
        meta: {
          title: 'Dashboard - Krishnagiri'
        }
      },
      {
        path: 'grn',
        name: 'KrishnagiriGRN',
        component: KrishnagiriGRN,
        meta: {
          title: 'GRN - Krishnagiri'
        }
      },
      {
        path: 'production-order',
        name: 'KrishnagiriProductionOrder',
        component: KrishnagiriProductionOrder,
        meta: {
          title: 'Production Order - Krishnagiri'
        }
      },
      {
        path: 'quality',
        name: 'KrishnagiriQuality',
        component: KrishnagiriQuality,
        meta: {
          title: 'Quality - Krishnagiri'
        }
      },
      {
        path: 'inventory-transfer',
        name: 'KrishnagiriInventoryTransfer',
        component: KrishnagiriInventoryTransfer,
        meta: {
          title: 'Inventory Transfer - Krishnagiri'
        }
      },
    ]
  },

  // Champavath Plant Routes
  {
    path: '/plant/champavath',
    component: ChampavathLayout,
    meta: {
      requiresAuth: true,
      requiresPlant: 'champavath'
    },
    children: [
      {
        path: '',
        redirect: 'dashboard',
        name: 'ChampavathRoot'
      },
      {
        path: 'dashboard',
        name: 'ChampavathDashboard',
        component: ChampavathDashboard,
        meta: {
          title: 'Dashboard - Champavath'
        }
      },
      {
        path: 'grn',
        name: 'ChampavathGRN',
        component: ChampavathGRN,
        meta: {
          title: 'GRN - Champavath'
        }
      },
      {
        path: 'production-order',
        name: 'ChampavathProductionOrder',
        component: ChampavathProductionOrder,
        meta: {
          title: 'Production Order - Champavath'
        }
      },
      {
        path: 'inventory-transfer',
        name: 'ChampavathInventoryTransfer',
        component: ChampavathInventoryTransfer,
        meta: {
          title: 'Inventory Transfer - Champavath'
        }
      },
    ]
  },

  // Dynamic plant feature routes
  {
    path: '/plant/:plantId/:feature',
    name: 'PlantFeature',
    component: () => import('./app/pages/PlantFeature.vue'),
    meta: {
      title: 'Plant Feature',
      requiresAuth: true,
      requiresPlant: true,
      layout: 'plant'
    },
    beforeEnter: (to, from, next) => {
      // Special handling: Redirect dashboard plant to admin
      if (to.params.plantId === 'dashboard') {
        next('/admin')
      } else {
        next()
      }
    }
  },

  // Batch Number Generator (global access, requires auth)
  {
    path: '/batch-generator',
    name: 'BatchNumberGenerator',
    component: BatchNumberGenerator,
    meta: {
      title: 'Batch Number Generator',
      requiresAuth: true
    }
  },

  // Ghee Reverse Production Order (KhanalFoods team, not plant-specific)
  {
    path: '/ghee-production-order',
    component: () => import('./ghee/layouts/GheeLayout.vue'),
    meta: {
      requiresFrappeAuth: true,
      layout: 'ghee'
    },
    children: [
      {
        path: '',
        name: 'GheeProductionDashboard',
        component: () => import('./ghee/pages/ProductionDashboard.vue'),
        meta: {
          title: 'Ghee Production Dashboard',
          requiresFrappeAuth: true
        }
      },
      {
        path: 'new',
        name: 'GheeProductionOrder',
        component: () => import('./ghee/pages/ProductionOrder.vue'),
        meta: {
          title: 'Ghee Production Order',
          requiresFrappeAuth: true
        }
      },
      {
        path: ':name',
        name: 'GheeProductionOrderDetail',
        component: () => import('./ghee/pages/ProductionOrderDetail.vue'),
        meta: {
          title: 'Ghee Production Order Detail',
          requiresFrappeAuth: true
        }
      }
    ]
  },

  // Admin routes with layout wrapper
  {
    path: '/admin',
    component: () => import('./admin/layouts/AdminLayout.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin'
    },
    children: [
      {
        path: '',
        name: 'AdminDashboard',
        component: () => import('./admin/pages/AdminDashboard.vue'),
        meta: {
          title: 'Admin Dashboard',
          requiresAuth: true,
          requiresAdmin: true,
          layout: 'admin'
        }
      },
      {
        path: 'avalara-dashboard',
        name: 'AvalaraDashboard',
        component: () => import('./admin/pages/AvalaraDashboard.vue'),
        meta: {
          title: 'Avalara Dashboard',
          requiresAuth: true,
          requiresAdmin: true,
          layout: 'admin'
        }
      },
      {
        path: 'unicommerce-dashboard',
        name: 'UnicommerceDashboard',
        component: () => import('./admin/pages/UnicommerceDashboard.vue'),
        meta: {
          title: 'Unicommerce Dashboard',
          requiresAuth: true,
          requiresAdmin: true,
          layout: 'admin'
        }
      },
      {
        path: 'logistics-dashboard',
        name: 'LogisticsDashboard',
        component: () => import('./admin/pages/LogisticsDashboard.vue'),
        meta: {
          title: 'POD Dashboard',
          requiresAuth: true,
          requiresAdmin: true,
          layout: 'admin'
        }
      },
      {
        path: 'vendor-master-dashboard',
        name: 'VendorMasterDashboard',
        component: () => import('./admin/pages/VendorMasterDashboard.vue'),
        meta: {
          title: 'Vendor Master Dashboard',
          requiresAuth: true,
          requiresAdmin: true,
          layout: 'admin'
        }
      }
    ]
  },

  // Error pages
  {
    path: '/unauthorized',
    name: 'Unauthorized',
    component: Unauthorized,
    meta: {
      title: 'Access Denied',
      requiresAuth: false,
      layout: 'public'
    }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound,
    meta: {
      title: 'Page Not Found',
      requiresAuth: false,
      layout: 'public'
    }
  }
]

const router = createRouter({
  history: createWebHistory(APP_CONFIG.BASE_PATH + '/'),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // Always scroll to top for kiosk
    return { top: 0, left: 0 }
  }
})

// Navigation guards
router.beforeEach((to, from, next) => {
  const sessionStore = useSessionStore()

  // Update page title
  if (to.meta.title) {
    document.title = `${to.meta.title} - Khanal Foods Kiosk`
  }

  // Frappe-auth routes (ghee, etc.): only need Frappe session, not kiosk plant session
  if (to.meta.requiresFrappeAuth) {
    const frappeUser = (window.session_user) ||
                       (window.boot && window.boot.session_user) || ''
    if (!frappeUser || frappeUser === 'Guest') {
      window.location.href = '/login?redirect-to=' + encodeURIComponent(window.location.pathname)
      return false
    }
    return next()
  }

  // Check authentication
  if (to.meta.requiresAuth) {
    // Initialize session from storage if not already done
    if (!sessionStore.isAuthenticated) {
      const hasValidSession = sessionStore.initializeFromStorage()
      if (!hasValidSession) {
        // no valid session
        return next({ name: 'LoginGeneric' })
      }
    }

    // Verify session is still valid
    if (!sessionStore.isSessionValid) {
      sessionStore.clearSession()
      return next({ name: 'LoginGeneric' })
    }
  }

  // Admin-only routes
  if (to.meta.requiresAdmin) {
    const session = sessionStore.getSession()
    if (!session) {
      return next({ name: 'LoginGeneric' })
    }
    // Admin if has 'admin' permission for current plant, or role present
    const hasAdminPerm = Array.isArray(session?.plant?.permissions) && session.plant.permissions.includes('admin')
    const userRoles = Array.isArray(session?.user?.roles) ? session.user.roles : []
    const hasAdminRole = userRoles.includes('System Administrator') || 
                        userRoles.includes('Administrator') || 
                        userRoles.includes('System Manager')
    if (!hasAdminPerm && !hasAdminRole) {
      return next({ name: 'Unauthorized' })
    }
  }

  // Check plant-specific access
  if (to.meta.requiresPlant) {
    const session = sessionStore.getSession()

    if (!session) {
      // no session
      return next({ name: 'LoginGeneric' })
    }

    // Check specific plant requirement
    if (typeof to.meta.requiresPlant === 'string') {
      if (session.plant.id !== to.meta.requiresPlant) {
        // wrong plant
        sessionStore.clearSession()
        return next({ name: 'LoginGeneric' })
      }
    }

    // Check plant access from URL params
    if (to.params.plantId && session.plant.id !== to.params.plantId) {
      // plant mismatch
      sessionStore.clearSession()
      return next({ name: 'LoginGeneric' })
    }
  }

  next()
})

// After navigation
router.afterEach((to, from) => {
  const sessionStore = useSessionStore()

  // Update activity
  sessionStore.updateActivity()
})

export default router