/**
 * Security Utilities
 * Handles encryption, sanitization, and security-related operations
 */

import CryptoJS from 'crypto-js'

/**
 * Get encryption key from environment or use default
 * In production, this MUST be set via environment variable
 */
function getEncryptionKey(): string {
  const key = import.meta.env.VITE_ENCRYPTION_KEY
  const isProduction = import.meta.env.PROD || import.meta.env.MODE === 'production'
  
  if (!key && isProduction) {
    console.warn('⚠️ VITE_ENCRYPTION_KEY not set in production. Using default key (not recommended for production).')
  }
  
  // Fallback for development only
  return key || 'default-dev-key-change-in-production'
}

/**
 * Encrypt data for secure storage
 * @param data - Any JSON-serializable data
 * @returns Encrypted string
 */
export function encrypt(data: any): string {
  try {
    const jsonString = JSON.stringify(data)
    const encrypted = CryptoJS.AES.encrypt(jsonString, getEncryptionKey())
    return encrypted.toString()
  } catch (error) {
    console.error('Encryption failed:', error)
    throw new Error('Failed to encrypt data')
  }
}

/**
 * Decrypt encrypted data
 * @param encryptedData - Encrypted string
 * @returns Decrypted data
 */
export function decrypt<T = any>(encryptedData: string): T | null {
  try {
    const bytes = CryptoJS.AES.decrypt(encryptedData, getEncryptionKey())
    const decryptedString = bytes.toString(CryptoJS.enc.Utf8)
    
    if (!decryptedString) {
      throw new Error('Decryption produced empty string')
    }
    
    return JSON.parse(decryptedString) as T
  } catch (error) {
    console.error('Decryption failed:', error)
    return null
  }
}

/**
 * Secure localStorage wrapper with encryption
 */
export const secureStorage = {
  /**
   * Set item in localStorage with encryption
   */
  setItem(key: string, value: any): void {
    try {
      const encrypted = encrypt(value)
      localStorage.setItem(key, encrypted)
    } catch (error) {
      console.error(`Failed to set secure item: ${key}`, error)
    }
  },

  /**
   * Get item from localStorage with decryption
   */
  getItem<T = any>(key: string): T | null {
    try {
      const encrypted = localStorage.getItem(key)
      if (!encrypted) return null
      
      return decrypt<T>(encrypted)
    } catch (error) {
      console.error(`Failed to get secure item: ${key}`, error)
      return null
    }
  },

  /**
   * Remove item from localStorage
   */
  removeItem(key: string): void {
    localStorage.removeItem(key)
  },

  /**
   * Clear all items from localStorage
   */
  clear(): void {
    localStorage.clear()
  },

  /**
   * Check if key exists in localStorage
   */
  hasItem(key: string): boolean {
    return localStorage.getItem(key) !== null
  }
}

/**
 * Sanitize user input to prevent XSS
 * @param input - Raw user input
 * @returns Sanitized string
 */
export function sanitizeInput(input: string): string {
  if (typeof input !== 'string') return ''
  
  return input
    .replace(/[<>]/g, '') // Remove angle brackets
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .replace(/on\w+=/gi, '') // Remove event handlers
    .trim()
}

/**
 * Sanitize HTML content (for rich text)
 * Uses a whitelist approach
 */
export function sanitizeHTML(html: string): string {
  if (typeof html !== 'string') return ''
  
  // Basic sanitization - in production, use DOMPurify library
  const temp = document.createElement('div')
  temp.textContent = html
  return temp.innerHTML
}

/**
 * Validate and sanitize email
 */
export function sanitizeEmail(email: string): string | null {
  if (typeof email !== 'string') return null
  
  const sanitized = email.trim().toLowerCase()
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  
  return emailRegex.test(sanitized) ? sanitized : null
}

/**
 * Generate random string for CSRF-like tokens
 */
export function generateRandomString(length: number = 32): string {
  const array = new Uint8Array(length)
  crypto.getRandomValues(array)
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('')
}

/**
 * Hash sensitive data (one-way)
 */
export function hashData(data: string): string {
  return CryptoJS.SHA256(data).toString()
}

/**
 * Check if string is likely sensitive data
 * (contains patterns like password, token, key, secret)
 */
export function isSensitiveData(key: string): boolean {
  const sensitivePatterns = [
    /password/i,
    /token/i,
    /secret/i,
    /key/i,
    /auth/i,
    /credential/i,
    /api[_-]?key/i
  ]
  
  return sensitivePatterns.some(pattern => pattern.test(key))
}

/**
 * Mask sensitive data for logging
 */
export function maskSensitiveData(data: any): any {
  if (typeof data === 'string') {
    return data.replace(/./g, '*')
  }
  
  if (Array.isArray(data)) {
    return data.map(maskSensitiveData)
  }
  
  if (typeof data === 'object' && data !== null) {
    const masked: any = {}
    for (const [key, value] of Object.entries(data)) {
      if (isSensitiveData(key)) {
        masked[key] = '***masked***'
      } else if (typeof value === 'object') {
        masked[key] = maskSensitiveData(value)
      } else {
        masked[key] = value
      }
    }
    return masked
  }
  
  return data
}

/**
 * Secure session storage wrapper
 */
export const secureSessionStorage = {
  setItem(key: string, value: any): void {
    try {
      const encrypted = encrypt(value)
      sessionStorage.setItem(key, encrypted)
    } catch (error) {
      console.error(`Failed to set secure session item: ${key}`, error)
    }
  },

  getItem<T = any>(key: string): T | null {
    try {
      const encrypted = sessionStorage.getItem(key)
      if (!encrypted) return null
      
      return decrypt<T>(encrypted)
    } catch (error) {
      console.error(`Failed to get secure session item: ${key}`, error)
      return null
    }
  },

  removeItem(key: string): void {
    sessionStorage.removeItem(key)
  },

  clear(): void {
    sessionStorage.clear()
  }
}

/**
 * Usage Examples:
 * 
 * import { secureStorage, sanitizeInput, maskSensitiveData } from '@/core/utils/security'
 * 
 * // Secure storage
 * secureStorage.setItem('session', { token: 'abc123', user: 'john@example.com' })
 * const session = secureStorage.getItem('session')
 * 
 * // Sanitize input
 * const safeInput = sanitizeInput(userInput)
 * 
 * // Mask for logging
 * const maskedData = maskSensitiveData({ password: '123456', email: 'user@example.com' })
 * logger.debug('User data', maskedData) // { password: '***masked***', email: 'user@example.com' }
 */

