<template>
  <component
    :is="to ? 'router-link' : 'div'"
    :to="to || undefined"
    class="bg-white rounded-xl shadow-sm border p-5 block"
    :class="to ? 'hover:shadow-md transition-shadow cursor-pointer' : ''"
  >
    <p class="text-sm text-gray-500">{{ label }}</p>
    <p class="text-3xl font-bold mt-1" :class="textColor">{{ count ?? '—' }}</p>
  </component>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: String,
  count: { type: Number, default: null },
  color: { type: String, default: 'gray' },
  to: { type: String, default: null },
})

const colorMap = {
  gray: 'text-gray-900',
  yellow: 'text-yellow-600',
  blue: 'text-blue-600',
  green: 'text-green-600',
  red: 'text-red-600',
  purple: 'text-purple-600',
}

const textColor = computed(() => colorMap[props.color] || 'text-gray-900')
</script>
