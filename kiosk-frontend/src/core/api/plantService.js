import axios from 'axios'
import { APP_CONFIG } from '@/config/constants.js'

const api = axios.create({
  baseURL: APP_CONFIG.FRAPPE_API_URL,
  timeout: APP_CONFIG.API_TIMEOUT,
  withCredentials: true
})

function normalizePlant(raw) {
  const plantId = raw.plant_id || raw.id || raw.name || ''
  const name = raw.plant_name || raw.name || plantId
  const location = raw.location || raw.address || raw.city || 'Unknown'
  const status = (raw.status || raw.enabled || 'Active')
  const icon = raw.icon || '🏭'
  const type = raw.type || raw.plant_type || 'Operations'
  return {
    id: String(plantId).toLowerCase().trim().replace(/\s+/g, '-').replace(/[^a-z0-9-_]/g, ''),
    plant_id: plantId,
    name,
    location,
    status,
    icon,
    type,
  }
}

export const plantService = {
  async getPlants({ includeInactive = false } = {}) {
    const res = await api.get(APP_CONFIG.API_ENDPOINTS.GET_PLANTS, { params: {} })
    const data = Array.isArray(res.data?.message) ? res.data.message : (res.data?.data || [])
    const normalized = data.map(normalizePlant)
    const filtered = includeInactive ? normalized : normalized.filter(p => String(p.status).toLowerCase() === 'active' || p.status === 1 || p.status === true)
    return filtered
  }
}

export default plantService

// (Removed duplicate class-based implementation to avoid redeclaration)
