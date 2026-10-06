/**
 * Mahadevpura Plant Configuration
 */

export const MAHADEVPURA_CONFIG = {
  plantId: 'mahadevpura',
  plantName: 'Mahadevpura',
  plantDisplayName: 'Mahadevpura Plant',
  
  // Feature flags
  features: {
    grn: true,
    productionOrder: true,
    inventoryTransfer: true,
    quality: true
  },
  
  // GRN Configuration
  grn: {
    allowDirectPosting: true,  // No draft state
    requireApproval: false,     // Direct SAP posting
    warehousePrefixes: ['DC'],
    defaultView: 'create',
    
    // Process types (update with actual types)
    processTypes: [
      { value: 'receiving', label: 'Receiving Process' },
      { value: 'quality_check', label: 'Quality Check Process' },
      { value: 'storage', label: 'Storage Process' }
    ]
  },
  
  // Production Configuration
  production: {
    processTypes: [
      { value: 'processing', label: 'Processing' },
      { value: 'packaging', label: 'Packaging' }
    ]
  },
  
  // Settings
  settings: {
    defaultPageSize: 20,
    timezone: 'Asia/Kolkata',
    dateFormat: 'DD/MM/YYYY',
    currency: 'INR'
  },
  
  // Notification Configuration
  notifications: {
    grn: {
      recipients: [
        'mahadevpura.plant@khanalfoods.com',
        'operations@khanalfoods.com'
      ]
    },
    production: {
      recipients: [
        'mahadevpura.plant@khanalfoods.com',
        'production@khanalfoods.com'
      ]
    }
  }
}

export default MAHADEVPURA_CONFIG

