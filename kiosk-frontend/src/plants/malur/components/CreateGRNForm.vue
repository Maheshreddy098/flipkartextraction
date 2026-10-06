<template>
  <div class="min-h-screen bg-gray-50 pb-24">
    <!-- Validation Summary Panel (Sticky) -->
    <div v-if="selectedPO" class="sticky top-0 z-20 mb-4 p-4 bg-white border rounded-lg shadow-md">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <!-- Error Count -->
          <div v-if="validationErrors.length" class="flex items-center gap-2 text-red-600">
            <span class="text-2xl">❌</span>
            <div>
              <div class="font-bold">{{ validationErrors.length }} Error(s)</div>
              <div class="text-xs">Must fix before posting</div>
            </div>
          </div>
          
          <!-- Warning Count -->
          <div v-if="validationWarnings.length" class="flex items-center gap-2 text-yellow-600">
            <span class="text-2xl">⚠️</span>
            <div>
              <div class="font-bold">{{ validationWarnings.length }} Warning(s)</div>
              <div class="text-xs">Review recommended</div>
            </div>
          </div>
          
          <!-- All Clear -->
          <div v-if="!validationErrors.length && !validationWarnings.length && lineItems.length" 
               class="flex items-center gap-2 text-green-600">
            <span class="text-2xl">✅</span>
            <div>
              <div class="font-bold">All Clear</div>
              <div class="text-xs">Ready to post to SAP</div>
            </div>
          </div>
        </div>
        
        <!-- Toggle Details -->
        <button 
          @click="showValidationDetails = !showValidationDetails" 
          v-if="validationErrors.length || validationWarnings.length"
          class="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          {{ showValidationDetails ? 'Hide Details ▲' : 'Show Details ▼' }}
        </button>
      </div>
      
      <!-- Detailed Validation Messages -->
      <div v-if="showValidationDetails && (validationErrors.length || validationWarnings.length)" 
           class="mt-4 space-y-2 max-h-60 overflow-y-auto">
        <!-- Errors -->
        <div 
          v-for="error in validationErrors" 
          :key="error.id" 
          class="p-3 bg-red-50 border-l-4 border-red-500 rounded"
        >
          <div class="flex items-start">
            <span class="text-red-600 mr-2">❌</span>
            <div>
              <div class="font-semibold text-red-800 text-sm">{{ error.field }}</div>
              <div class="text-sm text-red-700">{{ error.message }}</div>
            </div>
          </div>
        </div>
        
        <!-- Warnings -->
        <div 
          v-for="warning in validationWarnings" 
          :key="warning.id"
          class="p-3 bg-yellow-50 border-l-4 border-yellow-500 rounded"
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start flex-1">
              <span class="text-yellow-600 mr-2">⚠️</span>
              <div>
                <div class="font-semibold text-yellow-800 text-sm">{{ warning.field }}</div>
                <div class="text-sm text-yellow-700">{{ warning.message }}</div>
              </div>
            </div>
            <button 
              @click="acknowledgeWarning(warning.id)" 
              class="text-xs bg-yellow-100 px-2 py-1 rounded hover:bg-yellow-200 whitespace-nowrap ml-2"
            >
              Acknowledge
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent POs Quick Access -->
    <div v-if="recentPOs.length && !selectedPO" class="p-4 bg-blue-50 border border-blue-200 rounded-lg mb-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-blue-900 flex items-center gap-2">
          <span>🕒</span>
          <span>Recently Used Purchase Orders</span>
        </h3>
        <button 
          @click="clearRecentPOs" 
          class="text-xs text-blue-600 hover:text-blue-800 font-medium"
        >
          Clear History
        </button>
      </div>
      
      <div class="flex gap-2 overflow-x-auto pb-2">
        <button 
          v-for="po in recentPOs.slice(0, 5)" 
          :key="po.DocEntry"
          @click="quickSelectPO(po)"
          type="button"
          class="flex-shrink-0 px-4 py-3 bg-white border-2 border-blue-300 rounded-lg hover:bg-blue-100 hover:shadow-md transition-all text-left"
        >
          <div class="font-semibold text-blue-900">PO #{{ po.DocNum }}</div>
          <div class="text-xs text-gray-600 mt-1">{{ po.CardName.substring(0, 25) }}...</div>
        </button>
      </div>
    </div>

    <!-- Header -->
    <GRNFormHeader
      title="Create GRN - Malur Plant"
      :po-number="selectedPO?.DocNum"
      :vendor-name="selectedPO?.CardName"
      @back="$emit('cancel')"
      @show-help="showShortcuts = true"
    />

    <!-- Search Section (only if no PO selected) -->
    <div v-if="!selectedPO" class="mt-6">
      <GRNSearchSection
        v-model:fetch-all="fetchAllPOs"
        v-model:from-date="fromDate"
        v-model:to-date="toDate"
        v-model:bp-search="bpSearch"
        :loading="loading"
        :results-count="purchaseOrders.length"
        :quick-date-options="quickDateOptions"
        @quick-date="setQuickDateRange"
        @fetch="loadPurchaseOrders"
      />

      <!-- Purchase Order Dropdown -->
      <div v-if="purchaseOrders.length > 0" class="mt-6">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Select Purchase Order <span class="text-red-500">*</span>
        </label>
        <select
          v-model="selectedPODocEntry"
          @change="onPOSelect"
          class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white text-gray-900 font-medium"
        >
          <option value="">-- Select Purchase Order --</option>
          <option
            v-for="po in purchaseOrders"
            :key="po.DocEntry"
            :value="po.DocEntry"
          >
            PO #{{ po.DocNum }} - {{ po.CardName }} (Date: {{ formatDate(po.DocDate) }})
          </option>
        </select>
      </div>
    </div>

    <!-- GRN Form (when PO is selected) -->
    <div v-if="selectedPO" class="mt-6 space-y-6">
      <!-- Header Fields -->
      <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">GRN Information</h3>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Invoice Number -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Invoice Number <span class="text-red-500">*</span>
            </label>
            <input
              v-model="invoiceNumber"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-gray-900"
              placeholder="Enter invoice number"
            />
            <p v-if="fieldValidations.invoiceNumber.error" class="text-xs text-red-600 mt-1">
              {{ fieldValidations.invoiceNumber.error }}
            </p>
          </div>

          <!-- Invoice Date -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Invoice Date <span class="text-red-500">*</span>
            </label>
            <input
              v-model="invoiceDate"
              type="date"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-gray-900"
            />
            <p v-if="fieldValidations.invoiceDate.error" class="text-xs text-red-600 mt-1">
              {{ fieldValidations.invoiceDate.error }}
            </p>
          </div>

          <!-- Received Date -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Received Date <span class="text-red-500">*</span>
            </label>
            <input
              v-model="receivedDate"
              type="date"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-gray-900"
            />
            <p v-if="fieldValidations.receivedDate.error" class="text-xs text-red-600 mt-1">
              {{ fieldValidations.receivedDate.error }}
            </p>
          </div>

          <!-- Create CN for Leftover -->
          <div class="flex items-center">
            <input
              v-model="createCNForLeftover"
              type="checkbox"
              id="createCN"
              class="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
            />
            <label for="createCN" class="ml-2 text-sm text-gray-700">
              Create Credit Note for leftover quantity
            </label>
          </div>
        </div>

        <!-- Comments -->
        <div class="mt-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Comments
          </label>
          <textarea
            v-model="comments"
            rows="3"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-gray-900"
            placeholder="Enter any additional comments"
          ></textarea>
          
          <!-- Common Comments -->
          <div v-if="commonComments.length" class="mt-2 flex flex-wrap gap-2">
            <button
              v-for="(comment, index) in commonComments"
              :key="index"
              @click="comments = comment"
              type="button"
              class="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
            >
              {{ comment }}
            </button>
          </div>
        </div>
      </div>

      <!-- PO Details Section -->
      <div v-if="selectedPO" class="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span>📋</span>
          <span>Purchase Order Details</span>
        </h3>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- PO Number -->
          <div class="p-3 bg-blue-50 rounded-lg">
            <div class="text-xs text-gray-600 mb-1">PO Number</div>
            <div class="text-lg font-bold text-blue-900">#{{ selectedPO.DocNum }}</div>
          </div>
          
          <!-- Vendor -->
          <div class="p-3 bg-green-50 rounded-lg">
            <div class="text-xs text-gray-600 mb-1">Vendor</div>
            <div class="text-sm font-semibold text-green-900">{{ selectedPO.CardName }}</div>
          </div>
          
          <!-- PO Date -->
          <div class="p-3 bg-purple-50 rounded-lg">
            <div class="text-xs text-gray-600 mb-1">PO Date</div>
            <div class="text-sm font-semibold text-purple-900">{{ formatDate(selectedPO.DocDate) }}</div>
          </div>
          
          <!-- Total Items -->
          <div class="p-3 bg-yellow-50 rounded-lg">
            <div class="text-xs text-gray-600 mb-1">Total Items</div>
            <div class="text-lg font-bold text-yellow-900">{{ lineItems.length }}</div>
          </div>
          
          <!-- Completed Items -->
          <div class="p-3 bg-green-50 rounded-lg">
            <div class="text-xs text-gray-600 mb-1">Completed Items</div>
            <div class="text-lg font-bold text-green-900">{{ completedItems }}</div>
          </div>
          
          <!-- Total Batches -->
          <div class="p-3 bg-indigo-50 rounded-lg">
            <div class="text-xs text-gray-600 mb-1">Total Batches</div>
            <div class="text-lg font-bold text-indigo-900">{{ totalBatches }}</div>
          </div>
        </div>
        
        <!-- Progress Bar -->
        <div class="mt-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-gray-700">Receiving Progress</span>
            <span class="text-sm font-bold text-purple-600">{{ Math.round((completedItems / lineItems.length) * 100) }}%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-3">
            <div 
              class="bg-gradient-to-r from-green-500 to-blue-500 h-3 rounded-full transition-all duration-300"
              :style="{ width: `${(completedItems / lineItems.length) * 100}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div v-if="lineItems.length > 0" class="flex gap-3">
        <button
          @click="autoGenerateBatches"
          :disabled="!hasReceivedQuantities"
          type="button"
          class="px-4 py-2 bg-purple-100 border border-purple-300 rounded-lg hover:bg-purple-200 text-sm font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span>🏷️</span>
          <span>Auto-Generate Batches</span>
        </button>
        <button
          @click="receiveAllFullQuantity"
          type="button"
          class="px-4 py-2 bg-green-100 border border-green-300 rounded-lg hover:bg-green-200 text-sm font-medium flex items-center gap-2 transition-colors"
        >
          <span>📦</span>
          <span>Receive All (Full Qty)</span>
        </button>
        <button
          @click="clearAllReceivedQty"
          type="button"
          class="px-4 py-2 bg-red-100 border border-red-300 rounded-lg hover:bg-red-200 text-sm font-medium flex items-center gap-2 transition-colors"
        >
          <span>🗑️</span>
          <span>Clear All</span>
        </button>
      </div>

      <!-- Line Items Table -->
      <GRNItemsTable
        title="Line Items"
        :items="lineItems"
        :columns="tableColumns"
        :loading="loading"
        empty-text="No line items found"
        :show-actions="false"
      >
        <!-- @vue-ignore -->
        <template #cell-Quantity="{ item }">
          <input
            v-model.number="item.Quantity"
            @input="validateQuantity(item)"
            type="number"
            min="0"
            :max="item.OpenQuantity"
            step="0.01"
            class="w-full px-2 py-1 border rounded text-gray-900 focus:ring-2 focus:ring-purple-500"
            :class="{
              'border-red-500 bg-red-50': item.validation?.quantity?.error,
              'border-yellow-500 bg-yellow-50': item.validation?.quantity?.warning
            }"
          />
        </template>

        <!-- @vue-ignore -->
        <template #cell-Batches="{ item }">
          <div class="space-y-2">
            <!-- Column Headers -->
            <div v-if="item.BatchLines && item.BatchLines.length > 0" class="flex items-center gap-2 px-2">
              <div class="w-64 text-xs font-semibold text-gray-700">Batch Number</div>
              <div class="w-28 text-xs font-semibold text-gray-700">Quantity</div>
              <div class="w-28 text-xs font-semibold text-gray-700">Moisture %</div>
              <div class="w-10"></div>
            </div>
            
            <!-- Batch Lines -->
            <div
              v-for="(batch, batchIndex) in item.BatchLines"
              :key="batchIndex"
              class="flex items-center gap-2 p-2 bg-gray-50 rounded border border-gray-200"
            >
              <!-- Batch Number -->
              <div class="w-64">
                <input
                  v-model="batch.BatchNumber"
                  @blur="validateBatchNumber(batch, item)"
                  type="text"
                  placeholder="Enter batch number..."
                  class="w-full px-3 py-2 border rounded text-gray-900 text-sm"
                  :class="{
                    'border-red-500 bg-red-50': batch.validation?.batchNumber?.error
                  }"
                />
              </div>
              
              <!-- Batch Quantity -->
              <div class="w-28">
                <input
                  v-model.number="batch.Quantity"
                  @input="validateBatchQuantities(item)"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0"
                  class="w-full px-3 py-2 border rounded text-gray-900 text-sm text-right"
                />
              </div>
              
              <!-- Moisture Value -->
              <div class="w-28">
                <input
                  v-model.number="batch.MoistureValue"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  placeholder="0.00"
                  class="w-full px-3 py-2 border rounded text-gray-900 text-sm text-right"
                />
              </div>
              
              <!-- Remove Batch -->
              <button
                @click="item.BatchLines.splice(batchIndex, 1); validateBatchQuantities(item)"
                type="button"
                class="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
                title="Remove Batch"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
            
            <!-- Add Batch Button -->
            <button
              v-if="item.Quantity > 0"
              @click="addBatchLine(item)"
              type="button"
              class="w-full text-sm px-3 py-2 bg-green-50 text-green-700 rounded hover:bg-green-100 transition-colors font-medium border border-green-200"
            >
              + Add Batch
            </button>
          </div>
        </template>
      </GRNItemsTable>
    </div>

    <!-- Footer -->
    <GRNFormFooter
      v-if="selectedPO"
      :items-count="lineItems.length"
      :total-quantity="lineItems.reduce((sum, item) => sum + (item.Quantity || 0), 0)"
      :can-submit="canSubmit"
      :submitting="submitting"
      submit-text="Post to SAP"
      submit-icon="📦"
      @submit="submitGRN"
      @cancel="$emit('cancel')"
    >
      <!-- @vue-ignore -->
      <template #stats>
        <div class="text-sm">
          <span class="font-semibold text-gray-900">Completed:</span>
          <span class="ml-2 text-green-600 font-bold">{{ completedItems }}</span>
        </div>
        <div class="text-sm">
          <span class="font-semibold text-gray-900">Partial:</span>
          <span class="ml-2 text-yellow-600 font-bold">{{ partialItems }}</span>
        </div>
      </template>
    </GRNFormFooter>

    <!-- Keyboard Shortcuts Modal -->
    <div v-if="showShortcuts" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Keyboard Shortcuts</h3>
        
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-700">Submit GRN</span>
            <kbd class="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-xs font-mono">Ctrl + S</kbd>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-700">Cancel</span>
            <kbd class="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-xs font-mono">Esc</kbd>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-700">Show Help</span>
            <kbd class="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-xs font-mono">?</kbd>
          </div>
        </div>

        <button
          @click="showShortcuts = false"
          type="button"
          class="mt-6 w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  GRNFormHeader,
  GRNSearchSection,
  GRNItemsTable,
  GRNFormFooter
} from '@/shared/components/GRN'
import type { TableColumn } from '@/shared/components/GRN'
import { useGRNForm, type LineItem } from '@/shared/composables/useGRNForm'

