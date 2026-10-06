<template>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    <div
      v-for="department in departments"
      :key="department.id"
      class="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
      @click="$emit('departmentClick', department.id)"
    >
      <div class="flex items-center mb-2">
        <div class="w-8 h-8 bg-green-100 rounded-md flex items-center justify-center mr-3">
          <span class="text-green-600 text-lg">{{ department.icon }}</span>
        </div>
        <h4 class="font-medium text-gray-900">{{ department.name }}</h4>
      </div>
      <p class="text-sm text-gray-600 mb-2">{{ department.description }}</p>
      <div class="flex items-center justify-between">
        <span 
          class="text-xs font-medium"
          :class="department.status === 'Active' ? 'text-green-600' : 'text-red-600'"
        >
          {{ department.status }}
        </span>
        <span class="text-xs font-medium text-green-600">{{ department.efficiency }}%</span>
      </div>
    </div>
    <div v-if="departments.length === 0" class="col-span-full text-center text-gray-500 py-8">
      No departments configured
    </div>
  </div>
</template>

<script setup lang="ts">
interface Department {
  id: string
  name: string
  description: string
  icon: string
  status: string
  efficiency: number
}

interface Props {
  departments: Department[]
}

defineProps<Props>()
defineEmits<{
  departmentClick: [departmentId: string]
}>()
</script>