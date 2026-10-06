<template>
  <div class="bg-white rounded-xl shadow-sm border p-5">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold">{{ title }}</h2>
      <router-link :to="viewAllRoute" class="text-sm text-blue-600 hover:underline">View All</router-link>
    </div>
    <div v-if="!items.length" class="text-gray-400 text-sm py-4">{{ emptyMessage }}</div>
    <template v-else>
      <router-link
        v-for="item in items"
        :key="itemKey(item)"
        :to="getRowLink(item)"
        class="flex items-center justify-between py-2 border-b last:border-0 text-left w-full cursor-pointer hover:bg-gray-50 transition rounded px-1 -mx-1"
      >
        <div class="min-w-0">
          <span class="font-medium text-sm">{{ primaryLabel(item) }}</span>
          <span v-if="secondaryLabel(item)" class="text-gray-500 text-sm ml-2">{{ secondaryLabel(item) }}</span>
        </div>
        <StatusBadge v-if="status(item)" :status="status(item)" class="flex-shrink-0 ml-2" />
      </router-link>
    </template>
  </div>
</template>

<script setup>
import StatusBadge from './StatusBadge.vue'

defineProps({
  title: { type: String, required: true },
  viewAllRoute: { type: String, required: true },
  items: { type: Array, default: () => [] },
  itemKey: { type: Function, default: (item) => item.name || item.id },
  getRowLink: { type: Function, required: true },
  primaryLabel: { type: Function, required: true },
  secondaryLabel: { type: Function, default: () => '' },
  status: { type: Function, default: () => null },
  emptyMessage: { type: String, default: 'No items yet' },
})
</script>
