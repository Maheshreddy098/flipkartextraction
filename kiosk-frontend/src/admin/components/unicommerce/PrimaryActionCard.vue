<template>
  <div
    class="flex h-full flex-col rounded-xl border-2 border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
  >
    <div class="mb-4 flex flex-1 items-start gap-3">
      <div v-if="$slots.icon" class="mt-1 rounded-lg bg-slate-50 p-2 text-slate-600">
        <slot name="icon" />
      </div>
      <div class="space-y-2">
        <h3 class="text-lg font-semibold text-slate-900">
          {{ title }}
        </h3>
        <p v-if="description" class="text-sm text-slate-600">
          {{ description }}
        </p>
        <div v-if="bullets && bullets.length" class="space-y-1.5">
          <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            {{ bulletsTitle }}
          </p>
          <ul class="list-disc space-y-0.5 pl-4 text-xs text-slate-600">
            <li v-for="(item, idx) in bullets" :key="idx">
              {{ item }}
            </li>
          </ul>
        </div>
        <slot />
      </div>
    </div>
    <button
      type="button"
      :disabled="loading || disabled"
      :class="[
        'mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
        variantClass,
        (loading || disabled) && 'cursor-not-allowed opacity-60'
      ]"
      @click="$emit('click')"
    >
      <svg
        v-if="loading"
        class="h-4 w-4 animate-spin"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke-width="4" />
        <path
          class="opacity-75"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="4"
          d="M4 12a8 8 0 018-8"
        />
      </svg>
      <span>{{ buttonLabel }}</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  bulletsTitle: {
    type: String,
    default: 'Process'
  },
  bullets: {
    type: Array,
    default: () => []
  },
  buttonLabel: {
    type: String,
    required: true
  },
  variant: {
    type: String,
    default: 'primary' // primary | success | danger
  },
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const variantMap = {
  primary: 'bg-indigo-600 hover:bg-indigo-700 focus-visible:ring-indigo-500',
  success: 'bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500',
  danger: 'bg-red-600 hover:bg-red-700 focus-visible:ring-red-500'
}

const variantClass = computed(() => variantMap[props.variant] || variantMap.primary)
</script>

