<template>
  <div
    :class="[
      'flex gap-3 rounded-lg border px-4 py-3 text-xs sm:text-sm',
      toneClass
    ]"
  >
    <div class="mt-0.5 flex-shrink-0 text-current" aria-hidden="true">
      <slot name="icon">
        <svg v-if="tone === 'info'" class="h-4 w-4 sm:h-5 sm:w-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10A8 8 0 11.001 9.999 8 8 0 0118 10zm-9-4a1 1 0 11-2 .001 1 1 0 012-.001zM7 9a1 1 0 000 2v3a1 1 0 001 1h2a1 1 0 100-2v-3a1 1 0 00-1-1H7z" clip-rule="evenodd" />
        </svg>
        <svg v-else-if="tone === 'warning'" class="h-4 w-4 sm:h-5 sm:w-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l6.518 11.59C19.021 16.92 18.277 18 17.18 18H2.82c-1.098 0-1.842-1.08-1.58-2.31l6.518-11.59zM11 14a1 1 0 11-2 .001 1 1 0 012-.001zM9 8a1 1 0 112 0v3a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
        <svg v-else-if="tone === 'error'" class="h-4 w-4 sm:h-5 sm:w-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L10 9.586 7.707 7.293A1 1 0 106.293 8.707L8.586 11l-1.293 1.293a1 1 0 101.414 1.414L10 12.414l2.293 2.293a1 1 0 001.414-1.414L11.414 11l2.293-2.293z" clip-rule="evenodd" />
        </svg>
        <svg v-else class="h-4 w-4 sm:h-5 sm:w-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-5a1 1 0 102 0v-3a1 1 0 10-2 0v3zm1-7a1.25 1.25 0 100 2.5A1.25 1.25 0 0010 6z" clip-rule="evenodd" />
        </svg>
      </slot>
    </div>
    <div class="flex-1 space-y-1">
      <p v-if="title" class="font-semibold">
        {{ title }}
      </p>
      <div class="text-[11px] sm:text-xs leading-relaxed">
        <slot />
      </div>
    </div>
    <div v-if="$slots.actions" class="flex flex-shrink-0 items-start">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  tone: {
    type: String,
    default: 'info' // info | warning | error | success
  },
  title: {
    type: String,
    default: ''
  }
})

const toneClassMap = {
  info: 'border-blue-200 bg-blue-50 text-blue-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800'
}

const toneClass = computed(() => toneClassMap[props.tone] || toneClassMap.info)
</script>

