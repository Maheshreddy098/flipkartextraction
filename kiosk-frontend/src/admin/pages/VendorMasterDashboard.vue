<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Vendor Master Dashboard</h1>
      <button
        @click="refreshAll"
        :disabled="dashboardData.loading"
        class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ dashboardData.loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="dashboardData.loading && !dashboardData.data" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
        <p class="text-gray-600">Loading dashboard...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="dashboardData.error" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <div class="flex items-center">
        <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
        </svg>
        <p class="text-sm text-red-600">
          Failed to load dashboard data: {{ dashboardData.error?.message || dashboardData.error }}
        </p>
      </div>
    </div>

    <div v-if="summary" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-900 font-semibold">Total Registrations</p>
        <h3 class="text-2xl font-semibold text-gray-900 mt-2">{{ summary.total }}</h3>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-900 font-semibold">Pending (Not Seen)</p>
        <h3 class="text-2xl font-semibold text-yellow-700 mt-2">{{ summary.pending }}</h3>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-900 font-semibold">Approved</p>
        <h3 class="text-2xl font-semibold text-green-700 mt-2">{{ summary.approved }}</h3>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-900 font-semibold">Rejected</p>
        <h3 class="text-2xl font-semibold text-red-700 mt-2">{{ summary.rejected }}</h3>
      </div>
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <p class="text-xs uppercase tracking-wide text-gray-900 font-semibold">Created in SAP</p>
        <h3 class="text-2xl font-semibold text-blue-700 mt-2">{{ summary.sap_created }}</h3>
      </div>
    </div>

    <div class="bg-white border rounded-lg shadow-sm p-6 mb-6">
      <div class="flex items-start justify-between">
        <div>
          <h2 class="text-xl font-semibold text-gray-900">Bank Verification</h2>
          <p class="text-sm text-gray-800 mt-1">Enter SAP BP CardCode (supports comma-separated)</p>
        </div>
      </div>
      <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <div class="md:col-span-2">
          <label class="block text-sm font-medium text-gray-900 mb-1">BP CardCode</label>
          <input
            v-model="pennyVendorNumber"
            type="text"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Example: V01779 or V00033,V00034"
            @keydown.enter="runPennyValidation"
          />
        </div>
        <button
          @click="runPennyValidation"
          :disabled="pennyState.loading"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {{ pennyState.loading ? 'Updating...' : 'Update' }}
        </button>
      </div>
      <div class="mt-4">
        <p v-if="pennyState.vendorLabel" class="text-sm font-medium text-gray-900 mb-2">
          {{ pennyState.vendorLabel }}
        </p>
        <pre class="bg-gray-50 border rounded-lg p-3 text-xs text-gray-900 whitespace-pre-wrap">{{ pennyResultText }}</pre>
      </div>
    </div>

    <div class="bg-white border rounded-lg shadow-sm p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-xl font-semibold text-gray-900">Frappe Vendor Registrations</h2>
          <p class="text-sm text-gray-800">Latest registrations with SAP status</p>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="bg-gray-200 text-left text-gray-900">
              <th class="px-3 py-2 font-semibold">#</th>
              <th class="px-3 py-2 font-semibold">Company</th>
              <th class="px-3 py-2 font-semibold">Vendor Name</th>
              <th class="px-3 py-2 font-semibold">Status</th>
              <th class="px-3 py-2 font-semibold">Vendor Number</th>
              <th class="px-3 py-2 font-semibold">SAP Code</th>
              <th class="px-3 py-2 font-semibold">Email</th>
              <th class="px-3 py-2 font-semibold">Mobile</th>
              <th class="px-3 py-2 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in registrations" :key="row.name" class="border-b">
              <td class="px-3 py-2">{{ index + 1 }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.company_name }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_name }}</td>
              <td class="px-3 py-2">
                <span :class="statusClass(row.status)" class="px-2 py-1 rounded-full text-xs">
                  {{ row.status }}
                </span>
              </td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_number }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_code || '-' }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.email }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.mobile_number }}</td>
              <td class="px-3 py-2">
                <button
                  class="px-2 py-1 text-xs border rounded hover:bg-gray-50"
                  @click="useVendorNumber(row.vendor_number)"
                >
                  Use
                </button>
              </td>
            </tr>
            <tr v-if="registrations.length === 0">
              <td colspan="9" class="px-3 py-6 text-center text-gray-800">No registrations found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="bg-white border rounded-lg shadow-sm p-6 mb-6">
      <div class="mb-4">
        <h2 class="text-xl font-semibold text-gray-900">SAP Vendor Mapping</h2>
        <p class="text-sm text-gray-800">Latest SAP master data mapped in Frappe</p>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="bg-gray-200 text-left text-gray-900">
              <th class="px-3 py-2 font-semibold">#</th>
              <th class="px-3 py-2 font-semibold">Vendor Code</th>
              <th class="px-3 py-2 font-semibold">Vendor Name</th>
              <th class="px-3 py-2 font-semibold">Short Code</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in sapVendorMapping" :key="`${row.vendor_code}-${index}`" class="border-b">
              <td class="px-3 py-2">{{ index + 1 }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_code }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_name }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_short_code }}</td>
            </tr>
            <tr v-if="sapVendorMapping.length === 0">
              <td colspan="4" class="px-3 py-6 text-center text-gray-800">No vendor mapping found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="bg-white border rounded-lg shadow-sm p-6">
      <div class="mb-4">
        <h2 class="text-xl font-semibold text-gray-900">Recent Successful Vendors</h2>
        <p class="text-sm text-gray-800">Latest vendors created in SAP</p>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="bg-gray-200 text-left text-gray-900">
              <th class="px-3 py-2 font-semibold">#</th>
              <th class="px-3 py-2 font-semibold">Company</th>
              <th class="px-3 py-2 font-semibold">Vendor Name</th>
              <th class="px-3 py-2 font-semibold">SAP Code</th>
              <th class="px-3 py-2 font-semibold">Last Updated</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in recentSuccessful" :key="`${row.vendor_code}-${index}`" class="border-b">
              <td class="px-3 py-2 text-gray-900">{{ index + 1 }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.company_name }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_name }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.vendor_code }}</td>
              <td class="px-3 py-2 text-gray-900">{{ row.modified }}</td>
            </tr>
            <tr v-if="recentSuccessful.length === 0">
              <td colspan="5" class="px-3 py-6 text-center text-gray-800">No successful vendors found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { createResource, frappeRequest } from 'frappe-ui'
