<template>
  <div class="space-y-6">
    <div v-if="loading" class="text-center py-8">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
      <p class="mt-4 text-gray-600">Loading GRN details...</p>
    </div>

    <div v-else-if="grnDetails">
      <!-- Header Info -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <div class="flex justify-between items-start mb-4">
          <div>
            <h3 class="text-2xl font-bold text-gray-900">{{ grnDetails.name }}</h3>
            <p class="text-sm text-gray-500 mt-1">Created on {{ formatDateTime(grnDetails.creation) }} by {{ grnDetails.created_by }}</p>
          </div>
          <span :class="getStatusClass(grnDetails.status)" class="px-4 py-2 text-sm font-semibold rounded-full">
            {{ grnDetails.status }}
          </span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-500">PO Number</label>
            <p class="mt-1 text-lg font-semibold text-gray-900">{{ grnDetails.po_no }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500">Vendor</label>
            <p class="mt-1 text-lg font-semibold text-gray-900">{{ grnDetails.vendor_name }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500">Invoice Number</label>
            <p class="mt-1 text-lg font-semibold text-gray-900">{{ grnDetails.invoice_number }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500">Invoice Date</label>
            <p class="mt-1 text-lg font-semibold text-gray-900">{{ formatDate(grnDetails.invoice_date) }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500">Received Date</label>
            <p class="mt-1 text-lg font-semibold text-gray-900">{{ formatDate(grnDetails.received_date) }}</p>
          </div>
          <div v-if="grnDetails.sap_doc_num">
            <label class="block text-sm font-medium text-gray-500">SAP Document Number</label>
            <p class="mt-1 text-lg font-semibold text-green-600">{{ grnDetails.sap_doc_num }}</p>
          </div>
        </div>

        <!-- Approval/Rejection Info -->
        <div v-if="grnDetails.status === 'Approved'" class="mt-4 p-4 bg-green-50 rounded-lg">
          <p class="text-sm text-green-800">
            <strong>Approved by:</strong> {{ grnDetails.approved_by }} on {{ formatDateTime(grnDetails.approved_on) }}
          </p>
        </div>
        <div v-if="grnDetails.status === 'Rejected'" class="mt-4 p-4 bg-red-50 rounded-lg">
          <p class="text-sm text-red-800">
            <strong>Rejected by:</strong> {{ grnDetails.rejected_by }} on {{ formatDateTime(grnDetails.rejected_on) }}
          </p>
          <p class="text-sm text-red-800 mt-2">
            <strong>Reason:</strong> {{ grnDetails.rejection_reason }}
          </p>
        </div>

        <!-- Comments -->
        <div v-if="grnDetails.comments" class="mt-4">
          <label class="block text-sm font-medium text-gray-500">Comments</label>
          <p class="mt-1 text-gray-700">{{ grnDetails.comments }}</p>
        </div>
      </div>

      <!-- Line Items -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <h3 class="text-lg font-semibold mb-4">Received Items</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-100">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Item Code</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ordered Qty</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Received Qty</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Warehouse</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Batches</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <template v-for="(item, index) in grnDetails.line_items" :key="index">
                <tr>
                  <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ item.ItemCode }}</td>
                  <td class="px-4 py-3 text-sm text-gray-500">{{ item.ItemDescription }}</td>
                  <td class="px-4 py-3 text-sm text-right text-gray-500">{{ item.OrderedQuantity }}</td>
                  <td class="px-4 py-3 text-sm text-right font-semibold text-gray-900">{{ item.ReceivedQuantity }}</td>
                  <td class="px-4 py-3 text-sm text-gray-500">{{ item.WarehouseCode }}</td>
                  <td class="px-4 py-3 text-sm">
                    <button
                      @click="item.showBatches = !item.showBatches"
                      class="text-purple-600 hover:text-purple-900"
                    >
                      {{ item.showBatches ? '▼' : '▶' }} {{ item.BatchLines?.length || 0 }} Batch(es)
                    </button>
                  </td>
                </tr>
                <!-- Batch Details -->
                <tr v-if="item.showBatches" v-for="(batch, bIndex) in item.BatchLines" :key="`batch-${index}-${bIndex}`">
                  <td colspan="3" class="px-4 py-2 bg-gray-50"></td>
                  <td class="px-4 py-2 bg-gray-50 text-sm text-gray-900">
                    <span class="font-medium">Batch:</span> {{ batch.BatchNumber }}
                  </td>
                  <td class="px-4 py-2 bg-gray-50 text-sm text-right text-gray-900 font-medium">
                    Qty: {{ batch.Quantity }}
                  </td>
                  <td class="px-4 py-2 bg-gray-50 text-sm text-gray-700">
                    <span v-if="batch.MoistureValue">Moisture: {{ batch.MoistureValue }}%</span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Action Buttons for Pending Approval -->
      <div v-if="grnDetails.status === 'Pending Approval' && canApprove" class="flex justify-end gap-4">
        <button
          @click="openRejectDialog"
          class="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          Reject GRN
        </button>
        <button
          @click="approveGRN"
          class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
        >
          Approve & Post to SAP
        </button>
      </div>
    </div>

    <!-- Reject Dialog -->
    <div v-if="showRejectDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 w-96">
        <h3 class="text-lg font-bold mb-4">Reject GRN</h3>
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
import { ref, onMounted } from 'vue'
import { useGRN } from '@/composables/useGRN'

export default {
  name: 'GRNDetail',
  props: {
    grnId: {
      type: String,
      required: true
    }
  },
  emits: ['close', 'refresh'],
  setup(props, { emit }) {
    const loading = ref(true)
    const grnDetails = ref(null)
    const canApprove = ref(false)
    const showRejectDialog = ref(false)
    const rejectionReason = ref('')
    
    // Use frappe-ui based composable
    const { grnDetails: detailsResource, rejectGRN: rejectResource } = useGRN('krishnagiri')

    const loadGRNDetails = async () => {
      loading.value = true
      try {
        if (!props.grnId) {
          throw new Error('GRN ID is required')
        }
        
        await detailsResource.fetch(props.grnId)
        // frappe-ui transform returns {success: true, data: {...}}
        if (detailsResource.data?.success && detailsResource.data?.data) {
          // Transform snake_case to PascalCase for template compatibility
          const data = detailsResource.data.data
          
          // Transform line items to match template expectations
          if (data.line_items && Array.isArray(data.line_items)) {
            data.line_items = data.line_items.map(item => ({
              ...item,
              // Add PascalCase versions for template
              ItemCode: item.item_code,
              ItemDescription: item.item_description,
              ReceivedQuantity: item.received_quantity,
              OrderedQuantity: item.ordered_quantity || item.received_quantity,
              WarehouseCode: item.warehouse_code || '',
              BatchLines: (item.batch_lines || []).map(batch => ({
                ...batch,
                BatchNumber: batch.batch_number,
                Quantity: batch.quantity,
                MoistureValue: batch.moisture_value
              })),
              showBatches: false
            }))
          }
          
          grnDetails.value = data
        } else {
          alert('Failed to load GRN details: ' + (detailsResource.error || 'Unknown error'))
          emit('close')
        }
      } catch (error) {
        console.error('Error loading GRN details:', error)
        alert('Failed to load GRN details: ' + error.message)
        emit('close')
      } finally {
        loading.value = false
      }
    }

    const approveGRN = async () => {
      // Krishnagiri posts directly to SAP - no separate approval step
      alert('GRNs in Krishnagiri are posted directly to SAP upon creation')
      emit('close')
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
        await rejectResource.submit({ grnId: props.grnId, reason: rejectionReason.value })
        if (rejectResource.data?.success) {
          alert('GRN rejected successfully')
          closeRejectDialog()
          emit('refresh')
          emit('close')
        } else {
          alert('Failed to reject GRN: ' + (rejectResource.data?.message || 'Unknown error'))
        }
      } catch (error) {
        console.error('Error rejecting GRN:', error)
        alert('Failed to reject GRN: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '-'
      const date = new Date(dateStr)
      return date.toLocaleDateString('en-GB')
    }

    const formatDateTime = (dateStr) => {
      if (!dateStr) return '-'
      const date = new Date(dateStr)
      return date.toLocaleString('en-GB')
    }

    const getStatusClass = (status) => {
      const statusClasses = {
        'Pending Approval': 'bg-yellow-100 text-yellow-800',
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
      loadGRNDetails()
      checkApprovalPermission()
    })

    return {
      loading,
      grnDetails,
      canApprove,
      showRejectDialog,
      rejectionReason,
      approveGRN,
      openRejectDialog,
      closeRejectDialog,
      confirmReject,
      formatDate,
      formatDateTime,
      getStatusClass
    }
  }
}
</script>

