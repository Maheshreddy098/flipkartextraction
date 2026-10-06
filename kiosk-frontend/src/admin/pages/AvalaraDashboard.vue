<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Avalara Integration Dashboard</h1>
      <div class="flex gap-2">
        <button
          @click="refreshAll"
          :disabled="dashboardSummary.loading"
          class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ dashboardSummary.loading ? 'Refreshing...' : 'Refresh' }}
        </button>
        <button
          v-if="viewMode === 'transactions'"
          @click="showSyncDialog = true"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Trigger Sync
        </button>
        <button
          v-if="viewMode === 'credit_notes'"
          @click="showSyncCreditNotesDialog = true"
          class="px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700"
        >
          Sync Credit Notes
        </button>
      </div>
    </div>

    <!-- Prominent View Mode Selector -->
    <div v-if="dashboardSummary.data && !dashboardSummary.error" class="bg-gradient-to-r from-blue-50 to-pink-50 border-2 border-blue-200 rounded-lg shadow-lg p-6 mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
          <span class="text-lg font-semibold text-gray-800">View Mode:</span>
          <div class="flex bg-white rounded-lg p-1 shadow-md">
            <button
              @click="viewMode = 'transactions'"
              :class="[
                'px-6 py-3 text-sm font-semibold rounded-md transition-all duration-200',
                viewMode === 'transactions'
                  ? 'bg-blue-600 text-white shadow-lg transform scale-105'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              ]"
            >
              <span class="flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Transactions
              </span>
            </button>
            <button
              @click="viewMode = 'credit_notes'"
              :class="[
                'px-6 py-3 text-sm font-semibold rounded-md transition-all duration-200',
                viewMode === 'credit_notes'
                  ? 'bg-pink-600 text-white shadow-lg transform scale-105'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              ]"
            >
              <span class="flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Credit Notes
              </span>
            </button>
          </div>
        </div>
        <div class="text-sm text-gray-600 font-medium">
          <span v-if="viewMode === 'transactions'">Viewing transactions</span>
          <span v-else>Viewing credit notes</span>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="dashboardSummary.loading && !dashboardSummary.data" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
        <p class="text-gray-600">Loading dashboard...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="dashboardSummary.error" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <div class="flex items-center">
        <svg class="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
        </svg>
        <p class="text-sm text-red-600">
          Failed to load dashboard data: {{ dashboardSummary.error?.message || dashboardSummary.error }}
        </p>
      </div>
    </div>

    <!-- TRANSACTIONS SECTION -->
    <div v-if="viewMode === 'transactions' && dashboardSummary.data && !dashboardSummary.error" class="mb-8">
      <div class="flex items-center mb-4">
        <div class="flex-1 border-t-2 border-blue-500"></div>
        <h2 class="px-4 text-2xl font-bold text-blue-700 flex items-center gap-2">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Transactions
        </h2>
        <div class="flex-1 border-t-2 border-blue-500"></div>
      </div>

    <!-- Transaction Metrics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6">
      <!-- Total Transactions -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Total Transactions</p>
        </div>
        <div class="mt-1">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ dashboardSummary.data?.metrics?.total_transactions?.all_time || 0 }}
          </h3>
          <p class="text-xs text-gray-500 mt-1">
            All transactions from SAP
          </p>
        </div>
      </div>

      <!-- Success Rate -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Overall Success Rate</p>
        </div>
        <div class="mt-1 flex items-center gap-x-2">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ (dashboardSummary.data?.metrics?.success_rate?.all_time || 0).toFixed(1) }}%
          </h3>
          <span :class="getSuccessRateColor(dashboardSummary.data?.metrics?.success_rate?.all_time)">
            <svg class="inline-block w-4 h-4" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <template v-if="(dashboardSummary.data?.metrics?.success_rate?.all_time || 0) >= 95">
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                <polyline points="16 7 22 7 22 13" />
              </template>
              <template v-else>
                <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
                <polyline points="16 17 22 17 22 11" />
              </template>
            </svg>
          </span>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          Overall success rate
        </p>
      </div>

      <!-- Total Batches -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Total Batches</p>
        </div>
        <div class="mt-1">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ dashboardSummary.data?.metrics?.status_breakdown?.all_time?.total || 0 }}
          </h3>
          <p class="text-xs text-gray-500 mt-1">All sync batches</p>
        </div>
      </div>

      <!-- System Health -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">System Health</p>
        </div>
        <div class="mt-1 flex items-center gap-x-2">
          <h3 class="text-xl sm:text-2xl font-medium" :class="getHealthColor(dashboardSummary.data?.metrics?.system_health)">
            {{ (dashboardSummary.data?.metrics?.system_health || 'Unknown').toUpperCase() }}
          </h3>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          Active Jobs: {{ dashboardSummary.data?.metrics?.active_jobs_count || 0 }}
        </p>
      </div>
    </div>

    <!-- Transaction Status Breakdown Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      <!-- Posted to Avalara -->
      <div class="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-green-700 font-semibold">Posted to Avalara</p>
          <svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-green-800 mb-1">
          {{ dashboardSummary.data?.metrics?.status_breakdown?.all_time?.posted || 0 }}
        </h3>
        <p class="text-xs text-green-600">
          Total posted to Avalara
        </p>
      </div>

      <!-- Not Posted -->
      <div class="bg-gradient-to-br from-yellow-50 to-yellow-100 border border-yellow-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-yellow-700 font-semibold">Not Posted</p>
          <svg class="w-5 h-5 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-yellow-800 mb-1">
          {{ dashboardSummary.data?.metrics?.status_breakdown?.all_time?.not_posted || 0 }}
        </h3>
        <p class="text-xs text-yellow-600">
          Total not posted
        </p>
      </div>

      <!-- Cancelled -->
      <div class="bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-700 font-semibold">Cancelled</p>
          <svg class="w-5 h-5 text-gray-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-gray-800 mb-1">
          {{ dashboardSummary.data?.metrics?.status_breakdown?.all_time?.cancelled || 0 }}
        </h3>
        <p class="text-xs text-gray-600">
          Total cancelled
        </p>
      </div>

      <!-- Failed -->
      <div class="bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-red-700 font-semibold">Failed</p>
          <svg class="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-red-800 mb-1">
          {{ dashboardSummary.data?.metrics?.status_breakdown?.all_time?.failed || 0 }}
        </h3>
        <p class="text-xs text-red-600">
          Total failed
        </p>
      </div>

      <!-- Pending/Processing -->
      <div class="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-blue-700 font-semibold">Pending</p>
          <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-blue-800 mb-1">
          {{ dashboardSummary.data?.metrics?.status_breakdown?.all_time?.pending || 0 }}
        </h3>
        <p class="text-xs text-blue-600">
          Total pending
        </p>
      </div>

      <!-- Unposted from SAP -->
      <div class="bg-gradient-to-br from-indigo-50 to-indigo-100 border border-indigo-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-indigo-700 font-semibold">Unposted from SAP</p>
          <svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-indigo-800 mb-1">
          {{ dashboardSummary.data?.metrics?.unposted_from_sap || 0 }}
        </h3>
        <p class="text-xs text-indigo-600">
          Invoices in SAP not posted to Avalara
        </p>
      </div>
    </div>

    <!-- Transaction Action Buttons Section -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Transaction Actions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <button
          @click="showSyncDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span class="text-xs font-medium">Sync</span>
        </button>
        <button
          @click="showFetchDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span class="text-xs font-medium">Fetch</span>
        </button>
        <button
          @click="showPostDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <span class="text-xs font-medium">Post</span>
        </button>
        <button
          @click="showRetryDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span class="text-xs font-medium">Retry</span>
        </button>
        <button
          @click="showBulkDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span class="text-xs font-medium">Bulk Ops</span>
        </button>
        <button
          @click="exportData"
          class="flex flex-col items-center justify-center px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="text-xs font-medium">Export</span>
        </button>
      </div>
    </div>

    <!-- Transaction Charts Section -->
    <div v-if="chartData.data" class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <!-- Success Rate Over Time Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Success Rate Trend (Last 30 Days)</h3>
        <div class="h-64">
          <canvas ref="successRateChart"></canvas>
        </div>
      </div>

      <!-- Transaction Volume Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Transaction Volume (Last 30 Days)</h3>
        <div class="h-64">
          <canvas ref="volumeChart"></canvas>
        </div>
      </div>

      <!-- Status Distribution Pie Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Status Distribution (Last 30 Days)</h3>
        <div class="h-64">
          <canvas ref="statusPieChart"></canvas>
        </div>
      </div>

      <!-- Daily Transactions Bar Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Daily Transactions Breakdown</h3>
        <div class="h-64">
          <canvas ref="dailyBarChart"></canvas>
        </div>
      </div>
    </div>
    </div>

    <!-- CREDIT NOTES SECTION -->
    <div v-if="viewMode === 'credit_notes' && dashboardSummary.data && !dashboardSummary.error" class="mb-8">
      <div class="flex items-center mb-4">
        <div class="flex-1 border-t-2 border-pink-500"></div>
        <h2 class="px-4 text-2xl font-bold text-pink-700 flex items-center gap-2">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Credit Notes
        </h2>
        <div class="flex-1 border-t-2 border-pink-500"></div>
      </div>

    <!-- Credit Note Metrics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6">
      <!-- Total Credit Notes -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Total Credit Notes</p>
        </div>
        <div class="mt-1">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ dashboardSummary.data?.metrics?.total_credit_notes?.all_time || 0 }}
          </h3>
          <p class="text-xs text-gray-500 mt-1">
            All credit notes from SAP
          </p>
        </div>
      </div>

      <!-- Credit Note Success Rate -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Credit Note Success Rate</p>
        </div>
        <div class="mt-1 flex items-center gap-x-2">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ (dashboardSummary.data?.metrics?.credit_note_success_rate?.all_time || 0).toFixed(1) }}%
          </h3>
          <span :class="getSuccessRateColor(dashboardSummary.data?.metrics?.credit_note_success_rate?.all_time)">
            <svg class="inline-block w-4 h-4" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <template v-if="(dashboardSummary.data?.metrics?.credit_note_success_rate?.all_time || 0) >= 95">
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                <polyline points="16 7 22 7 22 13" />
              </template>
              <template v-else>
                <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
                <polyline points="16 17 22 17 22 11" />
              </template>
            </svg>
          </span>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          Overall success rate
        </p>
      </div>

      <!-- Total Refund Batches -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Total Refund Batches</p>
        </div>
        <div class="mt-1">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ dashboardSummary.data?.metrics?.total_refund_batches?.all_time || 0 }}
          </h3>
          <p class="text-xs text-gray-500 mt-1">All refund batches</p>
        </div>
      </div>

      <!-- Unposted Credit Notes from SAP -->
      <div class="bg-white border rounded-lg shadow-sm p-5">
        <div class="flex items-center gap-x-2 mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-500">Unposted from SAP</p>
        </div>
        <div class="mt-1">
          <h3 class="text-xl sm:text-2xl font-medium text-gray-800">
            {{ dashboardSummary.data?.metrics?.unposted_credit_notes_from_sap || 0 }}
          </h3>
          <p class="text-xs text-gray-500 mt-1">Credit notes not posted to Avalara</p>
        </div>
      </div>
    </div>

    <!-- Credit Note Status Breakdown Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      <!-- Posted to Avalara -->
      <div class="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-green-700 font-semibold">Posted to Avalara</p>
          <svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-green-800 mb-1">
          {{ dashboardSummary.data?.metrics?.credit_note_status_breakdown?.all_time?.posted || 0 }}
        </h3>
        <p class="text-xs text-green-600">
          Total posted to Avalara
        </p>
      </div>

      <!-- Not Posted -->
      <div class="bg-gradient-to-br from-yellow-50 to-yellow-100 border border-yellow-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-yellow-700 font-semibold">Not Posted</p>
          <svg class="w-5 h-5 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-yellow-800 mb-1">
          {{ dashboardSummary.data?.metrics?.credit_note_status_breakdown?.all_time?.not_posted || 0 }}
        </h3>
        <p class="text-xs text-yellow-600">
          Total not posted
        </p>
      </div>

      <!-- Cancelled -->
      <div class="bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-gray-700 font-semibold">Cancelled</p>
          <svg class="w-5 h-5 text-gray-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-gray-800 mb-1">
          {{ dashboardSummary.data?.metrics?.credit_note_status_breakdown?.all_time?.cancelled || 0 }}
        </h3>
        <p class="text-xs text-gray-600">
          Total cancelled
        </p>
      </div>

      <!-- Failed -->
      <div class="bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-red-700 font-semibold">Failed</p>
          <svg class="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-red-800 mb-1">
          {{ dashboardSummary.data?.metrics?.credit_note_status_breakdown?.all_time?.failed || 0 }}
        </h3>
        <p class="text-xs text-red-600">
          Total failed
        </p>
      </div>

      <!-- Pending/Processing -->
      <div class="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-lg shadow-sm p-5">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wide text-blue-700 font-semibold">Pending</p>
          <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 class="text-2xl font-bold text-blue-800 mb-1">
          {{ dashboardSummary.data?.metrics?.credit_note_status_breakdown?.all_time?.pending || 0 }}
        </h3>
        <p class="text-xs text-blue-600">
          Total pending
        </p>
      </div>
    </div>

    <!-- Credit Note Action Buttons Section -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Credit Note Actions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-4 gap-3">
        <button
          @click="showFetchCreditNotesDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span class="text-xs font-medium">Fetch Credit Notes</span>
        </button>
        <button
          @click="showSyncCreditNotesDialog = true"
          class="flex flex-col items-center justify-center px-4 py-3 bg-pink-600 text-white rounded-lg hover:bg-pink-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span class="text-xs font-medium">Sync Credit Notes</span>
        </button>
        <button
          @click="exportData"
          class="flex flex-col items-center justify-center px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="text-xs font-medium">Export</span>
        </button>
        <button
          @click="refreshAll"
          :disabled="dashboardSummary.loading"
          class="flex flex-col items-center justify-center px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          <svg class="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span class="text-xs font-medium">Refresh</span>
        </button>
      </div>
    </div>

    <!-- Credit Note Charts Section -->
    <div v-if="creditNoteChartData.data" class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <!-- Credit Note Success Rate Over Time Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Credit Note Success Rate Trend (Last 30 Days)</h3>
        <div class="h-64">
          <canvas ref="creditNoteSuccessRateChart"></canvas>
        </div>
      </div>

      <!-- Credit Note Volume Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Credit Note Volume (Last 30 Days)</h3>
        <div class="h-64">
          <canvas ref="creditNoteVolumeChart"></canvas>
        </div>
      </div>

      <!-- Credit Note Status Distribution Pie Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Credit Note Status Distribution (Last 30 Days)</h3>
        <div class="h-64">
          <canvas ref="creditNoteStatusPieChart"></canvas>
        </div>
      </div>

      <!-- Daily Credit Notes Bar Chart -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Daily Credit Notes Breakdown</h3>
        <div class="h-64">
          <canvas ref="creditNoteDailyBarChart"></canvas>
        </div>
      </div>
      </div>
    </div>

    <!-- Tabs Navigation -->
    <div v-if="dashboardSummary.data && !dashboardSummary.error" class="bg-white rounded-lg shadow-sm mb-6">
      <div class="border-b border-gray-200">
        <nav class="flex flex-wrap -mb-px">
          <!-- Transactions Section -->
          <template v-if="viewMode === 'transactions'">
            <div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider border-r border-gray-200">
              Transactions
            </div>
          <button
              v-for="tab in transactionTabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :class="[
              'px-6 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            {{ tab.label }}
          </button>
          </template>

          <!-- Credit Notes Section -->
          <template v-if="viewMode === 'credit_notes'">
            <div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider border-r border-gray-200">
              Credit Notes
            </div>
            <button
              v-for="tab in creditNoteTabs"
              :key="tab.id"
              @click="activeTab = tab.id"
              :class="[
                'px-6 py-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-pink-500 text-pink-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              ]"
            >
              {{ tab.label }}
            </button>
          </template>

        </nav>
      </div>

      <!-- Sync Batches Tab -->
      <div v-show="activeTab === 'batches' && viewMode === 'transactions'" class="p-6">
        <!-- Filters -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            v-model="batchFilters.search"
            type="text"
            placeholder="Search Batch ID..."
            @input="debounceLoadBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            v-model="batchFilters.status"
            @change="loadBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Status</option>
            <option value="Completed">Completed</option>
            <option value="Partial">Partial</option>
            <option value="Failed">Failed</option>
            <option value="In Progress">In Progress</option>
          </select>
          <input
            v-model="batchFilters.from_date"
            type="date"
            @change="loadBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="batchFilters.to_date"
            type="date"
            @change="loadBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- Table -->
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Batch ID</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date Range</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Successful</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Failed</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-if="syncBatches.loading">
                <td colspan="8" class="px-6 py-4 text-center text-gray-500">Loading...</td>
              </tr>
              <tr v-else-if="!syncBatches.data?.batches || syncBatches.data.batches.length === 0">
                <td colspan="8" class="px-6 py-4 text-center text-gray-500">No batches found</td>
              </tr>
              <tr v-else v-for="batch in syncBatches.data.batches" :key="batch.name" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ batch.name }}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span :class="getStatusBadgeClass(batch.status)" class="px-2 py-1 text-xs font-medium rounded-full">
                    {{ batch.status }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDateRange(batch.from_date, batch.to_date) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ batch.total_invoices || 0 }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-green-600">{{ batch.successful_count || 0 }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600">{{ batch.failed_count || 0 }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(batch.creation) }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    @click="viewBatchDetails(batch)"
                    class="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    View
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="syncBatches.data?.total_count > 0" class="mt-4 flex items-center justify-between">
          <div class="text-sm text-gray-700">
            Showing {{ (syncBatches.data?.start || 0) + 1 }} to
            {{ Math.min((syncBatches.data?.start || 0) + (syncBatches.data?.page_length || 20), syncBatches.data?.total_count) }} of
            {{ syncBatches.data?.total_count }}
          </div>
          <div class="flex gap-2">
            <button
              @click="loadBatches((syncBatches.data?.start || 0) - (syncBatches.data?.page_length || 20))"
              :disabled="(syncBatches.data?.start || 0) <= 0"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              @click="loadBatches((syncBatches.data?.start || 0) + (syncBatches.data?.page_length || 20))"
              :disabled="!syncBatches.data?.has_more"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <!-- Refund Batches Tab -->
      <div v-show="activeTab === 'refund_batches' && viewMode === 'credit_notes'" class="p-6">
        <!-- Filters -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            v-model="refundBatchFilters.search"
            type="text"
            placeholder="Search Batch ID..."
            @input="debounceLoadRefundBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            v-model="refundBatchFilters.status"
            @change="loadRefundBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Status</option>
            <option value="Completed">Completed</option>
            <option value="Partial">Partial</option>
            <option value="Failed">Failed</option>
            <option value="In Progress">In Progress</option>
          </select>
          <input
            v-model="refundBatchFilters.from_date"
            type="date"
            @change="loadRefundBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="refundBatchFilters.to_date"
            type="date"
            @change="loadRefundBatches"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- Table -->
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Batch ID</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date Range</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Successful</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Failed</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-if="refundBatches.loading">
                <td colspan="8" class="px-6 py-4 text-center text-gray-500">Loading...</td>
              </tr>
              <tr v-else-if="!refundBatches.data?.batches || refundBatches.data.batches.length === 0">
                <td colspan="8" class="px-6 py-4 text-center text-gray-500">No refund batches found</td>
              </tr>
              <tr v-else v-for="batch in refundBatches.data.batches" :key="batch.name" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ batch.batch_id || batch.name }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDateRange(batch.from_date, batch.to_date) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span :class="getStatusBadgeClass(batch.status)" class="px-2 py-1 text-xs font-medium rounded-full">
                    {{ batch.status }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ batch.total_credit_notes || 0 }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-green-600">{{ batch.successful_count || 0 }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600">{{ batch.failed_count || 0 }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(batch.creation) }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    @click="viewRefundBatchDetails(batch)"
                    class="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    View
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="refundBatches.data?.total_count > 0" class="mt-4 flex items-center justify-between">
          <div class="text-sm text-gray-700">
            Showing {{ (refundBatches.data?.start || 0) + 1 }} to
            {{ Math.min((refundBatches.data?.start || 0) + (refundBatches.data?.page_length || 20), refundBatches.data?.total_count) }} of
            {{ refundBatches.data?.total_count }}
          </div>
          <div class="flex gap-2">
            <button
              @click="loadRefundBatches((refundBatches.data?.start || 0) - (refundBatches.data?.page_length || 20))"
              :disabled="(refundBatches.data?.start || 0) <= 0"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              @click="loadRefundBatches((refundBatches.data?.start || 0) + (refundBatches.data?.page_length || 20))"
              :disabled="!refundBatches.data?.has_more"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <!-- Refund Logs Tab -->
      <div v-show="activeTab === 'refund_logs' && viewMode === 'credit_notes'" class="p-6">
        <!-- Filters -->
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <input
            v-model="refundLogFilters.search"
            type="text"
            placeholder="Search SAP Doc Num..."
            @input="debounceLoadRefundLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            v-model="refundLogFilters.status"
            @change="loadRefundLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Status</option>
            <option value="Success">Success</option>
            <option value="Failed">Failed</option>
            <option value="Pending">Pending</option>
            <option value="Retrying">Retrying</option>
          </select>
          <input
            v-model="refundLogFilters.batch_id"
            type="text"
            placeholder="Batch ID"
            @input="debounceLoadRefundLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="refundLogFilters.from_date"
            type="date"
            @change="loadRefundLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="refundLogFilters.to_date"
            type="date"
            @change="loadRefundLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- Table -->
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Refund ID</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">SAP Doc Num</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Original Transaction</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Refund Transaction ID</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tax Amount</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error Message</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-if="refundLogs.loading">
                <td colspan="9" class="px-6 py-4 text-center text-gray-500">Loading...</td>
              </tr>
              <tr v-else-if="!refundLogs.data?.refund_logs || refundLogs.data.refund_logs.length === 0">
                <td colspan="9" class="px-6 py-4 text-center text-gray-500">No refund logs found</td>
              </tr>
              <tr v-else v-for="log in refundLogs.data.refund_logs" :key="log.name" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ log.name }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ log.sap_doc_num || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span :class="getStatusBadgeClass(log.status)" class="px-2 py-1 text-xs font-medium rounded-full">
                    {{ log.status }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ log.original_transaction_code || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ log.refund_transaction_id || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ formatCurrency(log.avalara_total_tax) }}</td>
                <td class="px-6 py-4 text-sm text-gray-500" :title="log.error_message">
                  {{ truncate(log.error_message, 50) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(log.creation) }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    @click="viewRefundLogDetails(log)"
                    class="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    View
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="refundLogs.data?.total_count > 0" class="mt-4 flex items-center justify-between">
          <div class="text-sm text-gray-700">
            Showing {{ (refundLogs.data?.start || 0) + 1 }} to
            {{ Math.min((refundLogs.data?.start || 0) + (refundLogs.data?.page_length || 20), refundLogs.data?.total_count) }} of
            {{ refundLogs.data?.total_count }}
          </div>
          <div class="flex gap-2">
            <button
              @click="loadRefundLogs((refundLogs.data?.start || 0) - (refundLogs.data?.page_length || 20))"
              :disabled="(refundLogs.data?.start || 0) <= 0"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              @click="loadRefundLogs((refundLogs.data?.start || 0) + (refundLogs.data?.page_length || 20))"
              :disabled="!refundLogs.data?.has_more"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <!-- Transaction Logs Tab -->
      <div v-show="activeTab === 'logs' && viewMode === 'transactions'" class="p-6">
        <!-- Filters -->
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <input
            v-model="logFilters.search"
            type="text"
            placeholder="Search SAP Doc Num..."
            @input="debounceLoadLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            v-model="logFilters.status"
            @change="loadLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Status</option>
            <option value="Success">Success</option>
            <option value="Failed">Failed</option>
            <option value="Pending">Pending</option>
          </select>
          <input
            v-model="logFilters.batch_id"
            type="text"
            placeholder="Batch ID"
            @input="debounceLoadLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="logFilters.from_date"
            type="date"
            @change="loadLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="logFilters.to_date"
            type="date"
            @change="loadLogs"
            class="px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- Table -->
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Transaction ID</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">SAP Doc Num</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Avalara Doc Code</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tax Amount</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error Message</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-if="transactionLogs.loading">
                <td colspan="8" class="px-6 py-4 text-center text-gray-500">Loading...</td>
              </tr>
              <tr v-else-if="!transactionLogs.data?.transaction_logs || transactionLogs.data.transaction_logs.length === 0">
                <td colspan="8" class="px-6 py-4 text-center text-gray-500">No transaction logs found</td>
              </tr>
              <tr v-else v-for="log in transactionLogs.data.transaction_logs" :key="log.name" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ log.name }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ log.sap_doc_num || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span :class="getStatusBadgeClass(log.status)" class="px-2 py-1 text-xs font-medium rounded-full">
                    {{ log.status }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ log.avalara_doc_code || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ formatCurrency(log.tax_amount) }}</td>
                <td class="px-6 py-4 text-sm text-gray-500" :title="log.error_message">
                  {{ truncate(log.error_message, 50) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(log.creation) }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                  <div class="flex gap-2">
                    <button
                      @click="viewLogDetails(log)"
                      class="text-blue-600 hover:text-blue-800 text-sm"
                    >
                      View
                    </button>
                    <button
                      v-if="log.status === 'Failed'"
                      @click="retryTransaction(log)"
                      class="text-yellow-600 hover:text-yellow-800 text-sm"
                    >
                      Retry
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="transactionLogs.data?.total_count > 0" class="mt-4 flex items-center justify-between">
          <div class="text-sm text-gray-700">
            Showing {{ (transactionLogs.data?.start || 0) + 1 }} to
            {{ Math.min((transactionLogs.data?.start || 0) + (transactionLogs.data?.page_length || 20), transactionLogs.data?.total_count) }} of
            {{ transactionLogs.data?.total_count }}
          </div>
          <div class="flex gap-2">
            <button
              @click="loadLogs((transactionLogs.data?.start || 0) - (transactionLogs.data?.page_length || 20))"
              :disabled="(transactionLogs.data?.start || 0) <= 0"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              @click="loadLogs((transactionLogs.data?.start || 0) + (transactionLogs.data?.page_length || 20))"
              :disabled="!transactionLogs.data?.has_more"
              class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
          </div>
        </div>
      </div>

    <!-- Sync Dialog -->
    <div v-if="showSyncDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showSyncDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Trigger Manual Sync</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">From Date</label>
            <input v-model="syncForm.from_date" type="date" required class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">To Date</label>
            <input v-model="syncForm.to_date" type="date" required class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div class="flex items-center">
            <input
              v-model="syncForm.commit"
              type="checkbox"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label class="ml-2 text-sm text-gray-700">Commit transactions in Avalara</label>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showSyncDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="triggerSync"
            :disabled="syncing"
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ syncing ? 'Processing...' : 'Start Sync' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Fetch Dialog -->
    <div v-if="showFetchDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showFetchDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Fetch Invoices from SAP</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">From Date</label>
            <input v-model="fetchForm.from_date" type="date" required class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">To Date</label>
            <input v-model="fetchForm.to_date" type="date" required class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Limit (max invoices)</label>
            <input v-model.number="fetchForm.top" type="number" min="1" max="1000" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showFetchDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="triggerFetch"
            :disabled="fetching"
            class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ fetching ? 'Fetching...' : 'Fetch' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Post Dialog -->
    <div v-if="showPostDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showPostDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Post Transactions to Avalara</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Transaction IDs (comma-separated)</label>
            <textarea v-model="postForm.transaction_ids" rows="4" placeholder="Enter transaction log names or SAP doc numbers, one per line" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-purple-500"></textarea>
            <p class="text-xs text-gray-500 mt-1">Enter transaction log names (e.g., KFI2526-12345) or leave empty to post all pending</p>
          </div>
          <div class="flex items-center">
            <input
              v-model="postForm.commit"
              type="checkbox"
              class="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
            />
            <label class="ml-2 text-sm text-gray-700">Commit transactions in Avalara</label>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showPostDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="triggerPost"
            :disabled="posting"
            class="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ posting ? 'Posting...' : 'Post' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Retry Dialog -->
    <div v-if="showRetryDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showRetryDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Retry Failed Transactions</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Batch ID (optional)</label>
            <input v-model="retryForm.batch_id" type="text" placeholder="Leave empty to retry all failed" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Limit (max transactions)</label>
            <input v-model.number="retryForm.limit" type="number" min="1" max="500" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500" />
          </div>
          <div class="bg-orange-50 border border-orange-200 rounded-md p-3">
            <p class="text-sm text-orange-800">
              This will retry all failed transactions. Make sure the issues that caused the failures have been resolved.
            </p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showRetryDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="triggerRetry"
            :disabled="retrying"
            class="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ retrying ? 'Retrying...' : 'Retry' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bulk Ops Dialog -->
    <div v-if="showBulkDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showBulkDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Bulk Operations</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Operation</label>
            <select v-model="bulkForm.operation" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="retry_failed">Retry Failed Transactions</option>
              <option value="post_pending">Post Pending Transactions</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Limit (max records)</label>
            <input v-model.number="bulkForm.limit" type="number" min="1" max="500" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showBulkDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="triggerBulkOps"
            :disabled="bulkProcessing"
            class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ bulkProcessing ? 'Processing...' : 'Execute' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Fetched Invoices Dialog -->
    <div v-if="showFetchedInvoices" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showFetchedInvoices = false">
      <div class="bg-white rounded-lg shadow-xl max-w-6xl w-full m-4 max-h-[90vh] flex flex-col">
        <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 class="text-lg font-semibold text-gray-900">Fetched Invoices from SAP</h3>
          <button
            @click="showFetchedInvoices = false"
            class="text-gray-400 hover:text-gray-600"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="px-6 py-4 overflow-auto flex-1">
          <div v-if="fetchedInvoices.length === 0" class="text-center py-8 text-gray-500">
            No invoices fetched
          </div>
          <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocNum</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocDate</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CardCode</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CardName</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocTotal</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocStatus</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="(invoice, index) in fetchedInvoices" :key="index" class="hover:bg-gray-50">
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ invoice.DocNum || invoice.DocEntry || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ invoice.DocDate || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ invoice.CardCode || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ invoice.CardName || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ invoice.DocTotal ? invoice.DocTotal.toFixed(2) : '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span :class="getInvoiceStatusBadgeClass(invoice.DocStatus || 'O')" class="px-2 py-1 text-xs font-medium rounded-full">
                      {{ invoice.DocStatus === 'C' ? 'Closed' : invoice.DocStatus === 'O' ? 'Open' : invoice.DocStatus || 'Unknown' }}
                  </span>
                </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm">
                  <button
                      @click="viewInvoiceDetails(invoice)"
                      class="text-blue-600 hover:text-blue-800"
                  >
                      View Details
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <p class="text-sm text-gray-600">Total: {{ fetchedInvoices.length }} invoices</p>
          <button
            @click="showFetchedInvoices = false"
            class="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            Close
          </button>
              </div>
              </div>
              </div>

    <!-- Fetch Credit Notes Dialog -->
    <div v-if="showFetchCreditNotesDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showFetchCreditNotesDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Fetch Credit Notes from SAP</h3>
            </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">From Date</label>
            <input v-model="fetchCreditNotesForm.from_date" type="date" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">To Date</label>
            <input v-model="fetchCreditNotesForm.to_date" type="date" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Top (max records)</label>
            <input v-model.number="fetchCreditNotesForm.top" type="number" min="1" max="1000" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
            </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showFetchCreditNotesDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="fetchCreditNotes"
            :disabled="fetchingCreditNotes"
            class="px-4 py-2 bg-teal-600 text-white rounded-md hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ fetchingCreditNotes ? 'Fetching...' : 'Fetch' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Sync Credit Notes Dialog -->
    <div v-if="showSyncCreditNotesDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showSyncCreditNotesDialog = false">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full m-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">Sync Credit Notes to Avalara</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">From Date</label>
            <input v-model="syncCreditNotesForm.from_date" type="date" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-pink-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">To Date</label>
            <input v-model="syncCreditNotesForm.to_date" type="date" class="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-pink-500" />
          </div>
          <div class="flex items-center">
            <input
              v-model="syncCreditNotesForm.commit"
              type="checkbox"
              class="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
            />
            <label class="ml-2 text-sm text-gray-700">Commit refund transactions in Avalara</label>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            @click="showSyncCreditNotesDialog = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="syncCreditNotes"
            :disabled="syncingCreditNotes"
            class="px-4 py-2 bg-pink-600 text-white rounded-md hover:bg-pink-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ syncingCreditNotes ? 'Syncing...' : 'Sync' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Fetched Credit Notes Dialog -->
    <div v-if="showFetchedCreditNotes" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showFetchedCreditNotes = false">
      <div class="bg-white rounded-lg shadow-xl max-w-6xl w-full m-4 max-h-[90vh] flex flex-col">
        <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 class="text-lg font-semibold text-gray-900">Fetched Credit Notes from SAP</h3>
          <button
            @click="showFetchedCreditNotes = false"
            class="text-gray-400 hover:text-gray-600"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="px-6 py-4 overflow-auto flex-1">
          <div v-if="fetchedCreditNotes.length === 0" class="text-center py-8 text-gray-500">
            No credit notes fetched
          </div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocNum</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocDate</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CardCode</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CardName</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocTotal</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DocStatus</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="(cn, index) in fetchedCreditNotes" :key="index" class="hover:bg-gray-50">
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ cn.DocNum || cn.DocEntry || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ cn.DocDate || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ cn.CardCode || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ cn.CardName || '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ cn.DocTotal ? cn.DocTotal.toFixed(2) : '-' }}</td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span :class="getInvoiceStatusBadgeClass(cn.DocStatus || 'O')" class="px-2 py-1 text-xs font-medium rounded-full">
                      {{ cn.DocStatus === 'C' ? 'Closed' : cn.DocStatus === 'O' ? 'Open' : cn.DocStatus || 'Unknown' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm">
                    <button
                      @click="viewCreditNoteDetails(cn)"
                      class="text-blue-600 hover:text-blue-800"
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <p class="text-sm text-gray-600">Total: {{ fetchedCreditNotes.length }} credit notes</p>
          <button
            @click="showFetchedCreditNotes = false"
            class="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Detail Dialog -->
    <div v-if="showDetailModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="showDetailModal = false">
      <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full m-4 max-h-[90vh] flex flex-col">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">{{ detailModalTitle }}</h3>
        </div>
        <div class="px-6 py-4 overflow-auto flex-1">
          <pre class="bg-gray-50 p-4 rounded text-sm overflow-auto text-gray-900">{{ JSON.stringify(selectedItem, null, 2) }}</pre>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            @click="showDetailModal = false"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onErrorCaptured, nextTick, watch } from 'vue'
import { createResource, frappeRequest } from 'frappe-ui'

// Helper function to wrap frappe.call() for async/await with CSRF token support.
// Falls back to frappeRequest when frappe global is not available (e.g., kiosk SPA).
function frappeCall(method, args = {}) {
	return new Promise((resolve, reject) => {
		const frappeObj =
			(typeof frappe !== 'undefined' && frappe && frappe.call && frappe) ||
			(typeof window !== 'undefined' && window.frappe && window.frappe.call && window.frappe) ||
			null

		// If frappe global is present, use frappe.call (handles CSRF automatically)
		if (frappeObj) {
			frappeObj.call({
				method,
				args,
				callback: (r) => {
					if (r.message) {
						resolve(r.message)
					} else if (r.exc) {
						reject(new Error(r.exc))
					} else {
						reject(new Error('Unknown error occurred'))
					}
				},
				error: (r) => {
					let errorMsg = 'Request failed'
					if (r.message) {
						errorMsg = r.message
					} else if (r.exc) {
						errorMsg = r.exc
					} else if (r.responseJSON && r.responseJSON.exc) {
						errorMsg = r.responseJSON.exc
					} else if (r.responseJSON && r.responseJSON.message) {
						errorMsg = r.responseJSON.message
					}
					reject(new Error(errorMsg))
				}
			})
			return
		}

		// Fallback: use frappeRequest (frappe-ui) which handles CSRF via cookies
		// frappeRequest automatically adds /api/method/ prefix and handles CSRF tokens
		frappeRequest({
			method: 'POST',
			url: method,
			params: args
		})
			.then((res) => {
				resolve(res)
			})
			.catch((err) => {
				// If CSRF error, provide helpful message
				if (err?.message && err.message.includes('CSRF')) {
					reject(new Error('CSRF token error: Please refresh the page and try again. Your session may have expired.'))
				} else {
					reject(new Error(err?.message || 'Request failed'))
				}
			})
	})
}
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  LineController,
  BarController,
  DoughnutController
} from 'chart.js'

try {
  Chart.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    ArcElement,
    LineController,
    BarController,
    DoughnutController,
    Title,
    Tooltip,
    Legend,
    Filler
  )
} catch (error) {
  try {
    Chart.register(
      CategoryScale,
      LinearScale,
      PointElement,
      LineElement,
      BarElement,
      ArcElement,
      LineController,
      BarController,
      DoughnutController,
      Title,
      Tooltip,
      Legend,
      Filler
    )
  } catch (e2) {
    // Chart registration failed - charts will not render
  }
}

