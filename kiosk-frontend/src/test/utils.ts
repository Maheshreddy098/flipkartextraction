import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory, Router } from 'vue-router'
import type { Component } from 'vue'

// Mock routes for testing
const mockRoutes = [
  { path: '/login', name: 'Login', component: { template: '<div>Login</div>' } },
  { path: '/plant/:plantId/dashboard', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
  { path: '/plant/:plantId/grn', name: 'GRN', component: { template: '<div>GRN</div>' } }
]

/**
 * Creates a test router instance
 */
export function createTestRouter(): Router {
  return createRouter({
    history: createWebHistory('/kiosk/'),
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
 * Mock session data factory
 */
export function createMockSession(overrides = {}) {
  return {
    token: 'mock-token',
    user: {
      email: 'test@example.com',
      name: 'Test User',
      role: 'Plant Operator'
    },
    plant: {
      id: 'test-plant',
      name: 'Test Plant',
      permissions: ['dashboard', 'grn', 'production-order']
    },
    expiresAt: Date.now() + 3600000, // 1 hour from now
    loginTime: Date.now(),
    ...overrides
  }
}

/**
 * Mock activity data factory
 */
export function createMockActivity(overrides = {}) {
  return {
    id: 'mock-activity-1',
    type: 'navigation',
    action: 'page_view',
    page: '/kiosk/plant/test-plant/dashboard',
    timestamp: new Date().toISOString(),
    metadata: {
      user_agent: 'test-user-agent',
      screen_resolution: '1920x1080'
    },
    ...overrides
  }
}

/**
 * Mock plant stats data factory
 */
export function createMockPlantStats(overrides = {}) {
  return {
    production: '1,250 units',
    quality: 95.8,
    efficiency: 92.5,
    orders: 12,
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