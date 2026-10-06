import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { frappeRequest } from 'frappe-ui'

function getSessionUser() {
  const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
  const u = cookies.get('user_id')
  return u && u !== 'Guest' ? u : null
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref(getSessionUser())
  const fullName = ref(null)
  const role = ref(null)
  /** All consumables roles for this user (see backend get_current_user_context). */
  const consumablesRoles = ref([])
  const isSuperAdmin = ref(false)
  const isProcurementUser = ref(false)
  const plants = ref([])
  /** All active plants with warehouses — for fulfillment stock lookup (all plants for IM/Super Admin). */
  const sourcePlants = ref([])
  const loading = ref(false)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isManager = computed(() =>
    isSuperAdmin.value ||
    consumablesRoles.value.includes('Consumables Store Manager') ||
    consumablesRoles.value.includes('Consumables Inventory Manager'),
  )
  const isStoreUser = computed(() => !!role.value)

  async function fetchContext() {
    loading.value = true
    try {
      const data = await frappeRequest({
        url: 'khanal_tech_integrations.consumables.api.auth.get_current_user_context',
      })
      user.value = data.user
      fullName.value = data.full_name
      role.value = data.role
      consumablesRoles.value = Array.isArray(data.consumables_roles) ? data.consumables_roles : []
      isSuperAdmin.value = data.is_super_admin
      isProcurementUser.value = data.is_procurement_user
      plants.value = data.plants
      sourcePlants.value = data.source_plants || data.plants
      initialized.value = true
    } catch (e) {
      user.value = null
      initialized.value = true
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearAuth() {
    user.value = null
    fullName.value = null
    role.value = null
    consumablesRoles.value = []
    isSuperAdmin.value = false
    isProcurementUser.value = false
    plants.value = []
    sourcePlants.value = []
    initialized.value = false
  }

  return {
    user, fullName, role, consumablesRoles, isSuperAdmin, isProcurementUser, plants, sourcePlants,
    loading, initialized,
    isAuthenticated, isManager, isStoreUser,
    fetchContext, clearAuth,
  }
})