onErrorCaptured((err, instance, info) => {
  if (err?.message?.includes('Chart') || err?.message?.includes('canvas')) {
    return true
  }
  return false
})

// Active tab
const activeTab = ref('batches')
const viewMode = ref('transactions') // 'transactions', 'credit_notes'

// Grouped tabs
const transactionTabs = [
  { id: 'batches', label: 'Sync Batches', category: 'transactions' },
  { id: 'logs', label: 'Transaction Logs', category: 'transactions' }
]

const creditNoteTabs = [
  { id: 'refund_batches', label: 'Refund Batches', category: 'credit_notes' },
  { id: 'refund_logs', label: 'Refund Logs', category: 'credit_notes' }
]

// All tabs combined (for reference, not used since we removed 'all' mode)
const allTabs = [...transactionTabs, ...creditNoteTabs]

// Computed filtered tabs based on view mode
const filteredTabs = computed(() => {
  if (viewMode.value === 'transactions') {
    return transactionTabs
  } else if (viewMode.value === 'credit_notes') {
    return creditNoteTabs
  }
  return transactionTabs // Default to transactions
})

// Watch view mode changes and adjust active tab if needed
watch(viewMode, (newMode) => {
  if (newMode === 'transactions') {
    activeTab.value = 'batches'
  } else if (newMode === 'credit_notes') {
    activeTab.value = 'refund_batches'
  }
})