// Props & Emits
defineProps<{}>()
const emit = defineEmits<{
  'grn-created': []
  'cancel': []
}>()

// Use shared GRN form logic
const {
  // State
  fetchAllPOs,
  fromDate,
  toDate,
  bpSearch,
  loading,
  purchaseOrders,
  selectedPO,
  lineItems,
  invoiceNumber,
  invoiceDate,
  receivedDate,
  createCNForLeftover,
  comments,
  submitting,
  showValidationDetails,
  fieldValidations,
  recentPOs,
  commonComments,
  showShortcuts,
  
  // Computed
  completedItems,
  partialItems,
  totalBatches,
  validationErrors,
  validationWarnings,
  canSubmit,
  
  // Methods
  quickDateOptions,
  setQuickDateRange,
  loadPurchaseOrders,
  loadPOLineItems,
  quickSelectPO,
  clearRecentPOs,
  submitGRN,
  validateQuantity,
  validateBatchNumber,
  validateBatchQuantities,
  acknowledgeWarning
} = useGRNForm('malur')

// Dropdown selection state
const selectedPODocEntry = ref<string | number>('')

// Handle PO selection from dropdown
function onPOSelect() {
  if (!selectedPODocEntry.value) {
    selectedPO.value = null
    return
  }
  
  const po = purchaseOrders.value.find((p: any) => p.DocEntry === selectedPODocEntry.value)
  if (po) {
    selectedPO.value = po
    loadPOLineItems()
  }
}

