<template>
  <div class="space-y-6">
    <div v-if="loading" class="text-center py-8">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
      <p class="mt-4 text-gray-600">Loading production details...</p>
    </div>

    <div v-else-if="productionDetails">
      <!-- Production Info -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <h3 class="text-lg font-semibold mb-4">Production Order: {{ productionDetails.name }}</h3>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm text-gray-500">Process Type</label>
            <p class="font-semibold">{{ productionDetails.process_type }}</p>
          </div>
          <div>
            <label class="text-sm text-gray-500">Employee Count</label>
            <p class="font-semibold">{{ productionDetails.employee_count }}</p>
          </div>
        </div>
      </div>

      <!-- Input Summary -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <h3 class="text-lg font-semibold mb-4">Input Used</h3>
        <div class="space-y-2">
          <div v-for="(input, index) in productionDetails.crate_inputs" :key="index" class="flex justify-between text-sm">
            <span>{{ input.crate_number }}</span>
            <span class="font-semibold">{{ input.input_quantity }} Kg</span>
          </div>
          <div class="pt-2 border-t border-gray-300 flex justify-between font-bold">
            <span>Total Input:</span>
            <span>{{ totalInput }} Kg</span>
          </div>
        </div>
      </div>

      <!-- Output Items -->
      <div class="bg-gray-50 p-6 rounded-lg">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-semibold">Output Items</h3>
          <button
            @click="addOutputItem"
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
          >
            + Add Item
          </button>
        </div>

        <div class="space-y-4">
          <div v-for="(item, index) in outputItems" :key="index" class="border border-gray-300 rounded-lg p-4 bg-white">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Item Code *</label>
                <input
                  v-model="item.item_code"
                  type="text"
                  placeholder="Item code"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Description</label>
                <input
                  v-model="item.item_description"
                  type="text"
                  placeholder="Description"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Output Qty *</label>
                <input
                  v-model.number="item.output_quantity"
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Batch Number</label>
                <div class="flex gap-2">
                  <input
                    v-model="item.batch_number"
                    type="text"
                    placeholder="Batch number"
                    class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                  <button
                    v-if="outputItems.length > 1"
                    @click="removeOutputItem(index)"
                    class="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
                  >
                    ×
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Total Output -->
        <div class="mt-4 pt-4 border-t border-gray-300">
          <div class="flex justify-between font-bold">
            <span>Total Output:</span>
            <span>{{ totalOutput }} Kg</span>
          </div>
          <div class="flex justify-between text-sm text-gray-600 mt-2">
            <span>Loss:</span>
            <span :class="loss >= 0 ? 'text-red-600' : 'text-green-600'">{{ Math.abs(loss).toFixed(2) }} Kg ({{ lossPercentage }}%)</span>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex justify-end gap-4">
        <button
          @click="cancel"
          class="px-6 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="submitOutput"
          :disabled="!canSubmit || submitting"
          :class="canSubmit && !submitting ? 'bg-purple-600 hover:bg-purple-700' : 'bg-gray-400 cursor-not-allowed'"
          class="px-6 py-2 text-white rounded-lg transition-colors"
        >
          {{ submitting ? 'Submitting...' : 'Submit Output' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { malurProductionService } from '@/core/api/plants/malur/productionService'

export default {
  name: 'SubmitOutputForm',
  props: {
    productionId: {
      type: String,
      required: true
    }
  },
  emits: ['output-submitted', 'cancel'],
  setup(props, { emit }) {
    const loading = ref(true)
    const submitting = ref(false)
    const productionDetails = ref(null)
    const outputItems = ref([
      {
        item_code: '',
        item_description: '',
        output_quantity: 0,
        batch_number: '',
        uom: 'Kg'
      }
    ])

    const totalInput = computed(() => {
      if (!productionDetails.value) return 0
      return productionDetails.value.crate_inputs.reduce((sum, input) => sum + parseFloat(input.input_quantity || 0), 0)
    })

    const totalOutput = computed(() => {
      return outputItems.value.reduce((sum, item) => sum + parseFloat(item.output_quantity || 0), 0)
    })

    const loss = computed(() => {
      return totalInput.value - totalOutput.value
    })

    const lossPercentage = computed(() => {
      if (totalInput.value === 0) return 0
      return ((loss.value / totalInput.value) * 100).toFixed(2)
    })

    const canSubmit = computed(() => {
      return outputItems.value.some(item =>
        item.item_code && item.output_quantity > 0
      )
    })

    const loadProductionDetails = async () => {
      loading.value = true
      try {
        const response = await malurProductionService.getProductionOrderDetails(props.productionId)
        if (response.success) {
          productionDetails.value = response.data
        }
      } catch (error) {
        console.error('Error loading production details:', error)
        alert('Failed to load production details')
      } finally {
        loading.value = false
      }
    }

    const addOutputItem = () => {
      outputItems.value.push({
        item_code: '',
        item_description: '',
        output_quantity: 0,
        batch_number: '',
        uom: 'Kg'
      })
    }

    const removeOutputItem = (index) => {
      outputItems.value.splice(index, 1)
    }

    const submitOutput = async () => {
      if (!canSubmit.value) return

      // Validate
      for (const item of outputItems.value) {
        if (item.output_quantity > 0 && !item.item_code) {
          alert('Please enter item code for all output items')
          return
        }
      }

      submitting.value = true

      try {
        const outputData = outputItems.value.filter(item => item.item_code && item.output_quantity > 0)
        
        const response = await malurProductionService.submitProductionOutput(props.productionId, outputData)
        
        if (response.success) {
          alert('Production output submitted successfully! Awaiting approval.')
          emit('output-submitted')
        } else {
          alert('Failed to submit output: ' + response.message)
        }
      } catch (error) {
        console.error('Error submitting output:', error)
        alert('Failed to submit output: ' + error.message)
      } finally {
        submitting.value = false
      }
    }

    const cancel = () => {
      emit('cancel')
    }

    onMounted(() => {
      loadProductionDetails()
    })

    return {
      loading,
      submitting,
      productionDetails,
      outputItems,
      totalInput,
      totalOutput,
      loss,
      lossPercentage,
      canSubmit,
      addOutputItem,
      removeOutputItem,
      submitOutput,
      cancel
    }
  }
}
</script>