// Dashboard Summary
const dashboardSummary = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_dashboard_summary',
  auto: true,
  onError(error) {
    if (window.showGlobalError) {
      window.showGlobalError('Failed to load dashboard summary: ' + (error?.message || String(error)))
    }
  }
})

// Sync Batches
const batchFilters = ref({
  search: '',
  status: '',
  from_date: '',
  to_date: ''
})

const syncBatches = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_sync_batches',
  params: () => ({
    filters: getBatchFilters(),
    page_length: 20,
    start: 0
  }),
  auto: false
})

// Transaction Logs
const logFilters = ref({
  search: '',
  status: '',
  batch_id: '',
  from_date: '',
  to_date: ''
})

const transactionLogs = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_transaction_logs',
  params: () => ({
    filters: getLogFilters(),
    page_length: 20,
    start: 0
  }),
  auto: false
})

// Recent Jobs
const recentJobs = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_recent_jobs',
  params: { limit: 20 },
  auto: false
})

// Chart Data
const chartData = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_chart_data',
  params: { days: 30 },
  auto: true
})

// Credit Note Chart Data
const creditNoteChartData = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_credit_note_chart_data',
  params: { days: 30 },
  auto: true
})

// Refund Batches
const refundBatchFilters = ref({
  search: '',
  status: '',
  from_date: '',
  to_date: ''
})

