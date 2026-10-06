/**
 * Champavath Plant Configuration
 * Plant-specific settings and features
 */

export default {
  plantId: 'champavath',
  plantName: 'Champavath Plant',
  location: 'Champavath, Kerala',
  warehousePrefix: 'CH',
  
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
    batchNumberFormat: '{vendorCode}-{itemCode}-{date}',
    defaultProcessTypes: ['Drying Process', 'Churpi Process'],
    emailNotifications: true,
    approvalRequired: true,
    defaultPageSize: 20,
    autoRefreshInterval: 300,
    timezone: 'Asia/Kolkata'
  },
  
  // Validation rules
  validation: {
    warehouseMustStartWith: 'CH',
    minBatchSize: 1,
    maxBatchSize: 10000,
    minMoisture: 5,
    maxMoisture: 15,
    minEmployeeCount: 1,
    maxEmployeeCount: 50
  },
  
  // API endpoints overrides
  endpoints: {},
  
  // UI customization
  ui: {
    theme: {
      primary: '#f59e0b',
      secondary: '#14b8a6',
      danger: '#ef4444'
    },
    logo: '/assets/champavath-logo.png',
    dashboardWidgets: ['grn-stats', 'production-stats', 'inventory-summary']
  }
}

