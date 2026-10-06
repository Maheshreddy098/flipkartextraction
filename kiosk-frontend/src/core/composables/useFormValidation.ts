/**
 * Form Validation Composable
 * Provides reactive form validation with type safety
 */

import { ref, computed, reactive, Ref, ComputedRef } from 'vue'

// Validation rule type
export type ValidationRule<T = any> = (value: T) => string | null

// Validation rules object type
export type ValidationRules<T> = {
  [K in keyof T]?: ValidationRule<T[K]>
}

// Form validation composable return type
export interface UseFormValidationReturn<T> {
  values: Ref<T>
  errors: Ref<Partial<Record<keyof T, string>>>
  touched: Ref<Partial<Record<keyof T, boolean>>>
  isValid: ComputedRef<boolean>
  isDirty: ComputedRef<boolean>
  validate: (field?: keyof T) => boolean
  validateAll: () => boolean
  touch: (field: keyof T) => void
  touchAll: () => void
  reset: () => void
  setFieldValue: (field: keyof T, value: any) => void
  setFieldError: (field: keyof T, error: string | null) => void
}

/**
 * Form validation composable
 * @param initialValues - Initial form values
 * @param rules - Validation rules for each field
 * @returns Form validation utilities
 */
export function useFormValidation<T extends Record<string, any>>(
  initialValues: T,
  rules: ValidationRules<T>
): UseFormValidationReturn<T> {
  // Reactive state
  const values = ref<T>({ ...initialValues }) as Ref<T>
  const errors = ref<Partial<Record<keyof T, string>>>({})
  const touched = ref<Partial<Record<keyof T, boolean>>>({})

  /**
   * Check if form is valid (no errors)
   */
  const isValid = computed(() => {
    return Object.keys(errors.value).length === 0
  })

  /**
   * Check if form has been modified
   */
  const isDirty = computed(() => {
    return Object.keys(touched.value).length > 0
  })

  /**
   * Validate a specific field or all fields
   * @param field - Field to validate (optional)
   * @returns true if valid, false if invalid
   */
  function validate(field?: keyof T): boolean {
    if (field) {
      // Validate single field
      const rule = rules[field]
      if (!rule) return true

      const error = rule(values.value[field])
      if (error) {
        errors.value[field] = error
        return false
      } else {
        delete errors.value[field]
        return true
      }
    } else {
      // Validate all fields
      return validateAll()
    }
  }

  /**
   * Validate all fields
   * @returns true if all valid, false if any invalid
   */
  function validateAll(): boolean {
    let isFormValid = true
    const newErrors: Partial<Record<keyof T, string>> = {}

    for (const field in rules) {
      const rule = rules[field as keyof T]
      if (!rule) continue

      const error = rule(values.value[field as keyof T])
      if (error) {
        newErrors[field as keyof T] = error
        isFormValid = false
      }
    }

    errors.value = newErrors
    return isFormValid
  }

  /**
   * Mark field as touched
   * @param field - Field to mark as touched
   */
  function touch(field: keyof T): void {
    touched.value[field] = true
  }

  /**
   * Mark all fields as touched
   */
  function touchAll(): void {
    const allTouched: Partial<Record<keyof T, boolean>> = {}
    for (const field in values.value) {
      allTouched[field as keyof T] = true
    }
    touched.value = allTouched
  }

  /**
   * Reset form to initial state
   */
  function reset(): void {
    values.value = { ...initialValues }
    errors.value = {}
    touched.value = {}
  }

  /**
   * Set value for a specific field
   * @param field - Field name
   * @param value - New value
   */
  function setFieldValue(field: keyof T, value: any): void {
    values.value[field] = value
    touch(field)
    validate(field)
  }

  /**
   * Set error for a specific field (manual error)
   * @param field - Field name
   * @param error - Error message (null to clear)
   */
  function setFieldError(field: keyof T, error: string | null): void {
    if (error) {
      errors.value[field] = error
    } else {
      delete errors.value[field]
    }
  }

  return {
    values,
    errors,
    touched,
    isValid,
    isDirty,
    validate,
    validateAll,
    touch,
    touchAll,
    reset,
    setFieldValue,
    setFieldError
  }
}

/**
 * Common validation rules
 */
export const validators = {
  /**
   * Required field validator
   */
  required: (message: string = 'This field is required') => (value: any): string | null => {
    if (value === null || value === undefined || value === '') {
      return message
    }
    if (typeof value === 'string' && value.trim() === '') {
      return message
    }
    if (Array.isArray(value) && value.length === 0) {
      return message
    }
    return null
  },

  /**
   * Email validator
   */
  email: (message: string = 'Invalid email address') => (value: string): string | null => {
    if (!value) return null // Allow empty (use required separately)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(value) ? null : message
  },

  /**
   * Minimum length validator
   */
  minLength: (min: number, message?: string) => (value: string): string | null => {
    if (!value) return null
    const msg = message || `Minimum length is ${min} characters`
    return value.length >= min ? null : msg
  },

  /**
   * Maximum length validator
   */
  maxLength: (max: number, message?: string) => (value: string): string | null => {
    if (!value) return null
    const msg = message || `Maximum length is ${max} characters`
    return value.length <= max ? null : msg
  },

  /**
   * Minimum value validator (for numbers)
   */
  min: (min: number, message?: string) => (value: number): string | null => {
    if (value === null || value === undefined) return null
    const msg = message || `Minimum value is ${min}`
    return value >= min ? null : msg
  },

  /**
   * Maximum value validator (for numbers)
   */
  max: (max: number, message?: string) => (value: number): string | null => {
    if (value === null || value === undefined) return null
    const msg = message || `Maximum value is ${max}`
    return value <= max ? null : msg
  },

  /**
   * Pattern validator (regex)
   */
  pattern: (regex: RegExp, message: string = 'Invalid format') => (value: string): string | null => {
    if (!value) return null
    return regex.test(value) ? null : message
  },

  /**
   * Numeric validator
   */
  numeric: (message: string = 'Must be a number') => (value: any): string | null => {
    if (value === null || value === undefined || value === '') return null
    return !isNaN(Number(value)) ? null : message
  },

  /**
   * Positive number validator
   */
  positive: (message: string = 'Must be a positive number') => (value: number): string | null => {
    if (value === null || value === undefined) return null
    return value > 0 ? null : message
  },

  /**
   * Match field validator (e.g., password confirmation)
   */
  matches: (otherField: string, message?: string) => (value: any, allValues: any): string | null => {
    const msg = message || `Must match ${otherField}`
    return value === allValues[otherField] ? null : msg
  },

  /**
   * Custom validator
   */
  custom: (validatorFn: (value: any) => boolean, message: string) => (value: any): string | null => {
    return validatorFn(value) ? null : message
  }
}

/**
 * Usage Examples:
 * 
 * import { useFormValidation, validators } from '@/core/composables/useFormValidation'
 * 
 * // In component
 * const { values, errors, touched, isValid, validate, touch, setFieldValue } = useFormValidation(
 *   {
 *     email: '',
 *     password: '',
 *     quantity: 0
 *   },
 *   {
 *     email: validators.required('Email is required'),
 *     password: validators.minLength(8, 'Password must be at least 8 characters'),
 *     quantity: validators.positive('Quantity must be greater than 0')
 *   }
 * )
 * 
 * // In template
 * <input
 *   v-model="values.email"
 *   @blur="touch('email'); validate('email')"
 * />
 * <span v-if="touched.email && errors.email">{{ errors.email }}</span>
 * 
 * // On submit
 * function handleSubmit() {
 *   if (validateAll()) {
 *     // Form is valid, submit data
 *   }
 * }
 */