const refundBatches = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_refund_batches',
  params: () => {
    try {
      return {
        filters: getRefundBatchFilters(),
        page_length: 20,
        start: 0
      }
    } catch (error) {
      return {
        filters: {},
        page_length: 20,
        start: 0
      }
    }
  },
  auto: false
})

// Refund Logs
const refundLogFilters = ref({
  search: '',
  status: '',
  batch_id: '',
  from_date: '',
  to_date: ''
})

const refundLogs = createResource({
  url: 'khanal_foods_inc.utils.dashboard_api.get_refund_logs',
  params: () => ({
    filters: getRefundLogFilters ? getRefundLogFilters() : {},
    page_length: 20,
    start: 0
  }),
  auto: false,
  onError(error) {
    if (window.showGlobalError) {
      window.showGlobalError('Failed to load refund logs: ' + (error?.message || String(error)))
    }
  }
})

// Credit Note Dialogs
const showFetchCreditNotesDialog = ref(false)
const showSyncCreditNotesDialog = ref(false)
const fetchingCreditNotes = ref(false)
const syncingCreditNotes = ref(false)
const fetchCreditNotesForm = ref({
  from_date: new Date().toISOString().split('T')[0],
  to_date: new Date().toISOString().split('T')[0],
  top: 100
})
const syncCreditNotesForm = ref({
  from_date: new Date().toISOString().split('T')[0],
  to_date: new Date().toISOString().split('T')[0],
  commit: true
})
const fetchedCreditNotes = ref([])
const showFetchedCreditNotes = ref(false)