import { APP_CONFIG } from '@/config/constants.js'

function frappeCall(method, args = {}) {
  return new Promise((resolve, reject) => {
    const frappeObj =
      (typeof frappe !== 'undefined' && frappe && frappe.call && frappe) ||
      (typeof window !== 'undefined' && window.frappe && window.frappe.call && window.frappe) ||
      null

    if (frappeObj) {
      frappeObj.call({
        method,
        args,
        callback: (r) => {
          if (r && r.message !== undefined) {
            resolve(r.message)
          } else if (r && r.exc) {
            reject(new Error(r.exc))
          } else {
            resolve(r)
          }
        },
        error: (r) => {
          const errorMsg = r?.message || r?.exc || 'Request failed'
          reject(new Error(errorMsg))
        }
      })
    } else {
      frappeRequest({
        method: 'POST',
        url: method,
        params: args
      })
        .then((res) => resolve(res))
        .catch((err) => reject(new Error(err?.message || 'Request failed')))
    }
  })
}

const dashboardData = createResource({
  url: APP_CONFIG.API_ENDPOINTS.VENDOR_DASHBOARD.GET_DASHBOARD,
  method: 'GET',
  auto: false,
  transform(data) {
    if (!data) return null
    if (data.message) return data.message
    return data
  }
})

const summary = computed(() => dashboardData.data?.summary || null)
const registrations = computed(() => dashboardData.data?.registrations || [])
const sapVendorMapping = computed(() => dashboardData.data?.sap_vendor_mapping || [])
const recentSuccessful = computed(() => dashboardData.data?.recent_successful || [])

const pennyVendorNumber = ref('')
const pennyState = ref({
  loading: false,
  vendorLabel: '',
  result: null,
  message: 'Awaiting validation...'
})

const pennyResultText = computed(() => {
  if (pennyState.value.loading) return 'Validating bank details...'
  if (pennyState.value.result) {
    return JSON.stringify(pennyState.value.result, null, 2)
  }
  return pennyState.value.message
})

function statusClass(status) {
  const normalized = String(status || '').toLowerCase()
  if (normalized.includes('approved')) return 'bg-green-100 text-green-700'
  if (normalized.includes('reject')) return 'bg-red-100 text-red-700'
  if (normalized.includes('not seen') || normalized.includes('pending')) return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-700'
}

function useVendorNumber(vendorNumber) {
  pennyVendorNumber.value = vendorNumber || ''
  pennyState.value.vendorLabel = ''
  pennyState.value.result = null
  pennyState.value.message = 'Awaiting validation...'
}

async function runPennyValidation() {
  const vendorNumber = pennyVendorNumber.value.trim()
  if (!vendorNumber) {
    pennyState.value = {
      loading: false,
      vendorLabel: '',
      result: null,
      message: 'Please enter a BP CardCode.'
    }
    return
  }

  pennyState.value.loading = true
  pennyState.value.result = null
  pennyState.value.vendorLabel = ''
  pennyState.value.message = 'Updating bank verification...'

  try {
    const result = await frappeCall(
      APP_CONFIG.API_ENDPOINTS.VENDOR_DASHBOARD.MANUALLY_UPDATE_BANK_VERIFICATION,
      {
        CardCode: vendorNumber
      }
    )
    if (result?.ok === false) {
      pennyState.value.message = result.message || 'Update failed.'
      pennyState.value.result = null
    } else {
      pennyState.value.message = result?.message || 'Update completed.'
      pennyState.value.result = result?.results || result
    }
  } catch (error) {
    pennyState.value.message = error?.message || 'Update failed.'
  } finally {
    pennyState.value.loading = false
  }
}

function refreshAll() {
  dashboardData.fetch()
}

onMounted(() => {
  refreshAll()
})
</script>
