/**
 * Nandi Hills Plant Utilities
 * Plant-specific utility functions for Nandi Hills Plant
 */

/**
 * Format production data for display
 * @param {Object} data - Production data
 * @returns {Object} Formatted data
 */
export const formatProductionData = (data) => {
  return {
    milk: `${data.milk}L`,
    yogurt: `${data.yogurt}L`,
    cheese: `${data.cheese}kg`,
    packaging: `${data.packaging} units`
  }
}

/**
 * Calculate efficiency percentage
 * @param {number} actual - Actual production
 * @param {number} target - Target production
 * @returns {number} Efficiency percentage
 */
export const calculateEfficiency = (actual, target) => {
  if (target === 0) return 0
  return Math.round((actual / target) * 100)
}

/**
 * Get plant-specific color scheme
 * @returns {Object} Color scheme
 */
export const getPlantColors = () => {
  return {
    primary: '#3B82F6',    // Blue
    secondary: '#10B981',  // Green
    accent: '#F59E0B',     // Yellow
    danger: '#EF4444',     // Red
    warning: '#F97316',    // Orange
    info: '#8B5CF6'        // Purple
  }
}

/**
 * Get plant-specific icons
 * @returns {Object} Icon mapping
 */
export const getPlantIcons = () => {
  return {
    plant: '🏔️',
    milk: '🥛',
    yogurt: '🍶',
    cheese: '🧀',
    packaging: '📦',
    quality: '✅',
    maintenance: '🔧',
    production: '🏭',
    efficiency: '📊',
    department: '🏢'
  }
}

/**
 * Format time duration
 * @param {Date} startTime - Start time
 * @param {Date} endTime - End time (optional, defaults to now)
 * @returns {string} Formatted duration
 */
export const formatDuration = (startTime, endTime = new Date()) => {
  const diffMs = endTime - startTime
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes}m`
  }
  return `${diffMinutes}m`
}

/**
 * Get plant-specific KPIs
 * @returns {Array} KPI definitions
 */
export const getPlantKPIs = () => {
  return [
    {
      id: 'production',
      name: 'Daily Production',
      value: '12,500L',
      target: '15,000L',
      unit: 'Liters',
      icon: '🏭',
      color: 'blue'
    },
    {
      id: 'quality',
      name: 'Quality Score',
      value: '97.2%',
      target: '95%',
      unit: 'Percentage',
      icon: '✅',
      color: 'green'
    },
    {
      id: 'efficiency',
      name: 'Efficiency',
      value: '91%',
      target: '90%',
      unit: 'Percentage',
      icon: '📊',
      color: 'yellow'
    },
    {
      id: 'orders',
      name: 'Active Orders',
      value: '8',
      target: '10',
      unit: 'Count',
      icon: '📋',
      color: 'purple'
    }
  ]
}

/**
 * Validate plant data
 * @param {Object} data - Plant data to validate
 * @returns {Object} Validation result
 */
export const validatePlantData = (data) => {
  const errors = []
  
  if (!data.name || data.name.trim() === '') {
    errors.push('Plant name is required')
  }
  
  if (!data.location || data.location.trim() === '') {
    errors.push('Plant location is required')
  }
  
  if (!data.status || !['Active', 'Inactive', 'Maintenance'].includes(data.status)) {
    errors.push('Valid plant status is required')
  }
  
  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * Get plant-specific notifications
 * @returns {Array} Notification templates
 */
export const getPlantNotifications = () => {
  return [
    {
      id: 'production_target',
      type: 'success',
      title: 'Production Target Achieved',
      message: 'Nandi Hills Plant has achieved today\'s production target of 12,500L',
      icon: '🎉'
    },
    {
      id: 'quality_check',
      type: 'info',
      title: 'Quality Check Scheduled',
      message: 'Quality check for all departments is scheduled for 2:00 PM',
      icon: '🔍'
    },
    {
      id: 'maintenance_reminder',
      type: 'warning',
      title: 'Maintenance Reminder',
      message: 'Cheese Press #1 maintenance is due in 3 days',
      icon: '⚠️'
    }
  ]
}

/**
 * Calculate plant performance score
 * @param {Object} metrics - Performance metrics
 * @returns {number} Performance score (0-100)
 */
export const calculatePerformanceScore = (metrics) => {
  const weights = {
    production: 0.3,
    quality: 0.3,
    efficiency: 0.2,
    safety: 0.1,
    maintenance: 0.1
  }
  
  let score = 0
  for (const [metric, weight] of Object.entries(weights)) {
    if (metrics[metric] !== undefined) {
      score += (metrics[metric] / 100) * weight * 100
    }
  }
  
  return Math.round(score)
}

/**
 * Get plant-specific weather data (mock)
 * @returns {Object} Weather information
 */
export const getPlantWeather = () => {
  return {
    temperature: '28°C',
    humidity: '65%',
    condition: 'Partly Cloudy',
    windSpeed: '12 km/h',
    icon: '⛅'
  }
}

/**
 * Format plant address
 * @returns {string} Formatted address
 */
export const getPlantAddress = () => {
  return `
    Nandi Hills Plant
    Kolar District
    Karnataka 563101
    India
  `.trim()
}

/**
 * Get plant contact information
 * @returns {Object} Contact details
 */
export const getPlantContacts = () => {
  return {
    manager: {
      name: 'Rajesh Kumar',
      phone: '+91 98765 43210',
      email: 'rajesh.kumar@khanalfoods.com'
    },
    supervisor: {
      name: 'Priya Sharma',
      phone: '+91 98765 43211',
      email: 'priya.sharma@khanalfoods.com'
    },
    emergency: {
      phone: '+91 98765 43212',
      email: 'emergency.nandi@khanalfoods.com'
    }
  }
}
