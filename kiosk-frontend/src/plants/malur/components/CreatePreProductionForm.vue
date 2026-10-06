<template>
  <div class="space-y-6">
    <!-- Step 1: Process Type -->
    <div class="bg-gray-50 p-6 rounded-lg">
      <h3 class="text-lg font-semibold mb-4">Step 1: Select Process Type</h3>
      <select
        v-model="processType"
        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
      >
        <option :value="null">-- Select Process Type --</option>
        <option value="Drying Process">Drying Process</option>
        <option value="Churpi Process">Churpi Process</option>
      </select>
    </div>

    <!-- Step 2: Employee Count -->
    <div v-if="processType" class="bg-gray-50 p-6 rounded-lg">
      <h3 class="text-lg font-semibold mb-4">Step 2: Number of Employees</h3>
      <input
        v-model.number="employeeCount"
        type="number"
        min="1"
        placeholder="Enter number of employees"
        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
      />
    </div>

    <!-- Step 3: Select Crates -->
    <div v-if="employeeCount > 0" class="bg-gray-50 p-6 rounded-lg">
      <h3 class="text-lg font-semibold mb-4">Step 3: Select Crate Assignments</h3>
      
      <div v-if="loadingCrates" class="text-center py-4">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto"></div>
        <p class="mt-2 text-gray-600">Loading available crates...</p>
      </div>

      <div v-else-if="availableCrates.length === 0" class="text-center py-4 text-gray-500">
        No crates available for production
      </div>

      <div v-else class="space-y-4">
        <div v-for="(crate, index) in availableCrates" :key="index" class="border border-gray-300 rounded-lg p-4">
          <div class="flex items-center justify-between mb-2">
            <div>
              <h4 class="font-semibold text-gray-900">{{ crate.item_code }}</h4>
              <p class="text-sm text-gray-500">{{ crate.item_description }}</p>
              <p class="text-sm text-gray-500">Batch: {{ crate.batch_number }}</p>
            </div>
            <input
              type="checkbox"
              :checked="isCrateSelected(crate)"
              @change="toggleCrate(crate)"
              class="h-5 w-5 text-purple-600 focus:ring-purple-500 border-gray-300 rounded"
            />
          </div>

          <!-- Crate Lines -->
          <div v-if="isCrateSelected(crate)" class="mt-4 space-y-2">
            <div v-for="(line, lineIndex) in crate.Lineitem" :key="lineIndex" class="bg-white p-3 rounded border border-gray-200">
              <div class="flex items-center justify-between">
                <div class="flex-1">
                  <p class="text-sm font-medium">Crate: {{ line.batchnumber }}</p>
                  <p class="text-xs text-gray-500">Available Qty: {{ line.Quantity }}</p>
                </div>
                <div class="ml-4">
                  <input
                    v-model.number="line.EnteredInput"
                    type="number"
                    step="0.01"
                    :max="line.Quantity"
                    placeholder="Used Qty"
                    class="w-32 px-2 py-1 border border-gray-300 rounded text-sm"
                    @input="validateInput(line)"
                  />
                </div>
              </div>
            </div>
          </div>
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
        @click="submitPreProduction"
        :disabled="!canSubmit || submitting"
        :class="canSubmit && !submitting ? 'bg-purple-600 hover:bg-purple-700' : 'bg-gray-400 cursor-not-allowed'"
        class="px-6 py-2 text-white rounded-lg transition-colors"
      >
        {{ submitting ? 'Creating...' : 'Create Pre-Production' }}
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { malurProductionService } from '@/core/api/plants/malur/productionService'
import { authService } from '@/core/auth/authService'

export default {
  name: 'CreatePreProductionForm',
  emits: ['production-created', 'cancel'],
  setup(props, { emit }) {
    const processType = ref(null)
    const employeeCount = ref(0)
    const availableCrates = ref([])
    const selectedCrates = ref([])
    const loadingCrates = ref(false)
    const submitting = ref(false)

    const canSubmit = computed(() => {
      if (!processType.value || employeeCount.value <= 0) return false
      
      // Check if at least one crate has input entered
      return selectedCrates.value.some(crate =>
        crate.Lineitem.some(line => line.EnteredInput && line.EnteredInput > 0)
      )
    })

    const loadAvailableCrates = async () => {
      loadingCrates.value = true
      try {
        const response = await malurProductionService.getCrateAssignments()
        if (response.success) {
          availableCrates.value = response.data
        }
      } catch (error) {
        console.error('Error loading crates:', error)
        alert('Failed to load available crates')
      } finally {
        loadingCrates.value = false
      }
    }

    const isCrateSelected = (crate) => {
      return selectedCrates.value.some(c => c.name === crate.name)
    }

    const toggleCrate = (crate) => {
      const index = selectedCrates.value.findIndex(c => c.name === crate.name)
      if (index >= 0) {
        selectedCrates.value.splice(index, 1)
      } else {
        selectedCrates.value.push(JSON.parse(JSON.stringify(crate)))
      }
    }

    const validateInput = (line) => {
      if (line.EnteredInput > line.Quantity) {
        line.EnteredInput = line.Quantity
      }
      if (line.EnteredInput < 0) {
        line.EnteredInput = 0
      }
    }

    const submitPreProduction = async () => {
      if (!canSubmit.value) return

      submitting.value = true

      try {
        // Prepare crate details
        const crateDetails = selectedCrates.value.map(crate => ({
          ItemCode: crate.item_code,
          ItemDescription: crate.item_description,
          Frappe_key: crate.name,
          CrateData: crate.Lineitem.filter(line => line.EnteredInput && line.EnteredInput > 0)
        }))

        // Get user email
        const userEmail = authService.getUserEmail() || 'unknown@user.com'

        const response = await malurProductionService.createPreProduction(
          crateDetails,
          { ProcessTyp: processType.value },
          employeeCount.value,
          userEmail
        )

        if (response.success) {
          alert('Pre-production order created successfully! Please record the output.')
          emit('production-created')
        } else {
          alert('Failed to create pre-production order: ' + response.message)
        }
      } catch (error) {
        console.error('Error creating pre-production:', error)
        alert('Failed to create pre-production order: ' + error.message)
      } finally {
        submitting.value = false
      }
    }

    const cancel = () => {
      emit('cancel')
    }

    watch(employeeCount, (newVal) => {
      if (newVal > 0) {
        loadAvailableCrates()
      }
    })

    onMounted(() => {
      // Load crates initially if needed
    })

    return {
      processType,
      employeeCount,
      availableCrates,
      selectedCrates,
      loadingCrates,
      submitting,
      canSubmit,
      isCrateSelected,
      toggleCrate,
      validateInput,
      submitPreProduction,
      cancel
    }
  }
}
</script>

