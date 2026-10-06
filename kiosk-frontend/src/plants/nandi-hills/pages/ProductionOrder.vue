<template>
  <div class="p-6">
    <!-- Page Header -->
    <div class="mb-8">
      <div class="flex items-start justify-between">
        <div>
          <h1 class="text-3xl font-bold text-gray-900 mb-2">Production Order – Nandi Hills</h1>
          <p class="text-gray-600">Production Kiosk | Goods Issue & Receipt</p>
        </div>
        <button @click="goToBatchGenerator" class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
          Batch Number Generator
        </button>
      </div>
    </div>

    <!-- Process Type (Required) -->
    <div class="bg-white rounded-lg shadow-md p-4 mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">
        Process Type <span class="text-red-500">*</span>
      </label>
      <select 
        v-model="productionType" 
        required
        class="w-full px-4 py-2 border-2 border-blue-500 rounded-lg text-gray-900 font-semibold bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Select Process Type...</option>
        <option value="Standard">Standard</option>
        <option value="Special">Special</option>
        <option value="Disassembly">Disassembly</option>
      </select>
    </div>

    <!-- Top Bar with Search and Refresh -->
    <div class="bg-blue-50 rounded-lg border-2 border-blue-500 p-4 mb-6">
      <div class="flex flex-col md:flex-row gap-4 items-center justify-between">
        <div class="flex-1 w-full relative">
          <div class="relative">
            <input
              v-model="bomSearchQuery"
              @input="onBOMSearchInput"
              @focus="showBOMResults = bomResults.length > 0"
              type="text"
              placeholder="Search BOM by Item Name (OITT/ITT1) - Type at least 2 characters..."
              class="w-full px-4 py-3 pl-12 border-2 border-blue-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-600 bg-white text-gray-900"
            />
            <svg class="absolute left-3 top-3.5 h-6 w-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          
          <!-- BOM Search Results Dropdown -->
          <div v-if="showBOMResults && bomResults.length > 0" class="absolute z-50 w-full mt-1 bg-white border-2 border-blue-400 rounded-lg shadow-lg max-h-96 overflow-y-auto">
            <div class="px-3 py-2 bg-blue-100 border-b border-blue-300">
              <p class="text-xs font-semibold text-blue-700">Found {{ bomResults.length }} BOM record(s)</p>
            </div>
            <div 
              v-for="(bom, idx) in bomResults" 
              :key="idx"
              @mousedown.prevent="selectBOM(bom)"
              class="p-4 hover:bg-blue-50 cursor-pointer border-b border-gray-200 transition-colors"
            >
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <p class="font-bold text-blue-700 text-base">{{ bom.Name }}</p>
                  <div class="flex gap-3 mt-2">
                    <p class="text-sm text-gray-600">📋 Code: <span class="font-semibold">{{ bom.Code }}</span></p>
                    <p class="text-sm text-gray-600">📦 Type: <span class="font-semibold">{{ bom.TreeType }}</span></p>
                    <p class="text-sm text-gray-600">🏭 WH: <span class="font-semibold">{{ bom.ToWH }}</span></p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <button
          @click="refreshData"
          class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Refresh
        </button>
      </div>
      <p class="text-sm text-blue-600 mt-2">
        💡 Search BOM components from OITT (Bill of Materials Header) and ITT1 (Bill of Materials Components) tables
      </p>
    </div>

    <!-- Selected BOM Display - Simplified -->
    <div v-if="selectedBOM" class="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border-2 border-blue-400 p-4 mb-4">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-bold text-blue-700">{{ selectedBOM.ItemName || selectedBOM.Name }}</h3>
        <button
          @click="clearBOMSelection"
          class="px-3 py-1 bg-red-500 text-white rounded-lg hover:bg-red-600 text-sm"
        >
          Clear
        </button>
      </div>
    </div>


    <!-- BOM Components (ITT1) - Inputs -->
    <div v-if="selectedBOM" class="bg-white rounded-lg shadow-md overflow-hidden mb-6">
      <button
        @click="toggleSection('itt1')"
        class="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50"
      >
        <h2 class="text-xl font-semibold text-blue-700">🧩 Inputs</h2>
        <svg
          :class="{ 'rotate-180': !sections.itt1 }"
          class="h-5 w-5 text-gray-500 transition-transform"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="sections.itt1" class="px-6 pb-6">
        <div v-if="itt1Components.length > 0" class="space-y-4">
          <div v-for="(comp, idx) in itt1Components" :key="idx" class="border border-gray-200 rounded-lg p-4 bg-gray-50">
            <h3 class="font-semibold text-lg text-blue-700 mb-3">{{ comp.ItemName }}</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label class="block text-xs font-medium text-blue-700">Component Code</label>
                <input :value="comp.Code" readonly class="w-full px-3 py-2 border-2 border-blue-300 rounded-lg bg-blue-50 text-blue-700 font-medium" />
              </div>
              <div>
                <label class="block text-xs font-medium text-blue-700">Input Quantity *</label>
                <input v-model.number="comp.inputQuantity" type="number" placeholder="" class="w-full px-3 py-2 border-2 border-blue-500 rounded-lg text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label class="block text-xs font-medium text-blue-700">Batch Number</label>
                <input 
                  v-model="comp.batchNumber" 
                  type="text" 
                  placeholder="Enter batch" 
                  readonly
                  @click="openBatchModal(comp)"
                  class="w-full px-3 py-2 border-2 border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer bg-blue-50"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-blue-700">Warehouse</label>
                <select v-model="comp.warehouse" class="w-full px-3 py-2 border-2 border-blue-300 rounded-lg text-blue-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="" class="text-gray-600">Select...</option>
                  <option v-for="wh in warehouses" :key="wh" :value="wh" class="text-blue-700">{{ wh }}</option>
                </select>
              </div>
            </div>
            
            <!-- Batch Allocations Display -->
            <div v-if="comp.selectedBatches && comp.selectedBatches.length > 0" class="mt-4">
              <h4 class="text-sm font-semibold text-blue-700 mb-2">📊 Batch Allocations</h4>
              <div class="bg-white border-2 border-blue-200 rounded-lg overflow-hidden">
                <table class="min-w-full divide-y divide-gray-200">
                  <thead class="bg-blue-50">
                    <tr>
                      <th class="px-3 py-2 text-left text-xs font-medium text-blue-700 uppercase">Batch Number</th>
                      <th class="px-3 py-2 text-left text-xs font-medium text-blue-700 uppercase">Warehouse</th>
                      <th class="px-3 py-2 text-left text-xs font-medium text-blue-700 uppercase">Available Qty</th>
                      <th class="px-3 py-2 text-left text-xs font-medium text-blue-700 uppercase">Qty Used</th>
                      <th class="px-3 py-2 text-center text-xs font-medium text-blue-700 uppercase">Action</th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="(batch, batchIdx) in comp.selectedBatches" :key="batchIdx">
                      <td class="px-3 py-2 text-sm font-medium text-blue-600">{{ batch.BatchNumber }}</td>
                      <td class="px-3 py-2 text-sm text-gray-600">{{ batch.Warehouse }}</td>
                      <td class="px-3 py-2 text-sm text-gray-600">{{ batch.AvailableQty }}</td>
                      <td class="px-3 py-2 text-sm">
                        <input 
                          v-model.number="batch.inputQuantity" 
                          type="number" 
                          @input="updateComponentTotal(comp)"
                          class="w-full px-2 py-1 border border-blue-300 rounded text-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          :max="batch.AvailableQty"
                        />
                      </td>
                      <td class="px-3 py-2 text-center">
                        <button 
                          @click="removeBatchFromComponent(comp, batchIdx)"
                          class="text-red-600 hover:text-red-800"
                        >
                          ❌
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            
            <div class="mt-3 grid grid-cols-3 gap-3 text-sm">
              <div class="bg-white p-2 rounded">
                <span class="text-gray-600">Base Qty:</span> <span class="font-semibold">{{ comp.U_BaseQty || '-' }}</span>
              </div>
              <div class="bg-white p-2 rounded">
                <span class="text-gray-600">Scrap:</span> <span class="font-semibold">{{ comp.U_Scrap || '-' }}%</span>
              </div>
              <div class="bg-white p-2 rounded">
                <span class="text-gray-600">Mat Type:</span> <span class="font-semibold">{{ comp.U_MatType || '-' }}</span>
              </div>
          </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Output Goods Section -->
    <div v-if="selectedBOM" class="bg-white rounded-lg shadow-md overflow-hidden mb-6">
      <button
        @click="toggleSection('output')"
        class="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50"
      >
        <h2 class="text-xl font-semibold text-blue-700">📦 Output</h2>
        <svg
          :class="{ 'rotate-180': !sections.output }"
          class="h-5 w-5 text-gray-500 transition-transform"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="sections.output" class="px-6 pb-6">
        <div class="border-2 border-blue-200 rounded-lg p-6 bg-blue-50">
          <h3 class="font-bold text-xl text-blue-700 mb-4">{{ selectedBOM.Name }}</h3>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div class="bg-white rounded p-3">
              <label class="block text-xs font-medium text-blue-700 mb-1">Code</label>
              <p class="text-blue-700 font-semibold">{{ selectedBOM.Code }}</p>
            </div>
            <div class="bg-white rounded p-3">
              <label class="block text-xs font-medium text-blue-700 mb-1">Tree Type</label>
              <p class="text-blue-700 font-semibold">{{ selectedBOM.TreeType }}</p>
            </div>
            <div class="bg-white rounded p-3">
              <label class="block text-xs font-medium text-blue-700 mb-1">To Warehouse</label>
              <p class="text-blue-700 font-semibold">{{ selectedBOM.ToWH }}</p>
            </div>
            <div class="bg-white rounded p-3">
              <label class="block text-xs font-medium text-blue-700 mb-1">Output Quantity *</label>
              <input v-model.number="outputQuantity" type="number" placeholder="" class="w-full px-3 py-2 border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-blue-700" />
            </div>
          </div>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label class="block text-xs font-medium text-blue-700 mb-2">Date</label>
              <input v-model="outputBatchDate" type="date" class="w-full px-3 py-2 border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-blue-700" />
            </div>
            <div>
              <label class="block text-xs font-medium text-blue-700 mb-2">Batch Number</label>
              <div class="flex gap-2">
                <input v-model="outputBatchNumber" type="text" placeholder="Enter batch number" readonly class="flex-1 px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 cursor-pointer text-blue-700" @click="openOutputBatchLookup" />
                <button @click="openOutputBatchLookup" class="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  🔍
                </button>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-blue-700 mb-2">Warehouse</label>
              <select v-model="outputWarehouse" class="w-full px-3 py-2 border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-blue-700">
                <option value="">Select warehouse...</option>
                <option v-for="wh in warehouses" :key="wh" :value="wh" class="text-blue-700">{{ wh }}</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Byproducts Section (Negative quantity items) -->
        <div v-if="byProducts.length > 0" class="mt-6">
          <h4 class="text-lg font-bold text-green-700 mb-4">🔄 Byproducts</h4>
          <div class="space-y-4">
            <div v-for="(product, idx) in byProducts" :key="idx" class="border-2 border-green-200 rounded-lg p-4 bg-green-50">
              <h5 class="font-bold text-lg text-green-700 mb-3">{{ product.ItemName }}</h5>
              
              <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
                <div>
                  <label class="block text-xs font-medium text-green-700 mb-1">Component Code</label>
                  <input :value="product.Code" readonly class="w-full px-3 py-2 border-2 border-green-300 rounded-lg bg-green-50 text-green-700 font-medium" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-green-700 mb-1">Output Quantity *</label>
                  <input v-model.number="product.outputQuantity" type="number" placeholder="" class="w-full px-3 py-2 border-2 border-green-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-green-700 mb-1">Date</label>
                  <input v-model="product.batchDate" type="date" class="w-full px-3 py-2 border-2 border-green-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-green-700 mb-1">Batch Number</label>
                  <div class="flex gap-2">
                    <input v-model="product.outputBatchNumber" type="text" placeholder="Enter batch" readonly class="flex-1 px-3 py-2 border-2 border-green-300 rounded-lg bg-green-50 cursor-pointer" @click="openByproductBatchLookup(product)" />
                    <button @click="openByproductBatchLookup(product)" class="px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                      🔍
                    </button>
                  </div>
                </div>
                <div>
                  <label class="block text-xs font-medium text-green-700 mb-1">Warehouse</label>
                  <select v-model="product.outputWarehouse" class="w-full px-3 py-2 border-2 border-green-300 rounded-lg text-green-700 bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
                    <option value="" class="text-gray-600">Select...</option>
                    <option v-for="wh in warehouses" :key="wh" :value="wh" class="text-green-700">{{ wh }}</option>
                  </select>
                </div>
              </div>
              
              <div class="grid grid-cols-3 gap-3 text-sm">
                <div class="bg-white p-2 rounded">
                  <span class="text-gray-600">Base Qty:</span> <span class="font-semibold">{{ product.U_BaseQty || '-' }}</span>
                </div>
                <div class="bg-white p-2 rounded">
                  <span class="text-gray-600">Scrap:</span> <span class="font-semibold">{{ product.U_Scrap || '-' }}%</span>
                </div>
                <div class="bg-white p-2 rounded">
                  <span class="text-gray-600">Mat Type:</span> <span class="font-semibold">{{ product.U_MatType || '-' }}</span>
                </div>
              </div>
            </div>
      </div>
        </div>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="bg-white rounded-lg shadow-md p-6">
      <h2 class="text-xl font-semibold text-gray-900 mb-4">⚡ Production Actions</h2>
      <div class="flex flex-wrap gap-4">
        <button
          @click="submitApproval"
          :disabled="workflowState >= 1"
          class="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          ✓ Approve
        </button>
        <button
          @click="submitGoodsIssue"
          :disabled="workflowState < 1"
          class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          📤 Goods Issue
        </button>
        <button
          @click="submitGoodsReceipt"
          :disabled="workflowState < 2"
          class="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          📥 Goods Receipt
        </button>
        <button
          @click="closeProduction"
          :disabled="workflowState < 3"
          class="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          ✕ Close Production
        </button>
      </div>
      <p class="text-sm text-gray-500 mt-3">
        Current Workflow State: {{ ['Initial', 'Approved', 'Goods Issued', 'Goods Received'][workflowState] }}
      </p>
    </div>

    <!-- Batch Date Item Lookup Modal -->
    <div v-if="showBatchDateItemModal" class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4" @click.self="closeBatchDateItemModal">
      <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden" @click.stop>
        <!-- Modal Header -->
        <div class="bg-indigo-600 text-white px-6 py-4 flex items-center justify-between">
          <h3 class="text-xl font-bold">Batch Number Lookup - {{ currentBatchLookupItem?.Code || currentBatchLookupItem?.item_code }}</h3>
          <button @click="closeBatchDateItemModal" class="text-white hover:text-gray-200">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-6">
          <!-- Date Range Selection -->
          <div class="mb-4 grid grid-cols-3 gap-2">
            <div>
              <label class="block text-sm font-medium text-blue-700 mb-2">From Date</label>
              <input v-model="batchDateItemLookupDateFrom" type="date" class="w-full px-3 py-2 border-2 border-indigo-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-blue-700" />
            </div>
            <div>
              <label class="block text-sm font-medium text-blue-700 mb-2">To Date (Current Date)</label>
              <input v-model="batchDateItemLookupDateTo" type="date" class="w-full px-3 py-2 border-2 border-indigo-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-blue-700" />
            </div>
            <div class="flex items-end">
              <button @click="searchBatchDateItems" class="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                🔍 Search
              </button>
            </div>
          </div>
          <p class="text-xs text-gray-500 mb-4">💡 Leave dates empty to get latest batch numbers</p>

          <!-- Loading State -->
          <div v-if="loadingBatchDateItems" class="text-center py-8">
            <p class="text-gray-600">Loading batch numbers...</p>
          </div>

          <!-- Batch Numbers List -->
          <div v-else-if="batchDateItemResults.length > 0" class="overflow-y-auto max-h-96 border rounded-lg">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-indigo-50 sticky top-0">
                <tr>
                  <th class="px-4 py-3 text-left text-xs font-medium text-indigo-700 uppercase">Batch Number</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-indigo-700 uppercase">Warehouse</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-indigo-700 uppercase">Variant</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-indigo-700 uppercase">Date</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-indigo-700 uppercase">Action</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="(batch, idx) in batchDateItemResults" :key="idx" class="hover:bg-indigo-50">
                  <td class="px-4 py-3 text-sm font-medium text-indigo-600">{{ batch.batch_number }}</td>
                  <td class="px-4 py-3 text-sm text-gray-600">{{ batch.warehouse }}</td>
                  <td class="px-4 py-3 text-sm text-gray-600">{{ batch.variant || '-' }}</td>
                  <td class="px-4 py-3 text-sm text-gray-600">{{ batch.date }}</td>
                  <td class="px-4 py-3">
                    <button @click="selectBatchDateItem(batch)" class="px-3 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-sm">
                      Select
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- No Results -->
          <div v-else class="text-center py-8 text-gray-600">
            <p>No batch numbers found for this item code</p>
            <button @click="searchBatchDateItems" class="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
              Search
            </button>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="bg-gray-50 px-6 py-4 flex justify-end">
          <button @click="closeBatchDateItemModal" class="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700">
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Batch Selection Modal -->
    <div v-if="showBatchModal" class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4" @click.self="closeBatchModal">
      <div class="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden" @click.stop>
        <!-- Modal Header -->
        <div class="bg-blue-600 text-white px-6 py-4 flex items-center justify-between">
          <h3 class="text-xl font-bold">Select Batch Number - {{ currentComponent.ItemName }}</h3>
          <button @click="closeBatchModal" class="text-white hover:text-gray-200">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-6">
          <!-- Date Range Filter -->
          <div class="grid grid-cols-3 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-blue-700 mb-1">Admission Date (From)</label>
              <input v-model="batchDateFrom" type="date" class="w-full px-3 py-2 border-2 border-blue-500 rounded-lg text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-blue-700 mb-1">Admission Date (To)</label>
              <input v-model="batchDateTo" type="date" class="w-full px-3 py-2 border-2 border-blue-500 rounded-lg text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div class="flex items-end">
              <button 
                @click="searchBatches"
                class="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Search
              </button>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="loadingBatches" class="text-center py-8">
            <p class="text-gray-600">Loading batches...</p>
          </div>

          <!-- Batch Table -->
          <div v-else-if="batchNumbers.length > 0" class="overflow-y-auto max-h-96">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50 sticky top-0">
                <tr>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <input type="checkbox" @change="toggleSelectAll" :checked="allBatchesSelected" class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded" />
                  </th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Batch Number</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Warehouse</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Available Qty</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mfg Date</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exp Date</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Shelf Life</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Admission Date (InDate)</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="(batch, idx) in batchNumbers" :key="idx" class="hover:bg-blue-50">
                  <td class="px-4 py-3 whitespace-nowrap">
                    <input 
                      type="checkbox" 
                      :value="batch"
                      v-model="selectedBatchesInModal"
                      class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm font-medium text-blue-600">{{ batch.BatchNumber }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{{ batch.Warehouse }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{{ batch.Quantity }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{{ batch.ManufacturingDate || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{{ batch.ExpiryDate || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm">
                    <span :class="batch.RemainingShelfLife > 30 ? 'text-green-600' : 'text-red-600'">
                      {{ batch.RemainingShelfLife }} days
                    </span>
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{{ batch.InDate || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- No Results -->
          <div v-else class="text-center py-8 text-gray-600">
            No batch numbers found
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="bg-gray-50 px-6 py-4 flex justify-between items-center">
          <div class="text-sm text-gray-600">
            {{ selectedBatchesInModal.length }} batch(es) selected
          </div>
          <div class="flex gap-3">
            <button 
              @click="confirmBatchesSelection"
              :disabled="selectedBatchesInModal.length === 0"
              class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Confirm Selection
            </button>
            <button 
              @click="closeBatchModal"
              class="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { nandi_hillsProductionService } from '@/core/api/plants/nandi_hills/productionService'

// Search and BOM Data
const bomSearchQuery = ref('')
const bomResults = ref([])
const showBOMResults = ref(false)
const selectedBOM = ref(null)
const searchQuery = ref('')
const loading = ref(false)

// Production Data
const productionType = ref('')

// BOM Components
const itt1Components = ref([])
const byProducts = ref([]) // Negative quantity items (outputs/byproducts)
const oittHeader = ref(null)

// Workflow
const workflowState = ref(0)

// Output Data
const outputQuantity = ref('')
const outputBatchNumber = ref('')
const outputBatchDate = ref('')
const outputWarehouse = ref('')

// UI State
const sections = ref({
  itt1: true,
  output: true
})

const warehouses = ref(['NH01', 'NH02', 'NH03', 'NH-WIP'])

const router = useRouter()
const goToBatchGenerator = () => {
  router.push('/batch-generator')
}

// Batch Selection Modal
const showBatchModal = ref(false)
const batchNumbers = ref([])
const loadingBatches = ref(false)
const currentComponent = ref(null)
const batchDateFrom = ref('')
const batchDateTo = ref('')
const selectedBatchesInModal = ref([])

// Batch Date Item Lookup Modal
const showBatchDateItemModal = ref(false)
const batchDateItemResults = ref([])
const loadingBatchDateItems = ref(false)
const currentBatchLookupItem = ref(null)
const batchDateItemLookupDateFrom = ref('')
const batchDateItemLookupDateTo = ref('')

// Search with debounce
let searchTimeout = null
const onBOMSearchInput = () => {
  clearTimeout(searchTimeout)
  
  if (bomSearchQuery.value.length < 2) {
    bomResults.value = []
    showBOMResults.value = false
    return
  }
  
  searchTimeout = setTimeout(() => {
    searchBOMTables()
  }, 300)
}

const searchBOMTables = async () => {
  try {
    loading.value = true
    const response = await nandi_hillsProductionService.searchBOM(bomSearchQuery.value)
    
    if (response.success && response.data) {
      bomResults.value = response.data
      showBOMResults.value = true
    } else {
      bomResults.value = []
      showBOMResults.value = false
    }
  } catch (error) {
    console.error('Error searching BOM:', error)
    // Mock data for development - only OITT headers
    bomResults.value = [
      {
        Type: 'OITT',
        Code: 'BOM001',
        Name: 'Dogsee Chew Small bars - 100G India - Brushing',
        TreeType: 'S',
        ToWH: 'NH01'
      },
      {
        Type: 'OITT',
        Code: 'BOM002',
        Name: 'Fresh Churpi Bread',
        TreeType: 'M',
        ToWH: 'NH02'
      }
    ]
    showBOMResults.value = true
  } finally {
    loading.value = false
  }
}

const selectBOM = async (bom) => {
  selectedBOM.value = bom
  showBOMResults.value = false
  
  // All search results are OITT headers - fetch their ITT1 components automatically
  oittHeader.value = bom
  bomSearchQuery.value = bom.Name || bom.Code
  
      // Initialize output fields
      outputQuantity.value = ''
      outputBatchNumber.value = ''
      outputBatchDate.value = ''
      outputWarehouse.value = bom.ToWH || ''
  
  // Automatically fetch ITT1 components for the selected BOM
  await fetchITT1ForBOM(bom.Code)
}

const fetchITT1ForBOM = async (bomCode) => {
  try {
    loading.value = true
    const response = await nandi_hillsProductionService.getITT1Components(bomCode)
    
    if (response.success && response.data) {
      // Separate positive (inputs) and negative (byproducts) quantities
      const allComponents = response.data.map(comp => ({
        ...comp,
        inputQuantity: '',
        batchNumber: '',
        warehouse: comp.Warehouse || '',
        selectedBatches: []
      }))
      
      // Filter components by quantity sign
      itt1Components.value = allComponents.filter(comp => comp.Quantity >= 0)
      byProducts.value = allComponents.filter(comp => comp.Quantity < 0).map(comp => ({
        ...comp,
        outputQuantity: Math.abs(comp.Quantity).toString(), // Convert to positive for display
        outputBatchNumber: '',
        batchDate: '',
        outputWarehouse: comp.Warehouse || ''
      }))
    }
  } catch (error) {
    console.error('Error fetching ITT1:', error)
  } finally {
    loading.value = false
  }
}

const fetchOITTForBOM = async (bomCode) => {
  try {
    loading.value = true
    const response = await nandi_hillsProductionService.getOITTHeader(bomCode)
    
    if (response.success && response.data) {
      oittHeader.value = response.data
    }
  } catch (error) {
    console.error('Error fetching OITT:', error)
  } finally {
    loading.value = false
  }
}

const clearBOMSelection = () => {
  selectedBOM.value = null
  bomSearchQuery.value = ''
  itt1Components.value = []
  byProducts.value = []
  outputQuantity.value = ''
  outputBatchNumber.value = ''
  outputBatchDate.value = ''
  outputWarehouse.value = ''
}

const toggleSection = (section) => {
  sections.value[section] = !sections.value[section]
}

const fetchITT1Details = async () => {
  if (!selectedBOM.value?.Code) return
  
  try {
    loading.value = true
    const response = await nandi_hillsProductionService.getITT1Components(selectedBOM.value.Code)
    
    if (response.success && response.data) {
      itt1Components.value = response.data
    } else {
      // Mock data for development
      itt1Components.value = [
        {
          Code: 'ITEM001',
          ItemName: 'Raw Material 1',
          Quantity: 100,
          Warehouse: 'NH01',
          U_BaseQty: 100,
          U_Scrap: 5,
          U_MatType: 'Raw',
          inputQuantity: 100,
          batchNumber: '',
          warehouse: 'NH01'
        }
      ]
    }
  } catch (error) {
    console.error('Error fetching ITT1:', error)
  } finally {
    loading.value = false
  }
}

const fetchOITTDetails = async () => {
  if (!selectedBOM.value?.Code) return
  
  try {
    loading.value = true
    const response = await nandi_hillsProductionService.getOITTHeader(selectedBOM.value.Code)
    
    if (response.success && response.data) {
      oittHeader.value = response.data
    } else {
      // Mock data for development
      oittHeader.value = {
        Code: 'BOM001',
        Name: 'Sample BOM',
        TreeType: 'S',
        ToWH: 'NH01'
      }
    }
  } catch (error) {
    console.error('Error fetching OITT:', error)
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  fetchOITTDetails()
  fetchITT1Details()
}

// Workflow Actions (Placeholder - Backend endpoints not yet implemented)
const submitApproval = async () => {
  // TODO: Implement backend API for approval
  workflowState.value = 1
  alert('✅ Production approved successfully!')
}

const submitGoodsIssue = async () => {
  // TODO: Implement backend API for goods issue
  workflowState.value = 2
  alert('✅ Goods issued successfully!')
}

const submitGoodsReceipt = async () => {
  // TODO: Implement backend API for goods receipt
  workflowState.value = 3
  alert('✅ Goods received successfully!')
}

const closeProduction = () => {
  // TODO: Implement backend API for closing production
  alert('✅ Production closed successfully!')
  workflowState.value = 0
}

// Multi-batch selection functions
const allBatchesSelected = computed(() => {
  return batchNumbers.value.length > 0 && selectedBatchesInModal.value.length === batchNumbers.value.length
})

const toggleSelectAll = () => {
  if (allBatchesSelected.value) {
    selectedBatchesInModal.value = []
  } else {
    selectedBatchesInModal.value = [...batchNumbers.value]
  }
}

const confirmBatchesSelection = () => {
  if (currentComponent.value && selectedBatchesInModal.value.length > 0) {
    // Initialize selectedBatches array if it doesn't exist
    if (!currentComponent.value.selectedBatches) {
      currentComponent.value.selectedBatches = []
    }
    
    // Add each selected batch with its details
    selectedBatchesInModal.value.forEach(batch => {
      const exists = currentComponent.value.selectedBatches.some(b => b.BatchNumber === batch.BatchNumber)
      if (!exists) {
        currentComponent.value.selectedBatches.push({
          BatchNumber: batch.BatchNumber,
          Warehouse: batch.Warehouse,
          AvailableQty: batch.Quantity,
          inputQuantity: 0,
          ManufacturingDate: batch.ManufacturingDate,
          ExpiryDate: batch.ExpiryDate,
          RemainingShelfLife: batch.RemainingShelfLife,
          InDate: batch.InDate
        })
      }
    })
    
    // Update the total quantity
    updateComponentTotal(currentComponent.value)
    
    // Clear modal selections
    selectedBatchesInModal.value = []
    
    // Close modal
    closeBatchModal()
  }
}

const removeBatchFromComponent = (comp, batchIdx) => {
  if (comp.selectedBatches && comp.selectedBatches[batchIdx]) {
    comp.selectedBatches.splice(batchIdx, 1)
    updateComponentTotal(comp)
  }
}

const updateComponentTotal = (comp) => {
  if (comp.selectedBatches && comp.selectedBatches.length > 0) {
    const total = comp.selectedBatches.reduce((sum, batch) => {
      return sum + (batch.inputQuantity || 0)
    }, 0)
    comp.inputQuantity = total
    
    // Update batchNumber field for compatibility with single-batch selection
    if (comp.selectedBatches.length === 1) {
      comp.batchNumber = comp.selectedBatches[0].BatchNumber
      comp.warehouse = comp.selectedBatches[0].Warehouse
    } else {
      comp.batchNumber = `${comp.selectedBatches.length} batches selected`
    }
  }
}

const openBatchModal = async (comp) => {
  currentComponent.value = comp
  showBatchModal.value = true
  selectedBatchesInModal.value = []
  allBatchesSelected.value = false
  
  // Auto-fetch batches when modal opens
  await searchBatches()
  
  // Auto-select the most recent batch if available (for single-batch compatibility)
  if (batchNumbers.value.length > 0 && !comp.batchNumber && !comp.selectedBatches) {
    // This is the old single-batch behavior - keeping for backward compatibility
  }
}

const searchBatches = async () => {
  if (!currentComponent.value?.Code) {
    console.log('No component selected')
    return
  }
  
  console.log('Fetching batches for:', {
    Code: currentComponent.value.Code,
    warehouse: currentComponent.value.warehouse,
    dateFrom: batchDateFrom.value,
    dateTo: batchDateTo.value
  })
  
  try {
    loadingBatches.value = true
    const response = await nandi_hillsProductionService.getBatchNumbers(
      currentComponent.value.Code,
      currentComponent.value.warehouse,
      batchDateFrom.value || null,
      batchDateTo.value || null
    )
    
    console.log('Batch API Response:', response)
    
    if (response && response.success && response.data) {
      batchNumbers.value = response.data
      console.log('Found batches:', response.data.length)
    } else {
      batchNumbers.value = []
      console.log('No batches found')
    }
  } catch (error) {
    console.error('Error fetching batches:', error)
    console.error('Error details:', error.response || error.message)
    batchNumbers.value = []
  } finally {
    loadingBatches.value = false
  }
}

const closeBatchModal = () => {
  showBatchModal.value = false
  batchNumbers.value = []
  selectedBatchesInModal.value = []
  currentComponent.value = null
  batchDateFrom.value = ''
  batchDateTo.value = ''
}

// Batch Date Item Lookup Functions
const openOutputBatchLookup = async () => {
  if (!selectedBOM.value?.Code) {
    alert('Please select a BOM first')
    return
  }
  
  currentBatchLookupItem.value = {
    Code: selectedBOM.value.Code,
    item_code: selectedBOM.value.Code,
    ItemName: selectedBOM.value.Name || selectedBOM.value.ItemName
  }
  // Set both dates to current date by default
  const today = new Date().toISOString().split('T')[0]
  batchDateItemLookupDateFrom.value = today
  batchDateItemLookupDateTo.value = today
  showBatchDateItemModal.value = true
  batchDateItemResults.value = []
}

const openByproductBatchLookup = async (product) => {
  if (!product?.Code) {
    alert('Item code not available')
    return
  }
  
  currentBatchLookupItem.value = {
    Code: product.Code,
    item_code: product.Code,
    ItemName: product.ItemName
  }
  // Set both dates to current date by default
  const today = new Date().toISOString().split('T')[0]
  batchDateItemLookupDateFrom.value = today
  batchDateItemLookupDateTo.value = today
  showBatchDateItemModal.value = true
  batchDateItemResults.value = []
}

const searchBatchDateItems = async () => {
  if (!currentBatchLookupItem.value?.item_code && !currentBatchLookupItem.value?.Code) {
    return
  }
  
  const itemCode = currentBatchLookupItem.value.item_code || currentBatchLookupItem.value.Code
  const dateFrom = batchDateItemLookupDateFrom.value || null
  const dateTo = batchDateItemLookupDateTo.value || null
  
  try {
    loadingBatchDateItems.value = true
    const response = await nandi_hillsProductionService.getBatchNumbersFromBatchDateItem(itemCode, dateFrom, dateTo)
    
    if (response && response.success && response.data) {
      batchDateItemResults.value = response.data
    } else {
      batchDateItemResults.value = []
    }
  } catch (error) {
    console.error('Error fetching batch numbers from Batch Date Item:', error)
    batchDateItemResults.value = []
  } finally {
    loadingBatchDateItems.value = false
  }
}

const selectBatchDateItem = (batch) => {
  if (currentBatchLookupItem.value === null) return
  
  // Check if this is for Output or Byproduct
  const itemCode = currentBatchLookupItem.value.item_code || currentBatchLookupItem.value.Code
  
  // If it matches the selected BOM Code, update Output
  if (selectedBOM.value && itemCode === selectedBOM.value.Code) {
    outputBatchNumber.value = batch.batch_number
    // Use the batch date from the selected batch, or from date range
    outputBatchDate.value = batchDateItemLookupDateFrom.value || ''
    outputWarehouse.value = batch.warehouse || outputWarehouse.value
  }
  // Otherwise, find matching byproduct
  else {
    const byproduct = byProducts.value.find(p => p.Code === itemCode)
    if (byproduct) {
      byproduct.outputBatchNumber = batch.batch_number
      byproduct.batchDate = batchDateItemLookupDateFrom.value || ''
      byproduct.outputWarehouse = batch.warehouse || byproduct.outputWarehouse
    }
  }
  
  closeBatchDateItemModal()
}

const closeBatchDateItemModal = () => {
  showBatchDateItemModal.value = false
  batchDateItemResults.value = []
  currentBatchLookupItem.value = null
  batchDateItemLookupDateFrom.value = ''
  batchDateItemLookupDateTo.value = ''
}

onMounted(() => {
})
</script>

<style scoped>
/* Additional styles if needed */
</style>