// Chart refs
const successRateChart = ref(null)
const volumeChart = ref(null)
const statusPieChart = ref(null)
const dailyBarChart = ref(null)

// Credit Note Chart refs
const creditNoteSuccessRateChart = ref(null)
const creditNoteVolumeChart = ref(null)
const creditNoteStatusPieChart = ref(null)
const creditNoteDailyBarChart = ref(null)

// Chart instances
let successRateChartInstance = null
let volumeChartInstance = null
let statusPieChartInstance = null
let dailyBarChartInstance = null

// Credit Note Chart instances
let creditNoteSuccessRateChartInstance = null
let creditNoteVolumeChartInstance = null
let creditNoteStatusPieChartInstance = null
let creditNoteDailyBarChartInstance = null

// Dialog states
const showFetchDialog = ref(false)
const showPostDialog = ref(false)
const showRetryDialog = ref(false)
const showBulkDialog = ref(false)

// Sync Dialog
const showSyncDialog = ref(false)
const syncing = ref(false)
const syncForm = ref({
  from_date: new Date().toISOString().split('T')[0],
  to_date: new Date().toISOString().split('T')[0],
  commit: true
})

// Fetch Dialog
const fetching = ref(false)
const fetchForm = ref({
  from_date: new Date().toISOString().split('T')[0],
  to_date: new Date().toISOString().split('T')[0],
  top: 100
})
const fetchedInvoices = ref([])
const showFetchedInvoices = ref(false)

// Post Dialog
const posting = ref(false)
const postForm = ref({
  transaction_ids: '',
  commit: true
})

// Retry Dialog
const retrying = ref(false)
const retryForm = ref({
  batch_id: '',
  limit: 50
})

// Bulk Ops Dialog
const bulkProcessing = ref(false)
const bulkForm = ref({
  operation: 'retry_failed',
  limit: 100
})

// Detail Modal
const showDetailModal = ref(false)
const selectedItem = ref(null)
const detailModalTitle = ref('')

// Debounce timers
let batchesDebounceTimer = null
let logsDebounceTimer = null
let refundBatchesDebounceTimer = null
let refundLogsDebounceTimer = null

// Methods
function getBatchFilters() {
  const filters = {}
  if (batchFilters.value.search) {
    filters.name = ['like', `%${batchFilters.value.search}%`]
  }
  if (batchFilters.value.status) {
    filters.status = batchFilters.value.status
  }
  if (batchFilters.value.from_date) {
    filters.creation = ['>=', batchFilters.value.from_date]
  }
  if (batchFilters.value.to_date) {
    if (batchFilters.value.from_date) {
      filters.creation = ['between', [batchFilters.value.from_date, batchFilters.value.to_date]]
    } else {
      filters.creation = ['<=', batchFilters.value.to_date]
    }
  }
  return filters
}

function getLogFilters() {
  const filters = {}
  if (logFilters.value.search) {
    filters.sap_doc_num = ['like', `%${logFilters.value.search}%`]
  }
  if (logFilters.value.status) {
    filters.status = logFilters.value.status
  }
  if (logFilters.value.batch_id) {
    filters.batch_id = logFilters.value.batch_id
  }
  if (logFilters.value.from_date) {
    filters.creation = ['>=', logFilters.value.from_date]
  }
  if (logFilters.value.to_date) {
    if (logFilters.value.from_date) {
      filters.creation = ['between', [logFilters.value.from_date, logFilters.value.to_date]]
    } else {
      filters.creation = ['<=', logFilters.value.to_date]
    }
  }
  return filters
}

function loadBatches(start = 0) {
  syncBatches.params = {
    filters: getBatchFilters(),
    page_length: 20,
    start: start
  }
  syncBatches.fetch()
}

function loadLogs(start = 0) {
  transactionLogs.params = {
    filters: getLogFilters(),
    page_length: 20,
    start: start
  }
  transactionLogs.fetch()
}

function debounceLoadBatches() {
  clearTimeout(batchesDebounceTimer)
  batchesDebounceTimer = setTimeout(() => {
    loadBatches(0)
  }, 500)
}

function debounceLoadLogs() {
  clearTimeout(logsDebounceTimer)
  logsDebounceTimer = setTimeout(() => {
    loadLogs(0)
  }, 500)
}

