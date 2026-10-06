<template>
  <div class="p-4 sm:p-6">
    <h1 class="mb-5 text-xl font-bold text-gray-900 sm:text-2xl">Admin Setup</h1>

    <!-- Tabs -->
    <div class="mb-5 flex gap-1.5 border-b border-gray-200 overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors"
        :class="
          activeTab === tab.id
            ? 'border-teal-600 text-teal-700'
            : 'border-transparent text-gray-500 hover:text-gray-800'
        "
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ── Plants Tab ──────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'plants'" class="space-y-4">
      <div class="flex items-center justify-between">
        <p class="text-sm text-gray-600">Manage the 5 plants and their warehouses.</p>
        <button
          type="button"
          class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          @click="openPlantForm(null)"
        >
          + Add Plant
        </button>
      </div>

      <div v-if="loadingPlants" class="space-y-2">
        <div v-for="i in 3" :key="i" class="h-24 animate-pulse rounded-xl bg-gray-100" />
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="plant in plants"
          :key="plant.plant_code"
          class="rounded-xl border border-gray-200 bg-white p-4"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div class="flex items-center gap-2">
                <p class="font-semibold text-gray-900">{{ plant.plant_name }}</p>
                <span class="font-mono text-xs text-gray-400">{{ plant.plant_code }}</span>
                <span
                  class="rounded-full px-2 py-0.5 text-[10px] font-medium"
                  :class="plant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                >
                  {{ plant.is_active ? 'Active' : 'Inactive' }}
                </span>
              </div>
              <p class="mt-1 text-xs text-gray-500">{{ plant.location || '—' }}</p>
              <p class="text-xs text-gray-500">
                Customer Code: <strong>{{ plant.delivery_customer_code || '⚠ Not set' }}</strong>
              </p>
            </div>
            <button
              type="button"
              class="rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50"
              @click="openPlantForm(plant)"
            >
              Edit
            </button>
          </div>
          <div class="mt-3">
            <p class="mb-1.5 text-xs font-medium text-gray-600">Warehouses ({{ plant.warehouses.length }})</p>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="wh in plant.warehouses"
                :key="wh.warehouse_code"
                class="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-700"
                :class="!wh.is_active ? 'opacity-40 line-through' : ''"
              >
                {{ wh.warehouse_code }}
                <span class="text-gray-400">{{ wh.warehouse_type }}</span>
              </span>
              <span v-if="!plant.warehouses.length" class="text-xs text-amber-600">⚠ No warehouses — click Edit to add</span>
            </div>
          </div>
        </div>
        <p v-if="!plants.length" class="rounded-xl border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
          No plants configured yet. Click + Add Plant to get started.
        </p>
      </div>

      <!-- Plant Form Modal -->
      <div
        v-if="plantForm.open"
        class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-10 sm:items-center sm:pt-4"
        @click.self="plantForm.open = false"
      >
        <div class="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl">
          <h2 class="mb-4 text-lg font-bold text-gray-900">
            {{ plantForm.isNew ? 'Add Plant' : 'Edit Plant' }}
          </h2>

          <div class="space-y-4">
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs font-medium text-gray-700">Plant Code <span class="text-red-500">*</span></label>
                <input
                  v-model="plantForm.plant_code"
                  type="text"
                  :readonly="!plantForm.isNew"
                  class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  :class="!plantForm.isNew ? 'bg-gray-50 text-gray-500' : ''"
                  placeholder="e.g. MAHAD"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-gray-700">Plant Name <span class="text-red-500">*</span></label>
                <input v-model="plantForm.plant_name" type="text" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="e.g. Mahadevpura" />
              </div>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs font-medium text-gray-700">Location</label>
                <input v-model="plantForm.location" type="text" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="City / address" />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-gray-700">
                  Customer Code (SAP) <span class="text-red-500">*</span>
                </label>
                <input v-model="plantForm.delivery_customer_code" type="text" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="e.g. C0001 (dummy customer)" />
                <p class="mt-1 text-[10px] text-gray-400">Delivery notes will be posted to this SAP customer per plant.</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <input v-model="plantForm.is_active" type="checkbox" class="rounded" id="plant-active" />
              <label for="plant-active" class="text-sm text-gray-700">Active</label>
            </div>

            <!-- Warehouses -->
            <div>
              <div class="mb-2 flex items-center justify-between">
                <label class="text-xs font-medium text-gray-700">Warehouses</label>
                <button type="button" class="text-xs text-teal-700 hover:text-teal-900" @click="addWarehouse">+ Add Warehouse</button>
              </div>
              <div class="space-y-2">
                <div
                  v-for="(wh, idx) in plantForm.warehouses"
                  :key="idx"
                  class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-2"
                >
                  <input
                    v-model="wh.warehouse_code"
                    type="text"
                    class="flex-1 rounded border border-gray-300 bg-white px-2 py-1 text-xs"
                    placeholder="Warehouse Code (SAP)"
                  />
                  <input
                    v-model="wh.warehouse_name"
                    type="text"
                    class="flex-1 rounded border border-gray-300 bg-white px-2 py-1 text-xs"
                    placeholder="Name"
                  />
                  <select v-model="wh.warehouse_type" class="rounded border border-gray-300 bg-white px-2 py-1 text-xs">
                    <option>Main</option>
                    <option>Transit</option>
                    <option>Returns</option>
                  </select>
                  <input v-model="wh.is_active" type="checkbox" title="Active" />
                  <button type="button" class="text-red-400 hover:text-red-600 text-xs px-1" @click="plantForm.warehouses.splice(idx, 1)">✕</button>
                </div>
              </div>
            </div>

            <div v-if="plantForm.error" class="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{{ plantForm.error }}</div>
            <div v-if="plantForm.success" class="rounded-lg bg-green-50 px-3 py-2 text-xs text-green-700">{{ plantForm.success }}</div>

            <div class="flex gap-2 pt-2">
              <button
                type="button"
                class="flex-1 rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                :disabled="plantForm.saving"
                @click="savePlant"
              >
                {{ plantForm.saving ? 'Saving…' : 'Save Plant' }}
              </button>
              <button
                type="button"
                class="rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-700"
                @click="plantForm.open = false"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Users Tab ───────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'users'" class="space-y-4">
      <p class="text-sm text-gray-600">Assign Frappe users to plants so they can log in to StoreOps.</p>

      <div class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <strong>Before assigning:</strong> First create the user in Frappe Admin and give them one of:
        <em>Consumables Store User</em>, <em>Consumables Store Manager</em>, or <em>Consumables Procurement User</em> role.
        Then assign them here.
      </div>

      <!-- New assignment form -->
      <div class="rounded-xl border border-gray-200 bg-white p-4">
        <h3 class="mb-3 text-sm font-semibold text-gray-900">Add Assignment</h3>
        <div class="grid gap-3 sm:grid-cols-3">
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-700">User</label>
            <select v-model="newMapping.user" class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">
              <option value="">Select user</option>
              <option v-for="u in eligibleUsers" :key="u.user" :value="u.user">
                {{ u.full_name }} ({{ u.role.replace('Consumables ', '') }})
              </option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-700">Plant</label>
            <select v-model="newMapping.plant" class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">
              <option value="">Select plant</option>
              <option v-for="p in plants" :key="p.plant_code" :value="p.plant_code">
                {{ p.plant_name }}
              </option>
            </select>
          </div>
          <div class="flex items-end">
            <button
              type="button"
              class="w-full rounded-lg bg-teal-600 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
              :disabled="!newMapping.user || !newMapping.plant || savingMapping"
              @click="addMapping"
            >
              {{ savingMapping ? 'Saving…' : 'Assign' }}
            </button>
          </div>
        </div>
        <div v-if="mappingError" class="mt-2 text-xs text-red-600">{{ mappingError }}</div>
      </div>

      <!-- Existing mappings -->
      <div v-if="loadingMappings" class="space-y-2">
        <div v-for="i in 4" :key="i" class="h-14 animate-pulse rounded-xl bg-gray-100" />
      </div>

      <div v-else class="overflow-hidden rounded-xl border border-gray-200 bg-white">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-600">
            <tr>
              <th class="px-4 py-2.5 text-left font-medium">User</th>
              <th class="px-4 py-2.5 text-left font-medium">Plant</th>
              <th class="px-4 py-2.5 text-left font-medium">Status</th>
              <th class="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            <tr v-if="!userMappings.length">
              <td colspan="4" class="px-4 py-6 text-center text-gray-500">No assignments yet.</td>
            </tr>
            <tr
              v-for="m in userMappings"
              :key="m.name"
              class="border-t border-gray-100"
            >
              <td class="px-4 py-2.5">
                <p class="font-medium text-gray-900">{{ m.full_name }}</p>
                <p class="text-xs text-gray-500">{{ m.user }}</p>
              </td>
              <td class="px-4 py-2.5 text-gray-700">{{ m.plant }}</td>
              <td class="px-4 py-2.5">
                <span
                  class="rounded-full px-2 py-0.5 text-[10px] font-medium"
                  :class="m.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                >
                  {{ m.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  type="button"
                  class="text-xs text-red-500 hover:text-red-700"
                  @click="removeMapping(m.name)"
                >
                  Remove
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Settings Tab ────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'settings'" class="max-w-xl space-y-5">
      <p class="text-sm text-gray-600">Global settings for the StoreOps module.</p>

      <div v-if="loadingSettings" class="space-y-3">
        <div v-for="i in 4" :key="i" class="h-10 animate-pulse rounded-lg bg-gray-100" />
      </div>

      <div v-else class="space-y-4 rounded-xl border border-gray-200 bg-white p-5">
        <div>
          <label class="mb-1 block text-sm font-medium text-gray-700">HANA Schema</label>
          <input v-model="settings.hana_schema" type="text" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="e.g. KFL_LIVE" />
          <p class="mt-1 text-xs text-gray-400">Schema name used to query SAP HANA for inventory data.</p>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-gray-700">Default Delivery Customer</label>
          <input v-model="settings.default_delivery_customer" type="text" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="SAP CardCode" />
          <p class="mt-1 text-xs text-gray-400">Fallback customer code if a plant has no specific code set.</p>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-gray-700">SAP Posting Queue</label>
          <select v-model="settings.sap_posting_queue" class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">
            <option value="long">long (recommended)</option>
            <option value="default">default</option>
            <option value="short">short</option>
          </select>
        </div>
        <div class="flex items-center gap-2">
          <input v-model="settings.enable_realtime_notifications" type="checkbox" id="realtime" class="rounded" />
          <label for="realtime" class="text-sm text-gray-700">Enable realtime notifications</label>
        </div>

        <div v-if="settingsError" class="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{{ settingsError }}</div>
        <div v-if="settingsSuccess" class="rounded-lg bg-green-50 px-3 py-2 text-xs text-green-700">{{ settingsSuccess }}</div>

        <button
          type="button"
          class="w-full rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
          :disabled="savingSettings"
          @click="saveSettings"
        >
          {{ savingSettings ? 'Saving…' : 'Save Settings' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  get_plants, save_plant,
  get_user_plant_mappings, get_eligible_users, save_user_plant_mapping, delete_user_plant_mapping,
  get_settings, save_settings as apiSaveSettings,
} from '@/core/api/admin.js'

const tabs = [
  { id: 'plants', label: 'Plants & Warehouses' },
  { id: 'users', label: 'User Assignments' },
  { id: 'settings', label: 'Settings' },
]
const activeTab = ref('plants')

// ── Plants ────────────────────────────────────────────────────────────────────
const plants = ref([])
const loadingPlants = ref(false)

const plantForm = ref({
  open: false,
  isNew: true,
  saving: false,
  error: '',
  success: '',
  plant_code: '',
  plant_name: '',
  location: '',
  is_active: true,
  delivery_customer_code: '',
  warehouses: [],
})

function openPlantForm(plant) {
  if (plant) {
    Object.assign(plantForm.value, {
      open: true, isNew: false, saving: false, error: '', success: '',
      plant_code: plant.plant_code,
      plant_name: plant.plant_name,
      location: plant.location || '',
      is_active: !!plant.is_active,
      delivery_customer_code: plant.delivery_customer_code || '',
      warehouses: plant.warehouses.map(w => ({ ...w })),
    })
  } else {
    Object.assign(plantForm.value, {
      open: true, isNew: true, saving: false, error: '', success: '',
      plant_code: '', plant_name: '', location: '', is_active: true,
      delivery_customer_code: '', warehouses: [],
    })
  }
}

function addWarehouse() {
  plantForm.value.warehouses.push({ warehouse_code: '', warehouse_name: '', warehouse_type: 'Main', is_active: true })
}

async function savePlant() {
  plantForm.value.error = ''
  plantForm.value.success = ''
  if (!plantForm.value.plant_code.trim() || !plantForm.value.plant_name.trim()) {
    plantForm.value.error = 'Plant Code and Name are required.'
    return
  }
  plantForm.value.saving = true
  try {
    await save_plant({
      plant_code: plantForm.value.plant_code.trim(),
      plant_name: plantForm.value.plant_name.trim(),
      location: plantForm.value.location,
      is_active: plantForm.value.is_active ? 1 : 0,
      delivery_customer_code: plantForm.value.delivery_customer_code,
      warehouses: plantForm.value.warehouses,
    })
    plantForm.value.success = 'Plant saved.'
    await loadPlants()
    setTimeout(() => { plantForm.value.open = false }, 800)
  } catch (e) {
    plantForm.value.error = e?.message || 'Failed to save.'
  } finally {
    plantForm.value.saving = false
  }
}

async function loadPlants() {
  loadingPlants.value = true
  try {
    const res = await get_plants()
    plants.value = res?.message ?? res ?? []
  } catch {
    plants.value = []
  } finally {
    loadingPlants.value = false
  }
}

// ── Users ─────────────────────────────────────────────────────────────────────
const userMappings = ref([])
const eligibleUsers = ref([])
const loadingMappings = ref(false)
const newMapping = ref({ user: '', plant: '' })
const savingMapping = ref(false)
const mappingError = ref('')

async function loadMappings() {
  loadingMappings.value = true
  try {
    const [mr, ur] = await Promise.all([get_user_plant_mappings(), get_eligible_users()])
    userMappings.value = mr?.message ?? mr ?? []
    eligibleUsers.value = ur?.message ?? ur ?? []
  } catch {
    userMappings.value = []
  } finally {
    loadingMappings.value = false
  }
}

async function addMapping() {
  if (!newMapping.value.user || !newMapping.value.plant) return
  savingMapping.value = true
  mappingError.value = ''
  try {
    await save_user_plant_mapping(newMapping.value.user, newMapping.value.plant)
    newMapping.value = { user: '', plant: '' }
    await loadMappings()
  } catch (e) {
    mappingError.value = e?.message || 'Failed to assign.'
  } finally {
    savingMapping.value = false
  }
}

async function removeMapping(name) {
  if (!confirm('Remove this user-plant assignment?')) return
  try {
    await delete_user_plant_mapping(name)
    await loadMappings()
  } catch (e) {
    mappingError.value = e?.message || 'Failed to remove.'
  }
}

// ── Settings ──────────────────────────────────────────────────────────────────
const settings = ref({ hana_schema: '', default_delivery_customer: '', sap_posting_queue: 'long', enable_realtime_notifications: true })
const loadingSettings = ref(false)
const savingSettings = ref(false)
const settingsError = ref('')
const settingsSuccess = ref('')

async function loadSettings() {
  loadingSettings.value = true
  try {
    const res = await get_settings()
    const d = res?.message ?? res ?? {}
    settings.value = { ...d, enable_realtime_notifications: !!d.enable_realtime_notifications }
  } catch {
    /* use defaults */
  } finally {
    loadingSettings.value = false
  }
}

async function saveSettings() {
  savingSettings.value = true
  settingsError.value = ''
  settingsSuccess.value = ''
  try {
    await apiSaveSettings({
      ...settings.value,
      enable_realtime_notifications: settings.value.enable_realtime_notifications ? 1 : 0,
    })
    settingsSuccess.value = 'Settings saved.'
    setTimeout(() => { settingsSuccess.value = '' }, 3000)
  } catch (e) {
    settingsError.value = e?.message || 'Failed to save.'
  } finally {
    savingSettings.value = false
  }
}

onMounted(() => {
  loadPlants()
  loadMappings()
  loadSettings()
})
</script>
