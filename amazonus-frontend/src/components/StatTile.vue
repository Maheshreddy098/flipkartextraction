<script setup lang="ts">
defineProps<{ label: string; value: number | string; tone?: 'accent' | 'ok' | 'bad' | 'money' | 'muted' }>()
</script>

<template>
  <div class="card px-4 py-3">
    <div class="label">{{ label }}</div>
    <div
      class="num text-2xl mt-1 font-semibold"
      :class="{
        'text-accent': tone === 'accent',
        'text-ok': tone === 'ok',
        'text-bad': tone === 'bad',
        'text-money': tone === 'money',
        'text-ink-400': tone === 'muted',
        'text-ink-100': !tone,
      }"
    >{{ typeof value === 'number' ? value.toLocaleString() : value }}</div>
  </div>
</template>
