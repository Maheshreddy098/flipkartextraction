/**
 * Global Window Type Definitions
 * Extends the Window interface with custom properties and methods
 */

declare global {
  interface Window {
    /**
     * Global error notification method
     * Shows error toast to user
     */
    showGlobalError?: (message: string) => void

    /**
     * Global success notification method
     * Shows success toast to user
     */
    showGlobalSuccess?: (message: string) => void

    /**
     * Boot data injected by backend (Frappe)
     * Contains initialization data from Jinja templates
     */
    csrf_token?: string
    site_name?: string
    user?: string
    user_id?: string
    app_version?: string

    /**
     * Plant-specific configuration
     */
    plant_config?: {
      id: string
      name: string
      features: string[]
    }
  }
}

// Required for module augmentation
export {}

