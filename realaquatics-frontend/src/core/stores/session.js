import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'realaquatics_session'

export const useSessionStore = defineStore('session', () => {
  const user = ref(null)
  const team = ref(null)
  const roles = ref([])
  const isManagerFlag = ref(false)
  const isAuthenticated = ref(false)

  function setSession(data) {
    user.value = { email: data.user, full_name: data.full_name }
    team.value = data.team
    roles.value = data.roles || []
    isManagerFlag.value = data.is_manager || false
    isAuthenticated.value = true

    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      user: user.value,
      team: team.value,
      roles: roles.value,
      is_manager: isManagerFlag.value,
    }))
  }

  function clearSession() {
    user.value = null
    team.value = null
    roles.value = []
    isManagerFlag.value = false
    isAuthenticated.value = false
    localStorage.removeItem(STORAGE_KEY)
  }

  function initFromStorage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (!stored) return false

      const data = JSON.parse(stored)
      user.value = data.user
      team.value = data.team
      roles.value = data.roles || []
      isManagerFlag.value = data.is_manager || false
      isAuthenticated.value = true
      return true
    } catch {
      clearSession()
      return false
    }
  }

  const isManager = computed(() => isManagerFlag.value)
  const isProcurement = computed(() => team.value === 'procurement')
  const isProcurementManager = computed(() => team.value === 'procurement' && isManagerFlag.value)
  const fullName = computed(() => user.value?.full_name || '')
  const userEmail = computed(() => user.value?.email || '')

  return {
    user, team, roles, isAuthenticated,
    isManager, isProcurement, isProcurementManager,
    fullName, userEmail,
    setSession, clearSession, initFromStorage,
  }
})
