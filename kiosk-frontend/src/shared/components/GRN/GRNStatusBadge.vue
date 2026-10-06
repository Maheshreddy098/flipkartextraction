<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      statusClasses
    ]"
  >
    <span class="mr-1">{{ statusIcon }}</span>
    {{ label || status }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Status = 'open' | 'closed' | 'partial' | 'pending' | 'completed' | 'error' | 'warning' | 'success' | 'info'

interface Props {
  status: Status
  label?: string
}

const props = defineProps<Props>()

const statusClasses = computed(() => {
  const classes: Record<Status, string> = {
    open: 'bg-blue-100 text-blue-800',
    closed: 'bg-gray-100 text-gray-800',
    partial: 'bg-yellow-100 text-yellow-800',
    pending: 'bg-orange-100 text-orange-800',
    completed: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
    warning: 'bg-yellow-100 text-yellow-800',
    success: 'bg-green-100 text-green-800',
    info: 'bg-blue-100 text-blue-800'
  }
  return classes[props.status] || classes.info
})

const statusIcon = computed(() => {
  const icons: Record<Status, string> = {
    open: '🔓',
    closed: '🔒',
    partial: '⏳',
    pending: '📋',
    completed: '✅',
    error: '❌',
    warning: '⚠️',
    success: '✅',
    info: 'ℹ️'
  }
  return icons[props.status] || icons.info
})
</script>

