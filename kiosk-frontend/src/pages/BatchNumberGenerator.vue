<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Batch Number Generator</h1>
      <button
        @click="onGenerateNow"
        class="px-5 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
        :disabled="loading"
      >
        {{ loading ? 'Generating...' : 'Generate Now' }}
      </button>
    </div>

    <div class="bg-white rounded-lg shadow p-4">
      <div class="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <label class="block text-sm text-blue-600 font-medium mb-1">Date</label>
          <input v-model="selectedDate" type="date" class="px-3 py-2 border rounded w-48 text-blue-600" @change="fetchBatches" />
        </div>
        <div>
          <label class="block text-sm text-blue-600 font-medium mb-1">Show last N days</label>
          <input v-model.number="recentDays" type="number" min="1" max="7" class="px-3 py-2 border rounded w-24 text-blue-600" @change="fetchBatches" />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600 w-12"></th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Category</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Item Code</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Variant</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Warehouse</th>
              <th class="px-4 py-2 text-left text-xs font-semibold text-blue-600">Grams SKU</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <template v-for="(item, idx) in groupedRows" :key="idx">
              <!-- Main item row -->
              <tr class="hover:bg-gray-50 cursor-pointer" @click="toggleItem(idx)">
                <td class="px-4 py-2 text-sm text-blue-600">
                  <svg 
                    class="w-5 h-5 transition-transform" 
                    :class="{ 'rotate-90': expandedItems[idx] }"
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </td>
                <td class="px-4 py-2 text-sm text-blue-600">{{ item.category }}</td>
                <td class="px-4 py-2 text-sm font-medium text-blue-600">{{ item.item_code }}</td>
                <td class="px-4 py-2 text-sm text-blue-600">{{ item.variant }}</td>
                <td class="px-4 py-2 text-sm text-blue-600">{{ item.warehouse }}</td>
                <td class="px-4 py-2 text-sm text-blue-600">{{ item.grams_sku }}</td>
              </tr>
              <!-- Expandable batch numbers section -->
              <tr v-if="expandedItems[idx]" class="bg-gray-50">
                <td colspan="6" class="px-4 py-3">
                  <div class="pl-8">
                    <div v-if="item.batches && item.batches.length > 0" class="space-y-2">
                      <div 
                        v-for="(batch, batchIdx) in item.batches" 
                        :key="batchIdx"
                        class="flex items-center justify-between py-2 px-3 bg-white rounded border border-gray-200"
                      >
                        <span class="text-sm font-mono text-blue-700">{{ batch.batch_number }}</span>
                        <span class="text-sm text-blue-600">{{ batch.date }}</span>
                      </div>
                    </div>
                    <div v-else class="text-sm text-gray-500 py-2">
                      No batch numbers generated yet
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!loading && groupedRows.length === 0">
              <td colspan="6" class="px-4 py-6 text-center text-gray-500">No items configured</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { nandiHillsBatchNumberService } from '@/core/api/plants/nandi_hills/batchNumberService.js'

const loading = ref(false)
const groupedRows = ref([])
const expandedItems = ref({})
const selectedDate = ref(new Date().toISOString().slice(0, 10))
const recentDays = ref(1)

const toggleItem = (idx) => {
  expandedItems.value[idx] = !expandedItems.value[idx]
}

const fetchBatches = async () => {
  loading.value = true
  try {
    const response = await nandiHillsBatchNumberService.getBatches(selectedDate.value, recentDays.value)
    // Backend returns: {success: true, data: [...]}
    // extractResponse() extracts response.data.message or response.data
    // So response will be: {success: true, data: [...]}
    const data = response?.data || []
    groupedRows.value = Array.isArray(data) ? data : []
    
    // Initialize expanded state - expand first item by default if any items exist
    if (groupedRows.value.length > 0) {
      expandedItems.value = { 0: true }
    } else {
      expandedItems.value = {}
    }
  } catch (e) {
    console.error('Failed to fetch batches', e)
    groupedRows.value = []
    expandedItems.value = {}
  } finally {
    loading.value = false
  }
}

const onGenerateNow = async () => {
  loading.value = true
  try {
    await nandiHillsBatchNumberService.generateBatches(selectedDate.value)
    await fetchBatches()
  } catch (e) {
    console.error('Failed to generate batches', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchBatches()
})
</script>

<style scoped>
</style>



