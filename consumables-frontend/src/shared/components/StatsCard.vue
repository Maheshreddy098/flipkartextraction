<template>
  <div class="bg-white rounded-lg shadow p-6">
    <div class="flex items-center">
      <div class="flex-shrink-0">
        <div 
          class="w-8 h-8 rounded-md flex items-center justify-center"
          :class="iconColorClass"
        >
          <component 
            :is="iconComponent" 
            class="w-5 h-5 text-white" 
            v-if="iconComponent"
          />
          <span v-else class="text-white text-lg">{{ icon }}</span>
        </div>
      </div>
      <div class="ml-4">
        <p class="text-sm font-medium text-gray-500">{{ title }}</p>
        <p class="text-2xl font-semibold text-gray-900">
          <span v-if="loading" class="animate-pulse text-gray-400">Loading…</span>
          <span v-else>{{ formattedValue }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title: string
  value: string | number
  icon: string
  color: 'blue' | 'green' | 'yellow' | 'purple'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const iconColorClass = computed(() => {
  const colorMap = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    purple: 'bg-purple-500'
  }
  return colorMap[props.color]
})

const iconComponent = computed(() => {
  // Fallback to text icon; plug in lucide icons if needed
  return undefined as any
})

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString()
  }
  return props.value
})
</script>