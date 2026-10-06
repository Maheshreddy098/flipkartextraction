<template>
  <div class="sticky bottom-0 bg-white border-t-2 border-gray-300 p-4 shadow-lg">
    <div class="max-w-7xl mx-auto">
      <!-- Summary Row -->
      <div class="flex items-center justify-between mb-4">
        <!-- Left: Stats -->
        <div class="flex items-center gap-6">
          <div v-if="itemsCount !== null" class="text-sm">
            <span class="font-semibold text-gray-900">Items:</span>
            <span class="ml-2 text-gray-700">{{ itemsCount }}</span>
          </div>
          
          <div v-if="totalQuantity !== null" class="text-sm">
            <span class="font-semibold text-gray-900">Total Qty:</span>
            <span class="ml-2 text-gray-700">{{ formatNumber(totalQuantity) }}</span>
          </div>
          
          <div v-if="totalAmount !== null" class="text-sm">
            <span class="font-semibold text-gray-900">Total:</span>
            <span class="ml-2 text-lg font-bold text-purple-600">{{ formatCurrency(totalAmount) }}</span>
          </div>

          <!-- Custom Stats Slot -->
          <slot name="stats"></slot>
        </div>

        <!-- Right: Actions -->
        <div class="flex items-center gap-3">
          <!-- Custom Actions Slot -->
          <slot name="actions"></slot>

          <!-- Cancel Button -->
          <button
            v-if="showCancelButton"
            @click="$emit('cancel')"
            type="button"
            :disabled="submitting"
            class="px-6 py-2.5 text-gray-700 bg-white border-2 border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            {{ cancelText }}
          </button>

          <!-- Save Draft Button -->
          <button
            v-if="showSaveDraftButton"
            @click="$emit('save-draft')"
            type="button"
            :disabled="submitting || !canSaveDraft"
            class="px-6 py-2.5 text-blue-700 bg-blue-50 border-2 border-blue-300 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            💾 {{ saveDraftText }}
          </button>

          <!-- Submit Button -->
          <button
            @click="$emit('submit')"
            type="button"
            :disabled="submitting || !canSubmit"
            :class="[
              'px-8 py-2.5 rounded-lg font-semibold focus:outline-none focus:ring-2 transition-all',
              canSubmit && !submitting
                ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 focus:ring-purple-500 shadow-md hover:shadow-lg'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            ]"
          >
            <span v-if="submitting" class="flex items-center">
              <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ submittingText }}
            </span>
            <span v-else class="flex items-center">
              {{ submitIcon }} {{ submitText }}
            </span>
          </button>
        </div>
      </div>

      <!-- Validation Messages -->
      <div v-if="errorMessage" class="mb-2 p-3 bg-red-50 border-l-4 border-red-500 text-sm text-red-700 rounded">
        ❌ {{ errorMessage }}
      </div>
      
      <div v-if="warningMessage" class="mb-2 p-3 bg-yellow-50 border-l-4 border-yellow-500 text-sm text-yellow-700 rounded">
        ⚠️ {{ warningMessage }}
      </div>

      <div v-if="successMessage" class="mb-2 p-3 bg-green-50 border-l-4 border-green-500 text-sm text-green-700 rounded">
        ✅ {{ successMessage }}
      </div>

      <!-- Help Text -->
      <div v-if="helpText" class="text-xs text-gray-600 text-center">
        {{ helpText }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  itemsCount?: number | null
  totalQuantity?: number | null
  totalAmount?: number | null
  canSubmit?: boolean
  canSaveDraft?: boolean
  submitting?: boolean
  showCancelButton?: boolean
  showSaveDraftButton?: boolean
  submitText?: string
  submitIcon?: string
  submittingText?: string
  cancelText?: string
  saveDraftText?: string
  errorMessage?: string
  warningMessage?: string
  successMessage?: string
  helpText?: string
  currencySymbol?: string
}

withDefaults(defineProps<Props>(), {
  itemsCount: null,
  totalQuantity: null,
  totalAmount: null,
  canSubmit: false,
  canSaveDraft: false,
  submitting: false,
  showCancelButton: true,
  showSaveDraftButton: false,
  submitText: 'Submit GRN',
  submitIcon: '✅',
  submittingText: 'Submitting...',
  cancelText: 'Cancel',
  saveDraftText: 'Save Draft',
  errorMessage: '',
  warningMessage: '',
  successMessage: '',
  helpText: '',
  currencySymbol: '₹'
})

defineEmits<{
  submit: []
  cancel: []
  'save-draft': []
}>()

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-IN').format(value)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2
  }).format(value)
}
</script>