// Format date helper
function formatDate(dateStr: string | undefined) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ==================== Batch Management Functions ====================

// Add a new batch line to an item
function addBatchLine(item: LineItem) {
  if (!item.BatchLines) {
    item.BatchLines = []
  }
  item.BatchLines.push({
    BatchNumber: '',
    Quantity: 0,
    MoistureValue: 0,
    validation: { error: null, warning: null }
  })
}

// Generate batch number with format: MLR-VND-ITEM-20241028-001
function generateBatchNumber(item: LineItem) {
  try {
    const plantCode = 'MLR'
    const vendorCode = selectedPO.value?.CardCode?.substring(0, 3) || 'VND'
    const itemCode = item.ItemCode?.substring(0, 6) || 'ITEM'
    const date = new Date().toISOString().split('T')[0].replace(/-/g, '')
    const seq = String(Math.floor(Math.random() * 1000)).padStart(3, '0')
    
    return `${plantCode}-${vendorCode}-${itemCode}-${date}-${seq}`.toUpperCase()
  } catch (error) {
    console.error('Error generating batch number:', error)
    const timestamp = Date.now().toString().slice(-8)
    return `MLR-BATCH-${timestamp}`
  }
}

// Auto-generate batch numbers for all items with received quantity
function autoGenerateBatches() {
  let generatedCount = 0
  
  lineItems.value.forEach((item: LineItem) => {
    if (item.ReceivedQuantity > 0) {
      if (!item.BatchLines || item.BatchLines.length === 0) {
        item.BatchLines = [{
          BatchNumber: generateBatchNumber(item),
          Quantity: item.ReceivedQuantity,
          MoistureValue: 0,
          validation: { error: null, warning: null }
        }]
        generatedCount++
      } else {
        // Update existing batches if batch number is empty
        item.BatchLines.forEach((batch: any) => {
          if (!batch.BatchNumber || !batch.BatchNumber.trim()) {
            batch.BatchNumber = generateBatchNumber(item)
            generatedCount++
          }
        })
      }
    }
  })
  
  alert(`🏷️ Generated ${generatedCount} batch numbers`)
}

