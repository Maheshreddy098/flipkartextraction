<template>
  <div class="p-6">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">GRN Management - Malur Plant</h1>
      <p class="text-gray-600">Create and post Goods Receipt Notes directly to SAP</p>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-purple-100 rounded-lg">
            <span class="text-2xl">📦</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Total GRNs</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.total || 0 }}</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-green-100 rounded-lg">
            <span class="text-2xl">✅</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Posted to SAP</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.posted || 0 }}</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-blue-100 rounded-lg">
            <span class="text-2xl">📅</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">This Month</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.thisMonth || 0 }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ currentView === 'list' ? 'GRN History' : currentView === 'create' ? 'Create New GRN' : 'GRN Details' }}
        </h2>
        <div class="flex gap-2">
          <button
            v-if="currentView !== 'list'"
            @click="goBackToList"
            class="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
          >
            ← Back to List
          </button>
          <button
            v-if="currentView === 'list'"
            @click="showCreateForm"
            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            + Create New GRN
          </button>
        </div>
      </div>

      <div class="p-6">
        <!-- List View -->
        <div v-if="currentView === 'list'">
          <!-- Filters -->
          <div class="mb-6 flex gap-4">
            <input
              v-model="filters.search"
              @input="loadGRNList"
              type="text"
              placeholder="Search by PO No, Vendor, or SAP DocNum..."
              class="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white text-gray-900"
            />
            <select
              v-model="filters.dateRange"
              @change="loadGRNList"
              class="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white text-gray-900"
            >
              <option value="all">All Time</option>
              <option value="today">Today</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
            </select>
          </div>

          <!-- GRN List Table -->
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">GRN ID</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">SAP DocNum</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">PO Number</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vendor</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created By</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="grn in grnList" :key="grn.name" class="hover:bg-gray-50">
                  <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ grn.name }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <span v-if="grn.grn_docnum" class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      📄 {{ grn.grn_docnum }}
                    </span>
                    <span v-else class="text-gray-400">-</span>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ grn.po_no }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ grn.vendor_name }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(grn.received_date) }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ grn.owner }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div class="flex items-center gap-3">
                      <button
                        @click="viewGRN(grn)"
                        class="text-purple-600 hover:text-purple-900"
                      >
                        View Details
                      </button>
                      <button
                        v-if="canCancelGRN(grn)"
                        @click="openCancelModal(grn)"
                        class="text-red-600 hover:text-red-900 text-xs"
                        title="Cancel GRN"
                      >
                        ❌ Cancel
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="grnList.length === 0">
                  <td colspan="7" class="px-6 py-4 text-center text-sm text-gray-500">
                    No GRNs found
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="pagination.total_pages > 1" class="mt-6 flex items-center justify-between">
            <div class="text-sm text-gray-700">
              Showing {{ ((pagination.page - 1) * pagination.page_size) + 1 }} to 
              {{ Math.min(pagination.page * pagination.page_size, pagination.total) }} of 
              {{ pagination.total }} results
            </div>
            <div class="flex gap-2">
              <button
                @click="changePage(pagination.page - 1)"
                :disabled="pagination.page === 1"
                class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                @click="changePage(pagination.page + 1)"
                :disabled="pagination.page === pagination.total_pages"
                class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        <!-- Create Form -->
        <div v-else-if="currentView === 'create'">
          <CreateGRNForm @created="handleGRNCreated" @cancel="goBackToList" />
        </div>

        <!-- Detail View -->
        <div v-else-if="currentView === 'detail'">
          <GRNDetail :grn-id="selectedGRN" @close="goBackToList" />
        </div>
      </div>
    </div>

    <!-- Cancel GRN Modal -->
    <CancelGRNModal
      :is-open="showCancelModal"
      :grn="grnToCancel"
      :loading="cancellingGRN"
      @close="closeCancelModal"
      @confirm="handleCancelGRN"
    />
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { useGRN } from '@/composables/useGRN'
import { CancelGRNModal } from '@/shared/components/GRN'
import CreateGRNForm from '../components/CreateGRNForm.vue'
import GRNDetail from '../components/GRNDetail.vue'

