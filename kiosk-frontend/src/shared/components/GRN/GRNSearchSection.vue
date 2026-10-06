<template>
  <div class="bg-white border border-gray-200 p-6 rounded-lg shadow-sm">
    <h3 class="text-lg font-semibold mb-4 text-gray-900 flex items-center">
      <span class="mr-2">🔍</span>
      {{ title }}
    </h3>
    
    <!-- Fetch All Checkbox -->
    <div class="mb-4">
      <label class="flex items-center cursor-pointer">
        <input
          :checked="fetchAll"
          @change="$emit('update:fetchAll', ($event.target as HTMLInputElement).checked)"
          type="checkbox"
          class="h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 rounded"
        />
        <span class="ml-2 text-sm font-medium text-gray-700">Fetch All POs (No Date Filter)</span>
      </label>
    </div>

    <!-- Date Range Section -->
    <div class="space-y-4" :class="{ 'opacity-50 pointer-events-none': fetchAll }">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">From Date</label>
          <input
            :value="fromDate"
            @input="$emit('update:fromDate', ($event.target as HTMLInputElement).value)"
            type="date"
            :disabled="fetchAll"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white text-gray-900"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">To Date</label>
          <input
            :value="toDate"
            @input="$emit('update:toDate', ($event.target as HTMLInputElement).value)"
            type="date"
            :disabled="fetchAll"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white text-gray-900"
          />
        </div>
      </div>

      <!-- Quick Date Buttons -->
      <div class="flex flex-wrap gap-2">
        <span class="text-sm text-gray-700 font-medium mr-2">Quick Select:</span>
        <button
          v-for="option in quickDateOptions"
          :key="option.value"
          @click="$emit('quick-date', option.value)"
          :disabled="fetchAll"
          type="button"
          class="px-3 py-1 text-sm text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <!-- Business Partner Search -->
    <div class="mt-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">
        Business Partner (Optional)
      </label>
      <input
        :value="bpSearch"
        @input="$emit('update:bpSearch', ($event.target as HTMLInputElement).value)"
        type="text"
        placeholder="🔍 Search by Code or Name..."
        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white text-gray-900"
      />
      <p class="mt-1 text-xs text-gray-500">Example: "V001" or "ABC Suppliers"</p>
    </div>

    <!-- Fetch Button -->
    <div class="mt-6">
      <button
        @click="$emit('fetch')"
        type="button"
        :disabled="loading || (!fetchAll && (!fromDate || !toDate))"
        class="w-full px-6 py-3 bg-purple-600 text-white font-semibold rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
      >
        <span v-if="loading" class="mr-2">
          <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </span>
        {{ loading ? 'Loading...' : '🔍 Fetch Purchase Orders' }}
      </button>
    </div>

    <!-- Results Count -->
    <div v-if="resultsCount > 0" class="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
      <p class="text-sm text-green-800">
        ✅ Found {{ resultsCount }} purchase order(s)
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
interface QuickDateOption {
  label: string
  value: number
}

interface Props {
  title?: string
  fetchAll?: boolean
  fromDate?: string
  toDate?: string
  bpSearch?: string
  loading?: boolean
  resultsCount?: number
  quickDateOptions?: QuickDateOption[]
}

withDefaults(defineProps<Props>(), {
  title: 'Fetch Purchase Orders',
  fetchAll: false,
  fromDate: '',
  toDate: '',
  bpSearch: '',
  loading: false,
  resultsCount: 0,
  quickDateOptions: () => [
    { label: 'Today', value: 0 },
    { label: 'Last 7 Days', value: 7 },
    { label: 'Last 30 Days', value: 30 },
    { label: 'Last 90 Days', value: 90 }
  ]
})

defineEmits<{
  'update:fetchAll': [value: boolean]
  'update:fromDate': [value: string]
  'update:toDate': [value: string]
  'update:bpSearch': [value: string]
  'quick-date': [days: number]
  fetch: []
}>()
</script>

