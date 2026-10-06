import { describe, it, expect, vi, beforeEach } from 'vitest'
import router from './router'

vi.mock('./core/stores/session.js', () => ({
  useSessionStore: () => ({
    isAuthenticated: false,
    initializeFromStorage: vi.fn(() => false),
    isSessionValid: false,
    clearSession: vi.fn(),
    getSession: vi.fn(() => null),
    updateActivity: vi.fn()
  })
}))

vi.mock('./core/utils/activityLogger.js', () => ({
  useActivityLogger: () => ({
    logActivity: vi.fn(),
    logPageView: vi.fn(),
    startPageTracking: vi.fn()
  })
}))

describe('Router', () => {
  beforeEach(async () => {
    // jsdom lacks scrollTo; mock to avoid errors from vue-router scroll behavior
    // @ts-ignore
    window.scrollTo = () => {}
    try { await router.replace('/') } catch {}
  })

it.skip('redirects unauthenticated users to login', async () => {
  await router.push('/plant/mahadevpura')
  await Promise.resolve()
  expect(router.currentRoute.value.name).toBe('LoginGeneric')
})

  it('handles not found route', async () => {
    await router.push('/some/unknown/path')
    await Promise.resolve()
    expect(router.currentRoute.value.name).toBe('NotFound')
  })
})
