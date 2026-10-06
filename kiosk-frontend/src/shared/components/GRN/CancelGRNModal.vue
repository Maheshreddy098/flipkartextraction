<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 overflow-y-auto">
    <!-- Backdrop -->
    <div 
      class="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
      @click="close"
    ></div>
    
    <!-- Modal -->
    <div class="flex min-h-full items-center justify-center p-4">
      <div class="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6 transform transition-all">
        <!-- Header -->
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <span>⚠️</span>
            <span>Cancel GRN</span>
          </h3>
          <button
            @click="close"
            class="text-gray-400 hover:text-gray-600 transition-colors"
            :disabled="loading"
          >
            <span class="text-2xl">×</span>
          </button>
        </div>
        
        <!-- Content -->
        <div class="space-y-4">
          <!-- GRN Info -->
          <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div class="text-sm text-blue-900">
              <p class="font-semibold">GRN ID: {{ grn?.name }}</p>
              <p class="text-xs text-blue-700 mt-1">PO: {{ grn?.po_no }} | Vendor: {{ grn?.vendor_name }}</p>
            </div>
          </div>
          
          <!-- Warning Message -->
          <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <p class="text-sm text-yellow-800">
              <strong>⚠️ Warning:</strong> This will reopen the GRN and change its status from "Sent to SAP" to "Open". 
              The GRN will need to be re-submitted.
            </p>
          </div>
          
          <!-- Reason Input -->
          <div>
            <label for="cancel-reason" class="block text-sm font-medium text-gray-700 mb-2">
              Cancellation Reason <span class="text-red-500">*</span>
            </label>
            <textarea
              id="cancel-reason"
              v-model="reason"
              rows="4"
              placeholder="Please provide a reason for cancelling this GRN..."
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 text-sm"
              :class="{
                'border-red-500 bg-red-50': error
              }"
              :disabled="loading"
            ></textarea>
            <p v-if="error" class="mt-1 text-sm text-red-600">{{ error }}</p>
          </div>
        </div>
        
        <!-- Actions -->
        <div class="flex gap-3 mt-6">
          <button
            @click="close"
            class="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            :disabled="loading"
          >
            Close
          </button>
          <button
            @click="handleCancel"
            class="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            :disabled="loading || !reason.trim()"
          >
            <span v-if="loading" class="animate-spin">⏳</span>
            <span>{{ loading ? 'Cancelling...' : 'Cancel GRN' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  grn: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'confirm'])

const reason = ref('')
const error = ref('')

// Reset reason when modal opens/closes
watch(() => props.isOpen, (newValue) => {
  if (newValue) {
    reason.value = ''
    error.value = ''
  }
})

const close = () => {
  if (!props.loading) {
    emit('close')
  }
}

const handleCancel = () => {
  // Validate reason
  if (!reason.value.trim()) {
    error.value = 'Cancellation reason is required'
    return
  }
  
  if (reason.value.trim().length < 10) {
    error.value = 'Please provide a more detailed reason (at least 10 characters)'
    return
  }
  
  error.value = ''
  emit('confirm', { grnId: props.grn?.name, reason: reason.value.trim() })
}
</script>

