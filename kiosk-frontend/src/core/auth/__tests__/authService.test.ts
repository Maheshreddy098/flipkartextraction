import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createMockSession } from '@/test/utils'

// Hoisted session store mock to avoid TDZ issues
const { mockSessionStore } = vi.hoisted(() => ({
  mockSessionStore: {
    setSession: vi.fn(),
    clearSession: vi.fn(),
    getSession: vi.fn(),
    user: null
  }
}))

vi.mock('../../stores/session', () => ({
  useSessionStore: () => mockSessionStore
}))

// Mock axios client factory and capture instance
let mockAxios: any
vi.mock('axios', () => {
  mockAxios = {
    post: vi.fn(),
    get: vi.fn(),
    interceptors: {
      request: { use: vi.fn(() => {}) },
      response: { use: vi.fn(() => {}) }
    }
  }
  return {
    default: {
      create: vi.fn(() => mockAxios)
    }
  }
})

// Mock activity logger
vi.mock('../../utils/activityLogger', () => ({
  useActivityLogger: () => ({
    logActivity: vi.fn()
  })
}))

// Import after mocks so the singleton picks up mocked deps
const { authService } = await import('../authService')

describe('AuthService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('authenticate', () => {
    it('should successfully authenticate user', async () => {
      const email = 'test@example.com'
      const password = 'password123'
      const plantId = 'test-plant'

      // Mock API responses
      mockAxios.post.mockImplementation((url) => {
        if (url.includes('login')) {
          return Promise.resolve({ data: { message: 'success' } })
        }
        if (url.includes('generate_plant_token')) {
          return Promise.resolve({
            data: {
              message: {
                token: 'test-token',
                user_data: { email, name: 'Test User' },
                expires_at: Date.now() + 3600000
              }
            }
          })
        }
      })

      mockAxios.get.mockImplementation((url) => {
        if (url.includes('verify_plant_access')) {
          return Promise.resolve({
            data: {
              message: {
                has_access: true,
                plant_name: 'Test Plant'
              }
            }
          })
        }
        if (url.includes('get_user_permissions')) {
          return Promise.resolve({
            data: {
              message: ['dashboard', 'grn']
            }
          })
        }
      })

      const result = await authService.authenticate(email, password, plantId)

      expect(result.success).toBe(true)
      expect(result.user.email).toBe(email)
      expect(result.plant.id).toBe(plantId)
      expect(mockSessionStore.setSession).toHaveBeenCalled()
    })

    it('should throw error on authentication failure', async () => {
      const email = 'test@example.com'
      const password = 'wrongpassword'
      const plantId = 'test-plant'

      mockAxios.post.mockRejectedValue({
        response: {
          data: { message: 'Invalid credentials' }
        }
      })

      await expect(authService.authenticate(email, password, plantId))
        .rejects.toThrow('Invalid credentials')
    })

    it('should throw error when plant access is denied', async () => {
      const email = 'test@example.com'
      const password = 'password123'
      const plantId = 'unauthorized-plant'

      // Mock successful login but denied plant access
      mockAxios.post.mockResolvedValue({ data: { message: 'success' } })
      mockAxios.get.mockImplementation((url) => {
        if (url.includes('verify_plant_access')) {
          return Promise.resolve({
            data: {
              message: { has_access: false }
            }
          })
        }
      })

      await expect(authService.authenticate(email, password, plantId))
        .rejects.toThrow('Access denied for plant: unauthorized-plant')
    })
  })

  describe('logout', () => {
    it('should clear session and redirect to login', async () => {
      const mockSession = createMockSession()
      mockSessionStore.getSession.mockReturnValue(mockSession)
      mockAxios.post.mockResolvedValue({ data: {} })

      // Mock window.location
      delete window.location
      window.location = { href: '' } as any

      await authService.logout()

      expect(mockSessionStore.clearSession).toHaveBeenCalled()
      expect(window.location.href).toBe('/kiosk/login')
    })

    it('should handle logout API failure gracefully', async () => {
      const mockSession = createMockSession()
      mockSessionStore.getSession.mockReturnValue(mockSession)
      mockAxios.post.mockRejectedValue(new Error('Network error'))

      // Mock window.location
      delete window.location
      window.location = { href: '' } as any

      await authService.logout()

      // Should still clear session and redirect even if API fails
      expect(mockSessionStore.clearSession).toHaveBeenCalled()
      expect(window.location.href).toBe('/kiosk/login')
    })
  })

  describe('verifySession', () => {
    it('should return false when no session exists', async () => {
      mockSessionStore.getSession.mockReturnValue(null)

      const result = await authService.verifySession()

      expect(result).toBe(false)
    })

    it('should verify valid session with backend', async () => {
      const mockSession = createMockSession()
      mockSessionStore.getSession.mockReturnValue(mockSession)
      mockAxios.get.mockResolvedValue({
        data: { message: { valid: true } }
      })

      const result = await authService.verifySession()

      expect(result).toBe(true)
    })

    it('should return false for invalid session', async () => {
      const mockSession = createMockSession()
      mockSessionStore.getSession.mockReturnValue(mockSession)
      mockAxios.get.mockResolvedValue({
        data: { message: { valid: false } }
      })

      const result = await authService.verifySession()

      expect(result).toBe(false)
    })
  })

  describe('hasPermission', () => {
    it('should check user permissions correctly', () => {
      const mockSession = createMockSession({
        plant: {
          permissions: ['dashboard', 'grn', 'production-order']
        }
      })
      mockSessionStore.getSession.mockReturnValue(mockSession)

      expect(authService.hasPermission('dashboard')).toBe(true)
      expect(authService.hasPermission('admin')).toBe(false)
    })

    it('should return false when no session exists', () => {
      mockSessionStore.getSession.mockReturnValue(null)

      expect(authService.hasPermission('dashboard')).toBe(false)
    })
  })
})