/**
 * Centralized Logger Utility
 * Replaces console.log with environment-aware logging
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogEntry {
  level: LogLevel
  message: string
  data?: any
  timestamp: string
  context?: string
}

class Logger {
  private isDevelopment: boolean
  private logs: LogEntry[] = []
  private maxLogs: number = 100

  constructor() {
    this.isDevelopment = import.meta.env.DEV
  }

  /**
   * Debug level logging (only in development)
   */
  debug(message: string, data?: any, context?: string): void {
    if (this.isDevelopment) {
      this.log('debug', message, data, context)
    }
  }

  /**
   * Info level logging
   */
  info(message: string, data?: any, context?: string): void {
    this.log('info', message, data, context)
    if (this.isDevelopment) {
    }
  }

  /**
   * Warning level logging
   */
  warn(message: string, data?: any, context?: string): void {
    this.log('warn', message, data, context)
  }

  /**
   * Error level logging
   */
  error(message: string, error?: any, context?: string): void {
    this.log('error', message, error, context)
    console.error(`[ERROR]${context ? ` [${context}]` : ''} ${message}`, error || '')
  }

  /**
   * Internal log storage
   */
  private log(level: LogLevel, message: string, data?: any, context?: string): void {
    const entry: LogEntry = {
      level,
      message,
      data,
      timestamp: new Date().toISOString(),
      context
    }

    this.logs.push(entry)

    // Keep only last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs.shift()
    }
  }

  /**
   * Get recent logs
   */
  getRecentLogs(count: number = 50): LogEntry[] {
    return this.logs.slice(-count)
  }

  /**
   * Clear all logs
   */
  clearLogs(): void {
    this.logs = []
  }

  /**
   * Export logs for debugging
   */
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2)
  }

  /**
   * Performance timing
   */
  time(label: string): void {
    if (this.isDevelopment) {
      console.time(label)
    }
  }

  /**
   * End performance timing
   */
  timeEnd(label: string): void {
    if (this.isDevelopment) {
      console.timeEnd(label)
    }
  }

  /**
   * Group logging
   */
  group(label: string): void {
    if (this.isDevelopment) {
      console.group(label)
    }
  }

  /**
   * End group logging
   */
  groupEnd(): void {
    if (this.isDevelopment) {
      console.groupEnd()
    }
  }

  /**
   * Table logging (for arrays/objects)
   */
  table(data: any): void {
    if (this.isDevelopment) {
      console.table(data)
    }
  }
}

// Export singleton instance
export const logger = new Logger()

// Export types
export type { LogLevel, LogEntry }

/**
 * Usage Examples:
 * 
 * import { logger } from '@/core/utils/logger'
 * 
 * // Debug (only in dev)
 * logger.debug('Fetching purchase orders', { status: 'Open' }, 'GRNService')
 * 
 * // Info
 * logger.info('User logged in', { email: 'user@example.com' }, 'AuthService')
 * 
 * // Warning
 * logger.warn('Session about to expire', { expiresIn: '5m' }, 'SessionStore')
 * 
 * // Error
 * logger.error('API call failed', error, 'BaseService')
 * 
 * // Performance
 * logger.time('fetchPurchaseOrders')
 * await fetchPurchaseOrders()
 * logger.timeEnd('fetchPurchaseOrders')
 * 
 * // Grouped logs
 * logger.group('GRN Creation Process')
 * logger.debug('Step 1: Validate data')
 * logger.debug('Step 2: Create draft')
 * logger.groupEnd()
 */

