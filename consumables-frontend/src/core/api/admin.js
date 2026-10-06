import { frappeRequest } from 'frappe-ui'

const BASE = 'khanal_tech_integrations.consumables.api.admin'

export function get_plants() {
  return frappeRequest({ url: `${BASE}.get_plants` })
}

export function save_plant(data) {
  return frappeRequest({ url: `${BASE}.save_plant`, params: data })
}

export function get_user_plant_mappings(plant = '') {
  const params = plant ? { plant } : {}
  return frappeRequest({ url: `${BASE}.get_user_plant_mappings`, params })
}

export function get_eligible_users() {
  return frappeRequest({ url: `${BASE}.get_eligible_users` })
}

export function save_user_plant_mapping(user, plant, is_active = 1, notes = '') {
  return frappeRequest({ url: `${BASE}.save_user_plant_mapping`, params: { user, plant, is_active, notes } })
}

export function delete_user_plant_mapping(name) {
  return frappeRequest({ url: `${BASE}.delete_user_plant_mapping`, params: { name } })
}

export function get_settings() {
  return frappeRequest({ url: `${BASE}.get_settings` })
}

export function save_settings(data) {
  return frappeRequest({ url: `${BASE}.save_settings`, params: data })
}
