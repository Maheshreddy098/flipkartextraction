<template>
  <div
    :class="[
      'relative overflow-hidden rounded-xl border bg-white p-5 shadow-sm transition hover:shadow-md',
      borderClass
    ]"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="space-y-1">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          {{ label }}
        </p>
        <div class="flex items-baseline gap-2">
          <p class="text-2xl font-semibold text-slate-900">
            <slot name="value">
              {{ value }}
            </slot>
          </p>
          <p v-if="suffix" class="text-xs font-medium text-slate-500">
            {{ suffix }}
          </p>
        </div>
        <p v-if="helper" class="text-xs text-slate-500">
          {{ helper }}
        </p>
      </div>
      <div v-if="$slots.icon" class="rounded-lg bg-slate-50 p-2 text-slate-500">
        <slot name="icon" />
      </div>
      <div
        v-else
        class="rounded-lg bg-slate-50 p-2 text-slate-400"
        aria-hidden="true"
      >
        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M11 11V7a4 4 0 118 0v4m-9 4h10"
          />
        </svg>
      </div>
    </div>

    <div v-if="$slots.trend" class="mt-3 flex items-center gap-2 text-xs">
      <slot name="trend" />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    default: ''
  },
  suffix: {
    type: String,
    default: ''
  },
  helper: {
    type: String,
    default: ''
  },
  borderClass: {
    type: String,
    default: 'border-slate-100'
  }
})
</script>