export default {
  name: 'MalurGRN',
  components: {
    CreateGRNForm,
    GRNDetail,
    CancelGRNModal
  },
  setup() {
    // Initialize frappe-ui composable
    const { grnList: grnListResource, cancelGRN } = useGRN('malur')
    
    const currentView = ref('list')
    const grnList = ref([])
    const selectedGRN = ref(null)
    const loading = ref(false)
    
    const filters = ref({
      search: '',
      dateRange: 'month'
    })
    
    const pagination = ref({
      page: 1,
      page_size: 20,
      total: 0,
      total_pages: 0
    })
    
    const statistics = ref({
      total: 0,
      posted: 0,
      thisMonth: 0
    })
    
    const loadGRNList = async () => {
      try {
        loading.value = true
        
        // Fetch using frappe-ui resource
        await grnListResource.fetch({
          filters: {},
          page: pagination.value.page,
          page_size: pagination.value.page_size
        })
        
        if (grnListResource.data) {
          // Store original data
          const originalData = grnListResource.data.data || grnListResource.data || []
          
          grnList.value = [...originalData]
          pagination.value.total = grnListResource.data.total || originalData.length
          pagination.value.total_pages = grnListResource.data.total_pages || 1
          
          // Apply client-side filtering if needed
          if (filters.value.search) {
            grnList.value = grnList.value.filter(grn => 
              grn.po_no?.toString().includes(filters.value.search) ||
              grn.vendor_name?.toLowerCase().includes(filters.value.search.toLowerCase()) ||
              grn.grn_docnum?.toString().includes(filters.value.search) ||
              grn.name?.toLowerCase().includes(filters.value.search.toLowerCase())
            )
          }
          
          // Apply date range filter
          if (filters.value.dateRange !== 'all') {
            const now = new Date()
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
            
            grnList.value = grnList.value.filter(grn => {
              const grnDate = new Date(grn.received_date || grn.creation)
              
              if (filters.value.dateRange === 'today') {
                return grnDate >= today
              } else if (filters.value.dateRange === 'week') {
                const weekAgo = new Date(today)
                weekAgo.setDate(weekAgo.getDate() - 7)
                return grnDate >= weekAgo
              } else if (filters.value.dateRange === 'month') {
                const monthAgo = new Date(today)
                monthAgo.setMonth(monthAgo.getMonth() - 1)
                return grnDate >= monthAgo
              }
              return true
            })
          }
        } else {
          console.error('❌ No data received from API')
          alert('Failed to load GRN list. Please try again.')
          grnList.value = []
        }
      } catch (error) {
        console.error('❌ Error loading GRN list:', error)
        const errorMsg = error.message || 'Unknown error'
        alert(`Error loading GRN list:\n\n${errorMsg}\n\nPlease try refreshing the page.`)
        grnList.value = []
      } finally {
        loading.value = false
      }
    }
    
    const loadStatistics = async () => {
      try {
        // Fetch all GRNs for statistics
        await grnListResource.fetch({
          filters: {},
          page: 1,
          page_size: 1000 // Get all for stats
        })
        
        if (grnListResource.data) {
          const allGRNs = grnListResource.data.data || grnListResource.data || []
          statistics.value.total = allGRNs.length
          statistics.value.posted = allGRNs.filter(g => g.grn_docentry).length
          
          // This month
          const now = new Date()
          const firstDayOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
          statistics.value.thisMonth = allGRNs.filter(g => {
            const grnDate = new Date(g.received_date || g.creation)
            return grnDate >= firstDayOfMonth
          }).length
        }
      } catch (error) {
        console.error('Error loading statistics:', error)
      }
    }
    
    const showCreateForm = () => {
      currentView.value = 'create'
    }
    
    const goBackToList = () => {
      currentView.value = 'list'
      selectedGRN.value = null
      loadGRNList()
      loadStatistics()
    }
    
    const viewGRN = (grn) => {
      // Just store the GRN ID and switch to detail view
      // GRNDetail component will load the full details itself
      selectedGRN.value = grn.name
      currentView.value = 'detail'
    }
    
    const handleGRNCreated = (newGRN) => {
      goBackToList()
    }
    
    const changePage = (newPage) => {
      if (newPage >= 1 && newPage <= pagination.value.total_pages) {
        pagination.value.page = newPage
        loadGRNList()
      }
    }
    
    const formatDate = (dateString) => {
      if (!dateString) return '-'
      const date = new Date(dateString)
      return date.toLocaleDateString('en-IN', { 
        day: '2-digit', 
        month: 'short', 
        year: 'numeric' 
      })
    }
    
    // ==================== GRN Cancellation ====================
    const showCancelModal = ref(false)
    const grnToCancel = ref(null)
    const cancellingGRN = ref(false)
    
    const canCancelGRN = (grn) => {
      // Can cancel if:
      // 1. GRN has been posted to SAP (has grn_docentry)
      // 2. Status is "Sent to SAP" (not already cancelled/reopened)
      return grn.grn_docentry && grn.moist_select === "Sent to SAP"
    }
    
    const openCancelModal = (grn) => {
      grnToCancel.value = grn
      showCancelModal.value = true
    }
    
    const closeCancelModal = () => {
      if (!cancellingGRN.value) {
        showCancelModal.value = false
        grnToCancel.value = null
      }
    }
    
    const handleCancelGRN = async ({ grnId, reason }) => {
      try {
        cancellingGRN.value = true
        
        // Call cancel API
        await cancelGRN.submit({ grnId, reason })
        
        // Check if successful
        if (cancelGRN.data?.success) {
          alert(`✅ ${cancelGRN.data.message}\n\nThe GRN has been reopened and can now be re-submitted.`)
          closeCancelModal()
          // Reload the list to reflect changes
          loadGRNList()
          loadStatistics()
        } else {
          alert(`❌ Cancellation Failed:\n\n${cancelGRN.data?.message || 'Unknown error'}`)
        }
      } catch (error) {
        console.error('Error cancelling GRN:', error)
        alert(`❌ Error:\n\n${error.message || 'Failed to cancel GRN'}`)
      } finally {
        cancellingGRN.value = false
      }
    }
    
    onMounted(() => {
      loadGRNList()
      loadStatistics()
    })
    
    return {
      currentView,
      grnList,
      selectedGRN,
      showCancelModal,
      grnToCancel,
      cancellingGRN,
      canCancelGRN,
      openCancelModal,
      closeCancelModal,
      handleCancelGRN,
      loading,
      filters,
      pagination,
      statistics,
      showCreateForm,
      goBackToList,
      viewGRN,
      handleGRNCreated,
      changePage,
      formatDate,
      loadGRNList
    }
  }
}
</script>

<style scoped>
/* Add any component-specific styles here */
</style>
