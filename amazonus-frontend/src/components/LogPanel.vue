<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { JobLogLine } from '@/composables/useJobPolling'

const props = defineProps<{ lines: JobLogLine[]; running: boolean }>()
const box = ref<HTMLElement>()

watch(
  () => props.lines.length,
  async () => {
    await nextTick()
    box.value?.scrollTo({ top: box.value.scrollHeight })
  },
)
</script>

<template>
  <div class="card overflow-hidden">
    <div class="flex items-center justify-between px-3 py-2 border-b border-ink-700">
      <span class="label">Job log</span>
      <span v-if="running" class="text-[10px] text-accent animate-pulse">● running</span>
    </div>
    <div ref="box" class="h-64 overflow-auto px-3 py-2 font-mono text-[11px] leading-5 bg-ink-900/70">
      <div v-if="!lines.length" class="text-ink-400">No output yet.</div>
      <div
        v-for="(l, i) in lines" :key="i"
        :class="{ 'text-bad': l.level === 'error', 'text-money': l.level === 'warn', 'text-ink-300': l.level === 'info' }"
      >{{ l.msg }}</div>
    </div>
  </div>
</template>
