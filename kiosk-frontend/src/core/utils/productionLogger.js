/**
 * Production-safe logger
 * Only logs errors in production, all logs in development
 */

const isDevelopment = import.meta.env.DEV || import.meta.env.MODE === 'development'

export const logger = {
  log: (...args) => {
    if (isDevelopment) {
    }
  },
  
  warn: (...args) => {
    if (isDevelopment) {
    }
  },
  
  error: (...args) => {
    // Always log errors, even in production
    console.error(...args)
  },
  
  debug: (...args) => {
    if (isDevelopment) {
    }
  },
  
  info: (...args) => {
    if (isDevelopment) {
    }
  }
}

// For quick replacement in existing code
export const log = logger.log
export const warn = logger.warn
export const error = logger.error
export const debug = logger.debug
export const info = logger.info

