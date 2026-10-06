import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory, Router } from 'vue-router'
import type { Component } from 'vue'

// Mock routes for testing
const mockRoutes = [
  { path: '/login', name: 'Login', component: { template: '<div>Login</div>' } },
  { path: '/dashboard', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
  { path: '/inventory', name: 'InventoryIndex', component: { template: '<div>Inventory</div>' } },
  { path: '/transfers', name: 'TransfersIndex', component: { template: '<div>Transfers</div>' } },
  { path: '/delivery', name: 'DeliveryIndex', component: { template: '<div>Delivery</div>' } },
]

/**
 * Creates a test router instance
 */
export function createTestRouter(): Router {
  return createRouter({
    history: createWebHistory('/storeops/'),
    routes: mockRoutes
  })
}

/**
 * Creates a wrapper with common test setup (Pinia, Router)
 */
export function createWrapper(component: Component, options: any = {}) {
  // Create fresh Pinia instance for each test
  const pinia = createPinia()
  setActivePinia(pinia)
  
  // Create test router
  const router = createTestRouter()
  
  return mount(component, {
    global: {
      plugins: [pinia, router],
      stubs: {
        RouterLink: true,
        RouterView: true
      }
    },
    ...options
  })
}

/**
 * Mock auth context factory
 */
export function createMockAuthContext(overrides = {}) {
  return {
    user: 'test@khanalfoods.com',
    full_name: 'Test User',
    role: 'Consumables Store User',
    is_super_admin: false,
    is_procurement_user: false,
    plants: [
      {
        plant_code: 'ATP',
        plant_name: 'ATP',
        warehouses: [{ code: 'ATP-MAIN-WH', name: 'ATP Main Warehouse' }],
      },
    ],
    ...overrides
  }
}

/**
 * Async component test helper
 */
export async function flushPromises(): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, 0))
}

/**
 * Wait for next tick and DOM update
 */
export async function nextTick(): Promise<void> {
  await new Promise(resolve => setTimeout(resolve, 0))
}

/**
 * Create mock axios instance
 */
export function createMockAxios() {
  return {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    create: vi.fn().mockReturnThis(),
    interceptors: {
      request: {
        use: vi.fn()
      },
      response: {
        use: vi.fn()
      }
    }
  }
}