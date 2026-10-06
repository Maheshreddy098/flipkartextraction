<template>
  <div class="p-6 space-y-6">

    <!-- Page Header -->
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">POD Dashboard</h1>
        <p class="text-sm text-gray-500 mt-0.5">Proof of Delivery tracking — DSR Logistics &amp; SafeExpress</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <select
          v-model="datePreset"
          @change="applyDatePreset"
          class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="fiscal_year">Fiscal Year</option>
          <option value="this_month">This Month</option>
          <option value="last_month">Last Month</option>
          <option value="last_30_days">Last 30 Days</option>
          <option value="last_3_months">Last 3 Months</option>
          <option value="last_6_months">Last 6 Months</option>
          <option value="last_12_months">Last 12 Months</option>
          <option value="custom">Custom Range</option>
        </select>
        <input
          v-model="shipmentFilters.start_date"
          type="date"
          @change="handleCustomDateChange"
          class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <span class="text-gray-400 text-sm">→</span>
        <input
          v-model="shipmentFilters.end_date"
          type="date"
          @change="handleCustomDateChange"
          class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          @click="refreshAll"
          :disabled="dashboardSummary.loading"
          class="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ dashboardSummary.loading ? 'Refreshing…' : 'Refresh' }}
        </button>
        <button
          @click="exportData"
          class="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition-colors"
        >
          Export
        </button>
        <button
          @click="showReportPanel = !showReportPanel"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          Send Report
        </button>
      </div>
    </div>

    <!-- Send Report Panel -->
    <div v-if="showReportPanel" class="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex flex-wrap items-end gap-3">
      <div>
        <label class="block text-xs font-semibold text-indigo-700 mb-1">From</label>
        <input
          v-model="reportDateRange.start_date"
          type="date"
          class="px-3 py-2 bg-white border border-indigo-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-indigo-500"
        />
      </div>
      <div>
        <label class="block text-xs font-semibold text-indigo-700 mb-1">To</label>
        <input
          v-model="reportDateRange.end_date"
          type="date"
          class="px-3 py-2 bg-white border border-indigo-200 rounded-lg text-sm text-gray-700 focus:ring-2 focus:ring-indigo-500"
        />
      </div>
      <button
        @click="sendPodReport"
        :disabled="reportState.loading"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {{ reportState.loading ? 'Sending…' : 'Send Now' }}
      </button>
      <span v-if="reportState.message" :class="reportState.error ? 'text-red-600' : 'text-indigo-700'" class="text-sm font-medium">
        {{ reportState.message }}
      </span>
      <p class="w-full text-xs text-indigo-500 mt-1">
        Report will be emailed to recipients configured in DSR Settings.
      </p>
    </div>

    <!-- Loading State -->
    <div v-if="dashboardSummary.loading && !dashboardSummary.data" class="flex justify-center py-16">
      <div class="text-center">
        <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-3"></div>
        <p class="text-sm text-gray-500">Loading POD data…</p>
      </div>
    </div>

    <!-- Error Banner -->
    <div v-if="dashboardSummary.error" class="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-2">
      <svg class="w-4 h-4 text-red-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
      </svg>
      <p class="text-sm text-red-600">Failed to load dashboard: {{ dashboardSummary.error?.message || dashboardSummary.error }}</p>
    </div>

    <template v-if="!dashboardSummary.loading || dashboardSummary.data">

      <!-- ─── Section 1: KPI Overview ───────────────────────────────── -->
      <section>
        <div class="flex items-center gap-2 mb-3">
          <div class="w-1 h-5 bg-blue-500 rounded-full flex-shrink-0"></div>
          <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">POD Health Overview</h2>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">

          <!-- Total Invoices -->
          <div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Total Invoices</p>
            <p class="text-3xl font-bold text-gray-900">
              {{ dashboardSummary.data?.metrics?.total_invoices?.in_range || 0 }}
            </p>
            <p class="text-xs text-gray-400 mt-2">
              30d: {{ dashboardSummary.data?.metrics?.total_invoices?.last_30_days || 0 }}
              &nbsp;·&nbsp;
              Today: {{ dashboardSummary.data?.metrics?.total_invoices?.today || 0 }}
            </p>
          </div>

          <!-- Pending POD (SAP B1) -->
          <div class="bg-white border border-red-200 rounded-xl p-5 shadow-sm">
            <div class="flex items-center justify-between mb-2">
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Pending POD</p>
              <span class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-blue-50 text-blue-600 border border-blue-100">SAP B1</span>
            </div>
            <p class="text-3xl font-bold text-red-600">
              {{ dashboardSummary.data?.metrics?.pod_date?.without_date || 0 }}
            </p>
            <p class="text-xs text-gray-400 mt-2">
              Invoices missing POD date · selected period
            </p>
          </div>

          <!-- POD Link Coverage -->
          <div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">POD Link Coverage</p>
            <p class="text-3xl font-bold" :class="getCoverageColor(dashboardSummary.data?.metrics?.pod_link?.coverage_rate)">
              {{ (dashboardSummary.data?.metrics?.pod_link?.coverage_rate || 0).toFixed(1) }}%
            </p>
            <div class="mt-2 bg-gray-100 rounded-full h-1.5">
              <div
                class="h-1.5 rounded-full transition-all duration-500"
                :class="getCoverageBarColor(dashboardSummary.data?.metrics?.pod_link?.coverage_rate)"
                :style="{ width: Math.min(dashboardSummary.data?.metrics?.pod_link?.coverage_rate || 0, 100) + '%' }"
              ></div>
            </div>
            <p class="text-xs text-gray-400 mt-1.5">
              Available: {{ dashboardSummary.data?.metrics?.pod_link?.with_link || 0 }}
              &nbsp;·&nbsp;
              Missing: {{ dashboardSummary.data?.metrics?.pod_link?.without_link || 0 }}
            </p>
          </div>

          <!-- POD Date Coverage -->
          <div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">POD Date Coverage</p>
            <p class="text-3xl font-bold" :class="getCoverageColor(dashboardSummary.data?.metrics?.pod_date?.coverage_rate)">
              {{ (dashboardSummary.data?.metrics?.pod_date?.coverage_rate || 0).toFixed(1) }}%
            </p>
            <div class="mt-2 bg-gray-100 rounded-full h-1.5">
              <div
                class="h-1.5 rounded-full transition-all duration-500"
                :class="getCoverageBarColor(dashboardSummary.data?.metrics?.pod_date?.coverage_rate)"
                :style="{ width: Math.min(dashboardSummary.data?.metrics?.pod_date?.coverage_rate || 0, 100) + '%' }"
              ></div>
            </div>
            <p class="text-xs text-gray-400 mt-1.5">
              With Date: {{ dashboardSummary.data?.metrics?.pod_date?.with_date || 0 }}
              &nbsp;·&nbsp;
              Missing: {{ dashboardSummary.data?.metrics?.pod_date?.without_date || 0 }}
            </p>
          </div>

          <!-- Tracking Coverage -->
          <div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Tracking Coverage</p>
            <p class="text-3xl font-bold" :class="getCoverageColor(dashboardSummary.data?.metrics?.tracking_coverage?.coverage_rate)">
              {{ (dashboardSummary.data?.metrics?.tracking_coverage?.coverage_rate || 0).toFixed(1) }}%
            </p>
            <div class="mt-2 bg-gray-100 rounded-full h-1.5">
              <div
                class="h-1.5 rounded-full transition-all duration-500"
                :class="getCoverageBarColor(dashboardSummary.data?.metrics?.tracking_coverage?.coverage_rate)"
                :style="{ width: Math.min(dashboardSummary.data?.metrics?.tracking_coverage?.coverage_rate || 0, 100) + '%' }"
              ></div>
            </div>
            <p class="text-xs text-gray-400 mt-1.5">
              Tracked: {{ dashboardSummary.data?.metrics?.tracking_coverage?.with_tracking || 0 }}
            </p>
          </div>

        </div>
      </section>

      <!-- ─── Section 2: Transporter POD Status ─────────────────────── -->
      <section>
        <div class="flex items-center gap-2 mb-3">
          <div class="w-1 h-5 bg-green-500 rounded-full flex-shrink-0"></div>
          <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Transporter POD Status</h2>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">

          <!-- SafeExpress Card -->
          <div class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 bg-blue-50 border-b border-blue-100">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                </div>
                <span class="font-semibold text-blue-900 text-sm">SafeExpress</span>
              </div>
              <div class="flex items-center gap-2">
                <input
                  v-model.number="safexpressLookbackDays"
                  type="number"
                  min="1"
                  max="365"
                  class="w-16 px-2 py-1.5 text-xs border border-blue-200 rounded-lg text-gray-700 bg-white focus:ring-2 focus:ring-blue-400"
                />
                <span class="text-xs text-blue-500 select-none">days</span>
                <button
                  @click="runSafexpressTrigger"
                  :disabled="triggerState.safeexpress.loading"
                  class="px-3 py-1.5 text-xs font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {{ triggerState.safeexpress.loading ? 'Syncing…' : 'Sync POD' }}
                </button>
              </div>
            </div>
            <div class="px-5 py-4 grid grid-cols-2 gap-4">
              <div>
                <p class="text-xs text-gray-500 mb-1">POD Link Missing</p>
                <p class="text-2xl font-bold text-red-600">{{ safeExpressSummary?.without_pod_link ?? 0 }}</p>
                <button
                  class="mt-1 text-xs text-blue-600 hover:underline font-medium"
                  @click="applyQuickFilter('SafeExpress', 'Missing', '')"
                >View →</button>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">POD Date Pending</p>
                <p class="text-2xl font-bold text-amber-600">{{ safeExpressSummary?.without_pod_date ?? 0 }}</p>
                <button
                  class="mt-1 text-xs text-blue-600 hover:underline font-medium"
                  @click="applyQuickFilter('SafeExpress', '', 'Missing')"
                >View →</button>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">Total Shipments</p>
                <p class="text-xl font-semibold text-gray-800">{{ safeExpressSummary?.total_shipments ?? 0 }}</p>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">POD Link Rate</p>
                <p class="text-xl font-semibold" :class="getCoverageColor(safeExpressSummary?.pod_link_rate)">
                  {{ (safeExpressSummary?.pod_link_rate || 0).toFixed(1) }}%
                </p>
              </div>
            </div>
            <div v-if="triggerState.safeexpress.message" class="px-5 py-2 bg-gray-50 border-t border-gray-100 text-xs text-gray-500">
              SafeExpress: {{ triggerState.safeexpress.message }}
            </div>
          </div>

          <!-- DSR Logistics Card -->
          <div class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 bg-green-50 border-b border-green-100">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                </div>
                <span class="font-semibold text-green-900 text-sm">DSR Logistics</span>
              </div>
              <button
                @click="runDsrTrigger"
                :disabled="triggerState.dsr.loading"
                class="px-3 py-1.5 text-xs font-semibold bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {{ triggerState.dsr.loading ? 'Syncing…' : 'Sync POD' }}
              </button>
            </div>
            <div class="px-5 py-4 grid grid-cols-2 gap-4">
              <div>
                <p class="text-xs text-gray-500 mb-1">POD Link Missing</p>
                <p class="text-2xl font-bold text-red-600">{{ dsrSummary?.without_pod_link ?? 0 }}</p>
                <button
                  class="mt-1 text-xs text-green-700 hover:underline font-medium"
                  @click="applyQuickFilter('DSR Logistics', 'Missing', '')"
                >View →</button>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">POD Date Pending</p>
                <p class="text-2xl font-bold text-amber-600">{{ dsrSummary?.without_pod_date ?? 0 }}</p>
                <button
                  class="mt-1 text-xs text-green-700 hover:underline font-medium"
                  @click="applyQuickFilter('DSR Logistics', '', 'Missing')"
                >View →</button>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">Total Shipments</p>
                <p class="text-xl font-semibold text-gray-800">{{ dsrSummary?.total_shipments ?? 0 }}</p>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">POD Link Rate</p>
                <p class="text-xl font-semibold" :class="getCoverageColor(dsrSummary?.pod_link_rate)">
                  {{ (dsrSummary?.pod_link_rate || 0).toFixed(1) }}%
                </p>
              </div>
            </div>
            <div v-if="triggerState.dsr.message" class="px-5 py-2 bg-gray-50 border-t border-gray-100 text-xs text-gray-500">
              DSR: {{ triggerState.dsr.message }}
            </div>
          </div>

        </div>
      </section>

      <!-- ─── Section 3: POD Shipments Table ───────────────────────── -->
      <section>
        <div class="flex flex-wrap items-center gap-3 mb-3">
          <div class="w-1 h-5 bg-red-500 rounded-full flex-shrink-0"></div>
          <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">POD Shipments</h2>
          <!-- Missing / All toggle -->
          <div class="flex bg-gray-100 rounded-lg p-0.5">
            <button
              @click="setMissingOnlyMode(true)"
              :class="[
                'px-3 py-1 text-xs font-semibold rounded-md transition-all',
                missingPODOnly ? 'bg-white shadow text-red-700' : 'text-gray-500 hover:text-gray-700'
              ]"
            >Missing POD</button>
            <button
              @click="setMissingOnlyMode(false)"
              :class="[
                'px-3 py-1 text-xs font-semibold rounded-md transition-all',
                !missingPODOnly ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'
              ]"
            >All Shipments</button>
          </div>
        </div>

        <div class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">

          <!-- Filters bar -->
          <div class="p-4 border-b border-gray-100 bg-gray-50">
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-2">
              <input
                v-model="shipmentFilters.search"
                type="text"
                placeholder="DocNum / Tracking…"
                class="col-span-2 sm:col-span-1 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                @keyup.enter="loadShipments"
              />
              <select
                v-model="shipmentFilters.transporter_name"
                @change="loadShipments"
                class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Transporters</option>
                <option v-for="t in transporters" :key="t" :value="t">{{ t }}</option>
              </select>
              <select
                v-model="shipmentFilters.channel"
                @change="loadShipments"
                class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Channels</option>
                <option value="E-com B2C">E-com B2C</option>
                <option value="E-com B2B">E-com B2B</option>
                <option value="Offline HN">Offline HN</option>
                <option value="Offline Dogsee">Offline Dogsee</option>
                <option value="Export">Export</option>
                <option value="Inter Transfer">Inter Transfer</option>
                <option value="Others">Others</option>
              </select>
              <select
                v-model="shipmentFilters.pod_link_status"
                @change="loadShipments"
                class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All POD Links</option>
                <option value="Available">Link Available</option>
                <option value="Missing">Link Missing</option>
              </select>
              <select
                v-model="shipmentFilters.pod_date_status"
                @change="loadShipments"
                class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All POD Dates</option>
                <option value="Available">Date Available</option>
                <option value="Missing">Date Missing</option>
              </select>
              <div class="flex gap-1.5">
                <button
                  @click="loadShipments"
                  class="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 transition-colors"
                >Apply</button>
                <button
                  @click="clearFilters"
                  class="flex-1 px-3 py-2 bg-gray-200 text-gray-700 rounded-lg text-xs hover:bg-gray-300 transition-colors"
                >Clear</button>
              </div>
            </div>
          </div>

          <!-- Table -->
          <div class="overflow-x-auto">
            <table class="min-w-full">
              <thead>
                <tr class="border-b border-gray-100">
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">DocNum</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">Date</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">Customer</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">Channel</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">Transporter</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">Tracking ID</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">POD Date</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50">POD Link</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr
                  v-for="shipment in shipmentsData.data?.shipments || []"
                  :key="shipment.docentry"
                  class="hover:bg-gray-50 transition-colors"
                >
                  <td class="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap">{{ shipment.docnum }}</td>
                  <td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{{ formatDate(shipment.docdate) }}</td>
                  <td class="px-4 py-3 text-sm text-gray-700 max-w-[160px] truncate">{{ shipment.customer_name || '–' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-50 text-blue-700">
                      {{ shipment.channel || '–' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">{{ shipment.transporter_name || '–' }}</td>
                  <td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{{ shipment.tracking_id || '–' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span
                      :class="shipment.pod_date ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'"
                      class="px-2 py-0.5 text-xs font-semibold rounded-full"
                    >
                      {{ shipment.pod_date ? formatDate(shipment.pod_date) : 'Pending' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <a
                      v-if="shipment.pod_link && shipment.pod_link !== 'NA'"
                      :href="shipment.pod_link"
                      target="_blank"
                      class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full bg-green-50 text-green-700 hover:bg-green-100 transition-colors"
                    >
                      View POD
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                    <span v-else class="px-2 py-0.5 text-xs font-semibold rounded-full bg-red-50 text-red-600">
                      Missing
                    </span>
                  </td>
                </tr>

                <!-- Loading -->
                <tr v-if="shipmentsData.loading">
                  <td colspan="8" class="px-4 py-10 text-center">
                    <div class="flex justify-center items-center gap-2">
                      <div class="animate-spin h-5 w-5 border-b-2 border-blue-500 rounded-full"></div>
                      <span class="text-sm text-gray-500">Loading shipments…</span>
                    </div>
                  </td>
                </tr>

                <!-- Empty -->
                <tr v-if="!shipmentsData.loading && !shipmentsData.data?.shipments?.length">
                  <td colspan="8" class="px-4 py-12 text-center">
                    <svg class="mx-auto h-10 w-10 text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p class="text-sm text-gray-400">No shipments found</p>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="shipmentsData.data" class="px-4 py-3 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2">
            <p class="text-xs text-gray-500">
              Showing
              {{ ((currentPage - 1) * 50) + 1 }}–{{ Math.min(currentPage * 50, shipmentsData.data.total_count || 0) }}
              of {{ (shipmentsData.data.total_count || 0).toLocaleString() }} shipments
            </p>
            <div class="flex gap-1">
              <button
                @click="goToPreviousPage"
                :disabled="currentPage === 1 || shipmentsData.loading"
                class="px-3 py-1.5 text-xs font-semibold bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >Previous</button>
              <span class="px-3 py-1.5 text-xs font-bold text-gray-800 bg-gray-100 rounded-lg">{{ currentPage }}</span>
              <button
                @click="goToNextPage"
                :disabled="!shipmentsData.data?.has_more || shipmentsData.loading"
                class="px-3 py-1.5 text-xs font-semibold bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >Next</button>
            </div>
          </div>
        </div>
      </section>

      <!-- ─── Section 4: POD Trends (collapsible) ───────────────────── -->
      <section>
        <button
          @click="showCharts = !showCharts"
          class="flex items-center gap-2 mb-3 w-full text-left group"
        >
          <div class="w-1 h-5 bg-purple-500 rounded-full flex-shrink-0"></div>
          <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide group-hover:text-purple-700 transition-colors">
            POD Trends
          </h2>
          <svg
            :class="['w-4 h-4 text-gray-400 transition-transform duration-200 ml-1', showCharts ? 'rotate-180' : '']"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <div v-show="showCharts" class="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
            <h3 class="text-sm font-semibold text-gray-700 mb-4">Invoice Volume Over Time</h3>
            <canvas ref="shipmentVolumeChart" style="height: 220px; max-height: 220px;"></canvas>
          </div>
          <div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
            <h3 class="text-sm font-semibold text-gray-700 mb-4">POD Link Distribution</h3>
            <canvas ref="podStatusChart" style="height: 200px; max-height: 200px;"></canvas>
          </div>
        </div>
      </section>

    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { createResource, frappeRequest } from 'frappe-ui'
import { APP_CONFIG } from '@/config/constants.js'
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
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
  PointElement,
  LineElement,
  LineController,
  BarElement,
  BarController,
  ArcElement,
  DoughnutController,
  Title,
  Tooltip,
  Legend
)

// ─── Frappe call helper ──────────────────────────────────────────────────────
const FRAPPE_CALL_TIMEOUT_MS = 30_000

function frappeCall(method, args = {}) {
  const callPromise = new Promise((resolve, reject) => {
    const frappeObj =
      (typeof frappe !== 'undefined' && frappe?.call && frappe) ||
      (typeof window !== 'undefined' && window.frappe?.call && window.frappe) ||
      null

    if (frappeObj) {
      frappeObj.call({
        method,
        args,
        callback: (r) => {
          if (r.message) resolve(r.message)
          else if (r.exc) reject(new Error(r.exc))
          else reject(new Error('Unknown error occurred'))
        },
        error: (r) => {
          reject(new Error(r.message || r.exc || 'Request failed'))
        }
      })
    } else {
      const csrfToken = window?.csrf_token || window?.boot?.csrf_token || null
      const apiUrl = method.startsWith('/api')
        ? method
        : method.startsWith('/method')
          ? `/api${method}`
          : `/api/method/${method}`
      frappeRequest({
        method: 'POST',
        url: apiUrl,
        params: args,
        headers: csrfToken ? { 'X-Frappe-CSRF-Token': csrfToken } : undefined
      }).then(resolve).catch((err) => reject(new Error(err?.message || 'Request failed')))
    }
  })

  const timeoutPromise = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Request timed out after 30s — SAP B1 may be slow')), FRAPPE_CALL_TIMEOUT_MS)
  )

  return Promise.race([callPromise, timeoutPromise])
}

// ─── UI State ────────────────────────────────────────────────────────────────
const showCharts = ref(false)
const missingPODOnly = ref(true)

// ─── Date helpers ────────────────────────────────────────────────────────────
function toDateInput(d) {
  // Use local date parts — toISOString() converts to UTC which rolls back 1 day in IST (UTC+5:30)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function getFiscalYearRange() {
  const today = new Date()
  const year = today.getFullYear()
  const fyStart = new Date(today.getMonth() < 3 ? year - 1 : year, 3, 1)
  const fyEnd   = new Date(today.getMonth() < 3 ? year : year + 1, 2, 31)
  return { start: toDateInput(fyStart), end: toDateInput(fyEnd) }
}

function getPresetDateRange(preset) {
  const today = new Date()
  const end = new Date(today)
  let start = new Date(today)
  switch (preset) {
    case 'fiscal_year': return getFiscalYearRange()
    case 'this_month':
      start = new Date(today.getFullYear(), today.getMonth(), 1)
      return { start: toDateInput(start), end: toDateInput(end) }
    case 'last_month': {
      const first = new Date(today.getFullYear(), today.getMonth(), 1)
      const lastEnd = new Date(first.getTime() - 1)
      const lastStart = new Date(lastEnd.getFullYear(), lastEnd.getMonth(), 1)
      return { start: toDateInput(lastStart), end: toDateInput(lastEnd) }
    }
    case 'last_30_days':  start.setDate(start.getDate() - 29);        return { start: toDateInput(start), end: toDateInput(end) }
    case 'last_3_months': start.setMonth(start.getMonth() - 3);       return { start: toDateInput(start), end: toDateInput(end) }
    case 'last_6_months': start.setMonth(start.getMonth() - 6);       return { start: toDateInput(start), end: toDateInput(end) }
    case 'last_12_months':start.setFullYear(start.getFullYear() - 1); return { start: toDateInput(start), end: toDateInput(end) }
    default: return { start: shipmentFilters.value.start_date || '', end: shipmentFilters.value.end_date || '' }
  }
}

// ─── Filters ─────────────────────────────────────────────────────────────────
const last3Range = getPresetDateRange('last_3_months')
const datePreset = ref('last_3_months')
const shipmentFilters = ref({
  search: '',
  transporter_name: '',
  channel: '',
  pod_status: 'Pending',   // default: show missing POD
  pod_link_status: '',
  pod_date_status: '',
  start_date: last3Range.start,
  end_date: last3Range.end
})

function getShipmentFilters() {
  const f = {}
  if (shipmentFilters.value.search?.trim())              f.search            = shipmentFilters.value.search.trim()
  if (shipmentFilters.value.transporter_name)            f.transporter_name  = shipmentFilters.value.transporter_name
  if (shipmentFilters.value.channel)                     f.channel           = shipmentFilters.value.channel
  if (shipmentFilters.value.pod_link_status)             f.pod_link_status   = shipmentFilters.value.pod_link_status
  if (shipmentFilters.value.pod_date_status)             f.pod_date_status   = shipmentFilters.value.pod_date_status
  if (shipmentFilters.value.pod_status)                  f.pod_status        = shipmentFilters.value.pod_status
  if (shipmentFilters.value.start_date)                  f.start_date        = shipmentFilters.value.start_date
  if (shipmentFilters.value.end_date)                    f.end_date          = shipmentFilters.value.end_date
  // Prevent contradictory filters
  if ((f.pod_link_status === 'Missing' || f.pod_date_status === 'Missing') && f.pod_status === 'Completed') {
    f.pod_status = 'Pending'
  }
  return f
}

function applyDatePreset() {
  if (datePreset.value === 'custom') { loadShipments(); return }
  const range = getPresetDateRange(datePreset.value)
  shipmentFilters.value.start_date = range.start
  shipmentFilters.value.end_date   = range.end
  reportDateRange.value.start_date = range.start
  reportDateRange.value.end_date   = range.end
  loadShipments()
}

function handleCustomDateChange() {
  if (datePreset.value !== 'custom') datePreset.value = 'custom'
  reportDateRange.value.start_date = shipmentFilters.value.start_date
  reportDateRange.value.end_date   = shipmentFilters.value.end_date
  loadShipments()
}

function clearFilters() {
  const range = getPresetDateRange('last_3_months')
  datePreset.value = 'last_3_months'
  shipmentFilters.value = {
    search: '',
    transporter_name: '',
    channel: '',
    pod_status: missingPODOnly.value ? 'Pending' : '',
    pod_link_status: '',
    pod_date_status: '',
    start_date: range.start,
    end_date: range.end
  }
  loadShipments()
}

function setMissingOnlyMode(val) {
  missingPODOnly.value = val
  shipmentFilters.value.pod_status      = val ? 'Pending' : ''
  shipmentFilters.value.pod_link_status = ''
  shipmentFilters.value.pod_date_status = ''
  loadShipments()
}

function applyQuickFilter(transporterName, podLinkStatus, podDateStatus) {
  const range = getPresetDateRange('last_3_months')
  missingPODOnly.value = true
  datePreset.value = 'last_3_months'
  shipmentFilters.value = {
    search: '',
    transporter_name: transporterName || '',
    channel: '',
    pod_status: 'Pending',
    pod_link_status: podLinkStatus || '',
    pod_date_status: podDateStatus || '',
    start_date: range.start,
    end_date: range.end
  }
  loadShipments()
}

// ─── Resources ───────────────────────────────────────────────────────────────
// dashboardSummary, transporterAnalytics, chartData use reactive objects that are
// populated by direct frappeCall (POST) so filters are always serialised as JSON body.
// createResource GET requests fail to serialise nested filter objects correctly.
const dashboardSummary = reactive({ loading: false, data: null, error: null })
const transporterAnalytics = reactive({ loading: false, data: null })
const chartData = reactive({ loading: false, data: null })

const currentPage = ref(1)
const shipmentsData = createResource({
  url: APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.GET_SHIPMENTS,
  method: 'POST',
  makeParams: () => ({ filters: getShipmentFilters(), page: currentPage.value, page_size: 50 }),
  auto: false,
  transform(data) {
    if (data?.message) return data.message
    if (data?.data?.message) return data.data.message
    if (data?.data) return data.data
    return data
  },
  onError(error) { console.error('Shipments error:', error) }
})

// ─── Computed ─────────────────────────────────────────────────────────────────
const safeExpressSummary = computed(() => {
  const list = transporterAnalytics.data?.transporters || []
  return list.find(t => String(t.transporter_name || '').toLowerCase().includes('safeexpress')) || null
})

const dsrSummary = computed(() => {
  const list = transporterAnalytics.data?.transporters || []
  return list.find(t => String(t.transporter_name || '').toLowerCase().includes('dsr')) || null
})

const transporters = computed(() => {
  if (!dashboardSummary.data?.metrics?.transporter_breakdown) return []
  return Object.keys(dashboardSummary.data.metrics.transporter_breakdown)
})

// ─── Sync triggers ────────────────────────────────────────────────────────────
const safexpressLookbackDays = ref(20)
const triggerState = ref({
  dsr:         { loading: false, message: '' },
  safeexpress: { loading: false, message: '' }
})

const showReportPanel = ref(false)
const reportDateRange = ref({
  start_date: shipmentFilters.value.start_date,
  end_date:   shipmentFilters.value.end_date,
})
const reportState = ref({ loading: false, message: '', error: false })

async function runDsrTrigger() {
  if (triggerState.value.dsr.loading) return
  triggerState.value.dsr.loading = true
  triggerState.value.dsr.message = ''
  try {
    const res = await frappeCall(APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.TRIGGER_DSR_POD, {})
    const payload = res?.message || res?.data?.message || res?.data || res
    if (payload?.status === 'error' || payload?.error) throw new Error(payload?.error || 'DSR trigger failed')
    triggerState.value.dsr.message = payload?.job_id ? `Queued (${payload.job_id})` : 'Queued'
  } catch (err) {
    triggerState.value.dsr.message = `Error: ${err?.message || String(err)}`
  } finally {
    triggerState.value.dsr.loading = false
  }
}

async function runSafexpressTrigger() {
  if (triggerState.value.safeexpress.loading) return
  triggerState.value.safeexpress.loading = true
  triggerState.value.safeexpress.message = ''
  try {
    const res = await frappeCall(APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.TRIGGER_SAFEXPRESS_POD, { days: safexpressLookbackDays.value || 20 })
    const payload = res?.message || res?.data?.message || res?.data || res
    if (payload?.status === 'error' || payload?.error) throw new Error(payload?.error || 'SafeExpress trigger failed')
    triggerState.value.safeexpress.message = payload?.job_id ? `Queued (${payload.job_id})` : 'Queued'
  } catch (err) {
    triggerState.value.safeexpress.message = `Error: ${err?.message || String(err)}`
  } finally {
    triggerState.value.safeexpress.loading = false
  }
}

async function sendPodReport() {
  if (reportState.value.loading) return
  reportState.value.loading = true
  reportState.value.message = ''
  reportState.value.error   = false
  try {
    const res = await frappeCall(APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.SEND_REPORT, {
      start_date: reportDateRange.value.start_date || null,
      end_date:   reportDateRange.value.end_date   || null,
    })
    const payload = res?.message || res?.data?.message || res?.data || res
    if (payload?.status === 'error' || payload?.error) throw new Error(payload?.error || 'Failed to queue report')
    reportState.value.message = payload?.job_id ? `Queued (${payload.job_id})` : 'Report queued'
  } catch (err) {
    reportState.value.error   = true
    reportState.value.message = `Error: ${err?.message || String(err)}`
  } finally {
    reportState.value.loading = false
  }
}

// ─── Data loading ─────────────────────────────────────────────────────────────
async function fetchSummary() {
  dashboardSummary.loading = true
  dashboardSummary.error = null
  try {
    const res = await frappeCall(
      APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.GET_SUMMARY,
      { filters: getShipmentFilters() }
    )
    const payload = res?.message || res?.data?.message || res?.data || res
    dashboardSummary.data = payload
  } catch (err) {
    dashboardSummary.error = err
    console.error('Dashboard summary error:', err)
  } finally {
    dashboardSummary.loading = false
  }
}

async function fetchTransporterAnalytics() {
  transporterAnalytics.loading = true
  try {
    const res = await frappeCall(
      APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.GET_TRANSPORTER_ANALYTICS,
      { filters: getShipmentFilters() }
    )
    const payload = res?.message || res?.data?.message || res?.data || res
    transporterAnalytics.data = payload
  } catch (err) {
    console.error('Transporter analytics error:', err)
  } finally {
    transporterAnalytics.loading = false
  }
}

async function fetchChartData() {
  chartData.loading = true
  try {
    const res = await frappeCall(
      APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.GET_CHART_DATA,
      { filters: getShipmentFilters(), chart_type: 'shipments', days: 30 }
    )
    const payload = res?.message || res?.data?.message || res?.data || res
    chartData.data = payload
    if (showCharts.value) initAllCharts()
  } catch (err) {
    console.error('Chart data error:', err)
  } finally {
    chartData.loading = false
  }
}

async function fetchShipments(page = 1) {
  try {
    shipmentsData.loading = true
    const res = await frappeCall(APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.GET_SHIPMENTS, {
      filters: getShipmentFilters(),
      page,
      page_size: 50
    })
    const payload = res?.message || res?.data?.message || res?.data || res
    const hasShape = payload && typeof payload === 'object' && 'shipments' in payload && 'total_count' in payload
    if (!hasShape) {
      shipmentsData.data = { shipments: [], total_count: 0, has_more: false }
      return
    }
    shipmentsData.data = payload
  } catch (err) {
    console.error('Error loading shipments:', err)
    shipmentsData.data = null
  } finally {
    shipmentsData.loading = false
  }
}

function loadShipments() {
  currentPage.value = 1
  fetchShipments(1)
  fetchSummary()
  fetchTransporterAnalytics()
  fetchChartData()
}

function goToPreviousPage() {
  if (currentPage.value > 1 && !shipmentsData.loading) {
    currentPage.value--
    fetchShipments(currentPage.value)
  }
}

function goToNextPage() {
  if (shipmentsData.data?.has_more && !shipmentsData.loading) {
    currentPage.value++
    fetchShipments(currentPage.value)
  }
}

async function refreshAll() {
  fetchSummary()
  fetchShipments(currentPage.value)
  fetchTransporterAnalytics()
  fetchChartData()
}

async function exportData() {
  try {
    const result = await frappeCall(APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.EXPORT_DATA, {
      filters: getShipmentFilters(),
      format: 'csv',
      export_type: 'shipments'
    })
    if (result.status === 'success' && result.file_url) {
      window.open(window.location.origin + result.file_url, '_blank')
      window.showGlobalSuccess?.('Data exported successfully')
    } else {
      window.showGlobalError?.(result.error || 'Failed to export data')
    }
  } catch (error) {
    window.showGlobalError?.('Failed to export data: ' + (error.message || error))
  }
}

// ─── Charts ───────────────────────────────────────────────────────────────────
let shipmentVolumeChartInstance = null
let podStatusChartInstance      = null
const shipmentVolumeChart = ref(null)
const podStatusChart      = ref(null)

function initShipmentVolumeChart() {
  if (!shipmentVolumeChart.value?.getContext || !chartData.data?.labels) return
  const ctx = shipmentVolumeChart.value.getContext('2d')
  if (!ctx) return
  shipmentVolumeChartInstance?.destroy()
  shipmentVolumeChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartData.data.labels || [],
      datasets: [
        { label: 'Total Invoices', data: chartData.data.datasets?.total || [],         borderColor: 'rgb(59,130,246)',  backgroundColor: 'rgba(59,130,246,0.1)',  tension: 0.4 },
        { label: 'POD Completed',  data: chartData.data.datasets?.pod_completed || [], borderColor: 'rgb(34,197,94)',   backgroundColor: 'rgba(34,197,94,0.1)',   tension: 0.4 },
        { label: 'POD Pending',    data: chartData.data.datasets?.pod_pending || [],   borderColor: 'rgb(234,179,8)',   backgroundColor: 'rgba(234,179,8,0.1)',   tension: 0.4 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      elements: { point: { radius: 0 } },
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top' } },
      scales: { y: { beginAtZero: true }, x: { ticks: { maxTicksLimit: 12 } } }
    }
  })
}

function initPODStatusChart() {
  if (!podStatusChart.value?.getContext) return
  const ctx = podStatusChart.value.getContext('2d')
  if (!ctx) return
  podStatusChartInstance?.destroy()
  frappeCall(APP_CONFIG.API_ENDPOINTS.LOGISTICS_DASHBOARD.GET_CHART_DATA, {
    filters: getShipmentFilters(),
    chart_type: 'pod_status',
    days: 30
  }).then(data => {
    if (!data || data.error) return
    podStatusChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.labels || [],
        datasets: [{ data: data.values || [], backgroundColor: ['rgba(34,197,94,0.8)', 'rgba(234,179,8,0.8)', 'rgba(239,68,68,0.8)', 'rgba(107,114,128,0.8)'] }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
    })
  }).catch(err => console.error('POD status chart error:', err))
}

function initAllCharts() {
  nextTick(() => {
    initShipmentVolumeChart()
    initPODStatusChart()
  })
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getCoverageColor(rate) {
  if (rate == null) return 'text-gray-400'
  if (rate >= 90)   return 'text-green-600'
  if (rate >= 70)   return 'text-amber-500'
  return 'text-red-500'
}

function getCoverageBarColor(rate) {
  if (rate == null) return 'bg-gray-300'
  if (rate >= 90)   return 'bg-green-500'
  if (rate >= 70)   return 'bg-amber-400'
  return 'bg-red-500'
}

function formatDate(dateStr) {
  if (!dateStr) return '–'
  try { return new Date(dateStr).toLocaleDateString() } catch { return dateStr }
}

// ─── Chart data watcher ───────────────────────────────────────────────────────
watch(() => chartData.data, () => {
  if (chartData.data && !chartData.loading && showCharts.value) initAllCharts()
})

// Open charts and re-init when user expands the section
watch(showCharts, (open) => {
  if (open) setTimeout(() => initAllCharts(), 150)
})

// ─── Mount ────────────────────────────────────────────────────────────────────
onMounted(() => {
  fetchSummary()
  fetchShipments(1)
  fetchTransporterAnalytics()
  fetchChartData()
})
</script>
