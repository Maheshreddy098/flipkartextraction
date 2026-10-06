<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Inventory Reports</h1>
      <button
        @click="refreshAll"
        :disabled="isLoading"
        class="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ isLoading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <!-- Report catalog -->
    <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
      <div class="flex items-center justify-between gap-4 mb-3">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">
            Report Catalog <span class="text-gray-500 font-medium">({{ catalogCount }})</span>
          </h2>
          <p class="text-xs text-gray-600">Search and select a report to load.</p>
        </div>
        <div class="w-full max-w-md">
          <input
            v-model="catalogSearch"
            type="text"
            placeholder="Search reports…"
            class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <div v-if="catalogError" class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">
        Failed to load report catalog: {{ catalogError }}
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <button
          v-for="r in filteredCatalog"
          :key="r.id"
          @click="selectReport(r)"
          :class="[
            'text-left border rounded-lg p-3 bg-white hover:bg-gray-50 transition-colors',
            activeReportId === r.id ? 'ring-2 ring-blue-500 border-blue-200' : ''
          ]"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="font-semibold text-gray-900">{{ r.name }}</div>
            <div class="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">{{ r.category }}</div>
          </div>
          <div class="text-xs text-gray-600 mt-1">{{ r.description }}</div>
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3">
        <div class="lg:col-span-2">
          <label class="block text-xs font-semibold text-gray-600 mb-1">Search (ItemCode / ItemName)</label>
          <input
            v-model="filters.search"
            type="text"
            placeholder="e.g. RMHN0051"
            class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label class="block text-xs font-semibold text-gray-600 mb-1">Warehouse Code</label>
          <input
            v-model="filters.warehouse_code"
            type="text"
            placeholder="e.g. EC-FG"
            class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <div class="mt-3 flex gap-2">
        <button
          @click="refreshAll"
          :disabled="isLoading || !activeReportId"
          class="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Apply
        </button>
        <button
          @click="clearFilters"
          class="px-3 py-2 bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 text-sm font-semibold"
        >
          Reset All
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="errorMessage" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ errorMessage }}</p>
    </div>

    <div v-if="!activeReportId" class="bg-white border rounded-lg shadow-sm p-6 text-gray-700">
      Select a report from the catalog above to load and display it.
    </div>

    <template v-else>
      <div class="bg-white border rounded-lg shadow-sm p-4 mb-6 flex items-start justify-between gap-4">
        <div class="min-w-0">
          <h2 class="text-xl font-semibold text-gray-900 truncate">{{ activeReport?.name || 'Report' }}</h2>
          <p class="text-xs text-gray-600 mt-1">{{ activeReport?.description || '' }}</p>
        </div>
        <button
          @click="clearSelection"
          class="px-3 py-2 bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 text-sm font-semibold flex-shrink-0"
        >
          Change report
        </button>
      </div>

      <!-- OVERVIEW -->
      <div v-if="activeReportId === 'overview'">
        <p class="text-xs text-gray-600 mb-3">{{ asOfText }}</p>
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <label class="block text-xs font-semibold text-gray-600 mb-1">Low Stock Threshold</label>
          <div class="flex flex-wrap items-end gap-2">
            <input
              v-model.number="filters.low_stock_threshold"
              type="number"
              min="0"
              step="1"
              class="w-full max-w-xs px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="refreshAll"
            >
              Apply
            </button>
            <button
              class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="filters.low_stock_threshold = 10"
            >
              Reset
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">SKUs With Stock</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(summaryMetrics.total_skus_with_stock) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">On-Hand Quantity</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(summaryMetrics.total_onhand_qty) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Stock Value (AvgPrice)</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatCurrency(summaryMetrics.total_stock_value) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">
              Low Stock SKUs (&lt; {{ formatNumber(summaryMetrics.low_stock_threshold) }})
            </p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(summaryMetrics.low_stock_skus) }}</p>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Stock Value by Warehouse</h3>
            <canvas ref="warehouseValueChartEl" style="height: 260px; max-height: 260px;"></canvas>
            <p class="text-xs text-gray-500 mt-2">Click legend to toggle. Hover for values.</p>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Stock Health (SKUs)</h3>
            <canvas ref="overviewStockHealthChartEl" style="height: 260px; max-height: 260px;"></canvas>
            <p class="text-xs text-gray-500 mt-2">Low stock = below threshold. Interactive legend.</p>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Top Items by Stock Value</h3>
            <canvas ref="topItemsValueChartEl" style="height: 260px; max-height: 260px;"></canvas>
            <p class="text-xs text-gray-500 mt-2">Hover for exact values.</p>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4 mt-6">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Top Items</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">OnHand</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Value</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in topItemsRows" :key="row.item_code" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatNumber(row.onhand_qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatCurrency(row.stock_value) }}</td>
                </tr>
                <tr v-if="!isLoading && topItemsRows.length === 0">
                  <td colspan="3" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- WAREHOUSE VALUE -->
      <div v-else-if="activeReportId === 'warehouse_value'">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Stock Value by Warehouse</h3>
            <canvas ref="warehouseValueChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">On-hand Qty by Warehouse</h3>
            <canvas ref="warehouseQtyChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Warehouses</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">SKUs</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Value</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="w in warehouseRes.data?.warehouses || []" :key="w.whscode" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ w.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ w.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatInt(w.sku_count) }}</td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatNumber(w.onhand_qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatCurrency(w.stock_value) }}</td>
                </tr>
                <tr v-if="!isLoading && (!warehouseRes.data?.warehouses || warehouseRes.data.warehouses.length === 0)">
                  <td colspan="4" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TOP ITEMS -->
      <div v-else-if="activeReportId === 'top_items'">
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <label class="block text-xs font-semibold text-gray-600 mb-1">Top Items Limit</label>
          <div class="flex flex-wrap items-end gap-2">
            <select
              v-model.number="topItemsLimit"
              class="w-full max-w-xs px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option :value="10">Top 10</option>
              <option :value="20">Top 20</option>
              <option :value="50">Top 50</option>
            </select>
            <button
              class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="refreshAll"
            >
              Apply
            </button>
            <button
              class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="topItemsLimit = 10"
            >
              Reset
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Top Items by Stock Value</h3>
            <canvas ref="topItemsValueChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Top Items Share (vs Rest)</h3>
            <canvas ref="topItemsShareChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Top Items</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">OnHand</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Value</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in topItemsRows" :key="row.item_code" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatNumber(row.onhand_qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatCurrency(row.stock_value) }}</td>
                </tr>
                <tr v-if="!isLoading && topItemsRows.length === 0">
                  <td colspan="3" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- WAREHOUSE BATCH STOCK -->
      <div v-else-if="activeReportId === 'warehouse_batches'">
        <p class="text-xs text-gray-600 mb-3">
          {{ asOfText }} · {{ expiryWindowText }}<span v-if="batchIncludeExpired"> · including expired</span>
        </p>
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Limit</label>
              <select
                v-model.number="batchStockLimit"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
                <option :value="1000">1000</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Min Qty</label>
              <input
                v-model.number="batchMinQty"
                type="number"
                min="0"
                step="0.01"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div class="md:col-span-2 lg:col-span-2 flex items-end">
              <label class="inline-flex items-center gap-2 text-sm text-gray-800">
                <input v-model="batchIncludeExpired" type="checkbox" class="h-4 w-4" />
                Include expired batches
              </label>
            </div>
            <div class="md:col-span-3 lg:col-span-2 flex items-end">
              <div class="text-xs text-gray-600">
                Tip: set <b>Warehouse Code</b> filter above to avoid huge result sets.
              </div>
            </div>
          </div>
          <div class="mt-3 flex gap-2">
            <button
              class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="refreshAll"
            >
              Apply
            </button>
            <button
              class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="batchStockLimit = 200; batchMinQty = 0; batchIncludeExpired = false; expiryDays = 90"
            >
              Reset
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Batch Qty by Warehouse</h3>
            <canvas ref="warehouseBatchTotalsChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-base font-semibold text-gray-900">Expiry Buckets (Qty)</h3>
              <select
                v-model.number="expiryDays"
                class="px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="30">30 days</option>
                <option :value="60">60 days</option>
                <option :value="90">90 days</option>
                <option :value="180">180 days</option>
              </select>
            </div>
            <canvas ref="warehouseBatchExpiryChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Warehouse Batch Stock</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Batch</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Mfg</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Exp</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Remaining</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in warehouseBatchRows" :key="`${row.whscode}-${row.item_code}-${row.batch_number}-${row.exp_date}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ row.whsname }}</div>
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-900 font-semibold">{{ row.batch_number || '-' }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ row.mnf_date || '-' }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ row.exp_date || '-' }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(row.qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-800">
                    {{ row.remaining_days != null ? `${row.remaining_days}d` : '-' }}
                  </td>
                </tr>
                <tr v-if="!isLoading && warehouseBatchRows.length === 0">
                  <td colspan="7" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- PROCUREMENT TRACEABILITY -->
      <div v-else-if="activeReportId === 'procurement_trace'">
        <p class="text-xs text-gray-600 mb-3">{{ procurementAppliedRangeText }}</p>
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3">
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">From Date</label>
              <input
                v-model="procurementDateFrom"
                type="date"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">To Date</label>
              <input
                v-model="procurementDateTo"
                type="date"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div class="lg:col-span-2">
              <label class="block text-xs font-semibold text-gray-600 mb-1">Vendor Code</label>
              <input
                v-model="procurementVendorCode"
                type="text"
                placeholder="e.g. V000123"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Material Type</label>
              <select
                v-model="procurementMaterialType"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All</option>
                <option value="RM">RM (Raw Material)</option>
                <option value="PM">PM (Packaging Material)</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Limit</label>
              <select
                v-model.number="procurementLimit"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
              </select>
            </div>
            <div class="flex items-end justify-end gap-2">
              <button
                class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="refreshProcurement(true)"
              >
                Apply
              </button>
              <button
                class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="procurementDateFrom = ''; procurementDateTo = ''; procurementVendorCode = ''; procurementMaterialType = ''; procurementLimit = 200; procurementOffset = 0"
              >
                Reset
              </button>
            </div>
          </div>
          <div class="mt-2 text-xs text-gray-600">
            Uses GRPO (OPDN/PDN1) + batch transactions to show vendor → warehouse → item → batch.
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">GRPO Count</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(procurementTotals.grpo_count) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">SKUs Procured</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(procurementTotals.sku_count) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Total Qty</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(procurementTotals.qty) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Total Value</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatCurrency(procurementTotals.value) }}</p>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Procurement Value by Vendor (Top)</h3>
            <canvas ref="procurementVendorChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Procurement Qty by Warehouse</h3>
            <canvas ref="procurementWarehouseChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4 mb-6">
          <h3 class="text-base font-semibold text-gray-900 mb-3">RM vs PM (Value Split)</h3>
          <canvas ref="procurementMaterialTypeChartEl" style="height: 240px; max-height: 240px;"></canvas>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Procurement Traceability (GRPO)</h3>
          <div class="flex items-center justify-between gap-4 mb-3">
            <label class="inline-flex items-center gap-2 text-sm text-gray-800">
              <input v-model="procurementGroupByVendor" type="checkbox" class="h-4 w-4" />
              Group by vendor
            </label>
            <div class="flex items-center gap-2">
              <button
                class="px-3 py-1.5 text-sm font-semibold bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="procurementOffset === 0 || isLoading"
                @click="procurementPrevPage"
              >
                Prev
              </button>
              <div class="text-sm text-gray-700">
                Offset: {{ procurementOffset }}
              </div>
              <button
                class="px-3 py-1.5 text-sm font-semibold bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="!procurementHasMore || isLoading"
                @click="procurementNextPage"
              >
                Next
              </button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <!-- Grouped view -->
            <div v-if="procurementGroupByVendor">
              <div v-for="g in procurementGrouped" :key="g.vendor_code" class="border rounded-lg mb-3">
                <button
                  class="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100"
                  @click="toggleVendor(g.vendor_code)"
                >
                  <div class="text-left">
                    <div class="font-semibold text-gray-900">{{ g.vendor_code }} <span class="text-gray-600 font-normal">— {{ g.vendor_name }}</span></div>
                    <div class="text-xs text-gray-600">Rows: {{ g.rows.length }} | Qty: {{ formatNumber(g.qty) }} | Value: {{ formatCurrency(g.value) }}</div>
                  </div>
                  <div class="text-sm font-semibold text-gray-700">
                    {{ expandedVendors.has(g.vendor_code) ? 'Hide' : 'Show' }}
                  </div>
                </button>

                <div v-if="expandedVendors.has(g.vendor_code)" class="p-3">
                  <table class="min-w-full divide-y divide-gray-200 text-sm">
                    <thead class="bg-white">
                      <tr>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Date</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">GRPO</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Type</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Batch</th>
                        <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Batch Qty</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Mfg</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Exp</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                      <tr v-for="r in g.rows" :key="`${r.doc_num}-${r.item_code}-${r.batch_number}-${r.whscode}`" class="hover:bg-gray-50">
                        <td class="px-3 py-2 text-gray-800">{{ r.doc_date || '-' }}</td>
                        <td class="px-3 py-2 text-gray-900 font-semibold">{{ r.doc_num || '-' }}</td>
                        <td class="px-3 py-2">
                          <div class="font-semibold text-gray-900">{{ r.whscode }}</div>
                          <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ r.whsname }}</div>
                        </td>
                        <td class="px-3 py-2 font-semibold text-gray-900">{{ r.material_type || 'OTHER' }}</td>
                        <td class="px-3 py-2">
                          <div class="font-semibold text-gray-900">{{ r.item_code }}</div>
                          <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ r.item_name }}</div>
                        </td>
                        <td class="px-3 py-2 text-gray-900 font-semibold">{{ r.batch_number || '-' }}</td>
                        <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(r.batch_qty) }}</td>
                        <td class="px-3 py-2 text-gray-800">{{ r.mnf_date || '-' }}</td>
                        <td class="px-3 py-2 text-gray-800">{{ r.exp_date || '-' }}</td>
                      </tr>
                      <tr v-if="!isLoading && g.rows.length === 0">
                        <td colspan="9" class="px-3 py-6 text-center text-gray-600">No data</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- Flat view -->
            <table v-else class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Date</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">GRPO</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Vendor</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Type</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Batch</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Batch Qty</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Mfg</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Exp</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="r in procurementRows" :key="`${r.doc_num}-${r.item_code}-${r.batch_number}-${r.whscode}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2 text-gray-800">{{ r.doc_date || '-' }}</td>
                  <td class="px-3 py-2 text-gray-900 font-semibold">{{ r.doc_num || '-' }}</td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.vendor_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ r.vendor_name }}</div>
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ r.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 font-semibold text-gray-900">{{ r.material_type || 'OTHER' }}</td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ r.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-900 font-semibold">{{ r.batch_number || '-' }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(r.batch_qty) }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ r.mnf_date || '-' }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ r.exp_date || '-' }}</td>
                </tr>
                <tr v-if="!isLoading && procurementRows.length === 0">
                  <td colspan="10" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- PRODUCT SPECS -->
      <div v-else-if="activeReportId === 'product_specs'">
        <p class="text-xs text-gray-600 mb-3">{{ asOfText }}</p>

        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3">
            <div class="md:col-span-2 flex items-end">
              <label class="inline-flex items-center gap-2 text-sm text-gray-800">
                <input v-model="productSpecsIncludeZero" type="checkbox" class="h-4 w-4" />
                Include zero stock rows
              </label>
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Limit</label>
              <select
                v-model.number="productSpecsLimit"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
                <option :value="1000">1000</option>
              </select>
            </div>
            <div class="lg:col-span-3 flex items-end justify-end gap-2">
              <button
                class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="resetProductSpecsPaging(); refreshAll()"
              >
                Apply
              </button>
              <button
                class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="productSpecsIncludeZero = false; productSpecsLimit = 200; productSpecsOffset = 0"
              >
                Reset
              </button>
            </div>
          </div>
          <div class="mt-2 text-xs text-gray-600">
            Size is extracted from Item Name (e.g. 50g / 1kg). Flavour uses an Item Master UDF if present, else it is inferred from the text.
            Moisture/age come from the latest Production Order (SAP B1 OWOR/WOR1) for that item, if available.
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">SKUs</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(productSpecsTotals.sku_count) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Total Qty</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(productSpecsTotals.qty) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Rows with Moisture</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(productSpecsTotals.with_moisture) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Offset</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(productSpecsOffset) }}</p>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Stock Qty by Flavour (Top)</h3>
            <canvas ref="productSpecsFlavourChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Stock Qty by Size Bucket</h3>
            <canvas ref="productSpecsSizeChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4 mb-6">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Avg Moisture by Production Age (days)</h3>
          <canvas ref="productSpecsMoistureChartEl" style="height: 260px; max-height: 260px;"></canvas>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <div class="flex items-center justify-between gap-4 mb-3">
            <h3 class="text-base font-semibold text-gray-900">Warehouse-wise Stock (Specs + Moisture)</h3>
            <div class="flex items-center gap-2">
              <button
                class="px-3 py-1.5 text-sm font-semibold bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="productSpecsOffset === 0 || isLoading"
                @click="productSpecsPrevPage"
              >
                Prev
              </button>
              <div class="text-sm text-gray-700">Offset: {{ productSpecsOffset }}</div>
              <button
                class="px-3 py-1.5 text-sm font-semibold bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="!productSpecsHasMore || isLoading"
                @click="productSpecsNextPage"
              >
                Next
              </button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Size (g)</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Flavour</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">OnHand</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Moisture</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Prod Date</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Age</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Prod Order</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="r in productSpecsRows" :key="`${r.whscode}-${r.item_code}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ r.whsname }}</div>
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[30ch]">{{ r.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">
                    {{ r.size_grams != null ? formatNumber(r.size_grams) : '-' }}
                  </td>
                  <td class="px-3 py-2 text-gray-800">{{ r.flavour || 'Unknown' }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(r.onhand_qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">
                    {{ r.moisture_content != null ? formatNumber(r.moisture_content) : '-' }}
                  </td>
                  <td class="px-3 py-2 text-gray-800">{{ r.prod_post_date || '-' }}</td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ r.prod_age_days != null ? `${r.prod_age_days}d` : '-' }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ r.prod_doc_num || '-' }}</td>
                </tr>
                <tr v-if="!isLoading && productSpecsRows.length === 0">
                  <td colspan="9" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- BATCH AVAILABILITY -->
      <div v-else-if="activeReportId === 'batch_availability'">
        <p class="text-xs text-gray-600 mb-3">Shows batch stock with committed and on-order quantities. Filters: PM%, RM%, FG% items only.</p>

        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3">
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Limit</label>
              <select
                v-model.number="batchAvailabilityLimit"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
                <option :value="1000">1000</option>
              </select>
            </div>
            <div class="lg:col-span-5 flex items-end justify-end gap-2">
              <button
                class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="batchAvailabilityOffset = 0; refreshAll()"
              >
                Apply
              </button>
              <button
                class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="batchAvailabilityLimit = 200; batchAvailabilityOffset = 0"
              >
                Reset
              </button>
            </div>
          </div>
          <div class="mt-2 text-xs text-gray-600">
            Available = OnHand - IsCommitted + OnOrder. Data from OBTN (batch master), OBTQ (batch quantities), and OITW (item-warehouse).
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">SKUs</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(batchAvailabilityTotals.sku_count) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Total OnHand</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(batchAvailabilityTotals.total_onhand) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Total Committed</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(batchAvailabilityTotals.total_committed) }}</p>
          </div>
          <div class="bg-white border rounded-lg shadow-sm p-5">
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">Total Available</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatNumber(batchAvailabilityTotals.total_available) }}</p>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Available Stock by Warehouse</h3>
            <canvas ref="batchAvailabilityWarehouseChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">OnHand vs Committed vs OnOrder</h3>
            <canvas ref="batchAvailabilityComparisonChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <div class="flex items-center justify-between gap-4 mb-3">
            <h3 class="text-base font-semibold text-gray-900">Batch Availability Details</h3>
            <div class="flex items-center gap-2">
              <button
                class="px-3 py-1.5 text-sm font-semibold bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="batchAvailabilityOffset === 0 || isLoading"
                @click="batchAvailabilityOffset = Math.max(0, batchAvailabilityOffset - batchAvailabilityLimit); refreshAll()"
              >
                Prev
              </button>
              <div class="text-sm text-gray-700">Offset: {{ batchAvailabilityOffset }}</div>
              <button
                class="px-3 py-1.5 text-sm font-semibold bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="!batchAvailabilityHasMore || isLoading"
                @click="batchAvailabilityOffset += batchAvailabilityLimit; refreshAll()"
              >
                Next
              </button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item Code</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item Name</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">OnHand</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Committed</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">OnOrder</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Available</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="r in batchAvailabilityRows" :key="`${r.item_code}-${r.whscode}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2 font-semibold text-gray-900">{{ r.item_code }}</td>
                  <td class="px-3 py-2">
                    <div class="text-gray-900">{{ r.item_name }}</div>
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ r.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(r.onhand) }}</td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatNumber(r.is_committed) }}</td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatNumber(r.on_order) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(r.available) }}</td>
                </tr>
                <tr v-if="!isLoading && batchAvailabilityRows.length === 0">
                  <td colspan="7" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- SAP B1 BATCH INVENTORY (Raw / FG) -->
      <div v-else-if="activeReportId === 'sap_b1_batch_inventory'">
        <p class="text-xs text-gray-600 mb-3">{{ asOfText }} · Raw Material & Finished Good batches only (FIFO per item). Excludes WASTE%.</p>

        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <h3 class="text-sm font-semibold text-gray-900 mb-3">Search & filters</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            <div class="lg:col-span-2">
              <label class="block text-xs font-semibold text-gray-600 mb-1">Search (Item code or name)</label>
              <input
                v-model="sapB1Search"
                type="text"
                placeholder="e.g. RMHN0051 or Milk"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                @keydown.enter="refreshAll"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Warehouse code</label>
              <input
                v-model="sapB1WarehouseCode"
                type="text"
                placeholder="e.g. EC-FG, WH01"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                @keydown.enter="refreshAll"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Material type</label>
              <select
                v-model="sapB1BatchInventoryMaterialType"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All (Raw + FG)</option>
                <option value="Raw Material">Raw Material</option>
                <option value="Finished Good">Finished Good</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-600 mb-1">Max rows (limit)</label>
              <select
                v-model.number="sapB1BatchInventoryLimit"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
                <option :value="1000">1000</option>
              </select>
            </div>
            <div class="flex items-end gap-2">
              <button
                class="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="refreshAll"
              >
                Apply filters
              </button>
              <button
                class="px-4 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isLoading"
                @click="resetSapB1Filters()"
              >
                Reset
              </button>
            </div>
          </div>
          <p class="text-xs text-gray-500 mt-3">Search matches item code or item name. Leave blank to see all. Apply filters to refresh the table and summary.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div
            v-for="s in sapB1BatchInventorySummary"
            :key="s.material_type"
            class="bg-white border rounded-lg shadow-sm p-5"
          >
            <p class="text-xs uppercase tracking-wide text-gray-600 font-semibold">{{ s.material_type || '—' }}</p>
            <p class="mt-2 text-2xl font-bold text-gray-900">{{ formatInt(s.batch_count) }} batches</p>
            <p class="text-sm text-gray-700">{{ formatNumber(s.total_qty) }} qty</p>
          </div>
          <div v-if="!isLoading && sapB1BatchInventorySummary.length === 0" class="bg-white border rounded-lg shadow-sm p-5 flex items-center text-gray-500 text-sm">
            No summary (apply filters or check data).
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Quantity by Material Type</h3>
            <canvas ref="sapB1BatchInventoryChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
            <h3 class="text-base font-semibold text-gray-900">SAP B1 Batch Inventory</h3>
            <div class="w-full sm:w-72">
              <label class="sr-only">Filter table results</label>
              <input
                v-model="sapB1TableFilter"
                type="text"
                placeholder="Filter table (item, batch, warehouse…)"
                class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
          <p v-if="sapB1TableFilter.trim()" class="text-xs text-gray-600 mb-2">
            Showing {{ sapB1FilteredRows.length }} of {{ sapB1BatchInventoryRows.length }} rows
          </p>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item Code</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item Name</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Material Type</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Batch</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">UoM</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Production</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Expiry</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Days from Prod.</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr
                  v-for="r in sapB1FilteredRows"
                  :key="`${r.item_code}-${r.whscode}-${r.batch_number}`"
                  class="hover:bg-gray-50"
                >
                  <td class="px-3 py-2 font-semibold text-gray-900">{{ r.item_code }}</td>
                  <td class="px-3 py-2 text-gray-900 truncate max-w-[20ch]" :title="r.item_name">{{ r.item_name }}</td>
                  <td class="px-3 py-2">
                    <span
                      :class="[
                        'px-2 py-0.5 rounded text-xs font-medium',
                        r.material_type === 'Raw Material' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                      ]"
                    >
                      {{ r.material_type || '—' }}
                    </span>
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ r.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[18ch]">{{ r.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-900 font-mono text-xs">{{ r.batch_number || '—' }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(r.quantity) }}</td>
                  <td class="px-3 py-2 text-gray-700">{{ r.uom || '—' }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ r.production_date || '—' }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ r.expiry_date || '—' }}</td>
                  <td class="px-3 py-2 text-right text-gray-700">{{ r.days_from_production != null ? r.days_from_production : '—' }}</td>
                </tr>
                <tr v-if="!isLoading && sapB1BatchInventoryRows.length === 0">
                  <td colspan="10" class="px-3 py-6 text-center text-gray-600">No data. Try changing filters and click Apply filters.</td>
                </tr>
                <tr v-else-if="!isLoading && sapB1BatchInventoryRows.length > 0 && sapB1FilteredRows.length === 0">
                  <td colspan="10" class="px-3 py-6 text-center text-gray-600">No rows match the table filter. Clear the filter box or change the text.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="sapB1BatchInventoryHasMore" class="text-xs text-amber-700 mt-2">More rows available; increase Limit to see more.</p>
        </div>
      </div>

      <!-- SLOW MOVING -->
      <div v-else-if="activeReportId === 'slow_moving'">
        <p class="text-xs text-gray-600 mb-3">{{ slowMovingWindowText }}</p>
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6">
          <label class="block text-xs font-semibold text-gray-600 mb-1">Slow Moving Days</label>
          <div class="flex flex-wrap items-end gap-2">
            <input
              v-model.number="slowMovingDays"
              type="number"
              min="1"
              max="3650"
              step="1"
              class="w-full max-w-xs px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="refreshAll"
            >
              Apply
            </button>
            <button
              class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="slowMovingDays = 90"
            >
              Reset
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Slow-moving Value by Warehouse</h3>
            <canvas ref="slowMovingWarehouseChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Slow-moving Value by Age Bucket</h3>
            <canvas ref="slowMovingBucketChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Slow Moving (OnHand &gt; 0)</h3>
          <p class="text-xs text-gray-600 mb-2">Cutoff: {{ slowMovingCutoff || '-' }} ({{ slowMovingDays }} days)</p>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">OnHand</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Last Move</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in slowMovingRows" :key="`${row.item_code}-${row.whscode}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-800">
                    <div class="font-semibold">{{ row.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ row.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(row.onhand_qty) }}</td>
                  <td class="px-3 py-2 text-gray-800">{{ row.last_movement_date || 'Unknown' }}</td>
                </tr>
                <tr v-if="!isLoading && slowMovingRows.length === 0">
                  <td colspan="4" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- EXPIRY RISK -->
      <div v-else-if="activeReportId === 'expiry_risk'">
        <p class="text-xs text-gray-600 mb-3">{{ expiryWindowText }}</p>
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6 flex items-center justify-between">
          <h3 class="text-base font-semibold text-gray-900">Expiry Risk (next {{ expiryDays }} days)</h3>
          <div class="flex items-center gap-2">
            <select
              v-model.number="expiryDays"
              class="px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option :value="30">30 days</option>
              <option :value="60">60 days</option>
              <option :value="90">90 days</option>
              <option :value="180">180 days</option>
            </select>
            <button
              class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="refreshAll"
            >
              Apply
            </button>
            <button
              class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="expiryDays = 90"
            >
              Reset
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Expiry Buckets (Value)</h3>
            <canvas ref="expiryValueChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Expiry Buckets (Qty)</h3>
            <canvas ref="expiryQtyChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">Expiring Batches (top 100)</h3>
          <p class="text-xs text-gray-600 mb-2">Sorted by earliest expiry. Value uses warehouse AvgPrice.</p>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item / Batch</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Exp</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Value</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in expiringBatchRows" :key="`${row.item_code}-${row.whscode}-${row.batch_number}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.batch_number || '-' }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-800">
                    <div class="font-semibold">{{ row.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ row.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-800">
                    <div class="font-semibold">{{ row.exp_date || '-' }}</div>
                    <div class="text-xs text-gray-600">{{ row.remaining_days != null ? `${row.remaining_days}d` : '' }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(row.qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatCurrency(row.stock_value) }}</td>
                </tr>
                <tr v-if="!isLoading && expiringBatchRows.length === 0">
                  <td colspan="5" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- EXPIRING BATCHES -->
      <!-- Production Trace -->
      <div v-else-if="activeReportId === 'production_trace'">
        <ProductionTraceVisualization />
      </div>

      <!-- Batch Genealogy Tree (run_batch_genealogy API — collapsible tree) -->
      <div v-else-if="activeReportId === 'batch_genealogy_tree'">
        <BatchGenealogyTree />
      </div>

      <div v-else-if="activeReportId === 'expiring_batches'">
        <p class="text-xs text-gray-600 mb-3">{{ expiryWindowText }}</p>
        <div class="bg-white border rounded-lg shadow-sm p-4 mb-6 flex items-center justify-between">
          <h3 class="text-base font-semibold text-gray-900">Expiring Batches (action list)</h3>
          <div class="flex items-center gap-2">
            <select
              v-model.number="expiryDays"
              class="px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option :value="30">30 days</option>
              <option :value="60">60 days</option>
              <option :value="90">90 days</option>
              <option :value="180">180 days</option>
            </select>
            <button
              class="px-3 py-2 text-sm font-semibold bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="refreshAll"
            >
              Apply
            </button>
            <button
              class="px-3 py-2 text-sm font-semibold bg-gray-100 text-gray-800 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isLoading"
              @click="expiryDays = 90"
            >
              Reset
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Expiry Buckets (Value)</h3>
            <canvas ref="expiryValueChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Expiring Stock by Warehouse (Value)</h3>
            <canvas ref="expiringByWarehouseChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <p class="text-xs text-gray-600 mb-2">Sorted by earliest expiry. Value uses warehouse AvgPrice.</p>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item / Batch</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Warehouse</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Exp</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Value</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in expiringBatchRows" :key="`${row.item_code}-${row.whscode}-${row.batch_number}`" class="hover:bg-gray-50">
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.batch_number || '-' }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-800">
                    <div class="font-semibold">{{ row.whscode }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[22ch]">{{ row.whsname }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-800">
                    <div class="font-semibold">{{ row.exp_date || '-' }}</div>
                    <div class="text-xs text-gray-600">{{ row.remaining_days != null ? `${row.remaining_days}d` : '' }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatNumber(row.qty) }}</td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatCurrency(row.stock_value) }}</td>
                </tr>
                <tr v-if="!isLoading && expiringBatchRows.length === 0">
                  <td colspan="5" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ABC -->
      <div v-else-if="activeReportId === 'abc'">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">ABC Value Concentration</h3>
            <canvas ref="abcChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-base font-semibold text-gray-900 mb-3">Top 10 ABC Items (Value)</h3>
            <canvas ref="abcTopItemsChartEl" style="height: 260px; max-height: 260px;"></canvas>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">ABC Items (top 200)</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Class</th>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase">Item</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Value</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700 uppercase">Cum%</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="row in abcRows" :key="row.item_code" class="hover:bg-gray-50">
                  <td
                    class="px-3 py-2 font-bold"
                    :class="row.class === 'A' ? 'text-red-700' : row.class === 'B' ? 'text-yellow-700' : 'text-green-700'"
                  >
                    {{ row.class }}
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-semibold text-gray-900">{{ row.item_code }}</div>
                    <div class="text-xs text-gray-600 truncate max-w-[28ch]">{{ row.item_name }}</div>
                  </td>
                  <td class="px-3 py-2 text-right text-gray-900 font-semibold">{{ formatCurrency(row.stock_value) }}</td>
                  <td class="px-3 py-2 text-right text-gray-800">{{ formatNumber(row.cumulative_share) }}</td>
                </tr>
                <tr v-if="!isLoading && abcRows.length === 0">
                  <td colspan="4" class="px-3 py-6 text-center text-gray-600">No data</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { createResource } from 'frappe-ui'
import { APP_CONFIG } from '@/config/constants.js'
import ProductionTraceVisualization from '../components/ProductionTraceVisualization.vue'
import BatchGenealogyTree from '../components/BatchGenealogyTree.vue'
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  BarController,
  ArcElement,
  DoughnutController,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

Chart.register(
  CategoryScale,
  LinearScale,
  BarElement,
  BarController,
  ArcElement,
  DoughnutController,
  Title,
  Tooltip,
  Legend
)

function unwrapFrappeResponse(data) {
  if (data?.message) return data.message
  if (data?.data?.message) return data.data.message
  if (data?.data) return data.data
  return data
}

const catalogSearch = ref('')
const catalogRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_REPORT_CATALOG,
  method: 'GET',
  auto: false,
  transform: unwrapFrappeResponse
})

const activeReportId = ref(null)

const filters = ref({
  search: '',
  warehouse_code: '',
  low_stock_threshold: 10
})

const slowMovingDays = ref(90)
const topItemsLimit = ref(10)
const expiryDays = ref(90)

function buildFilters() {
  const f = {}
  if (filters.value.search && filters.value.search.trim()) f.search = filters.value.search.trim()
  if (filters.value.warehouse_code && filters.value.warehouse_code.trim()) f.warehouse_code = filters.value.warehouse_code.trim()
  if (typeof filters.value.low_stock_threshold === 'number' && filters.value.low_stock_threshold >= 0) {
    f.low_stock_threshold = filters.value.low_stock_threshold
  }
  return f
}

const summaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_SUMMARY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const warehouseRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_WAREHOUSE_BREAKDOWN,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const topItemsRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_TOP_ITEMS,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()), limit: topItemsLimit.value, sort: 'value' }),
  auto: false,
  transform: unwrapFrappeResponse
})

const slowMovingRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_SLOW_MOVING,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()), days: slowMovingDays.value, limit: 50 }),
  auto: false,
  transform: unwrapFrappeResponse
})

const expirySummaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_EXPIRY_SUMMARY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()), days: expiryDays.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const expiringBatchesRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_EXPIRING_BATCHES,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()), days: expiryDays.value, limit: 100 }),
  auto: false,
  transform: unwrapFrappeResponse
})

const expiringByWarehouseRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_EXPIRING_BY_WAREHOUSE,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()), days: expiryDays.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const slowMovingSummaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_SLOW_MOVING_SUMMARY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()), days: slowMovingDays.value }),
  auto: false,
  transform: unwrapFrappeResponse
})

const batchStockLimit = ref(200)
const batchMinQty = ref(0)
const batchIncludeExpired = ref(false)

const warehouseBatchRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_WAREHOUSE_BATCH_STOCK,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({
    filters: JSON.stringify(buildFilters()),
    limit: batchStockLimit.value,
    min_qty: batchMinQty.value,
    include_expired: batchIncludeExpired.value ? 1 : 0
  }),
  auto: false,
  transform: unwrapFrappeResponse
})

const warehouseBatchTotalsRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_WAREHOUSE_BATCH_TOTALS,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({
    filters: JSON.stringify(buildFilters()),
    min_qty: batchMinQty.value,
    include_expired: batchIncludeExpired.value ? 1 : 0
  }),
  auto: false,
  transform: unwrapFrappeResponse
})

const procurementDateFrom = ref('')
const procurementDateTo = ref('')
const procurementVendorCode = ref('')
const procurementMaterialType = ref('')
const procurementLimit = ref(200)
const procurementOffset = ref(0)
const procurementGroupByVendor = ref(true)
const expandedVendors = ref(new Set())

function toDateInput(d) {
  // Local date (avoids UTC day-shift issues)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDays(date, days) {
  const d = new Date(date)
  d.setDate(d.getDate() + Number(days || 0))
  return d
}

const todayISO = computed(() => toDateInput(new Date()))
const asOfText = computed(() => `As of ${todayISO.value}`)

const expiryWindowText = computed(() => {
  const start = todayISO.value
  const end = toDateInput(addDays(new Date(), expiryDays.value))
  return `Date window: ${start} → ${end} (next ${expiryDays.value} days)`
})

const slowMovingWindowText = computed(() => {
  const end = todayISO.value
  const start = toDateInput(addDays(new Date(), -slowMovingDays.value))
  return `Date window: ${start} → ${end} (last ${slowMovingDays.value} days)`
})

const procurementRangeText = computed(() => {
  const t = new Date()
  const defFrom = toDateInput(addDays(t, -30))
  const defTo = toDateInput(t)
  const from = procurementDateFrom.value || defFrom
  const to = procurementDateTo.value || defTo
  return `Date range: ${from} → ${to}`
})

const procurementAppliedRangeText = computed(() => {
  // Try rows response first (combined endpoint), then fallback to summary
  const f = procurementRowsRes.data?.filters || procurementSummaryRes.data?.filters || null
  const from = f?.start_date
  const to = f?.end_date
  if (from && to) return `Applied date range: ${from} → ${to}`
  return procurementRangeText.value
})

function ensureProcurementDefaultDates() {
  // Default to last 30 days if user hasn't selected anything yet
  if (!procurementDateFrom.value && !procurementDateTo.value) {
    const today = new Date()
    const from = new Date(today)
    from.setDate(from.getDate() - 30)
    procurementDateFrom.value = toDateInput(from)
    procurementDateTo.value = toDateInput(today)
  }
}

function buildProcurementFilters() {
  const base = buildFilters()
  const f = { ...base }
  if (procurementDateFrom.value) f.start_date = procurementDateFrom.value
  if (procurementDateTo.value) f.end_date = procurementDateTo.value
  if (procurementVendorCode.value && procurementVendorCode.value.trim()) {
    f.vendor_code = procurementVendorCode.value.trim()
  }
  if (procurementMaterialType.value) {
    f.material_type = procurementMaterialType.value
  }
  return f
}

const procurementSummaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_PROCUREMENT_TRACEABILITY_SUMMARY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildProcurementFilters()) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const procurementRowsRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_PROCUREMENT_TRACEABILITY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({
    filters: JSON.stringify(buildProcurementFilters()),
    limit: procurementLimit.value,
    offset: procurementOffset.value,
    include_summary: 1  // OPTIMIZATION: Get summary + rows in one call (reduces HTTP calls by 50%)
  }),
  auto: false,
  transform: unwrapFrappeResponse
})

const productSpecsIncludeZero = ref(false)
const productSpecsLimit = ref(200)
const productSpecsOffset = ref(0)

function buildProductSpecsFilters() {
  const base = buildFilters()
  return {
    ...base,
    include_zero: productSpecsIncludeZero.value ? 1 : 0
  }
}

const productSpecsSummaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_PRODUCT_SPECS_STOCK_SUMMARY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildProductSpecsFilters()) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const productSpecsRowsRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_PRODUCT_SPECS_STOCK,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({
    filters: JSON.stringify(buildProductSpecsFilters()),
    limit: productSpecsLimit.value,
    offset: productSpecsOffset.value
  }),
  auto: false,
  transform: unwrapFrappeResponse
})

const abcRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_ABC_ANALYSIS,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const batchAvailabilityLimit = ref(200)
const batchAvailabilityOffset = ref(0)

const batchAvailabilityRowsRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_BATCH_AVAILABILITY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({
    filters: JSON.stringify(buildFilters()),
    limit: batchAvailabilityLimit.value,
    offset: batchAvailabilityOffset.value
  }),
  auto: false,
  transform: unwrapFrappeResponse
})

const batchAvailabilitySummaryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_BATCH_AVAILABILITY_SUMMARY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({ filters: JSON.stringify(buildFilters()) }),
  auto: false,
  transform: unwrapFrappeResponse
})

const sapB1BatchInventoryLimit = ref(500)
const sapB1BatchInventoryMaterialType = ref('')
const sapB1Search = ref('')
const sapB1WarehouseCode = ref('')

function buildSapB1BatchInventoryFilters() {
  const f = {}
  if (sapB1Search.value && sapB1Search.value.trim()) f.search = sapB1Search.value.trim()
  if (sapB1WarehouseCode.value && sapB1WarehouseCode.value.trim()) f.warehouse_code = sapB1WarehouseCode.value.trim()
  if (sapB1BatchInventoryMaterialType.value) f.material_type = sapB1BatchInventoryMaterialType.value
  return f
}

const sapB1BatchInventoryRes = createResource({
  url: APP_CONFIG.API_ENDPOINTS.INVENTORY_DASHBOARD.GET_SAP_B1_BATCH_INVENTORY,
  method: 'GET',
  headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate', Pragma: 'no-cache' },
  makeParams: () => ({
    filters: JSON.stringify(buildSapB1BatchInventoryFilters()),
    limit: sapB1BatchInventoryLimit.value,
    include_summary: 1
  }),
  auto: false,
  transform: unwrapFrappeResponse
})

const isLoading = computed(() => {
  if (catalogRes.loading) return true
  const id = activeReportId.value
  if (!id) return false
  if (id === 'overview') return Boolean(summaryRes.loading || warehouseRes.loading || topItemsRes.loading)
  if (id === 'warehouse_value') return Boolean(warehouseRes.loading)
  if (id === 'top_items') return Boolean(summaryRes.loading || topItemsRes.loading)
  if (id === 'warehouse_batches') return Boolean(warehouseBatchRes.loading || warehouseBatchTotalsRes.loading || expirySummaryRes.loading)
  if (id === 'slow_moving') return Boolean(slowMovingRes.loading || slowMovingSummaryRes.loading)
  if (id === 'expiry_risk') return Boolean(expirySummaryRes.loading || expiringBatchesRes.loading)
  if (id === 'expiring_batches') return Boolean(expiringBatchesRes.loading || expiringByWarehouseRes.loading || expirySummaryRes.loading)
  if (id === 'procurement_trace') return Boolean(procurementRowsRes.loading || (procurementSummaryRes.loading && !procurementRowsRes.data?.totals))
  if (id === 'product_specs') return Boolean(productSpecsSummaryRes.loading || productSpecsRowsRes.loading)
  if (id === 'abc') return Boolean(abcRes.loading)
  if (id === 'batch_availability') return Boolean(batchAvailabilityRowsRes.loading || batchAvailabilitySummaryRes.loading)
  if (id === 'sap_b1_batch_inventory') return Boolean(sapB1BatchInventoryRes.loading)
  if (id === 'production_trace' || id === 'batch_genealogy_tree') return false // These reports handle their own loading
  return false
})

const errorMessage = computed(() => {
  const id = activeReportId.value
  if (!id) return ''

  const err =
    (id === 'overview' && (summaryRes.error || summaryRes.data?.error)) ||
    (id === 'warehouse_value' && (warehouseRes.error || warehouseRes.data?.error)) ||
    (id === 'top_items' && (topItemsRes.error || topItemsRes.data?.error)) ||
    (id === 'warehouse_batches' &&
      (warehouseBatchRes.error || warehouseBatchRes.data?.error || warehouseBatchTotalsRes.error || warehouseBatchTotalsRes.data?.error || expirySummaryRes.error || expirySummaryRes.data?.error)) ||
    (id === 'slow_moving' && (slowMovingRes.error || slowMovingRes.data?.error || slowMovingSummaryRes.error || slowMovingSummaryRes.data?.error)) ||
    (id === 'expiry_risk' && (expirySummaryRes.error || expirySummaryRes.data?.error || expiringBatchesRes.error || expiringBatchesRes.data?.error)) ||
    (id === 'expiring_batches' &&
      (expiringBatchesRes.error || expiringBatchesRes.data?.error || expiringByWarehouseRes.error || expiringByWarehouseRes.data?.error || expirySummaryRes.error || expirySummaryRes.data?.error)) ||
    (id === 'procurement_trace' &&
      (procurementRowsRes.error || procurementRowsRes.data?.error || (procurementSummaryRes.error && !procurementRowsRes.data?.totals) || (procurementSummaryRes.data?.error && !procurementRowsRes.data?.totals))) ||
    (id === 'product_specs' &&
      (productSpecsSummaryRes.error ||
        productSpecsSummaryRes.data?.error ||
        productSpecsRowsRes.error ||
        productSpecsRowsRes.data?.error)) ||
    (id === 'abc' && (abcRes.error || abcRes.data?.error)) ||
    (id === 'batch_availability' &&
      (batchAvailabilityRowsRes.error ||
        batchAvailabilityRowsRes.data?.error ||
        batchAvailabilitySummaryRes.error ||
        batchAvailabilitySummaryRes.data?.error)) ||
    (id === 'sap_b1_batch_inventory' && (sapB1BatchInventoryRes.error || sapB1BatchInventoryRes.data?.error)) ||
    ((id === 'production_trace' || id === 'batch_genealogy_tree') && false) // These reports handle their own error state
  return err ? String(err?.message || err) : ''
})

const summaryMetrics = computed(() => summaryRes.data?.metrics || {})
const topItemsRows = computed(() => topItemsRes.data?.items || [])
const slowMovingRows = computed(() => slowMovingRes.data?.items || [])
const slowMovingCutoff = computed(() => slowMovingRes.data?.cutoff_date || '')
const expiryBuckets = computed(() => expirySummaryRes.data?.buckets || [])
const expiringBatchRows = computed(() => expiringBatchesRes.data?.batches || [])
const expiringByWarehouseRows = computed(() => expiringByWarehouseRes.data?.warehouses || [])
const abcRows = computed(() => abcRes.data?.items || [])
const warehouseBatchRows = computed(() => warehouseBatchRes.data?.rows || [])
const warehouseBatchTotalsRows = computed(() => warehouseBatchTotalsRes.data?.warehouses || [])
const slowMovingByWarehouseRows = computed(() => slowMovingSummaryRes.data?.by_warehouse || [])
const slowMovingByBucketRows = computed(() => slowMovingSummaryRes.data?.by_bucket || [])
// OPTIMIZATION: Get summary from rows response if available (combined endpoint), else fallback to separate summary
const procurementTotals = computed(() => procurementRowsRes.data?.totals || procurementSummaryRes.data?.totals || {})
const procurementByVendor = computed(() => procurementRowsRes.data?.by_vendor || procurementSummaryRes.data?.by_vendor || [])
const procurementByWarehouse = computed(() => procurementRowsRes.data?.by_warehouse || procurementSummaryRes.data?.by_warehouse || [])
const procurementByMaterialType = computed(() => procurementRowsRes.data?.by_material_type || procurementSummaryRes.data?.by_material_type || [])
const procurementRows = computed(() => procurementRowsRes.data?.rows || [])
const procurementHasMore = computed(() => Boolean(procurementRowsRes.data?.has_more))

const productSpecsTotals = computed(() => productSpecsSummaryRes.data?.totals || {})
const productSpecsByFlavour = computed(() => productSpecsSummaryRes.data?.by_flavour || [])
const productSpecsBySizeBucket = computed(() => productSpecsSummaryRes.data?.by_size_bucket || [])
const productSpecsMoistureByAgeBucket = computed(() => productSpecsSummaryRes.data?.moisture_by_age_bucket || [])
const productSpecsRows = computed(() => productSpecsRowsRes.data?.rows || [])
const productSpecsHasMore = computed(() => Boolean(productSpecsRowsRes.data?.has_more))

const batchAvailabilityTotals = computed(() => batchAvailabilitySummaryRes.data?.totals || {})
const batchAvailabilityByWarehouse = computed(() => batchAvailabilitySummaryRes.data?.by_warehouse || [])
const batchAvailabilityRows = computed(() => batchAvailabilityRowsRes.data?.rows || [])
const batchAvailabilityHasMore = computed(() => Boolean(batchAvailabilityRowsRes.data?.has_more))

const sapB1BatchInventoryRows = computed(() => sapB1BatchInventoryRes.data?.rows || [])
const sapB1BatchInventorySummary = computed(() => sapB1BatchInventoryRes.data?.summary || [])
const sapB1BatchInventoryHasMore = computed(() => Boolean(sapB1BatchInventoryRes.data?.has_more))

const sapB1TableFilter = ref('')
const sapB1FilteredRows = computed(() => {
  const rows = sapB1BatchInventoryRows.value
  const q = (sapB1TableFilter.value || '').trim().toLowerCase()
  if (!q) return rows
  return rows.filter(r => {
    const code = (r.item_code || '').toLowerCase()
    const name = (r.item_name || '').toLowerCase()
    const batch = (r.batch_number || '').toLowerCase()
    const whs = (r.whscode || '').toLowerCase()
    const whsName = (r.whsname || '').toLowerCase()
    return code.includes(q) || name.includes(q) || batch.includes(q) || whs.includes(q) || whsName.includes(q)
  })
})

const procurementGrouped = computed(() => {
  const rows = procurementRows.value || []
  const groups = new Map()
  for (const r of rows) {
    const key = r.vendor_code || 'UNKNOWN'
    if (!groups.has(key)) {
      groups.set(key, {
        vendor_code: r.vendor_code || 'UNKNOWN',
        vendor_name: r.vendor_name || '',
        qty: 0,
        value: 0,
        rows: []
      })
    }
    const g = groups.get(key)
    g.qty += Number(r.line_qty || 0)
    g.value += Number(r.line_total || 0)
    g.rows.push(r)
  }
  return Array.from(groups.values()).sort((a, b) => b.value - a.value)
})

function toggleVendor(vendorCode) {
  const s = new Set(expandedVendors.value)
  if (s.has(vendorCode)) s.delete(vendorCode)
  else s.add(vendorCode)
  expandedVendors.value = s
}

function resetProcurementPaging() {
  procurementOffset.value = 0
}

async function refreshProcurement(resetOffset = true) {
  if (resetOffset) resetProcurementPaging()
  await refreshAll()
}

function procurementNextPage() {
  if (!procurementHasMore.value) return
  procurementOffset.value = procurementOffset.value + procurementLimit.value
  refreshAll()
}

function procurementPrevPage() {
  if (procurementOffset.value <= 0) return
  procurementOffset.value = Math.max(0, procurementOffset.value - procurementLimit.value)
  refreshAll()
}

function resetProductSpecsPaging() {
  productSpecsOffset.value = 0
}

async function productSpecsNextPage() {
  if (!productSpecsHasMore.value) return
  productSpecsOffset.value = productSpecsOffset.value + productSpecsLimit.value
  await productSpecsRowsRes.fetch()
}

async function productSpecsPrevPage() {
  if (productSpecsOffset.value <= 0) return
  productSpecsOffset.value = Math.max(0, productSpecsOffset.value - productSpecsLimit.value)
  await productSpecsRowsRes.fetch()
}

// Add Production Trace and Batch Genealogy Tree to catalog items
const catalogItems = computed(() => {
  const apiReports = catalogRes.data?.reports || []
  const hasProductionTrace = apiReports.some(r => r.id === 'production_trace')
  const hasBatchGenealogyTree = apiReports.some(r => r.id === 'batch_genealogy_tree')
  const extras = []
  if (!hasProductionTrace) {
    extras.push({
      id: 'production_trace',
      name: 'Production Genealogy / Batch Trace',
      description: 'Visualize batch flow through all production stages from root batch to finished goods',
      category: 'Traceability'
    })
  }
  if (!hasBatchGenealogyTree) {
    extras.push({
      id: 'batch_genealogy_tree',
      name: 'Batch Genealogy Tree',
      description: 'Forward trace from one batch — collapsible tree (Raw Milk → SFG → FG)',
      category: 'Traceability'
    })
  }
  if (extras.length) return [...apiReports, ...extras]
  return apiReports
})
const catalogCount = computed(() => catalogRes.data?.count || catalogItems.value.length || 0)
const catalogError = computed(() => {
  const err = catalogRes.error || catalogRes.data?.error
  return err ? String(err?.message || err) : ''
})
const filteredCatalog = computed(() => {
  const q = (catalogSearch.value || '').trim().toLowerCase()
  const list = catalogItems.value
  if (!q) return list
  return list.filter(r => {
    const hay = `${r.name || ''} ${r.description || ''} ${r.category || ''}`.toLowerCase()
    return hay.includes(q)
  })
})

const activeReport = computed(() => {
  const id = activeReportId.value
  if (!id) return null
  return catalogItems.value.find(r => r.id === id) || null
})

const warehouseValueChartEl = ref(null)
const warehouseQtyChartEl = ref(null)
const overviewStockHealthChartEl = ref(null)

const topItemsValueChartEl = ref(null)
const topItemsShareChartEl = ref(null)

const expiryValueChartEl = ref(null)
const expiryQtyChartEl = ref(null)

const expiringByWarehouseChartEl = ref(null)

const slowMovingWarehouseChartEl = ref(null)
const slowMovingBucketChartEl = ref(null)

const warehouseBatchTotalsChartEl = ref(null)
const warehouseBatchExpiryChartEl = ref(null)

const procurementVendorChartEl = ref(null)
const procurementWarehouseChartEl = ref(null)
const procurementMaterialTypeChartEl = ref(null)

const productSpecsFlavourChartEl = ref(null)
const productSpecsSizeChartEl = ref(null)
const productSpecsMoistureChartEl = ref(null)

const batchAvailabilityWarehouseChartEl = ref(null)
const batchAvailabilityComparisonChartEl = ref(null)

const sapB1BatchInventoryChartEl = ref(null)

const abcChartEl = ref(null)
const abcTopItemsChartEl = ref(null)
let warehouseValueChartInstance = null
let overviewStockHealthChartInstance = null
let topItemsValueChartInstance = null
let warehouseQtyChartInstance = null
let topItemsShareChartInstance = null
let expiryValueChartInstance = null
let expiryQtyChartInstance = null
let expiringByWarehouseChartInstance = null
let slowMovingWarehouseChartInstance = null
let slowMovingBucketChartInstance = null
let warehouseBatchTotalsChartInstance = null
let warehouseBatchExpiryChartInstance = null
let procurementVendorChartInstance = null
let procurementWarehouseChartInstance = null
let procurementMaterialTypeChartInstance = null
let productSpecsFlavourChartInstance = null
let productSpecsSizeChartInstance = null
let productSpecsMoistureChartInstance = null
let batchAvailabilityWarehouseChartInstance = null
let batchAvailabilityComparisonChartInstance = null
let sapB1BatchInventoryChartInstance = null
let abcChartInstance = null
let abcTopItemsChartInstance = null

function destroyCharts() {
  if (warehouseValueChartInstance) warehouseValueChartInstance.destroy()
  if (overviewStockHealthChartInstance) overviewStockHealthChartInstance.destroy()
  if (topItemsValueChartInstance) topItemsValueChartInstance.destroy()
  if (warehouseQtyChartInstance) warehouseQtyChartInstance.destroy()
  if (topItemsShareChartInstance) topItemsShareChartInstance.destroy()
  if (expiryValueChartInstance) expiryValueChartInstance.destroy()
  if (expiryQtyChartInstance) expiryQtyChartInstance.destroy()
  if (expiringByWarehouseChartInstance) expiringByWarehouseChartInstance.destroy()
  if (slowMovingWarehouseChartInstance) slowMovingWarehouseChartInstance.destroy()
  if (slowMovingBucketChartInstance) slowMovingBucketChartInstance.destroy()
  if (warehouseBatchTotalsChartInstance) warehouseBatchTotalsChartInstance.destroy()
  if (warehouseBatchExpiryChartInstance) warehouseBatchExpiryChartInstance.destroy()
  if (procurementVendorChartInstance) procurementVendorChartInstance.destroy()
  if (procurementWarehouseChartInstance) procurementWarehouseChartInstance.destroy()
  if (procurementMaterialTypeChartInstance) procurementMaterialTypeChartInstance.destroy()
  if (productSpecsFlavourChartInstance) productSpecsFlavourChartInstance.destroy()
  if (productSpecsSizeChartInstance) productSpecsSizeChartInstance.destroy()
  if (productSpecsMoistureChartInstance) productSpecsMoistureChartInstance.destroy()
  if (batchAvailabilityWarehouseChartInstance) batchAvailabilityWarehouseChartInstance.destroy()
  if (batchAvailabilityComparisonChartInstance) batchAvailabilityComparisonChartInstance.destroy()
  if (sapB1BatchInventoryChartInstance) sapB1BatchInventoryChartInstance.destroy()
  if (abcChartInstance) abcChartInstance.destroy()
  if (abcTopItemsChartInstance) abcTopItemsChartInstance.destroy()
  warehouseValueChartInstance = null
  overviewStockHealthChartInstance = null
  topItemsValueChartInstance = null
  warehouseQtyChartInstance = null
  topItemsShareChartInstance = null
  expiryValueChartInstance = null
  expiryQtyChartInstance = null
  expiringByWarehouseChartInstance = null
  slowMovingWarehouseChartInstance = null
  slowMovingBucketChartInstance = null
  warehouseBatchTotalsChartInstance = null
  warehouseBatchExpiryChartInstance = null
  procurementVendorChartInstance = null
  procurementWarehouseChartInstance = null
  procurementMaterialTypeChartInstance = null
  productSpecsFlavourChartInstance = null
  productSpecsSizeChartInstance = null
  productSpecsMoistureChartInstance = null
  batchAvailabilityWarehouseChartInstance = null
  batchAvailabilityComparisonChartInstance = null
  sapB1BatchInventoryChartInstance = null
  abcChartInstance = null
  abcTopItemsChartInstance = null
}

function clearSelection() {
  activeReportId.value = null
  destroyCharts()
}

async function loadActiveReport() {
  const id = activeReportId.value
  if (!id) {
    console.log('[Load Active Report] No active report ID')
    return
  }
  console.log('[Load Active Report] Loading report:', id)

  destroyCharts()

  if (id === 'overview') {
    await Promise.all([summaryRes.fetch(), warehouseRes.fetch(), topItemsRes.fetch()])
    await nextTick()
    initWarehouseValueChart()
    initOverviewStockHealthChart()
    initTopItemsValueChart()
    return
  }

  if (id === 'warehouse_value') {
    await warehouseRes.fetch()
    await nextTick()
    initWarehouseValueChart()
    initWarehouseQtyChart()
    return
  }

  if (id === 'top_items') {
    await Promise.all([summaryRes.fetch(), topItemsRes.fetch()])
    await nextTick()
    initTopItemsValueChart()
    initTopItemsShareChart()
    return
  }

  if (id === 'warehouse_batches') {
    await Promise.all([warehouseBatchRes.fetch(), warehouseBatchTotalsRes.fetch(), expirySummaryRes.fetch()])
    await nextTick()
    initWarehouseBatchTotalsChart()
    initWarehouseBatchExpiryChart()
    return
  }

  if (id === 'slow_moving') {
    await Promise.all([slowMovingRes.fetch(), slowMovingSummaryRes.fetch()])
    await nextTick()
    initSlowMovingWarehouseChart()
    initSlowMovingBucketChart()
    return
  }

  if (id === 'expiry_risk') {
    await Promise.all([expirySummaryRes.fetch(), expiringBatchesRes.fetch()])
    await nextTick()
    initExpiryValueChart()
    initExpiryQtyChart()
    return
  }

  if (id === 'expiring_batches') {
    await Promise.all([expiringBatchesRes.fetch(), expirySummaryRes.fetch(), expiringByWarehouseRes.fetch()])
    await nextTick()
    initExpiryValueChart()
    initExpiringByWarehouseChart()
    return
  }

  if (id === 'procurement_trace') {
    ensureProcurementDefaultDates()
    // OPTIMIZATION: Only fetch rows (with include_summary=1) - reduces HTTP calls from 2 to 1
    await procurementRowsRes.fetch()
    // Only fetch separate summary if rows response doesn't include it (backward compatibility)
    if (!procurementRowsRes.data?.totals) {
      await procurementSummaryRes.fetch()
    }
    await nextTick()
    initProcurementVendorChart()
    initProcurementWarehouseChart()
    initProcurementMaterialTypeChart()
    return
  }

  if (id === 'product_specs') {
    await Promise.all([productSpecsSummaryRes.fetch(), productSpecsRowsRes.fetch()])
    await nextTick()
    initProductSpecsFlavourChart()
    initProductSpecsSizeChart()
    initProductSpecsMoistureChart()
    return
  }

  if (id === 'batch_availability') {
    console.log('[Batch Availability] Loading report data...')
    try {
      await Promise.all([batchAvailabilitySummaryRes.fetch(), batchAvailabilityRowsRes.fetch()])
      await nextTick()
      initBatchAvailabilityWarehouseChart()
      initBatchAvailabilityComparisonChart()
      console.log('[Batch Availability] Report loaded successfully')
    } catch (error) {
      console.error('[Batch Availability] Error loading report:', error)
      throw error
    }
    return
  }

  if (id === 'sap_b1_batch_inventory') {
    await sapB1BatchInventoryRes.fetch()
    await nextTick()
    initSapB1BatchInventoryChart()
    return
  }

  if (id === 'abc') {
    await abcRes.fetch()
    await nextTick()
    initAbcChart()
    initAbcTopItemsChart()
  }
}

async function selectReport(report) {
  const id = report?.id
  if (!id) return
  console.log('[Select Report] Selected report ID:', id)
  activeReportId.value = id
  await loadActiveReport()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function initWarehouseValueChart() {
  const canvas = warehouseValueChartEl.value
  if (!canvas?.getContext) return
  const rows = warehouseRes.data?.warehouses || []
  if (!rows.length) return

  if (warehouseValueChartInstance) warehouseValueChartInstance.destroy()

  const ctx = canvas.getContext('2d')
  const bgColors = rows.map((_, idx) => {
    const hue = (idx * 47) % 360
    return `hsla(${hue}, 75%, 55%, 0.8)`
  })
  warehouseValueChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          data: rows.map(r => r.stock_value || 0),
          backgroundColor: bgColors
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  })
}

function initWarehouseQtyChart() {
  const canvas = warehouseQtyChartEl.value
  if (!canvas?.getContext) return
  const rows = warehouseRes.data?.warehouses || []
  if (!rows.length) return

  if (warehouseQtyChartInstance) warehouseQtyChartInstance.destroy()

  const ctx = canvas.getContext('2d')
  warehouseQtyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'On-hand Qty',
          data: rows.map(r => r.onhand_qty || 0),
          backgroundColor: 'rgba(34, 197, 94, 0.75)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } }
    }
  })
}

function initOverviewStockHealthChart() {
  const canvas = overviewStockHealthChartEl.value
  if (!canvas?.getContext) return
  const metrics = summaryMetrics.value || {}
  const total = Number(metrics.total_skus_with_stock) || 0
  const low = Number(metrics.low_stock_skus) || 0
  const ok = Math.max(0, total - low)
  if (total === 0 && low === 0) return

  if (overviewStockHealthChartInstance) overviewStockHealthChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  overviewStockHealthChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Low stock (below threshold)', 'OK stock'],
      datasets: [{
        data: [low, ok],
        backgroundColor: ['rgba(239, 68, 68, 0.8)', 'rgba(34, 197, 94, 0.8)'],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  })
}

function initTopItemsValueChart() {
  const canvas = topItemsValueChartEl.value
  if (!canvas?.getContext) return
  const rows = topItemsRows.value || []
  if (!rows.length) return

  if (topItemsValueChartInstance) topItemsValueChartInstance.destroy()

  const ctx = canvas.getContext('2d')
  topItemsValueChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.item_code),
      datasets: [
        {
          label: 'Stock Value',
          data: rows.map(r => r.stock_value || 0),
          backgroundColor: 'rgba(59, 130, 246, 0.7)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { beginAtZero: true }
      }
    }
  })
}

function initTopItemsShareChart() {
  const canvas = topItemsShareChartEl.value
  if (!canvas?.getContext) return

  const items = topItemsRows.value || []
  if (!items.length) return

  const total = Number(summaryMetrics.value?.total_stock_value || 0)
  const topValue = items.reduce((acc, r) => acc + Number(r.stock_value || 0), 0)
  const restValue = Math.max(0, total - topValue)

  if (topItemsShareChartInstance) topItemsShareChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  topItemsShareChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Top items', 'Rest'],
      datasets: [
        {
          data: [topValue, restValue],
          backgroundColor: ['rgba(59, 130, 246, 0.85)', 'rgba(107, 114, 128, 0.35)']
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  })
}

function initExpiryValueChart() {
  const canvas = expiryValueChartEl.value
  if (!canvas?.getContext) return
  const rows = expiryBuckets.value || []
  if (!rows.length) return

  if (expiryValueChartInstance) expiryValueChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  expiryValueChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.bucket),
      datasets: [
        {
          label: 'Stock Value',
          data: rows.map(r => r.stock_value || 0),
          backgroundColor: 'rgba(239, 68, 68, 0.7)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } }
    }
  })
}

function initExpiryQtyChart() {
  const canvas = expiryQtyChartEl.value
  if (!canvas?.getContext) return
  const rows = expiryBuckets.value || []
  if (!rows.length) return

  if (expiryQtyChartInstance) expiryQtyChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  expiryQtyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.bucket),
      datasets: [
        {
          label: 'Qty',
          data: rows.map(r => r.qty || 0),
          backgroundColor: 'rgba(234, 179, 8, 0.75)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } }
    }
  })
}

function initExpiringByWarehouseChart() {
  const canvas = expiringByWarehouseChartEl.value
  if (!canvas?.getContext) return
  const rows = expiringByWarehouseRows.value || []
  if (!rows.length) return

  if (expiringByWarehouseChartInstance) expiringByWarehouseChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  expiringByWarehouseChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'Expiring Stock Value',
          data: rows.map(r => r.stock_value || 0),
          backgroundColor: 'rgba(168, 85, 247, 0.75)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } }
    }
  })
}

function initSlowMovingWarehouseChart() {
  const canvas = slowMovingWarehouseChartEl.value
  if (!canvas?.getContext) return
  const rows = slowMovingByWarehouseRows.value || []
  if (!rows.length) return

  if (slowMovingWarehouseChartInstance) slowMovingWarehouseChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  slowMovingWarehouseChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'Slow-moving Stock Value',
          data: rows.map(r => r.stock_value || 0),
          backgroundColor: 'rgba(59, 130, 246, 0.7)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initSlowMovingBucketChart() {
  const canvas = slowMovingBucketChartEl.value
  if (!canvas?.getContext) return
  const rows = slowMovingByBucketRows.value || []
  if (!rows.length) return

  if (slowMovingBucketChartInstance) slowMovingBucketChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  slowMovingBucketChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => r.bucket),
      datasets: [
        {
          data: rows.map(r => r.stock_value || 0),
          backgroundColor: rows.map((_, idx) => `hsla(${(idx * 61) % 360}, 70%, 55%, 0.8)`)
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  })
}

function initWarehouseBatchTotalsChart() {
  const canvas = warehouseBatchTotalsChartEl.value
  if (!canvas?.getContext) return
  const rows = warehouseBatchTotalsRows.value || []
  if (!rows.length) return

  if (warehouseBatchTotalsChartInstance) warehouseBatchTotalsChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  warehouseBatchTotalsChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'Batch Qty',
          data: rows.map(r => r.qty || 0),
          backgroundColor: 'rgba(34, 197, 94, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initWarehouseBatchExpiryChart() {
  const canvas = warehouseBatchExpiryChartEl.value
  if (!canvas?.getContext) return
  const rows = expiryBuckets.value || []
  if (!rows.length) return

  if (warehouseBatchExpiryChartInstance) warehouseBatchExpiryChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  warehouseBatchExpiryChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.bucket),
      datasets: [
        {
          label: 'Batch Qty',
          data: rows.map(r => r.qty || 0),
          backgroundColor: 'rgba(234, 179, 8, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initProcurementVendorChart() {
  const canvas = procurementVendorChartEl.value
  if (!canvas?.getContext) return
  const rows = procurementByVendor.value || []
  if (!rows.length) return

  if (procurementVendorChartInstance) procurementVendorChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  procurementVendorChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.vendor_code),
      datasets: [
        {
          label: 'Procurement Value',
          data: rows.map(r => r.value || 0),
          backgroundColor: 'rgba(59, 130, 246, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initProcurementWarehouseChart() {
  const canvas = procurementWarehouseChartEl.value
  if (!canvas?.getContext) return
  const rows = procurementByWarehouse.value || []
  if (!rows.length) return

  if (procurementWarehouseChartInstance) procurementWarehouseChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  procurementWarehouseChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'Procurement Qty',
          data: rows.map(r => r.qty || 0),
          backgroundColor: 'rgba(34, 197, 94, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initProcurementMaterialTypeChart() {
  const canvas = procurementMaterialTypeChartEl.value
  if (!canvas?.getContext) return
  const rows = procurementByMaterialType.value || []
  if (!rows.length) return

  if (procurementMaterialTypeChartInstance) procurementMaterialTypeChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  procurementMaterialTypeChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => r.material_type),
      datasets: [
        {
          data: rows.map(r => r.value || 0),
          backgroundColor: ['rgba(239,68,68,0.8)', 'rgba(59,130,246,0.8)', 'rgba(107,114,128,0.55)']
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  })
}

function initProductSpecsFlavourChart() {
  const canvas = productSpecsFlavourChartEl.value
  if (!canvas?.getContext) return
  const rows = productSpecsByFlavour.value || []
  if (!rows.length) return

  const top = rows.slice(0, 10)
  const rest = rows.slice(10)
  const labels = [...top.map(r => r.flavour || 'Unknown')]
  const values = [...top.map(r => r.qty || 0)]
  if (rest.length) {
    labels.push('Rest')
    values.push(rest.reduce((s, r) => s + Number(r.qty || 0), 0))
  }
  if (!values.some(v => Number(v) > 0)) return

  if (productSpecsFlavourChartInstance) productSpecsFlavourChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  const colors = labels.map((_, idx) => `hsla(${(idx * 47) % 360}, 70%, 55%, 0.82)`)
  productSpecsFlavourChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  })
}

function initProductSpecsSizeChart() {
  const canvas = productSpecsSizeChartEl.value
  if (!canvas?.getContext) return
  const rows = productSpecsBySizeBucket.value || []
  if (!rows.length) return
  if (!rows.some(r => Number(r.qty || 0) > 0)) return

  if (productSpecsSizeChartInstance) productSpecsSizeChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  productSpecsSizeChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.size_bucket),
      datasets: [
        {
          label: 'Stock Qty',
          data: rows.map(r => r.qty || 0),
          backgroundColor: 'rgba(59, 130, 246, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initProductSpecsMoistureChart() {
  const canvas = productSpecsMoistureChartEl.value
  if (!canvas?.getContext) return
  const rows = productSpecsMoistureByAgeBucket.value || []
  if (!rows.length) return
  if (!rows.some(r => Number(r.avg_moisture || 0) > 0)) return

  if (productSpecsMoistureChartInstance) productSpecsMoistureChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  productSpecsMoistureChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.age_bucket),
      datasets: [
        {
          label: 'Avg Moisture',
          data: rows.map(r => r.avg_moisture || 0),
          backgroundColor: 'rgba(34, 197, 94, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initBatchAvailabilityWarehouseChart() {
  const canvas = batchAvailabilityWarehouseChartEl.value
  if (!canvas?.getContext) return
  const rows = batchAvailabilityByWarehouse.value || []
  if (!rows.length) return

  if (batchAvailabilityWarehouseChartInstance) batchAvailabilityWarehouseChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  batchAvailabilityWarehouseChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'Available Stock',
          data: rows.map(r => r.total_available || 0),
          backgroundColor: 'rgba(34, 197, 94, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

function initBatchAvailabilityComparisonChart() {
  const canvas = batchAvailabilityComparisonChartEl.value
  if (!canvas?.getContext) return
  const rows = batchAvailabilityByWarehouse.value || []
  if (!rows.length) return

  if (batchAvailabilityComparisonChartInstance) batchAvailabilityComparisonChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  batchAvailabilityComparisonChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.whscode),
      datasets: [
        {
          label: 'OnHand',
          data: rows.map(r => r.total_onhand || 0),
          backgroundColor: 'rgba(59, 130, 246, 0.75)'
        },
        {
          label: 'Committed',
          data: rows.map(r => r.total_committed || 0),
          backgroundColor: 'rgba(239, 68, 68, 0.75)'
        },
        {
          label: 'OnOrder',
          data: rows.map(r => r.total_on_order || 0),
          backgroundColor: 'rgba(234, 179, 8, 0.75)'
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }
  })
}

function initSapB1BatchInventoryChart() {
  const canvas = sapB1BatchInventoryChartEl.value
  if (!canvas?.getContext) return
  const summary = sapB1BatchInventorySummary.value || []
  if (!summary.length) return

  if (sapB1BatchInventoryChartInstance) sapB1BatchInventoryChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  sapB1BatchInventoryChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: summary.map(s => s.material_type || '—'),
      datasets: [
        {
          data: summary.map(s => Number(s.total_qty) || 0),
          backgroundColor: ['rgba(245, 158, 11, 0.8)', 'rgba(16, 185, 129, 0.8)']
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  })
}

function initAbcChart() {
  const canvas = abcChartEl.value
  if (!canvas?.getContext) return
  const summary = abcRes.data?.summary || {}
  const labels = ['A', 'B', 'C']
  const values = labels.map(k => summary?.[k]?.stock_value || 0)
  if (!values.some(v => Number(v) > 0)) return

  if (abcChartInstance) abcChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  abcChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: ['rgba(239, 68, 68, 0.8)', 'rgba(234, 179, 8, 0.8)', 'rgba(34, 197, 94, 0.8)']
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  })
}

function initAbcTopItemsChart() {
  const canvas = abcTopItemsChartEl.value
  if (!canvas?.getContext) return
  const rows = abcRows.value || []
  if (!rows.length) return

  const top = rows.slice(0, 10)
  if (!top.length) return

  if (abcTopItemsChartInstance) abcTopItemsChartInstance.destroy()
  const ctx = canvas.getContext('2d')
  abcTopItemsChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(r => r.item_code),
      datasets: [
        {
          label: 'Stock Value',
          data: top.map(r => r.stock_value || 0),
          backgroundColor: top.map(r => (r.class === 'A' ? 'rgba(239,68,68,0.75)' : r.class === 'B' ? 'rgba(234,179,8,0.75)' : 'rgba(34,197,94,0.75)'))
        }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  })
}

async function refreshAll() {
  // Avoid refetching catalog on every filter change; keep it cached.
  if (!catalogRes.data && !catalogRes.loading) {
    await catalogRes.fetch().catch(() => {})
  }
  await loadActiveReport()
}

function clearFilters() {
  filters.value = { search: '', warehouse_code: '', low_stock_threshold: 10 }
  slowMovingDays.value = 90
  topItemsLimit.value = 10
  expiryDays.value = 90
  batchStockLimit.value = 200
  batchMinQty.value = 0
  batchIncludeExpired.value = false

  procurementDateFrom.value = ''
  procurementDateTo.value = ''
  procurementVendorCode.value = ''
  procurementMaterialType.value = ''
  procurementLimit.value = 200
  procurementOffset.value = 0

  productSpecsIncludeZero.value = false
  productSpecsLimit.value = 200
  productSpecsOffset.value = 0

  resetSapB1Filters()
}

function resetSapB1Filters() {
  sapB1Search.value = ''
  sapB1WarehouseCode.value = ''
  sapB1BatchInventoryLimit.value = 500
  sapB1BatchInventoryMaterialType.value = ''
  sapB1TableFilter.value = ''
}

const numberFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })
const intFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const currencyFmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })

function formatNumber(v) {
  const n = Number(v || 0)
  return numberFmt.format(n)
}

function formatInt(v) {
  const n = Number(v || 0)
  return intFmt.format(n)
}

function formatCurrency(v) {
  const n = Number(v || 0)
  return currencyFmt.format(n)
}

onMounted(() => {
  catalogRes.fetch().catch(() => {})
})
</script>

