/**
 * Malur Plant Configuration
 * Plant-specific settings and features
 */

export default {
  plantId: 'malur',
  plantName: 'Malur Plant',
  location: 'Malur, Karnataka',
  warehousePrefix: 'HN',
  
  // Feature flags
  features: {
    grn: true,
    production: true,
    inventory: true,
    quality: false,
    reports: true
  },
  
  // Plant-specific settings
  settings: {
    // Batch number format: {vendorCode}-{itemCode}-{date}
    batchNumberFormat: '{vendorCode}-{itemCode}-{date}',
    
    // Available process types for this plant
    defaultProcessTypes: ['Drying Process', 'Churpi Process'],
    
    // Email notifications enabled
    emailNotifications: true,
    
    // Approval required for GRN/Production
    approvalRequired: true,
    
    // Default pagination
    defaultPageSize: 20,
    
    // Auto-refresh intervals (in seconds)
    autoRefreshInterval: 300, // 5 minutes
    
    // Timezone
    timezone: 'Asia/Kolkata'
  },
  
  // Validation rules
  validation: {
    // Warehouse must start with this prefix
    warehouseMustStartWith: 'HN',
    
    // Batch size limits
    minBatchSize: 1,
    maxBatchSize: 10000,
    
    // Moisture content limits (percentage)
    minMoisture: 5,
    maxMoisture: 15,
    
    // Employee count limits
    minEmployeeCount: 1,
    maxEmployeeCount: 50
  },
  
  // API endpoints overrides (if any)
  endpoints: {
    // Custom endpoints for Malur if needed
  },
  
  // UI customization
  ui: {
    theme: {
      primary: '#3b82f6',
      secondary: '#10b981',
      danger: '#ef4444'
    },
    logo: '/assets/malur-logo.png',
    dashboardWidgets: ['grn-stats', 'production-stats', 'inventory-summary']
  }
}