function getRefundBatchFilters() {
  const filters = {}
  if (refundBatchFilters.value.search) {
    filters.batch_id = ['like', `%${refundBatchFilters.value.search}%`]
  }
  if (refundBatchFilters.value.status) {
    filters.status = refundBatchFilters.value.status
  }
  // Date filtering: Check if batch date range overlaps with filter range
  // A batch overlaps if: batch.start_date <= filter.to_date AND batch.end_date >= filter.from_date
  if (refundBatchFilters.value.from_date && refundBatchFilters.value.to_date) {
    // Both dates provided: find batches that overlap with the date range
    filters.start_date = ['<=', refundBatchFilters.value.to_date]
    filters.end_date = ['>=', refundBatchFilters.value.from_date]
  } else if (refundBatchFilters.value.from_date) {
    // Only from_date: find batches that end on or after this date
    filters.end_date = ['>=', refundBatchFilters.value.from_date]
  } else if (refundBatchFilters.value.to_date) {
    // Only to_date: find batches that start on or before this date
    filters.start_date = ['<=', refundBatchFilters.value.to_date]
  }
  return filters
}

function getRefundLogFilters() {
  const filters = {}
  if (refundLogFilters.value.search) {
    filters.sap_doc_num = ['like', `%${refundLogFilters.value.search}%`]
  }
  if (refundLogFilters.value.status) {
    filters.status = refundLogFilters.value.status
  }
  if (refundLogFilters.value.batch_id) {
    filters.refund_batch_id = refundLogFilters.value.batch_id
  }
  if (refundLogFilters.value.from_date) {
    if (refundLogFilters.value.to_date) {
      filters.creation = ['between', [refundLogFilters.value.from_date, refundLogFilters.value.to_date]]
    } else {
      filters.creation = ['>=', refundLogFilters.value.from_date]
    }
  } else if (refundLogFilters.value.to_date) {
    filters.creation = ['<=', refundLogFilters.value.to_date]
  }
  return filters
}

function loadRefundBatches(start = 0) {
  refundBatches.params = {
    filters: getRefundBatchFilters(),
    page_length: 20,
    start: start
  }
  refundBatches.fetch()
}

function loadRefundLogs(start = 0) {
  refundLogs.params = {
    filters: getRefundLogFilters(),
    page_length: 20,
    start: start
  }
  refundLogs.fetch()
}

function debounceLoadRefundBatches() {
  clearTimeout(refundBatchesDebounceTimer)
  refundBatchesDebounceTimer = setTimeout(() => {
    loadRefundBatches(0)
  }, 500)
}

function debounceLoadRefundLogs() {
  clearTimeout(refundLogsDebounceTimer)
  refundLogsDebounceTimer = setTimeout(() => {
    loadRefundLogs(0)
  }, 500)
}

function viewRefundBatchDetails(batch) {
  selectedItem.value = batch
  detailModalTitle.value = `Refund Batch Details: ${batch.name}`
  showDetailModal.value = true
}

function viewRefundLogDetails(log) {
  selectedItem.value = log
  detailModalTitle.value = `Refund Log Details: ${log.name}`
  showDetailModal.value = true
}

async function fetchCreditNotes() {
  if (!fetchCreditNotesForm.value.from_date || !fetchCreditNotesForm.value.to_date) {
    if (window.showGlobalError) {
      window.showGlobalError('Please provide both from and to dates')
    }
    return
  }

  // Ensure dates are in YYYY-MM-DD format (HTML date inputs should already be in this format)
  let fromDate = fetchCreditNotesForm.value.from_date
  let toDate = fetchCreditNotesForm.value.to_date
  
  // Convert from MM/DD/YYYY to YYYY-MM-DD if needed
  if (fromDate.includes('/')) {
    const [month, day, year] = fromDate.split('/')
    fromDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  }
  if (toDate.includes('/')) {
    const [month, day, year] = toDate.split('/')
    toDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  }

  fetchingCreditNotes.value = true
  try {
    const result = await frappeCall('khanal_foods_inc.utils.dashboard_api.fetch_credit_notes_from_sap', {
      from_date: fromDate,
      to_date: toDate,
      top: fetchCreditNotesForm.value.top || 100
    })

    if (result && result.status === 'success') {
      fetchedCreditNotes.value = result.credit_notes || []
      if (window.showGlobalSuccess) {
        window.showGlobalSuccess(`Fetched ${result.count || 0} credit notes from SAP`)
      }
      showFetchCreditNotesDialog.value = false
      if (result.credit_notes && result.credit_notes.length > 0) {
        showFetchedCreditNotes.value = true
      }
      await dashboardSummary.fetch()
    } else {
      if (window.showGlobalError) {
        window.showGlobalError('Failed to fetch credit notes: ' + (result?.error || 'Unknown error'))
      }
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError('Failed to fetch credit notes: ' + (error?.message || error))
    }
  } finally {
    fetchingCreditNotes.value = false
  }
}

async function syncCreditNotes() {
  if (!syncCreditNotesForm.value.from_date || !syncCreditNotesForm.value.to_date) {
    if (window.showGlobalError) {
      window.showGlobalError('Please provide both from and to dates')
    }
    return
  }

  // Ensure dates are in YYYY-MM-DD format (HTML date inputs should already be in this format)
  let fromDate = syncCreditNotesForm.value.from_date
  let toDate = syncCreditNotesForm.value.to_date
  
  // Convert from MM/DD/YYYY to YYYY-MM-DD if needed
  if (fromDate.includes('/')) {
    const [month, day, year] = fromDate.split('/')
    fromDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  }
  if (toDate.includes('/')) {
    const [month, day, year] = toDate.split('/')
    toDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  }

  syncingCreditNotes.value = true
  try {
    const result = await frappeCall('khanal_foods_inc.utils.dashboard_api.sync_credit_notes_to_avalara_api', {
      from_date: fromDate,
      to_date: toDate,
      commit: syncCreditNotesForm.value.commit
    })

    if (result && (result.status === 'success' || result.status === 'partial')) {
      const total = result.total || 0
      const successful = result.successful || 0
      const failed = result.failed || 0
      
      let statusMsg = ''
      if (result.status === 'partial') {
        statusMsg = `Credit note sync completed with some failures: ${successful} successful, ${failed} failed out of ${total} total`
        
        // Show detailed error if there are failed items
        if (result.failed_details && result.failed_details.length > 0) {
          const firstError = result.failed_details[0]
          const errorMsg = firstError.error || 'Unknown error'
          const docNum = firstError.DocNum || firstError.DocEntry || 'N/A'
          
          // Show warning for partial success
          if (window.showGlobalError) {
            window.showGlobalError(
              `Credit note ${docNum} failed: ${errorMsg}. ${successful} succeeded, ${failed} failed.`
            )
          }
        } else {
          if (window.showGlobalSuccess) {
            window.showGlobalSuccess(statusMsg)
          }
        }
      } else {
        statusMsg = `Credit note sync completed: ${successful} successful, ${failed} failed out of ${total} total`
        if (window.showGlobalSuccess) {
          window.showGlobalSuccess(statusMsg)
        }
      }
      
      showSyncCreditNotesDialog.value = false
      await loadRefundBatches()
      await loadRefundLogs()
      await refreshAll()
    } else {
      // Handle different error response formats
      let errorMessage = 'Unknown error'
      if (result) {
        if (result.error) {
          errorMessage = result.error
        } else if (result.message) {
          errorMessage = result.message
        } else if (result.exc_type) {
          errorMessage = `${result.exc_type}: ${result.exc || result.exception || 'Unknown error'}`
        } else if (result.exception) {
          errorMessage = result.exception
        } else if (typeof result === 'string') {
          errorMessage = result
        } else if (result.failed_details && result.failed_details.length > 0) {
          errorMessage = `Failed to process ${result.failed || 0} credit notes. First error: ${result.failed_details[0]?.error || 'Unknown error'}`
        } else {
          errorMessage = JSON.stringify(result)
        }
      }
      
      if (window.showGlobalError) {
        window.showGlobalError('Failed to sync credit notes: ' + errorMessage)
      }
    }
  } catch (error) {
    let errorMessage = 'Unknown error'
    if (error) {
      if (error.message) {
        errorMessage = error.message
      } else if (error.exc) {
        errorMessage = error.exc
      } else if (error.exception) {
        errorMessage = error.exception
      } else if (typeof error === 'string') {
        errorMessage = error
      } else {
        errorMessage = JSON.stringify(error)
      }
    }
    if (window.showGlobalError) {
      window.showGlobalError('Failed to sync credit notes: ' + errorMessage)
    }
  } finally {
    syncingCreditNotes.value = false
  }
}

async function refreshAll() {
  await Promise.all([
    dashboardSummary.fetch(),
    loadBatches(),
    loadLogs(),
    loadRefundBatches(),
    loadRefundLogs(),
    recentJobs.fetch()
  ])
}

async function triggerSync() {
  syncing.value = true
  try {
    const triggerSyncResource = createResource({
      url: 'khanal_foods_inc.utils.background_jobs.enqueue_sync_invoices',
      method: 'POST',
      params: {
        from_date: syncForm.value.from_date,
        to_date: syncForm.value.to_date,
        commit: syncForm.value.commit
      },
      auto: false
    })
    await triggerSyncResource.fetch()
    showSyncDialog.value = false
    await recentJobs.fetch()
    if (window.showGlobalSuccess) {
      window.showGlobalSuccess('Sync job enqueued successfully')
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError('Failed to trigger sync: ' + (error.message || error))
    }
  } finally {
    syncing.value = false
  }
}

