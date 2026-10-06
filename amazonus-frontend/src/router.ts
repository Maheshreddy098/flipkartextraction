import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory('/amazonus'),
  routes: [
    { path: '/', name: 'overview', component: () => import('./views/OverviewView.vue') },
    { path: '/orders', name: 'orders', component: () => import('./views/OrdersView.vue') },
    { path: '/actions', name: 'actions', component: () => import('./views/ActionsView.vue') },
    { path: '/settlements', name: 'settlements', component: () => import('./views/SettlementsView.vue') },
    { path: '/credit-notes', name: 'credit-notes', component: () => import('./views/CreditNotesView.vue') },
    { path: '/inventory', name: 'inventory', component: () => import('./views/InventoryView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
