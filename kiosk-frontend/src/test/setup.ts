import { vi } from 'vitest'

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn()
}

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage
})

// Mock sessionStorage
const mockSessionStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn()
}

Object.defineProperty(window, 'sessionStorage', {
  value: mockSessionStorage
})

// Mock navigator
Object.defineProperty(window.navigator, 'onLine', {
  writable: true,
  value: true
})

Object.defineProperty(window.navigator, 'userAgent', {
  writable: true,
  value: 'test-user-agent'
})

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  // Silence specific console methods
  warn: vi.fn(),
  error: vi.fn()
}

// Mock window.location
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost:3000/kiosk',
    origin: 'http://localhost:3000',
    pathname: '/kiosk',
    search: '',
    hash: ''
  },
  writable: true
})

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn(() => ({
  disconnect: vi.fn(),
  observe: vi.fn(),
  unobserve: vi.fn()
}))

// Mock ResizeObserver
global.ResizeObserver = vi.fn(() => ({
  disconnect: vi.fn(),
  observe: vi.fn(),
  unobserve: vi.fn()
}))

// Reset all mocks before each test
beforeEach(() => {
  vi.clearAllMocks()
})