function viewBatchDetails(batch) {
  selectedItem.value = batch
  detailModalTitle.value = `Batch Details: ${batch.name}`
  showDetailModal.value = true
}

function viewLogDetails(log) {
  selectedItem.value = log
  detailModalTitle.value = `Transaction Log Details: ${log.name}`
  showDetailModal.value = true
}

function viewJobDetails(job) {
  selectedItem.value = job
  detailModalTitle.value = `Job Details: ${job.name}`
  showDetailModal.value = true
}

function viewInvoiceDetails(invoice) {
  selectedItem.value = invoice
  detailModalTitle.value = `Invoice Details: ${invoice.DocNum || invoice.DocEntry || 'N/A'}`
  showDetailModal.value = true
}

function viewCreditNoteDetails(cn) {
  selectedItem.value = cn
  detailModalTitle.value = `Credit Note Details: ${cn.DocNum || cn.DocEntry || 'N/A'}`
  showDetailModal.value = true
}

function getInvoiceStatusBadgeClass(status) {
  if (status === 'C' || status === 'Closed') {
    return 'bg-gray-100 text-gray-800'
  } else if (status === 'O' || status === 'Open') {
    return 'bg-green-100 text-green-800'
  } else {
    return 'bg-yellow-100 text-yellow-800'
  }
}

function retryTransaction(log) {
  if (window.showGlobalError) {
    window.showGlobalError('Retry functionality to be implemented')
  }
}

function getStatusBadgeClass(status) {
  if (!status) return 'bg-gray-100 text-gray-800'
  const lowerStatus = status.toLowerCase()
  if (lowerStatus.includes('success') || lowerStatus.includes('completed')) {
    return 'bg-green-100 text-green-800'
  } else if (lowerStatus.includes('failed') || lowerStatus.includes('error')) {
    return 'bg-red-100 text-red-800'
  } else if (lowerStatus.includes('partial') || lowerStatus.includes('pending') || lowerStatus.includes('progress')) {
    return 'bg-yellow-100 text-yellow-800'
  }
  return 'bg-gray-100 text-gray-800'
}

function getJobStatusBadgeClass(status) {
  if (!status) return 'bg-gray-100 text-gray-800'
  const lowerStatus = status.toLowerCase()
  if (lowerStatus.includes('finished')) {
    return 'bg-green-100 text-green-800'
  } else if (lowerStatus.includes('failed')) {
    return 'bg-red-100 text-red-800'
  } else if (lowerStatus.includes('queued') || lowerStatus.includes('started')) {
    return 'bg-blue-100 text-blue-800'
  }
  return 'bg-gray-100 text-gray-800'
}

function getHealthBadgeClass(health) {
  if (!health) return 'bg-gray-100 text-gray-800'
  const lowerHealth = health.toLowerCase()
  if (lowerHealth === 'healthy') {
    return 'bg-green-100 text-green-800'
  } else if (lowerHealth === 'degraded' || lowerHealth === 'warning') {
    return 'bg-yellow-100 text-yellow-800'
  } else if (lowerHealth === 'unhealthy' || lowerHealth === 'error') {
    return 'bg-red-100 text-red-800'
  }
  return 'bg-gray-100 text-gray-800'
}

function getHealthColor(health) {
  if (!health) return 'text-gray-600'
  const lowerHealth = health.toLowerCase()
  if (lowerHealth === 'healthy') {
    return 'text-green-600'
  } else if (lowerHealth === 'degraded' || lowerHealth === 'warning') {
    return 'text-yellow-600'
  } else if (lowerHealth === 'unhealthy' || lowerHealth === 'error') {
    return 'text-red-600'
  }
  return 'text-gray-600'
}

function getSuccessRateColor(rate) {
  if (rate >= 95) return 'text-green-600'
  if (rate >= 80) return 'text-yellow-600'
  return 'text-red-600'
}

function formatDate(dateString) {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatDateRange(from, to) {
  if (!from && !to) return '-'
  if (from === to) return formatDate(from)
  return `${formatDate(from)} to ${formatDate(to)}`
}

function formatCurrency(amount) {
  if (amount === null || amount === undefined) return '-'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount)
}

function truncate(text, length) {
  if (!text) return '-'
  if (text.length <= length) return text
  return text.substring(0, length) + '...'
}

function getRecentErrors() {
  const health = dashboardSummary.data?.health
  if (!health) return []
  return health.recent_errors || health.health?.recent_errors || health.errors || []
}

// Chart initialization functions
function initSuccessRateChart() {
  try {
    if (!successRateChart.value || !chartData.data?.success_rate_over_time) return
    if (!successRateChart.value.getContext) return
    
    const ctx = successRateChart.value.getContext('2d')
    if (!ctx) return
    
    if (successRateChartInstance) {
      successRateChartInstance.destroy()
    }
    
    successRateChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartData.data.success_rate_over_time.labels || [],
      datasets: [{
        label: 'Success Rate %',
        data: chartData.data.success_rate_over_time.values || [],
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        tension: 0.4,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { callback: (value) => value + '%' }
        }
      }
    }
  })
  } catch (error) {
    // Chart initialization failed
  }
}

function initVolumeChart() {
  try {
    if (!volumeChart.value || !chartData.data?.transaction_volume) return
    if (!volumeChart.value.getContext) return
    
    const ctx = volumeChart.value.getContext('2d')
    if (!ctx) return
    
    if (volumeChartInstance) {
      volumeChartInstance.destroy()
    }
    
    volumeChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: chartData.data.transaction_volume.labels || [],
      datasets: [
        {
          label: 'Successful',
          data: chartData.data.transaction_volume.successful || [],
          backgroundColor: 'rgba(34, 197, 94, 0.8)'
        },
        {
          label: 'Failed',
          data: chartData.data.transaction_volume.failed || [],
          backgroundColor: 'rgba(239, 68, 68, 0.8)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' }
      },
      scales: {
        y: { beginAtZero: true }
      }
    }
  })
  } catch (error) {
    // Chart initialization failed
  }
}

function initStatusPieChart() {
  try {
    if (!statusPieChart.value || !chartData.data?.status_distribution) return
    if (!statusPieChart.value.getContext) return
    
    const ctx = statusPieChart.value.getContext('2d')
    if (!ctx) return
    
    if (statusPieChartInstance) {
      statusPieChartInstance.destroy()
    }
    
    statusPieChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: chartData.data.status_distribution.labels || [],
      datasets: [{
        data: chartData.data.status_distribution.values || [],
        backgroundColor: [
          'rgba(34, 197, 94, 0.8)',
          'rgba(239, 68, 68, 0.8)',
          'rgba(156, 163, 175, 0.8)',
          'rgba(59, 130, 246, 0.8)',
          'rgba(251, 146, 60, 0.8)'
        ]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right' }
      }
    }
  })
  } catch (error) {
    // Chart initialization failed
  }
}

function initDailyBarChart() {
  try {
    if (!dailyBarChart.value || !chartData.data?.transaction_volume) return
    if (!dailyBarChart.value.getContext) return
    
    const ctx = dailyBarChart.value.getContext('2d')
    if (!ctx) return
    
    if (dailyBarChartInstance) {
      dailyBarChartInstance.destroy()
    }
    
    dailyBarChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: chartData.data.transaction_volume.labels || [],
      datasets: [{
        label: 'Total Transactions',
        data: chartData.data.transaction_volume.total || [],
        backgroundColor: 'rgba(59, 130, 246, 0.8)'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true }
      }
    }
  })
  } catch (error) {
    // Chart initialization failed
  }
}

function initAllCharts() {
  try {
    nextTick(() => {
      initSuccessRateChart()
      initVolumeChart()
      initStatusPieChart()
      initDailyBarChart()
      initCreditNoteCharts()
    })
  } catch (error) {
    // Chart initialization failed
  }
}

function initCreditNoteCharts() {
  try {
    nextTick(() => {
      initCreditNoteSuccessRateChart()
      initCreditNoteVolumeChart()
      initCreditNoteStatusPieChart()
      initCreditNoteDailyBarChart()
    })
  } catch (error) {
    // Credit note chart initialization failed
  }
}

function initCreditNoteSuccessRateChart() {
  if (!creditNoteSuccessRateChart.value || !creditNoteChartData.data?.success_rate_over_time) return
  if (!creditNoteSuccessRateChart.value.getContext) return
  
  const ctx = creditNoteSuccessRateChart.value.getContext('2d')
  if (!ctx) return
  
  if (creditNoteSuccessRateChartInstance) {
    creditNoteSuccessRateChartInstance.destroy()
  }
  
  creditNoteSuccessRateChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: creditNoteChartData.data.success_rate_over_time.labels || [],
      datasets: [{
        label: 'Credit Note Success Rate %',
        data: creditNoteChartData.data.success_rate_over_time.values || [],
        borderColor: 'rgb(236, 72, 153)',
        backgroundColor: 'rgba(236, 72, 153, 0.1)',
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true }
      },
      scales: {
        y: { beginAtZero: true, max: 100 }
      }
    }
  })
}

