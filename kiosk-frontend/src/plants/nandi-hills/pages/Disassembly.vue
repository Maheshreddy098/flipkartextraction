<template>
  <div class="p-6">
    <!-- Page Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Disassembly Report – Nandi Hills</h1>
      <p class="text-gray-600">Fetch Goods Issue & Goods Receipt details for Production Orders</p>
    </div>

    <!-- Input Section -->
    <div class="bg-blue-50 rounded-lg border-2 border-blue-500 p-6 mb-6">
      <div class="flex flex-col md:flex-row gap-4 items-end">
        <div class="flex-1">
          <label class="block text-sm font-semibold text-gray-700 mb-2">
            Production Order Document Number (DocNum)
          </label>
          <input
            v-model.number="docNum"
            @keyup.enter="fetchDetails"
            type="number"
            placeholder="Enter DocNum (e.g., 37491)"
            class="w-full px-4 py-3 border-2 border-blue-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-600 bg-white text-gray-900"
            :disabled="loading"
          />
        </div>
        <div class="flex gap-2">
          <button
            @click="fetchDetails"
            :disabled="!docNum || loading"
            class="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg v-if="loading" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ loading ? 'Fetching...' : 'Fetch Details' }}</span>
          </button>
          <button
            @click="fetchAllDisassemblies"
            :disabled="loadingAllDisassemblies"
            class="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
            title="View all Disassembly records from DocType"
          >
            <svg v-if="loadingAllDisassemblies" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ loadingAllDisassemblies ? 'Loading...' : '📋 View All Disassembly Records' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Completed Disassemblies Section - Right below input -->
    <div v-if="showAllRecords" class="bg-white rounded-lg border-2 border-green-300 p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-semibold text-gray-900">
          ✅ Completed Disassemblies
          <span class="text-sm font-normal text-gray-600 ml-2">(All Records)</span>
        </h2>
        <button
          @click="toggleCompletedView"
          class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
        >
          {{ showCompletedView ? 'Hide' : 'Show' }}
        </button>
      </div>
      
      <div v-if="showCompletedView" class="overflow-x-auto">
        <div v-if="completedDisassemblies.length === 0" class="text-center py-8 text-gray-500">
          <svg class="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="text-lg font-semibold text-gray-600 mb-2">No Completed Disassemblies Found</p>
          <p class="text-sm text-gray-500">No completed disassembly records found in the system.</p>
          <p class="text-xs text-gray-400 mt-2">Create Goods Issue or Goods Receipt to see them here.</p>
        </div>
        <table v-else class="min-w-full divide-y divide-gray-200 border border-gray-300">
          <thead class="bg-green-100">
            <tr>
              <th class="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Production Order</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Type</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Date</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase">SAP DocNum</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Status</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Modified</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="item in completedDisassemblies" :key="item.name" class="hover:bg-green-50">
              <td class="px-4 py-2 text-sm text-gray-900">
                <div class="font-semibold">{{ item.production_order_docnum }}</div>
                <div class="text-xs text-gray-500" v-if="item.production_order_docentry">Entry: {{ item.production_order_docentry }}</div>
              </td>
              <td class="px-4 py-2 text-sm">
                <span :class="getTransactionTypeClass(item.transaction_type)" class="font-medium">
                  {{ getTransactionTypeLabel(item.transaction_type) }}
                </span>
              </td>
              <td class="px-4 py-2 text-sm text-gray-900">{{ formatDate(item.doc_date) }}</td>
              <td class="px-4 py-2 text-sm text-gray-900">
                <div v-if="item.sap_goods_receipt_docnum || item.sap_goods_issue_docnum" class="space-y-1">
                  <div v-if="item.sap_goods_receipt_docnum" class="text-green-700">
                    <span class="font-medium">📥 Receipt:</span> {{ item.sap_goods_receipt_docnum }}
                  </div>
                  <div v-if="item.sap_goods_issue_docnum" class="text-orange-700">
                    <span class="font-medium">📤 Issue:</span> {{ item.sap_goods_issue_docnum }}
                  </div>
                </div>
                <span v-else class="text-gray-400">-</span>
              </td>
              <td class="px-4 py-2 text-sm">
                <span :class="item.status === 'Success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'" class="px-2 py-1 rounded-full text-xs font-medium">
                  {{ item.status }}
                </span>
              </td>
              <td class="px-4 py-2 text-sm text-gray-600">{{ formatDateTime(item.modified) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Filter Section (shown after data is loaded) -->
    <div v-if="filteredData.length > 0 || allData.length > 0" class="bg-gray-50 rounded-lg border border-gray-300 p-4 mb-6">
      <div class="flex items-center gap-4">
        <label class="text-sm font-semibold text-gray-700">Filter by Movement Type:</label>
        <select
          v-model="movementTypeFilter"
          class="px-4 py-2 border-2 border-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-600 bg-white text-gray-900"
        >
          <option value="all">All Types</option>
          <option value="Goods Issue">Goods Issue</option>
          <option value="Goods Receipt">Goods Receipt</option>
        </select>
        <span class="text-sm text-gray-600">
          Showing {{ filteredData.length }} of {{ allData.length }} record(s)
        </span>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="bg-red-50 border-2 border-red-500 rounded-lg p-4 mb-6">
      <div class="flex items-start gap-3">
        <svg class="h-6 w-6 text-red-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <p class="font-semibold text-red-800">Error</p>
          <p class="text-red-700">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- Success Message -->
    <div v-if="successMessage && !error" class="bg-green-50 border-2 border-green-500 rounded-lg p-4 mb-6">
      <div class="flex items-center gap-3">
        <svg class="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        <p class="font-semibold text-green-800">{{ successMessage }}</p>
      </div>
    </div>

    <!-- Results Table -->
    <div v-if="filteredData.length > 0" class="bg-white rounded-lg border-2 border-gray-300 overflow-hidden mb-6">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-100">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Movement Type
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Item Code
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Quantity
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Batch Number
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Batch Qty
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Per Batch Cost
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-300">
                Ref Doc Num
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Ref Doc Date
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="(row, index) in filteredData"
              :key="index"
              :class="row.MovementType === 'Goods Issue' ? 'bg-red-50 hover:bg-red-100' : 'bg-green-50 hover:bg-green-100'"
              class="transition-colors"
            >
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium border-r border-gray-200">
                <span
                  :class="row.MovementType === 'Goods Issue' ? 'text-red-700' : 'text-green-700'"
                  class="inline-flex items-center gap-1"
                >
                  {{ row.MovementType === 'Goods Issue' ? '📤' : '📥' }}
                  {{ row.MovementType }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
                {{ row.ItemCode || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
                {{ formatNumber(row.Quantity) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
                {{ row.BatchNum || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
                {{ formatNumber(row.BatchQty) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
                {{ formatCurrency(row.PerBatchCost) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
                {{ row.RefDocNum || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ formatDate(row.RefDocDate) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Reverse Transaction Form Section -->
    <div v-if="allData.length > 0" class="bg-white rounded-lg border-2 border-purple-300 p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-semibold text-gray-900">🔄 Create Reverse Transaction</h2>
        <button
          @click="performFullDisassembly"
          :disabled="disassemblyLoading || goodsIssueLoading || goodsReceiptLoading || !reverseForm.docDate || !docNum || (goodsReceiptItems.length === 0 && goodsIssueItems.length === 0)"
          class="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:from-purple-700 hover:to-pink-700 transition-all font-bold disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg hover:shadow-xl transform hover:scale-105 relative overflow-hidden"
          type="button"
        >
          <span v-if="disassemblyLoading" class="absolute inset-0 bg-white opacity-20 animate-pulse"></span>
          <svg v-if="disassemblyLoading" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span v-if="disassemblyLoading">{{ disassemblyStep }}...</span>
          <span v-else>🚀 Click to Disassemble</span>
        </button>
      </div>
      
      <!-- Date Field -->
      <div class="mb-6">
        <label class="block text-sm font-semibold text-gray-700 mb-2">Document Date</label>
        <input
          v-model="reverseForm.docDate"
          type="date"
          class="px-4 py-2 border-2 border-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-blue-600"
        />
      </div>
      
      <!-- Goods Issue Creation from Goods Receipt -->
      <div v-if="goodsReceiptItems.length > 0" class="mb-6 pb-6 border-b border-gray-300">
        <h3 class="text-lg font-semibold text-blue-700 mb-3">📤 Create Goods Issue from Receipt Items</h3>
        
        <!-- Goods Receipt Items Table -->
        <div class="mb-4 overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200 border border-gray-300">
            <thead class="bg-green-100">
              <tr>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Item Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Warehouse Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Account Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Production Order DocEntry</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Quantity</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Batch Number</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Unit Cost</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Total Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(item, idx) in goodsReceiptItems" :key="idx" class="hover:bg-gray-50">
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.ItemCode }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.WarehouseCode || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.AccountCode || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.ProdOrderEntry || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ formatNumber(item.Quantity) }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.BatchNum || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ formatCurrency(item.PerBatchCost) }}</span></td>
                <td class="px-4 py-2 text-sm font-semibold"><span class="text-blue-600">{{ formatCurrency(calculateItemValue(item)) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <button
          @click.stop="createGoodsIssueFromReceipt"
          :disabled="goodsIssueLoading || goodsReceiptLoading || !reverseForm.docDate || !docNum"
          class="px-6 py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
          type="button"
        >
          <svg v-if="goodsIssueLoading" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>{{ goodsIssueLoading ? 'Processing...' : '📤 Create Goods Issue' }}</span>
        </button>

        <!-- SAP Response Display for Goods Issue -->
        <div v-if="sapGoodsIssueResponse" class="mt-6 bg-blue-50 border-2 border-blue-500 rounded-lg p-6 shadow-lg">
          <div class="flex items-center justify-between mb-4">
            <h4 class="text-xl font-bold text-blue-800 flex items-center gap-2">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              SAP B1 Response - Goods Issue
            </h4>
            <button 
              @click="sapGoodsIssueResponse = null" 
              class="text-blue-600 hover:text-blue-800 font-semibold"
              title="Close"
            >
              ✕
            </button>
          </div>
          <div class="bg-white rounded-lg p-4 border-2 border-blue-300 overflow-x-auto max-h-96 overflow-y-auto">
            <pre class="text-sm text-gray-800 font-mono whitespace-pre-wrap">{{ JSON.stringify(sapGoodsIssueResponse, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <!-- Goods Receipt Creation from Goods Issue -->
      <div v-if="goodsIssueItems.length > 0">
        <h3 class="text-lg font-semibold text-green-700 mb-3">📥 Create Goods Receipt from Issue Items</h3>
        
        <!-- Goods Issue Items Table -->
        <div class="mb-4 overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200 border border-gray-300">
            <thead class="bg-red-100">
              <tr>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Item Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Quantity</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Batch Number</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Warehouse Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Account Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Production Order DocEntry</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Location Code</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Unit Cost</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Total Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(item, idx) in goodsIssueItems" :key="idx" class="hover:bg-gray-50">
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.ItemCode }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ formatNumber(item.Quantity) }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.BatchNum || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.WarehouseCode || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.AccountCode || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.ProdOrderEntry || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ item.LocationCode || '-' }}</span></td>
                <td class="px-4 py-2 text-sm"><span class="text-blue-600">{{ formatCurrency(item.PerBatchCost) }}</span></td>
                <td class="px-4 py-2 text-sm font-semibold"><span class="text-blue-600">{{ formatCurrency(calculateItemValue(item)) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <button
          @click.stop="createGoodsReceiptFromIssue"
          :disabled="goodsReceiptLoading || goodsIssueLoading || !reverseForm.docDate || !docNum"
          class="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
          type="button"
        >
          <svg v-if="goodsReceiptLoading" class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span class="text-blue-600">{{ goodsReceiptLoading ? 'Processing...' : '📥 Create Goods Receipt' }}</span>
        </button>

        <!-- SAP Response Display for Goods Receipt -->
        <div v-if="sapGoodsReceiptResponse" class="mt-6 bg-green-50 border-2 border-green-500 rounded-lg p-6 shadow-lg">
          <div class="flex items-center justify-between mb-4">
            <h4 class="text-xl font-bold text-green-800 flex items-center gap-2">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              SAP B1 Response - Goods Receipt
            </h4>
            <button 
              @click="sapGoodsReceiptResponse = null" 
              class="text-green-600 hover:text-green-800 font-semibold"
              title="Close"
            >
              ✕
            </button>
          </div>
          <div class="bg-white rounded-lg p-4 border-2 border-green-300 overflow-x-auto max-h-96 overflow-y-auto">
            <pre class="text-sm text-gray-800 font-mono whitespace-pre-wrap">{{ JSON.stringify(sapGoodsReceiptResponse, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Success Animation Overlay -->
    <div v-if="showSuccessAnimation" class="success-blast">
      <div class="success-text">🎉</div>
      <div class="particle"></div>
      <div class="particle"></div>
      <div class="particle"></div>
      <div class="particle"></div>
      <div class="particle"></div>
      <div class="particle"></div>
      <div class="particle"></div>
      <div class="particle"></div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && allData.length === 0 && docNum && !error" class="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-8 text-center">
      <svg class="mx-auto h-12 w-12 text-yellow-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p class="text-lg font-semibold text-yellow-800 mb-2">No Data Found</p>
      <p class="text-yellow-700">No disassembly details found for Production Order DocNum: <strong>{{ docNum }}</strong></p>
    </div>

  </div>
</template>



<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import nandi_hillsDisassemblyService from '../../../core/api/plants/nandi_hills/disassembly'

const router = useRouter()

// Reactive state
const docNum = ref(null)
const loading = ref(false)
const error = ref(null)
const successMessage = ref(null)
const allData = ref([])
const movementTypeFilter = ref('all')
const sapGoodsIssueResponse = ref(null)
const sapGoodsReceiptResponse = ref(null)
const goodsIssueLoading = ref(false)
const goodsReceiptLoading = ref(false)
const completedDisassemblies = ref([])
const showCompletedView = ref(true)
const loadingAllDisassemblies = ref(false)
const showAllRecords = ref(false)
const disassemblyLoading = ref(false)
const disassemblyStep = ref('')
const showSuccessAnimation = ref(false)
const disassemblyStartTime = ref(null)
const disassemblyDuration = ref(null)

// Reverse transaction form
const reverseForm = ref({
  productionOrderEntry: null,
  docDate: new Date().toISOString().split('T')[0] // Current date in YYYY-MM-DD format
})

// Computed: Filter data based on movement type
const filteredData = computed(() => {
  if (movementTypeFilter.value === 'all') {
    return allData.value
  }
  return allData.value.filter(row => row.MovementType === movementTypeFilter.value)
})

// Computed: Separate Goods Issue and Goods Receipt items
const goodsIssueItems = computed(() => {
  return allData.value.filter(row => row.MovementType === 'Goods Issue')
})

const goodsReceiptItems = computed(() => {
  return allData.value.filter(row => row.MovementType === 'Goods Receipt')
})

// Computed: Calculate total consumed value from Goods Receipt items
const totalConsumedValue = computed(() => {
  let total = 0
  goodsReceiptItems.value.forEach(item => {
    const quantity = parseFloat(item.Quantity) || 0
    const unitCost = parseFloat(item.PerBatchCost) || 0
    total += quantity * unitCost
  })
  return total
})

// Computed: Calculate total quantity for Goods Issue items
const goodsIssueTotalQty = computed(() => {
  let total = 0
  goodsIssueItems.value.forEach(item => {
    total += parseFloat(item.Quantity) || 0
  })
  return total
})

// Computed: Calculate unit price for Goods Issue items
const calculatedUnitPrice = computed(() => {
  if (goodsIssueTotalQty.value === 0) return 0
  return totalConsumedValue.value / goodsIssueTotalQty.value
})

// Methods
const fetchDetails = async () => {
  if (!docNum.value) {
    error.value = 'Please enter a Production Order Document Number'
    return
  }

  loading.value = true
  error.value = null
  successMessage.value = null
  allData.value = []

  try {
    const response = await nandi_hillsDisassemblyService.getDisassemblyDetails(docNum.value)
    
    if (response.status === 'success') {
      allData.value = response.data || []
      if (allData.value.length > 0) {
        successMessage.value = `Successfully fetched ${allData.value.length} record(s)`
        movementTypeFilter.value = 'all'
        // Auto-populate production order entry from first record
        if (allData.value[0] && allData.value[0].ProdOrderEntry) {
          reverseForm.value.productionOrderEntry = parseInt(allData.value[0].ProdOrderEntry)
        }
      } else {
        error.value = `No disassembly details found for Production Order DocNum: ${docNum.value}`
      }
    } else {
      error.value = response.message || 'Failed to fetch disassembly details'
    }
  } catch (err) {
    error.value = err.message || 'An unexpected error occurred while fetching data'
    console.error('Error fetching disassembly details:', err)
  } finally {
    loading.value = false
  }
}

const toggleCompletedView = () => {
  showCompletedView.value = !showCompletedView.value
}


// Fetch all Disassembly records (without filtering by production order)
const fetchAllDisassemblies = async () => {
  loadingAllDisassemblies.value = true
  showAllRecords.value = true
  try {
    const filters = { limit: 100 } // Get more records when showing all
    // Don't filter by production_order_docnum - get all records
    const response = await nandi_hillsDisassemblyService.getCompletedDisassemblies(filters)
    console.log('All disassemblies response:', response)
    if (response.status === 'success') {
      completedDisassemblies.value = response.data || []
      console.log('All disassemblies count:', completedDisassemblies.value.length)
    } else {
      console.error('Failed to fetch all disassemblies:', response.message)
      completedDisassemblies.value = []
    }
  } catch (err) {
    console.error('Error fetching all disassemblies:', err)
    completedDisassemblies.value = []
  } finally {
    loadingAllDisassemblies.value = false
  }
}

const fetchCompletedDisassemblies = async (productionOrderDocNum = null) => {
  try {
    const filters = { limit: 50 }
    // Filter by production order docnum if provided - convert to string to match database
    if (productionOrderDocNum) {
      filters.production_order_docnum = String(productionOrderDocNum)
    }
    console.log('Fetching completed disassemblies with filters:', filters)
    const response = await nandi_hillsDisassemblyService.getCompletedDisassemblies(filters)
    console.log('Completed disassemblies response:', response)
    if (response.status === 'success') {
      completedDisassemblies.value = response.data || []
      console.log('Completed disassemblies count:', completedDisassemblies.value.length)
    } else {
      console.error('Failed to fetch completed disassemblies:', response.message)
      completedDisassemblies.value = []
    }
  } catch (err) {
    console.error('Error fetching completed disassemblies:', err)
    completedDisassemblies.value = []
  }
}

// Calculate item value
const calculateItemValue = (item) => {
  const quantity = parseFloat(item.Quantity) || 0
  const unitCost = parseFloat(item.PerBatchCost) || 0
  return quantity * unitCost
}

// Create Goods Issue from Receipt Items
const createGoodsIssueFromReceipt = async () => {
  if (!reverseForm.value.docDate) {
    error.value = 'Please select a document date'
    return
  }

  if (!docNum.value) {
    error.value = 'Production Order Document Number is required'
    return
  }

  goodsIssueLoading.value = true
  error.value = null
  successMessage.value = null
  sapGoodsIssueResponse.value = null

  try {
    // Construct document lines from Goods Receipt items (matching table format)
    // Use values directly from database tables, no hardcoding
    const documentLines = goodsReceiptItems.value.map(item => ({
      ItemCode: item.ItemCode,
      WarehouseCode: item.WarehouseCode,
      AccountCode: item.AccountCode,
      ProductionOrderDocEntry: item.ProdOrderEntry,
      Quantity: parseFloat(item.Quantity) || 0,
      BatchNumber: item.BatchNum || '-',
      UnitCost: parseFloat(item.PerBatchCost) || 0,
      TotalValue: calculateItemValue(item)
    }))

    const payload = {
      doc_date: reverseForm.value.docDate,
      production_order_docnum: String(docNum.value),
      production_order_docentry: reverseForm.value.productionOrderEntry,
      document_lines: documentLines
    }

    const response = await nandi_hillsDisassemblyService.createGoodsIssue(payload)

    if (response.status === 'success') {
      successMessage.value = `Goods Issue created successfully! DocNum: ${response.doc_num || 'N/A'}`
      // Store SAP response for display
      sapGoodsIssueResponse.value = response.data || response
      // Refresh completed disassemblies list for this production order immediately and after delay
      fetchCompletedDisassemblies(docNum.value)
      setTimeout(() => {
        fetchCompletedDisassemblies(docNum.value)
      }, 1500)
    } else {
      error.value = response.message || 'Failed to create Goods Issue'
      // Store error response if available
      sapGoodsIssueResponse.value = response.data || response
    }
  } catch (err) {
    error.value = err.message || 'An unexpected error occurred while creating Goods Issue'
    console.error('Error creating Goods Issue:', err)
  } finally {
    goodsIssueLoading.value = false
  }
}

// Perform Full Disassembly (Both Goods Issue and Goods Receipt)
const performFullDisassembly = async () => {
  if (!reverseForm.value.docDate) {
    error.value = 'Please select a document date'
    return
  }

  if (!docNum.value) {
    error.value = 'Production Order Document Number is required'
    return
  }

  // Check if we have items to process
  if (goodsReceiptItems.value.length === 0 && goodsIssueItems.value.length === 0) {
    error.value = 'No items available for disassembly'
    return
  }

  disassemblyLoading.value = true
  disassemblyStartTime.value = Date.now()
  error.value = null
  successMessage.value = null
  sapGoodsIssueResponse.value = null
  sapGoodsReceiptResponse.value = null
  showSuccessAnimation.value = false

  try {
    let goodsIssueSuccess = false
    let goodsReceiptSuccess = false
    const results = {
      goodsIssue: null,
      goodsReceipt: null
    }

    // Step 1: Create Goods Issue (if Goods Receipt items exist)
    if (goodsReceiptItems.value.length > 0) {
      disassemblyStep.value = 'Creating Goods Issue'
      
      const documentLines = goodsReceiptItems.value.map(item => ({
        ItemCode: item.ItemCode,
        WarehouseCode: item.WarehouseCode,
        AccountCode: item.AccountCode,
        ProductionOrderDocEntry: item.ProdOrderEntry,
        Quantity: parseFloat(item.Quantity) || 0,
        BatchNumber: item.BatchNum || '-',
        UnitCost: parseFloat(item.PerBatchCost) || 0,
        TotalValue: calculateItemValue(item)
      }))

      const issuePayload = {
        doc_date: reverseForm.value.docDate,
        production_order_docnum: String(docNum.value),
        production_order_docentry: reverseForm.value.productionOrderEntry,
        document_lines: documentLines
      }

      const issueResponse = await nandi_hillsDisassemblyService.createGoodsIssue(issuePayload)
      results.goodsIssue = issueResponse
      sapGoodsIssueResponse.value = issueResponse.data || issueResponse

      if (issueResponse.status === 'success') {
        goodsIssueSuccess = true
        disassemblyStep.value = 'Goods Issue Created ✓'
        await new Promise(resolve => setTimeout(resolve, 500)) // Small delay for UX
      } else {
        throw new Error(`Goods Issue failed: ${issueResponse.message || 'Unknown error'}`)
      }
    } else {
      goodsIssueSuccess = true // Skip if no items
    }

    // Step 2: Create Goods Receipt (only if Goods Issue succeeded and Goods Issue items exist)
    if (goodsIssueSuccess && goodsIssueItems.value.length > 0) {
      disassemblyStep.value = 'Creating Goods Receipt'
      
      const documentLines = goodsIssueItems.value.map(item => ({
        ItemCode: item.ItemCode,
        WarehouseCode: item.WarehouseCode,
        AccountCode: item.AccountCode,
        ProductionOrderDocEntry: item.ProdOrderEntry,
        Quantity: parseFloat(item.Quantity) || 0,
        BatchNumber: item.BatchNum || '-',
        LocationCode: item.LocationCode,
        UnitCost: parseFloat(item.PerBatchCost) || 0,
        TotalValue: calculateItemValue(item)
      }))

      const receiptPayload = {
        doc_date: reverseForm.value.docDate,
        production_order_docnum: String(docNum.value),
        production_order_docentry: reverseForm.value.productionOrderEntry,
        document_lines: documentLines
      }

      const receiptResponse = await nandi_hillsDisassemblyService.createGoodsReceipt(receiptPayload)
      results.goodsReceipt = receiptResponse
      sapGoodsReceiptResponse.value = receiptResponse.data || receiptResponse

      if (receiptResponse.status === 'success') {
        goodsReceiptSuccess = true
        disassemblyStep.value = 'Goods Receipt Created ✓'
      } else {
        throw new Error(`Goods Receipt failed: ${receiptResponse.message || 'Unknown error'}`)
      }
    } else if (goodsIssueSuccess) {
      goodsReceiptSuccess = true // Skip if no items
    }

    // Calculate duration
    disassemblyDuration.value = ((Date.now() - disassemblyStartTime.value) / 1000).toFixed(2)

    // Success!
    if (goodsIssueSuccess && goodsReceiptSuccess) {
      disassemblyStep.value = 'Disassembly Complete! 🎉'
      
      // Show success animation
      showSuccessAnimation.value = true
      
      // Build success message
      const parts = []
      if (results.goodsIssue?.doc_num) {
        parts.push(`Issue: ${results.goodsIssue.doc_num}`)
      }
      if (results.goodsReceipt?.doc_num) {
        parts.push(`Receipt: ${results.goodsReceipt.doc_num}`)
      }
      successMessage.value = `✅ Disassembly completed successfully! ${parts.join(' | ')} (${disassemblyDuration.value}s)`
      
      // Refresh completed disassemblies
      fetchCompletedDisassemblies(docNum.value)
      setTimeout(() => {
        fetchCompletedDisassemblies(docNum.value)
      }, 1500)
      
      // Hide animation after 3 seconds
      setTimeout(() => {
        showSuccessAnimation.value = false
        disassemblyStep.value = ''
      }, 3000)
    }

  } catch (err) {
    error.value = err.message || 'An unexpected error occurred during disassembly'
    console.error('Error performing full disassembly:', err)
    disassemblyStep.value = 'Error occurred'
  } finally {
    // Keep loading state for a moment to show final status
    setTimeout(() => {
      disassemblyLoading.value = false
      disassemblyStep.value = ''
    }, 2000)
  }
}

// Create Goods Receipt from Issue Items
const createGoodsReceiptFromIssue = async () => {
  if (!reverseForm.value.docDate) {
    error.value = 'Please select a document date'
    return
  }

  if (!docNum.value) {
    error.value = 'Production Order Document Number is required'
    return
  }

  goodsReceiptLoading.value = true
  error.value = null
  successMessage.value = null
  sapGoodsReceiptResponse.value = null

  try {
    // Construct document lines from Goods Issue items (matching table format)
    // Use values directly from database tables, no hardcoding
    const documentLines = goodsIssueItems.value.map(item => ({
      ItemCode: item.ItemCode,
      WarehouseCode: item.WarehouseCode,
      AccountCode: item.AccountCode,
      ProductionOrderDocEntry: item.ProdOrderEntry,
      Quantity: parseFloat(item.Quantity) || 0,
      BatchNumber: item.BatchNum || '-',
      LocationCode: item.LocationCode,
      UnitCost: parseFloat(item.PerBatchCost) || 0,
      TotalValue: calculateItemValue(item)
    }))

    const payload = {
      doc_date: reverseForm.value.docDate,
      production_order_docnum: String(docNum.value),
      production_order_docentry: reverseForm.value.productionOrderEntry,
      document_lines: documentLines
    }

    const response = await nandi_hillsDisassemblyService.createGoodsReceipt(payload)

    if (response.status === 'success') {
      successMessage.value = `Goods Receipt created successfully! DocNum: ${response.doc_num || 'N/A'}`
      // Store SAP response for display
      sapGoodsReceiptResponse.value = response.data || response
      // Refresh completed disassemblies list for this production order immediately and after delay
      fetchCompletedDisassemblies(docNum.value)
      setTimeout(() => {
        fetchCompletedDisassemblies(docNum.value)
      }, 1500)
    } else {
      error.value = response.message || 'Failed to create Goods Receipt'
      // Store error response if available
      sapGoodsReceiptResponse.value = response.data || response
    }
  } catch (err) {
    error.value = err.message || 'An unexpected error occurred while creating Goods Receipt'
    console.error('Error creating Goods Receipt:', err)
  } finally {
    goodsReceiptLoading.value = false
  }
}

const formatNumber = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  const num = parseFloat(value)
  return isNaN(num) ? '-' : num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatCurrency = (value) => {
  if (value === null || value === undefined || value === '' || value === '0') return '-'
  const num = parseFloat(value)
  return isNaN(num) ? '-' : `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const getTransactionTypeLabel = (type) => {
  if (type === 'Both') return '📥 Receipt & 📤 Issue'
  if (type === 'Goods Issue') return '📤 Issue'
  if (type === 'Goods Receipt') return '📥 Receipt'
  return type || '-'
}

const getTransactionTypeClass = (type) => {
  if (type === 'Both') return 'text-purple-600'
  if (type === 'Goods Issue') return 'text-orange-600'
  if (type === 'Goods Receipt') return 'text-green-600'
  return 'text-gray-600'
}

const formatDate = (value) => {
  if (!value) return '-'
  try {
    const date = new Date(value)
    if (isNaN(date.getTime())) return value
    return date.toLocaleDateString('en-IN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return value
  }
}

const formatDateTime = (value) => {
  if (!value) return '-'
  try {
    const date = new Date(value)
    if (isNaN(date.getTime())) return value
    return date.toLocaleString('en-IN', { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return value
  }
}


// Lifecycle
onMounted(() => {
  // Don't load completed disassemblies on mount - only show when user enters a production order docnum
  // fetchCompletedDisassemblies()
})
</script>

<style scoped>
/* Additional component-specific styles can be added here */

/* Success Animation - Bomb Blast Effect */
@keyframes bombBlast {
  0% {
    transform: translate(-50%, -50%) scale(0);
    opacity: 0;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.5);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(2);
    opacity: 0;
  }
}

@keyframes particle {
  0% {
    transform: translate(0, 0) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(var(--tx), var(--ty)) scale(0);
    opacity: 0;
  }
}

.success-blast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 9999;
  pointer-events: none;
}

.success-blast::before,
.success-blast::after {
  content: '';
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255,215,0,0.8) 0%, rgba(255,165,0,0.6) 50%, transparent 100%);
  animation: bombBlast 1s ease-out forwards;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.success-blast::after {
  animation-delay: 0.1s;
  width: 300px;
  height: 300px;
}

.particle {
  position: absolute;
  width: 10px;
  height: 10px;
  background: radial-gradient(circle, #FFD700, #FFA500);
  border-radius: 50%;
  animation: particle 1.5s ease-out forwards;
  top: 50%;
  left: 50%;
}

.particle:nth-child(1) { --tx: 100px; --ty: -50px; animation-delay: 0s; }
.particle:nth-child(2) { --tx: -100px; --ty: -50px; animation-delay: 0.1s; }
.particle:nth-child(3) { --tx: 50px; --ty: 100px; animation-delay: 0.2s; }
.particle:nth-child(4) { --tx: -50px; --ty: 100px; animation-delay: 0.3s; }
.particle:nth-child(5) { --tx: 150px; --ty: 50px; animation-delay: 0.1s; }
.particle:nth-child(6) { --tx: -150px; --ty: 50px; animation-delay: 0.2s; }
.particle:nth-child(7) { --tx: 80px; --ty: -100px; animation-delay: 0.15s; }
.particle:nth-child(8) { --tx: -80px; --ty: -100px; animation-delay: 0.25s; }

.success-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 4rem;
  font-weight: bold;
  color: #FFD700;
  text-shadow: 
    0 0 10px rgba(255, 215, 0, 0.8),
    0 0 20px rgba(255, 165, 0, 0.6),
    0 0 30px rgba(255, 140, 0, 0.4),
    0 0 40px rgba(255, 215, 0, 0.3);
  animation: bombBlast 1s ease-out forwards;
  z-index: 10000;
  filter: drop-shadow(0 0 20px rgba(255, 215, 0, 0.8));
}
</style>

