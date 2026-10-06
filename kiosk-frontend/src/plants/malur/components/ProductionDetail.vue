<template>
  <div class="space-y-6">
    <div v-if="loading" class="text-center py-8">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
      <p class="mt-4 text-gray-600">Loading production details...</p>
    </div>

    <div v-else-if="productionDetails">
      <!-- Header Info -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <div class="flex justify-between items-start mb-4">
          <div>
            <h3 class="text-2xl font-bold text-gray-900">{{ productionDetails.name }}</h3>
            <p class="text-sm text-gray-500 mt-1">Created on {{ formatDateTime(productionDetails.created_date) }}</p>
          </div>
          <span :class="getStatusClass(productionDetails.status)" class="px-4 py-2 text-sm font-semibold rounded-full">
            {{ productionDetails.status }}
          </span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-500">Process Type</label>
            <p class="mt-1 text-lg font-semibold">{{ productionDetails.process_type }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500">Employee Count</label>
            <p class="mt-1 text-lg font-semibold">{{ productionDetails.employee_count }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500">Created By</label>
            <p class="mt-1 text-lg font-semibold">{{ productionDetails.user_email }}</p>
          </div>
          <div v-if="productionDetails.sap_doc_num">
            <label class="block text-sm font-medium text-gray-500">SAP Document Number</label>
            <p class="mt-1 text-lg font-semibold text-green-600">{{ productionDetails.sap_doc_num }}</p>
          </div>
        </div>

        <!-- Approval/Rejection Info -->
        <div v-if="productionDetails.status === 'Approved'" class="mt-4 p-4 bg-green-50 rounded-lg">
          <p class="text-sm text-green-800">
            <strong>Approved by:</strong> {{ productionDetails.approved_by }} on {{ formatDateTime(productionDetails.approved_on) }}
          </p>
        </div>
        <div v-if="productionDetails.status === 'Rejected'" class="mt-4 p-4 bg-red-50 rounded-lg">
          <p class="text-sm text-red-800">
            <strong>Rejected by:</strong> {{ productionDetails.rejected_by }} on {{ formatDateTime(productionDetails.rejected_on) }}
          </p>
          <p class="text-sm text-red-800 mt-2">
            <strong>Reason:</strong> {{ productionDetails.rejection_reason }}
          </p>
        </div>
      </div>

      <!-- Crate Inputs -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <h3 class="text-lg font-semibold mb-4">Input Crates</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-100">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Crate Number</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Crate Quantity</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Used Quantity</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(input, index) in productionDetails.crate_inputs" :key="index">
                <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ input.crate_number }}</td>
                <td class="px-4 py-3 text-sm text-right text-gray-500">{{ input.crate_quantity }}</td>
                <td class="px-4 py-3 text-sm text-right font-semibold text-gray-900">{{ input.input_quantity }}</td>
              </tr>
              <tr class="bg-gray-50 font-bold">
                <td class="px-4 py-3 text-sm">Total Input</td>
                <td class="px-4 py-3"></td>
                <td class="px-4 py-3 text-sm text-right">{{ totalInput }} Kg</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Output Details -->
      <div v-if="productionDetails.output_details && productionDetails.output_details.length > 0" class="bg-gray-50 p-6 rounded-lg">
        <h3 class="text-lg font-semibold mb-4">Output Items</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-100">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Item Code</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Quantity</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Batch Number</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(output, index) in productionDetails.output_details" :key="index">
                <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ output.item_code }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ output.item_description }}</td>
                <td class="px-4 py-3 text-sm text-right font-semibold text-gray-900">{{ output.output_quantity }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ output.batch_number }}</td>
              </tr>
              <tr class="bg-gray-50 font-bold">
                <td colspan="2" class="px-4 py-3 text-sm">Total Output</td>
                <td class="px-4 py-3 text-sm text-right">{{ totalOutput }} Kg</td>
                <td></td>
              </tr>
              <tr class="bg-gray-50">
                <td colspan="2" class="px-4 py-3 text-sm font-semibold">Loss</td>
                <td class="px-4 py-3 text-sm text-right font-semibold" :class="loss >= 0 ? 'text-red-600' : 'text-green-600'">
                  {{ Math.abs(loss).toFixed(2) }} Kg ({{ lossPercentage }}%)
                </td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Action Buttons -->
      <div v-if="productionDetails.status === 'Output Submitted' && canApprove" class="flex justify-end gap-4">
        <button
          @click="openRejectDialog"
          class="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          Reject
        </button>
        <button
          @click="approveProduction"
          class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
        >
          Approve & Post to SAP
        </button>
      </div>
    </div>

    <!-- Reject Dialog -->
    <div v-if="showRejectDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
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
            @click="confirmReject"
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { malurProductionService } from '@/core/api/plants/malur/productionService'