function initCreditNoteVolumeChart() {
  if (!creditNoteVolumeChart.value || !creditNoteChartData.data?.transaction_volume) return
  if (!creditNoteVolumeChart.value.getContext) return
  
  const ctx = creditNoteVolumeChart.value.getContext('2d')
  if (!ctx) return
  
  if (creditNoteVolumeChartInstance) {
    creditNoteVolumeChartInstance.destroy()
  }
  
  creditNoteVolumeChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: creditNoteChartData.data.transaction_volume.labels || [],
      datasets: [
        {
          label: 'Successful',
          data: creditNoteChartData.data.transaction_volume.successful || [],
          backgroundColor: 'rgba(34, 197, 94, 0.8)'
        },
        {
          label: 'Failed',
          data: creditNoteChartData.data.transaction_volume.failed || [],
          backgroundColor: 'rgba(239, 68, 68, 0.8)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true }
      }
    }
  })
}

function initCreditNoteStatusPieChart() {
  if (!creditNoteStatusPieChart.value || !creditNoteChartData.data?.status_distribution) return
  if (!creditNoteStatusPieChart.value.getContext) return
  
  const ctx = creditNoteStatusPieChart.value.getContext('2d')
  if (!ctx) return
  
  if (creditNoteStatusPieChartInstance) {
    creditNoteStatusPieChartInstance.destroy()
  }
  
  creditNoteStatusPieChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: creditNoteChartData.data.status_distribution.labels || [],
      datasets: [{
        data: creditNoteChartData.data.status_distribution.values || [],
        backgroundColor: [
          'rgba(34, 197, 94, 0.8)',
          'rgba(234, 179, 8, 0.8)',
          'rgba(107, 114, 128, 0.8)',
          'rgba(239, 68, 68, 0.8)',
          'rgba(59, 130, 246, 0.8)'
        ]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'bottom' }
      }
    }
  })
}

function initCreditNoteDailyBarChart() {
  if (!creditNoteDailyBarChart.value || !creditNoteChartData.data?.transaction_volume) return
  if (!creditNoteDailyBarChart.value.getContext) return
  
  const ctx = creditNoteDailyBarChart.value.getContext('2d')
  if (!ctx) return
  
  if (creditNoteDailyBarChartInstance) {
    creditNoteDailyBarChartInstance.destroy()
  }
  
  creditNoteDailyBarChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: creditNoteChartData.data.transaction_volume.labels || [],
      datasets: [{
        label: 'Total Credit Notes',
        data: creditNoteChartData.data.transaction_volume.total || [],
        backgroundColor: 'rgba(236, 72, 153, 0.8)'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true }
      }
    }
  })
}

// Watch for chart data changes
watch(() => chartData.data, () => {
  if (chartData.data && !chartData.loading) {
    initAllCharts()
  }
}, { deep: true })

watch(() => creditNoteChartData.data, () => {
  if (creditNoteChartData.data && !creditNoteChartData.loading) {
    initCreditNoteCharts()
  }
}, { deep: true })

// Dialog handlers
async function triggerFetch() {
  if (!fetchForm.value.from_date || !fetchForm.value.to_date) {
    if (window.showGlobalError) {
      window.showGlobalError('Please provide both from and to dates')
    }
    return
  }

  // Ensure dates are in YYYY-MM-DD format (HTML date inputs should already be in this format)
  let fromDate = fetchForm.value.from_date
  let toDate = fetchForm.value.to_date
  
  // Convert from MM/DD/YYYY to YYYY-MM-DD if needed
  if (fromDate.includes('/')) {
    const [month, day, year] = fromDate.split('/')
    fromDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  }
  if (toDate.includes('/')) {
    const [month, day, year] = toDate.split('/')
    toDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
  }

  fetching.value = true
  try {
    const result = await frappeCall('khanal_foods_inc.utils.dashboard_api.fetch_invoices_from_sap', {
      from_date: fromDate,
      to_date: toDate,
      top: fetchForm.value.top || 100,
      skip: 0
    })

    if (result.status === 'success') {
      fetchedInvoices.value = result.invoices || []
      if (window.showGlobalSuccess) {
        window.showGlobalSuccess(`Fetched ${result.count} invoices from SAP. Click "View Fetched Invoices" to see them.`)
      }
      showFetchDialog.value = false
      // Show fetched invoices dialog
      if (result.invoices && result.invoices.length > 0) {
        showFetchedInvoices.value = true
      }
      // Refresh dashboard
      await dashboardSummary.fetch()
    } else {
      if (window.showGlobalError) {
        window.showGlobalError(result.error || 'Failed to fetch invoices')
      }
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError(error.message || 'Failed to fetch invoices')
    }
  } finally {
    fetching.value = false
  }
}

async function triggerPost() {
  posting.value = true
  try {
    // Parse transaction IDs from textarea
    let transactionIds = []
    if (postForm.value.transaction_ids.trim()) {
      transactionIds = postForm.value.transaction_ids
        .split('\n')
        .map(id => id.trim())
        .filter(id => id.length > 0)
    } else {
      // If empty, get all pending transactions
      const pendingLogs = await frappeCall('khanal_foods_inc.utils.dashboard_api.get_transaction_logs', {
        filters: { status: 'Pending' },
        page_length: 100
      })
      if (pendingLogs.transaction_logs && pendingLogs.transaction_logs.length > 0) {
        transactionIds = pendingLogs.transaction_logs.map(log => log.name)
      } else {
        if (window.showGlobalError) {
          window.showGlobalError('No pending transactions found')
        }
        posting.value = false
        return
      }
    }

    if (transactionIds.length === 0) {
      if (window.showGlobalError) {
        window.showGlobalError('No transactions to post')
      }
      posting.value = false
      return
    }

    const result = await frappeCall('khanal_foods_inc.utils.dashboard_api.post_transactions_to_avalara', {
      transaction_ids: transactionIds,
      commit: postForm.value.commit
    })

    if (result.status === 'success') {
      if (window.showGlobalSuccess) {
        window.showGlobalSuccess(`Posted ${result.successful} transactions successfully. ${result.failed} failed.`)
      }
      showPostDialog.value = false
      postForm.value.transaction_ids = ''
      // Refresh dashboard
      await dashboardSummary.fetch()
      await recentJobs.fetch()
    } else {
      if (window.showGlobalError) {
        window.showGlobalError(result.error || 'Failed to post transactions')
      }
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError(error.message || 'Failed to post transactions')
    }
  } finally {
    posting.value = false
  }
}

async function triggerRetry() {
  retrying.value = true
  try {
    const result = await frappeCall('khanal_foods_inc.utils.dashboard_api.retry_failed_transactions', {
      batch_id: retryForm.value.batch_id || null,
      limit: retryForm.value.limit || 50
    })

    if (result.status === 'success') {
      if (window.showGlobalSuccess) {
        window.showGlobalSuccess(`Retry queued for ${result.count} transactions`)
      }
      showRetryDialog.value = false
      retryForm.value.batch_id = ''
      // Refresh dashboard
      await dashboardSummary.fetch()
      await recentJobs.fetch()
    } else {
      if (window.showGlobalError) {
        window.showGlobalError(result.error || 'Failed to retry transactions')
      }
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError(error.message || 'Failed to retry transactions')
    }
  } finally {
    retrying.value = false
  }
}

async function triggerBulkOps() {
  bulkProcessing.value = true
  try {
    const result = await frappeCall('khanal_foods_inc.utils.dashboard_api.bulk_operations', {
      operation: bulkForm.value.operation,
      limit: bulkForm.value.limit || 100
    })

    if (result.status === 'success') {
      if (window.showGlobalSuccess) {
        const message = result.message || `Bulk operation completed: ${result.count || 0} records processed`
        window.showGlobalSuccess(message)
      }
      showBulkDialog.value = false
      // Refresh dashboard
      await dashboardSummary.fetch()
      await recentJobs.fetch()
    } else {
      if (window.showGlobalError) {
        window.showGlobalError(result.error || 'Bulk operation failed')
      }
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError(error.message || 'Bulk operation failed')
    }
  } finally {
    bulkProcessing.value = false
  }
}

async function exportData() {
  try {
    const exportResource = createResource({
      url: 'khanal_foods_inc.utils.dashboard_api.export_data',
      method: 'POST',
      params: {
        doctype: 'Avalara Transaction Log',
        format: 'csv'
      }
    })
    await exportResource.fetch()
    if (exportResource.data?.file_url) {
      window.open(exportResource.data.file_url, '_blank')
      if (window.showGlobalSuccess) {
        window.showGlobalSuccess('Data exported successfully')
      }
    }
  } catch (error) {
    if (window.showGlobalError) {
      window.showGlobalError('Failed to export data: ' + (error.message || error))
    }
  }
}

// Load data on mount
onMounted(() => {
  try {
  loadBatches()
  loadLogs()
    loadRefundBatches()
    loadRefundLogs()
  recentJobs.fetch()
    
    // Initialize charts after a delay to ensure DOM is ready
    setTimeout(() => {
      try {
        if (chartData.data && !chartData.loading) {
          initAllCharts()
        }
      } catch (error) {
        // Chart initialization failed
      }
    }, 1000)
  } catch (error) {
    // Component mount error
  }
})
</script>

