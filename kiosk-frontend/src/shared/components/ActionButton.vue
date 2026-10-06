<template>
  <button
    @click="$emit('click')"
    class="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors text-left w-full"
  >
    <div class="flex items-center mb-2">
      <div class="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center mr-3">
        <span class="text-blue-600 text-lg">{{ feature.icon }}</span>
      </div>
      <h4 class="font-medium text-gray-900">{{ feature.name }}</h4>
    </div>
    <p class="text-sm text-gray-600">{{ feature.description }}</p>
  </button>
</template>

<script setup lang="ts">
interface Feature {
  id: string
  name: string
  description: string
  icon: string
}

interface Props {
  feature: Feature
}

defineProps<Props>()
defineEmits<{
  click: []
}>()
</script>