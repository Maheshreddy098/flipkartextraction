<template>
  <div class="bg-white border-b border-gray-200 p-4 sticky top-0 z-30 shadow-sm">
    <div class="flex items-center justify-between">
      <!-- Left: Back Button + Title -->
      <div class="flex items-center gap-4">
        <button
          v-if="showBackButton"
          @click="$emit('back')"
          type="button"
          class="flex items-center gap-2 px-3 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          <span class="font-medium">Back</span>
        </button>
        
        <div>
          <h2 class="text-xl font-bold text-gray-900">{{ title }}</h2>
          <p v-if="subtitle" class="text-sm text-gray-600 mt-0.5">{{ subtitle }}</p>
        </div>
      </div>

      <!-- Right: PO Info + Actions -->
      <div class="flex items-center gap-4">
        <!-- PO Information -->
        <div v-if="poNumber" class="text-right">
          <div class="text-sm font-medium text-gray-900">
            PO #{{ poNumber }}
          </div>
          <div v-if="vendorName" class="text-xs text-gray-600">
            {{ vendorName }}
          </div>
        </div>

        <!-- Action Slots -->
        <slot name="actions"></slot>

        <!-- Help/Shortcuts Button -->
        <button
          v-if="showHelpButton"
          @click="$emit('show-help')"
          type="button"
          class="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          title="Keyboard Shortcuts"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title?: string
  subtitle?: string
  poNumber?: string | number
  vendorName?: string
  showBackButton?: boolean
  showHelpButton?: boolean
}

withDefaults(defineProps<Props>(), {
  title: 'Create GRN',
  subtitle: '',
  poNumber: '',
  vendorName: '',
  showBackButton: true,
  showHelpButton: true
})

defineEmits<{
  back: []
  'show-help': []
}>()
</script>