export default {
  name: 'ProductionDetail',
  props: {
    productionId: {
      type: String,
      required: true
    }
  },
  emits: ['close', 'refresh'],
  setup(props, { emit }) {
    const loading = ref(true)
    const productionDetails = ref(null)
    const canApprove = ref(false)
    const showRejectDialog = ref(false)
    const rejectionReason = ref('')

    const totalInput = computed(() => {
      if (!productionDetails.value) return 0
      return productionDetails.value.crate_inputs.reduce((sum, input) => sum + parseFloat(input.input_quantity || 0), 0)
    })

    const totalOutput = computed(() => {
      if (!productionDetails.value || !productionDetails.value.output_details) return 0
      return productionDetails.value.output_details.reduce((sum, output) => sum + parseFloat(output.output_quantity || 0), 0)
    })

    const loss = computed(() => {
      return totalInput.value - totalOutput.value
    })

    const lossPercentage = computed(() => {
      if (totalInput.value === 0) return 0
      return ((loss.value / totalInput.value) * 100).toFixed(2)
    })

    const loadProductionDetails = async () => {
      loading.value = true
      try {
        const response = await malurProductionService.getProductionOrderDetails(props.productionId)
        if (response.success) {
          productionDetails.value = response.data
        }
      } catch (error) {
        console.error('Error loading production details:', error)
        alert('Failed to load production details')
      } finally {
        loading.value = false
      }
    }

    const approveProduction = async () => {
      if (!confirm('Are you sure you want to approve this production order and post to SAP?')) {
        return
      }

      loading.value = true
      try {
        const response = await malurProductionService.approveProductionOrder(props.productionId)
        if (response.success) {
          alert('Production order approved and posted to SAP successfully!')
          emit('refresh')
          emit('close')
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

    const openRejectDialog = () => {
      rejectionReason.value = ''
      showRejectDialog.value = true
    }

    const closeRejectDialog = () => {
      showRejectDialog.value = false
      rejectionReason.value = ''
    }

    const confirmReject = async () => {
      if (!rejectionReason.value.trim()) {
        alert('Please enter a rejection reason')
        return
      }

      loading.value = true
      try {
        const response = await malurProductionService.rejectProductionOrder(props.productionId, rejectionReason.value)
        if (response.success) {
          alert('Production order rejected successfully')
          closeRejectDialog()
          emit('refresh')
          emit('close')
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

    const formatDateTime = (dateStr) => {
      if (!dateStr) return '-'
      const date = new Date(dateStr)
      return date.toLocaleString('en-GB')
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
      loadProductionDetails()
      checkApprovalPermission()
    })

    return {
      loading,
      productionDetails,
      canApprove,
      showRejectDialog,
      rejectionReason,
      totalInput,
      totalOutput,
      loss,
      lossPercentage,
      approveProduction,
      openRejectDialog,
      closeRejectDialog,
      confirmReject,
      formatDateTime,
      getStatusClass
    }
  }
}
</script>

