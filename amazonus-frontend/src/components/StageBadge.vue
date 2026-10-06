<script setup lang="ts">
defineProps<{ stage: string }>()
const cls: Record<string, string> = {
  posted: 'text-ok border-ok-dim',
  ready: 'text-accent border-accent-dim',
  failed: 'text-bad border-bad-dim',
  fetched: 'text-ink-300 border-ink-600',
  posting: 'text-money border-money-dim',
  dead: 'text-ink-400 border-ink-600',
}
</script>

<template>
  <span class="inline-block px-1.5 py-0.5 rounded border text-[10px] uppercase tracking-wider"
        :class="cls[stage] || 'text-ink-300 border-ink-600'">{{ stage }}</span>
</template>
