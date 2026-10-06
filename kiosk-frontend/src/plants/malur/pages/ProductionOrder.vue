<template>
  <div class="p-6">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Production Orders - Malur Plant</h1>
      <p class="text-gray-600">Create and manage production orders for drying and churpi processing</p>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-purple-100 rounded-lg">
            <span class="text-2xl">🏭</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Active Orders</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.active || 0 }}</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-green-100 rounded-lg">
            <span class="text-2xl">✅</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Completed</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.completed || 0 }}</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-yellow-100 rounded-lg">
            <span class="text-2xl">⏳</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Pending</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.pending || 0 }}</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-red-100 rounded-lg">
            <span class="text-2xl">❌</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Rejected</p>
            <p class="text-2xl font-bold text-gray-900">{{ statistics.rejected || 0 }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ currentView === 'list' ? 'Production Orders' : currentView === 'create' ? 'Create Pre-Production' : currentView === 'output' ? 'Submit Output' : 'Production Details' }}
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
            + Create Pre-Production
          </button>
        </div>
      </div>

      <div class="p-6">
        <!-- List View -->
        <div v-if="currentView === 'list'">
          <!-- Filters -->
          <div class="mb-6 flex gap-4">
            <select
              v-model="filters.status"
              @change="loadProductionOrders"
              class="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">All Status</option>
              <option value="Input Submitted">Input Submitted</option>
              <option value="Output Submitted">Pending Approval</option>
              <option value="Approved">Approved</option>
              <option value="Rejected">Rejected</option>
            </select>
            <select
              v-model="filters.process_type"
              @change="loadProductionOrders"
              class="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">All Process Types</option>
              <option value="Drying Process">Drying Process</option>
              <option value="Churpi Process">Churpi Process</option>
            </select>
          </div>

          <!-- Production Orders Table -->
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Production ID</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Process Type</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created Date</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Employee Count</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="order in productionOrders" :key="order.name" class="hover:bg-gray-50">
                  <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ order.name }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ order.process_type }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(order.created_date) }}</td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ order.employee_count }}</td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <span :class="getStatusClass(order.status)" class="px-2 py-1 text-xs font-semibold rounded-full">
                      {{ order.status }}
                    </span>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button
                      @click="viewProductionDetails(order.name)"
                      class="text-purple-600 hover:text-purple-900 mr-3"
                    >
                      View
                    </button>
                    <button
                      v-if="order.status === 'Input Submitted'"
                      @click="showOutputForm(order.name)"
                      class="text-blue-600 hover:text-blue-900 mr-3"
                    >
                      Submit Output
                    </button>
                    <button
                      v-if="order.status === 'Output Submitted' && canApprove"
                      @click="approveProduction(order.name)"
                      class="text-green-600 hover:text-green-900 mr-3"
                    >
                      Approve
                    </button>
                    <button
                      v-if="order.status === 'Output Submitted' && canApprove"
                      @click="openRejectDialog(order.name)"
                      class="text-red-600 hover:text-red-900"
                    >
                      Reject
                    </button>
                  </td>
                </tr>
                <tr v-if="productionOrders.length === 0">
                  <td colspan="6" class="px-6 py-4 text-center text-sm text-gray-500">
                    No production orders found
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div class="mt-4 flex justify-between items-center">
            <div class="text-sm text-gray-700">
              Showing {{ (currentPage - 1) * pageSize + 1 }} to {{ Math.min(currentPage * pageSize, totalCount) }} of {{ totalCount }} entries
            </div>
            <div class="flex gap-2">
              <button
                @click="previousPage"
                :disabled="currentPage === 1"
                :class="currentPage === 1 ? 'bg-gray-300 cursor-not-allowed' : 'bg-purple-600 hover:bg-purple-700'"
                class="px-4 py-2 text-white rounded-lg transition-colors"
              >
                Previous
              </button>
              <button
                @click="nextPage"
                :disabled="currentPage >= totalPages"
                :class="currentPage >= totalPages ? 'bg-gray-300 cursor-not-allowed' : 'bg-purple-600 hover:bg-purple-700'"
                class="px-4 py-2 text-white rounded-lg transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        <!-- Create Form View -->
        <div v-if="currentView === 'create'">
          <CreatePreProductionForm @production-created="onProductionCreated" @cancel="goBackToList" />
        </div>

        <!-- Output Form View -->
        <div v-if="currentView === 'output'">
          <SubmitOutputForm :production-id="selectedProductionId" @output-submitted="onOutputSubmitted" @cancel="goBackToList" />
        </div>

        <!-- Detail View -->
        <div v-if="currentView === 'detail'">
          <ProductionDetail :production-id="selectedProductionId" @close="goBackToList" @refresh="loadProductionOrders" />
        </div>
      </div>
    </div>

    <!-- Reject Dialog -->
    <div v-if="showRejectModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 w-96">
        <h3 class="text-lg font-bold mb-4">Reject Production Order</h3>
        <textarea
          v-model="rejectionReason"
          placeholder="Enter rejection reason..."
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
          rows="4"
        ></textarea>
        <div class="mt-4 flex justify-end gap-2">
          <button
            @click="closeRejectDialog"
            class="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
          >
            Cancel
          </button>
          <button
            @click="confirmRejectProduction"
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Reject
          </button>
        </div>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6">
        <div class="flex items-center">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
          <span class="ml-3 text-gray-700">{{ loadingMessage }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { malurProductionService } from '@/core/api/plants/malur/productionService'
import CreatePreProductionForm from '../components/CreatePreProductionForm.vue'
import SubmitOutputForm from '../components/SubmitOutputForm.vue'
import ProductionDetail from '../components/ProductionDetail.vue'

export default {
  name: 'ProductionOrderPage',
  components: {
    CreatePreProductionForm,
    SubmitOutputForm,
    ProductionDetail
  },
  setup() {
    const currentView = ref('list') // 'list', 'create', 'output', 'detail'
    const productionOrders = ref([])
    const statistics = ref({})
    const loading = ref(false)
    const loadingMessage = ref('Loading...')
    const currentPage = ref(1)
    const pageSize = ref(20)
    const totalCount = ref(0)
    const totalPages = ref(0)
    const filters = ref({
      status: '',
      process_type: ''
    })
    const selectedProductionId = ref(null)
    const showRejectModal = ref(false)
    const rejectionReason = ref('')
    const rejectProductionId = ref(null)
    const canApprove = ref(false)

    const loadProductionOrders = async () => {
      loading.value = true
      loadingMessage.value = 'Loading production orders...'
      try {
        const filterObj = {}
        if (filters.value.status) {
          filterObj.status = filters.value.status
        }
        if (filters.value.process_type) {
          filterObj.process_type = filters.value.process_type
        }

        const response = await malurProductionService.getProductionOrders(filterObj, currentPage.value, pageSize.value)
        if (response.success) {
          productionOrders.value = response.data
          totalCount.value = response.total_count
          totalPages.value = response.total_pages
        }
      } catch (error) {
        console.error('Error loading production orders:', error)
        alert('Failed to load production orders')
      } finally {
        loading.value = false
      }
    }

    const loadStatistics = async () => {
      try {
        const response = await malurProductionService.getProductionStatistics()
        if (response.success) {
          statistics.value = response.data
        }
      } catch (error) {
        console.error('Error loading statistics:', error)
      }
    }

    const showCreateForm = () => {
      currentView.value = 'create'
    }

    const showOutputForm = (productionId) => {
      selectedProductionId.value = productionId
      currentView.value = 'output'
    }

    const goBackToList = () => {
      currentView.value = 'list'
      selectedProductionId.value = null
      loadProductionOrders()
      loadStatistics()
    }

    const viewProductionDetails = (productionId) => {
      selectedProductionId.value = productionId
      currentView.value = 'detail'
    }

    const approveProduction = async (productionId) => {
      if (!confirm('Are you sure you want to approve this production order and post to SAP?')) {
        return
      }

      loading.value = true
      loadingMessage.value = 'Approving production order and posting to SAP...'
      try {
        const response = await malurProductionService.approveProductionOrder(productionId)
        if (response.success) {
          alert('Production order approved successfully!')
          loadProductionOrders()
          loadStatistics()
        } else {
          alert('Failed to approve production order: ' + response.message)
        }
      } catch (error) {
        console.error('Error approving production order:', error)
        alert('Failed to approve production order: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const openRejectDialog = (productionId) => {
      rejectProductionId.value = productionId
      rejectionReason.value = ''
      showRejectModal.value = true
    }

    const closeRejectDialog = () => {
      showRejectModal.value = false
      rejectProductionId.value = null
      rejectionReason.value = ''
    }

    const confirmRejectProduction = async () => {
      if (!rejectionReason.value.trim()) {
        alert('Please enter a rejection reason')
        return
      }

      loading.value = true
      loadingMessage.value = 'Rejecting production order...'
      try {
        const response = await malurProductionService.rejectProductionOrder(rejectProductionId.value, rejectionReason.value)
        if (response.success) {
          alert('Production order rejected successfully')
          closeRejectDialog()
          loadProductionOrders()
          loadStatistics()
        } else {
          alert('Failed to reject production order: ' + response.message)
        }
      } catch (error) {
        console.error('Error rejecting production order:', error)
        alert('Failed to reject production order: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const onProductionCreated = () => {
      goBackToList()
    }

    const onOutputSubmitted = () => {
      goBackToList()
    }

    const previousPage = () => {
      if (currentPage.value > 1) {
        currentPage.value--
        loadProductionOrders()
      }
    }

    const nextPage = () => {
      if (currentPage.value < totalPages.value) {
        currentPage.value++
        loadProductionOrders()
      }
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '-'
      const date = new Date(dateStr)
      return date.toLocaleDateString('en-GB')
    }

    const getStatusClass = (status) => {
      const statusClasses = {
        'Input Submitted': 'bg-blue-100 text-blue-800',
        'Output Submitted': 'bg-yellow-100 text-yellow-800',
        'Approved': 'bg-green-100 text-green-800',
        'Rejected': 'bg-red-100 text-red-800'
      }
      return statusClasses[status] || 'bg-gray-100 text-gray-800'
    }

    const checkApprovalPermission = () => {
      // TODO: Implement actual role check
      canApprove.value = true
    }

    onMounted(() => {
      loadProductionOrders()
      loadStatistics()
      checkApprovalPermission()
    })

    return {
      currentView,
      productionOrders,
      statistics,
      loading,
      loadingMessage,
      currentPage,
      pageSize,
      totalCount,
      totalPages,
      filters,
      selectedProductionId,
      showRejectModal,
      rejectionReason,
      canApprove,
      loadProductionOrders,
      showCreateForm,
      showOutputForm,
      goBackToList,
      viewProductionDetails,
      approveProduction,
      openRejectDialog,
      closeRejectDialog,
      confirmRejectProduction,
      onProductionCreated,
      onOutputSubmitted,
      previousPage,
      nextPage,
      formatDate,
      getStatusClass
    }
  }
}
</script>
