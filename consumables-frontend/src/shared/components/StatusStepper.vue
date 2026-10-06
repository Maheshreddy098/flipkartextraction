<template>
  <div class="overflow-x-auto pb-1">
    <ol class="flex min-w-max items-start">
      <li v-for="(step, i) in steps" :key="step.key ?? i" class="flex items-start">
        <!-- Step node -->
        <div class="flex flex-col items-center">
          <div
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ring-2 ring-offset-1 transition-colors"
            :class="circleClass(i)"
          >
            <!-- checkmark for done steps -->
            <svg v-if="stateAt(i) === 'done'" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
            <!-- X for error/rejected -->
            <svg v-else-if="stateAt(i) === 'error'" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
            <!-- step number for future or current -->
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span
            class="mt-1.5 max-w-[5.5rem] text-center text-[10px] leading-snug sm:text-xs"
            :class="labelClass(i)"
          >{{ step.label }}</span>
        </div>

        <!-- Connector line (not after last step) -->
        <div
          v-if="i < steps.length - 1"
          class="mt-3 h-0.5 w-8 shrink-0 sm:w-10"
          :class="stateAt(i) === 'done' ? 'bg-teal-500' : 'bg-gray-200'"
        />
      </li>
    </ol>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  steps: { type: Array, required: true },
  current: { type: String, default: '' },
  isError: { type: Boolean, default: false },
})

const currentIndex = computed(() => {
  const k = (props.current || '').trim().toLowerCase()
  return props.steps.findIndex((s) => {
    const keys = Array.isArray(s.key) ? s.key : [s.key ?? s.label]
    return keys.some((key) => (key || '').toLowerCase() === k)
  })
})

function stateAt(i) {
  const ci = currentIndex.value
  if (ci < 0) return i === 0 ? 'current' : 'future'
  if (i < ci) return 'done'
  if (i === ci) return props.isError ? 'error' : 'current'
  return 'future'
}

function circleClass(i) {
  const s = stateAt(i)
  if (s === 'done')    return 'bg-teal-600 text-white ring-teal-500'
  if (s === 'current') return 'bg-teal-600 text-white ring-teal-400 shadow-sm'
  if (s === 'error')   return 'bg-red-600 text-white ring-red-400'
  return 'bg-white text-gray-400 ring-gray-200'
}

function labelClass(i) {
  const s = stateAt(i)
  if (s === 'done')    return 'font-medium text-teal-700'
  if (s === 'current') return 'font-semibold text-gray-900'
  if (s === 'error')   return 'font-semibold text-red-700'
  return 'text-gray-400'
}
</script>
