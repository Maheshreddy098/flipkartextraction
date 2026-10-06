import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from '../session.js'

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn()
}
vi.stubGlobal('localStorage', mockLocalStorage)

describe('Session Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockLocalStorage.getItem.mockClear()
    mockLocalStorage.setItem.mockClear()
    mockLocalStorage.removeItem.mockClear()
  })

  it('should initialize with default state', () => {
    const store = useSessionStore()
    
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBe(null)
    expect(store.plant).toBe(null)
    expect(store.token).toBe(null)
  })

  it('should set session data correctly', () => {
    const store = useSessionStore()
    const sessionData = {
      token: 'test-token',
      user: { email: 'test@example.com', name: 'Test User' },
      plant: { id: 'test-plant', name: 'Test Plant' },
      expiresAt: Date.now() + 3600000 // 1 hour from now
    }

    store.setSession(sessionData)

    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual(sessionData.user)
    expect(store.plant).toEqual(sessionData.plant)
    expect(store.token).toBe(sessionData.token)
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('kiosk-session', expect.any(String))
  })

  it('should clear session data', () => {
    const store = useSessionStore()
    
    // First set some data
    const sessionData = {
      token: 'test-token',
      user: { email: 'test@example.com' },
      plant: { id: 'test-plant' },
      expiresAt: Date.now() + 3600000
    }
    store.setSession(sessionData)
    
    // Then clear it
    store.clearSession()
    
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBe(null)
    expect(store.plant).toBe(null)
    expect(store.token).toBe(null)
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('kiosk-session')
  })

  it('should check permissions correctly', () => {
    const store = useSessionStore()
    const sessionData = {
      token: 'test-token',
      user: { email: 'test@example.com' },
      plant: { 
        id: 'test-plant',
        permissions: ['dashboard', 'grn', 'production-order']
      },
      expiresAt: Date.now() + 3600000
    }
    
    store.setSession(sessionData)
    
    expect(store.hasPermission('dashboard')).toBe(true)
    expect(store.hasPermission('admin')).toBe(false)
    expect(store.hasAnyPermission(['admin', 'grn'])).toBe(true)
    expect(store.hasAllPermissions(['dashboard', 'grn'])).toBe(true)
    expect(store.hasAllPermissions(['dashboard', 'admin'])).toBe(false)
  })
})