// Set received quantity = open quantity for all items
function receiveAllFullQuantity() {
  if (!confirm(`Set received quantity = open quantity for all ${lineItems.value.length} items?`)) {
    return
  }
  
  lineItems.value.forEach((item: LineItem) => {
    item.ReceivedQuantity = item.OpenQuantity
    
    if (!item.BatchLines || item.BatchLines.length === 0) {
      item.BatchLines = [{
        BatchNumber: generateBatchNumber(item),
        Quantity: item.OpenQuantity,
        MoistureValue: 0,
        validation: { error: null, warning: null }
      }]
    }
    
    validateQuantity(item)
  })
  
  alert('✅ All items set to full quantity with auto-generated batches')
}

// Clear all received quantities and batches
function clearAllReceivedQty() {
  if (!confirm('Clear all received quantities and batches?')) {
    return
  }
  
  lineItems.value.forEach((item: LineItem) => {
    item.ReceivedQuantity = 0
    item.BatchLines = []
    item.validation = {
      quantity: { error: null, warning: null },
      hasError: false,
      hasWarning: false
    }
  })
  
  alert('🗑️ All quantities cleared')
}

// Computed: Check if any items have received quantities
const hasReceivedQuantities = computed(() => {
  return lineItems.value.some((item: LineItem) => item.ReceivedQuantity > 0)
})

// Table columns definition
const tableColumns = computed<TableColumn[]>(() => [
  { key: 'LineNum', label: '#', width: 'w-12', align: 'center' },
  { key: 'ItemCode', label: 'Item Code', width: 'w-32' },
  { key: 'ItemDescription', label: 'Description' },
  { key: 'OrderedQuantity', label: 'Ordered', width: 'w-24', align: 'right' },
  { key: 'OpenQuantity', label: 'Open', width: 'w-24', align: 'right' },
  { key: 'Quantity', label: 'Receiving', width: 'w-32', align: 'center' },
  { key: 'Batches', label: 'Batch Details', width: 'w-96' }
])
</script>

<style scoped>
/* Add any component-specific styles here */
</style>
