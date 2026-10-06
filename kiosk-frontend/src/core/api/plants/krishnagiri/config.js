/**
 * Krishnagiri Plant Configuration
 */

export const KRISHNAGIRI_CONFIG = {
  plantId: 'krishnagiri',
  plantName: 'Krishnagiri',
  plantDisplayName: 'Krishnagiri Plant',
  
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
    warehousePrefixes: ['KG', 'DK'],
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
        'krishnagiri.plant@khanalfoods.com',
        'operations@khanalfoods.com'
      ]
    },
    production: {
      recipients: [
        'krishnagiri.plant@khanalfoods.com',
        'production@khanalfoods.com'
      ]
    }
  }
}

export default KRISHNAGIRI_CONFIG
