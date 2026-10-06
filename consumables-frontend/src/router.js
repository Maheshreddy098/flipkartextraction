import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const Login = () => import('./pages/Login.vue')
const Dashboard = () => import('./pages/Dashboard.vue')
const InventoryIndex = () => import('./pages/inventory/index.vue')
const PlantDetail = () => import('./pages/inventory/PlantDetail.vue')
const TransfersIndex = () => import('./pages/transfers/index.vue')
const TransferNew = () => import('./pages/transfers/New.vue')
const TransferDetail = () => import('./pages/transfers/Detail.vue')
const DeliveryIndex = () => import('./pages/delivery/index.vue')
const DeliveryNew = () => import('./pages/delivery/New.vue')
const DeliveryDetail = () => import('./pages/delivery/Detail.vue')
const MaterialRequestsIndex = () => import('./pages/material_requests/index.vue')
const MaterialRequestNew = () => import('./pages/material_requests/New.vue')
const MaterialRequestDetail = () => import('./pages/material_requests/Detail.vue')
const ProcurementIndex = () => import('./pages/procurement/index.vue')
const ProcurementDetail = () => import('./pages/procurement/Detail.vue')
const AdminIndex = () => import('./pages/admin/index.vue')

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', name: 'Login', component: Login, meta: { requiresAuth: false } },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/inventory', name: 'InventoryIndex', component: InventoryIndex, meta: { requiresAuth: true } },
  { path: '/inventory/:plant_code', name: 'PlantDetail', component: PlantDetail, meta: { requiresAuth: true } },
  { path: '/transfers', name: 'TransfersIndex', component: TransfersIndex, meta: { requiresAuth: true } },
  { path: '/transfers/new', name: 'TransferNew', component: TransferNew, meta: { requiresAuth: true } },
  { path: '/transfers/:name', name: 'TransferDetail', component: TransferDetail, meta: { requiresAuth: true } },
  { path: '/delivery', name: 'DeliveryIndex', component: DeliveryIndex, meta: { requiresAuth: true } },
  { path: '/delivery/new', name: 'DeliveryNew', component: DeliveryNew, meta: { requiresAuth: true } },
  { path: '/delivery/:name', name: 'DeliveryDetail', component: DeliveryDetail, meta: { requiresAuth: true } },
  { path: '/material-requests', name: 'MaterialRequestsIndex', component: MaterialRequestsIndex, meta: { requiresAuth: true } },
  { path: '/material-requests/new', name: 'MaterialRequestNew', component: MaterialRequestNew, meta: { requiresAuth: true } },
  { path: '/material-requests/:name', name: 'MaterialRequestDetail', component: MaterialRequestDetail, meta: { requiresAuth: true } },
  { path: '/procurement', name: 'ProcurementIndex', component: ProcurementIndex, meta: { requiresAuth: true, requiresProcurementOrStoreManager: true } },
  { path: '/procurement/:name', name: 'ProcurementDetail', component: ProcurementDetail, meta: { requiresAuth: true, requiresProcurementOrStoreManager: true } },
  {
    path: '/admin',
    name: 'AdminIndex',
    component: AdminIndex,
    meta: { requiresAuth: true, requiresRole: 'Consumables Super Admin' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAuth === false) return next()

  const authStore = useAuthStore()

  // Check Frappe session cookie
  const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
  const sessionUser = cookies.get('user_id')
  if (!sessionUser || sessionUser === 'Guest') {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  // Fetch context once per session
  if (!authStore.initialized) {
    try {
      await authStore.fetchContext()
    } catch {
      return next({ name: 'Login' })
    }
  }

  // Block users with no consumables role — they have a Frappe session but no access here
  if (!authStore.role) {
    return next({ name: 'Login', query: { error: 'no_role' } })
  }

  // Role guard: admin routes restricted to Super Admin
  if (to.meta.requiresRole && !authStore.isSuperAdmin && authStore.role !== to.meta.requiresRole) {
    return next({ name: 'Dashboard' })
  }
  // Procurement guard: list restricted to procurement users / admin
  if (to.meta.requiresProcurement && !(authStore.isSuperAdmin || authStore.isProcurementUser)) {
    return next({ name: 'Dashboard' })
  }
  // CPR: procurement users, store managers, inventory managers, and admins can view
  if (
    to.meta.requiresProcurementOrStoreManager &&
    !(
      authStore.isSuperAdmin ||
      authStore.isProcurementUser ||
      authStore.consumablesRoles.includes('Consumables Store Manager') ||
      authStore.consumablesRoles.includes('Consumables Inventory Manager')
    )
  ) {
    return next({ name: 'Dashboard' })
  }

  next()
})

export default router
