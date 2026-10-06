<template>
  <div class="p-4 bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-lg font-bold text-gray-900">{{ title }}</h3>
      <span class="text-2xl font-bold text-purple-600">{{ progressPercentage }}%</span>
    </div>
    
    <!-- Progress Bar -->
    <div class="relative w-full h-4 bg-gray-200 rounded-full overflow-hidden mb-3">
      <div 
        class="absolute h-full bg-gradient-to-r from-green-500 to-blue-500 transition-all duration-500 ease-out"
        :style="{width: `${progressPercentage}%`}"
      >
        <div class="absolute inset-0 bg-white opacity-20 animate-pulse"></div>
      </div>
    </div>
    
    <!-- Stats Grid -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="p-2 bg-white rounded-lg shadow-sm"
      >
        <div :class="['text-2xl font-bold', stat.color]">{{ stat.value }}</div>
        <div class="text-xs text-gray-600">
          <span class="mr-1">{{ stat.icon }}</span>
          {{ stat.label }}
        </div>
      </div>
    </div>

    <!-- Additional Info Slot -->
    <slot name="additional-info"></slot>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Stat {
  label: string
  value: number | string
  icon: string
  color: string
}

interface Props {
  title?: string
  completedItems?: number
  partialItems?: number
  pendingItems?: number
  totalItems?: number
  customStats?: Stat[]
}

const props = withDefaults(defineProps<Props>(), {
  title: 'GRN Progress',
  completedItems: 0,
  partialItems: 0,
  pendingItems: 0,
  totalItems: 0,
  customStats: () => []
})

const progressPercentage = computed(() => {
  if (props.totalItems === 0) return 0
  return Math.round((props.completedItems / props.totalItems) * 100)
})

const stats = computed<Stat[]>(() => {
  if (props.customStats.length > 0) {
    return props.customStats
  }
  
  return [
    {
      label: 'Completed',
      value: props.completedItems,
      icon: '✅',
      color: 'text-green-600'
    },
    {
      label: 'Partial',
      value: props.partialItems,
      icon: '⏳',
      color: 'text-yellow-600'
    },
    {
      label: 'Pending',
      value: props.pendingItems,
      icon: '📋',
      color: 'text-gray-600'
    },
    {
      label: 'Total',
      value: props.totalItems,
      icon: '📊',
      color: 'text-purple-600'
    }
  ]
})
</script>

