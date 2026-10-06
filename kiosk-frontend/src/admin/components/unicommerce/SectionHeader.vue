<template>
  <div class="mb-4 flex items-center justify-between gap-3">
    <div class="flex items-center gap-3">
      <div class="hidden h-px flex-1 rounded-full bg-slate-200 sm:block" v-if="showDivider" />
      <div class="flex items-center gap-2">
        <div v-if="$slots.icon" class="rounded-lg bg-slate-50 p-2 text-slate-500">
          <slot name="icon" />
        </div>
        <h2 class="text-lg sm:text-2xl font-semibold tracking-tight text-slate-900">
          {{ title }}
        </h2>
      </div>
      <div class="hidden h-px flex-1 rounded-full bg-slate-200 sm:block" v-if="showDivider" />
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true
  },
  showDivider: {
    type: Boolean,
    default: true
  }
})
</script>

