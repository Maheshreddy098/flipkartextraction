/**
 * Validation utilities for form inputs and data validation
 */

import { APP_CONFIG } from '@/config/constants'

export interface ValidationRule {
  required?: boolean
  minLength?: number
  maxLength?: number
  pattern?: RegExp
  custom?: (value: any) => string | null
  message?: string
}

export interface ValidationResult {
  isValid: boolean
  errors: string[]
}

/**
 * Validate a single value against rules
 */
export function validateValue(value: any, rules: ValidationRule[]): ValidationResult {
  const errors: string[] = []

  for (const rule of rules) {
    // Required validation
    if (rule.required && (!value || value.toString().trim() === '')) {
      errors.push(rule.message || 'This field is required')
      continue
    }

    // Skip other validations if value is empty and not required
    if (!value || value.toString().trim() === '') {
      continue
    }

    const strValue = value.toString()

    // Min length validation
    if (rule.minLength && strValue.length < rule.minLength) {
      errors.push(rule.message || `Must be at least ${rule.minLength} characters`)
    }

    // Max length validation
    if (rule.maxLength && strValue.length > rule.maxLength) {
      errors.push(rule.message || `Must be no more than ${rule.maxLength} characters`)
    }

    // Pattern validation
    if (rule.pattern && !rule.pattern.test(strValue)) {
      errors.push(rule.message || 'Invalid format')
    }

    // Custom validation
    if (rule.custom) {
      const customError = rule.custom(value)
      if (customError) {
        errors.push(customError)
      }
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * Validate an object with multiple fields
 */
export function validateObject(
  data: Record<string, any>,
  rules: Record<string, ValidationRule[]>
): Record<string, ValidationResult> {
  const results: Record<string, ValidationResult> = {}

  for (const [field, fieldRules] of Object.entries(rules)) {
    results[field] = validateValue(data[field], fieldRules)
  }

  return results
}

/**
 * Email validation
 */
export function validateEmail(email: string): ValidationResult {
  return validateValue(email, [
    { required: true, message: 'Email is required' },
    { 
      pattern: APP_CONFIG.VALIDATION.EMAIL_REGEX,
      message: 'Please enter a valid email address'
    }
  ])
}

/**
 * Password validation
 */
export function validatePassword(password: string): ValidationResult {
  return validateValue(password, [
    { required: true, message: 'Password is required' },
    {
      minLength: APP_CONFIG.VALIDATION.PASSWORD_MIN_LENGTH,
      message: `Password must be at least ${APP_CONFIG.VALIDATION.PASSWORD_MIN_LENGTH} characters`
    },
    {
      maxLength: APP_CONFIG.VALIDATION.PASSWORD_MAX_LENGTH,
      message: `Password must be no more than ${APP_CONFIG.VALIDATION.PASSWORD_MAX_LENGTH} characters`
    }
  ])
}

/**
 * Plant ID validation
 */
export function validatePlantId(plantId: string): ValidationResult {
  return validateValue(plantId, [
    { required: true, message: 'Plant selection is required' },
    {
      pattern: APP_CONFIG.VALIDATION.PLANT_ID_REGEX,
      message: 'Invalid plant ID format'
    }
  ])
}

/**
 * Username validation
 */
export function validateUsername(username: string): ValidationResult {
  return validateValue(username, [
    { required: true, message: 'Username is required' },
    {
      minLength: 3,
      message: 'Username must be at least 3 characters'
    },
    {
      pattern: APP_CONFIG.VALIDATION.USERNAME_REGEX,
      message: 'Username can only contain letters, numbers, dots, underscores, and hyphens'
    }
  ])
}

/**
 * Sanitize string input
 */
export function sanitizeString(input: string): string {
  if (!input) return ''
  
  return input
    .toString()
    .trim()
    .replace(/[<>]/g, '') // Remove potential HTML tags
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .replace(/on\w+=/gi, '') // Remove event handlers
}

/**
 * Validate and sanitize form data
 */
export function sanitizeFormData<T extends Record<string, any>>(data: T): T {
  const sanitized: Record<string, any> = { ...data }

  for (const [key, value] of Object.entries(sanitized)) {
    if (typeof value === 'string') {
      sanitized[key] = sanitizeString(value)
    }
  }

  return sanitized as T
}

/**
 * Check if a value is a valid number
 */
export function isValidNumber(value: any): boolean {
  return !isNaN(value) && !isNaN(parseFloat(value))
}

/**
 * Check if a value is a valid integer
 */
export function isValidInteger(value: any): boolean {
  return Number.isInteger(Number(value))
}

/**
 * Check if a value is a valid date
 */
export function isValidDate(value: any): boolean {
  const date = new Date(value)
  return date instanceof Date && !isNaN(date.getTime())
}

/**
 * Validate file upload
 */
export function validateFile(
  file: File,
  options: {
    maxSize?: number // in bytes
    allowedTypes?: string[]
    allowedExtensions?: string[]
  } = {}
): ValidationResult {
  const errors: string[] = []

  if (!file) {
    errors.push('No file selected')
    return { isValid: false, errors }
  }

  // Check file size
  if (options.maxSize && file.size > options.maxSize) {
    const maxSizeMB = (options.maxSize / (1024 * 1024)).toFixed(1)
    errors.push(`File size must be less than ${maxSizeMB}MB`)
  }

  // Check file type
  if (options.allowedTypes && !options.allowedTypes.includes(file.type)) {
    errors.push(`File type ${file.type} is not allowed`)
  }

  // Check file extension
  if (options.allowedExtensions) {
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!extension || !options.allowedExtensions.includes(extension)) {
      errors.push(`File extension .${extension} is not allowed`)
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * Debounce function for validation
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout>

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }

    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}
