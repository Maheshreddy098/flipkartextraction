<template>
  <span :class="badgeClass" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
    {{ status }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ status: { type: String, required: true } })

const colorMap = {
  Draft: 'bg-gray-100 text-gray-700',
  'Pending Approval': 'bg-yellow-100 text-yellow-800',
  Approved: 'bg-blue-100 text-blue-800',
  Rejected: 'bg-red-100 text-red-800',
  Accepted: 'bg-indigo-100 text-indigo-800',
  Received: 'bg-green-100 text-green-800',
  'In Progress': 'bg-purple-100 text-purple-800',
  Completed: 'bg-green-100 text-green-800',
  Pending: 'bg-yellow-100 text-yellow-800',
  Processed: 'bg-green-100 text-green-800',
  'Sent to SAP': 'bg-green-100 text-green-800',
  Packaging: 'bg-amber-100 text-amber-800',
  'In Preparation': 'bg-purple-100 text-purple-800',
  Dispatched: 'bg-green-100 text-green-800',
  'Sent to SAP': 'bg-green-100 text-green-800',
  Posted: 'bg-green-100 text-green-800',
  Error: 'bg-red-100 text-red-800',
}

const badgeClass = computed(() => colorMap[props.status] || 'bg-gray-100 text-gray-700')
</script>
