<template>
  <div class="space-y-4">
    <div
      v-for="activity in activities"
      :key="activity.id"
      class="flex items-start space-x-3"
    >
      <div class="flex-shrink-0">
        <div class="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
          <span class="text-gray-600 text-sm">{{ activity.icon }}</span>
        </div>
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-gray-900">{{ activity.action }}</p>
        <p class="text-sm text-gray-500">{{ activity.time }}</p>
      </div>
    </div>
    <div v-if="activities.length === 0" class="text-center text-gray-500 py-4">
      No recent activity
    </div>
  </div>
</template>

<script setup lang="ts">
interface Activity {
  id: number | string
  action: string
  time: string
  icon: string
}

interface Props {
  activities: Activity[]
}

defineProps<Props>()
</script>