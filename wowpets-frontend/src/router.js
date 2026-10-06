import { createRouter, createWebHistory } from 'vue-router'
import { APP_CONFIG } from '@/config/settings.js'
import { useSessionStore } from '@/core/stores/session.js'
import { checkSession } from '@/core/auth/authService.js'

import Login from '@/pages/Login.vue'

const KFDashboard = () => import('@/pages/khanalfoods/Dashboard.vue')
const KFPurchaseOrders = () => import('@/pages/khanalfoods/PurchaseOrders.vue')
const KFPurchaseOrderForm = () => import('@/pages/khanalfoods/PurchaseOrderForm.vue')
const KFWorkOrders = () => import('@/pages/khanalfoods/WorkOrders.vue')
const KFWorkOrderForm = () => import('@/pages/khanalfoods/WorkOrderForm.vue')
const KFReturns = () => import('@/pages/khanalfoods/Returns.vue')
const KFShipheroTransfers = () => import('@/pages/khanalfoods/ShipheroTransfers.vue')
const KFShipheroTransferForm = () => import('@/pages/khanalfoods/ShipheroTransferForm.vue')
const KFOrders = () => import('@/pages/khanalfoods/Orders.vue')
const KFOrderForm = () => import('@/pages/khanalfoods/OrderForm.vue')
const KFDispatchOrders = () => import('@/pages/khanalfoods/DispatchOrders.vue')
const KFDispatchOrderForm = () => import('@/pages/khanalfoods/DispatchOrderForm.vue')
const KFTickets = () => import('@/pages/khanalfoods/Tickets.vue')

const WHDashboard = () => import('@/pages/warehouse/Dashboard.vue')
const WHPendingPurchaseOrders = () => import('@/pages/warehouse/PendingPurchaseOrders.vue')
const WHPurchaseOrderDetail = () => import('@/pages/warehouse/PurchaseOrderDetail.vue')
const WHPendingWorkOrders = () => import('@/pages/warehouse/PendingWorkOrders.vue')
const WHWorkOrderProcess = () => import('@/pages/warehouse/WorkOrderProcess.vue')
const WHInventory = () => import('@/pages/warehouse/Inventory.vue')
const WHReturns = () => import('@/pages/warehouse/Returns.vue')
const WHShipheroTransfers = () => import('@/pages/khanalfoods/ShipheroTransfers.vue')
const WHShipheroTransferDetail = () => import('@/pages/khanalfoods/ShipheroTransferForm.vue')
const WHOrders = () => import('@/pages/khanalfoods/Orders.vue')
const WHOrderProcess = () => import('@/pages/warehouse/OrderProcess.vue')
const WHDispatchOrders = () => import('@/pages/khanalfoods/DispatchOrders.vue')
const WHDispatchOrderProcess = () => import('@/pages/warehouse/DispatchOrderProcess.vue')
const WHTickets = () => import('@/pages/khanalfoods/Tickets.vue')

const AppLayout = () => import('@/layouts/AppLayout.vue')

const routes = [
  { path: '/', redirect: '/login' },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false },
  },
  {
    path: '/khanalfoods',
    component: AppLayout,
    meta: { requiresAuth: true, team: 'khanalfoods' },
    children: [
      { path: '', redirect: 'dashboard' },
      { path: 'dashboard', name: 'KFDashboard', component: KFDashboard },
      { path: 'purchase-orders', name: 'KFPurchaseOrders', component: KFPurchaseOrders },
      { path: 'purchase-orders/new', name: 'KFPurchaseOrderNew', component: KFPurchaseOrderForm },
      { path: 'purchase-orders/:id', name: 'KFPurchaseOrderEdit', component: KFPurchaseOrderForm, props: true },
      { path: 'work-orders', name: 'KFWorkOrders', component: KFWorkOrders },
      { path: 'work-orders/new', name: 'KFWorkOrderNew', component: KFWorkOrderForm },
      { path: 'work-orders/:id', name: 'KFWorkOrderEdit', component: KFWorkOrderForm, props: true },
      { path: 'returns', name: 'KFReturns', component: KFReturns },
      { path: 'shiphero-transfers', name: 'KFShipheroTransfers', component: KFShipheroTransfers },
      { path: 'shiphero-transfers/new', name: 'KFShipheroTransferNew', component: KFShipheroTransferForm },
      { path: 'shiphero-transfers/:id', name: 'KFShipheroTransferEdit', component: KFShipheroTransferForm, props: true },
      { path: 'orders', name: 'KFOrders', component: KFOrders },
      { path: 'orders/new', name: 'KFOrderNew', component: KFOrderForm },
      { path: 'orders/:id', name: 'KFOrderEdit', component: KFOrderForm, props: true },
      { path: 'dispatch-orders', name: 'KFDispatchOrders', component: KFDispatchOrders },
      { path: 'dispatch-orders/new', name: 'KFDispatchOrderNew', component: KFDispatchOrderForm },
      { path: 'dispatch-orders/:id', name: 'KFDispatchOrderEdit', component: KFDispatchOrderForm, props: true },
      { path: 'tickets', name: 'KFTickets', component: KFTickets },
      { path: 'inventory', name: 'KFInventory', component: WHInventory },
    ],
  },
  {
    path: '/warehouse',
    component: AppLayout,
    meta: { requiresAuth: true, team: 'warehouse' },
    children: [
      { path: '', redirect: 'dashboard' },
      { path: 'dashboard', name: 'WHDashboard', component: WHDashboard },
      { path: 'purchase-orders', name: 'WHPurchaseOrders', component: WHPendingPurchaseOrders },
      { path: 'purchase-orders/:id', name: 'WHPurchaseOrderDetail', component: WHPurchaseOrderDetail, props: true },
      { path: 'work-orders', name: 'WHWorkOrders', component: WHPendingWorkOrders },
      { path: 'work-orders/:id', name: 'WHWorkOrderProcess', component: WHWorkOrderProcess, props: true },
      { path: 'inventory', name: 'WHInventory', component: WHInventory },
      { path: 'returns', name: 'WHReturns', component: WHReturns },
      { path: 'shiphero-transfers', name: 'WHShipheroTransfers', component: WHShipheroTransfers },
      { path: 'shiphero-transfers/:id', name: 'WHShipheroTransferDetail', component: WHShipheroTransferDetail, props: true },
      { path: 'orders', name: 'WHOrders', component: WHOrders },
      { path: 'orders/:id', name: 'WHOrderProcess', component: WHOrderProcess, props: true },
      { path: 'dispatch-orders', name: 'WHDispatchOrders', component: WHDispatchOrders },
      { path: 'dispatch-orders/:id', name: 'WHDispatchOrderProcess', component: WHDispatchOrderProcess, props: true },
      { path: 'tickets', name: 'WHTickets', component: WHTickets },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(APP_CONFIG.BASE_PATH + '/'),
  routes,
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAuth === false) return next()

  const sessionStore = useSessionStore()

  if (!sessionStore.isAuthenticated) {
    const valid = await checkSession()
    if (!valid) return next({ name: 'Login' })
  }

  if (to.meta.team && sessionStore.team !== to.meta.team) {
    // Procurement team shares the khanalfoods route namespace
    if (to.meta.team === 'khanalfoods' && sessionStore.team === 'procurement') {
      return next()
    }
    const teamPath = sessionStore.team === 'warehouse' ? '/warehouse/dashboard' : '/khanalfoods/dashboard'
    return next(teamPath)
  }

  next()
})

export default router
