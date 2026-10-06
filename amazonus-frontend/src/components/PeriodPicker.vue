<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePeriod } from '@/stores/period'

const period = usePeriod()
const open = ref(false)
const draftFrom = ref(period.from)
const draftTo = ref(period.to)

// Last 12 months for quick jumps, newest first.
const recentMonths = computed(() => {
  const out: { ym: string; label: string }[] = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    out.push({ ym, label: d.toLocaleString('en', { month: 'short', year: 'numeric' }) })
  }
  return out
})

function pickMonth(ym: string) {
  period.setMonth(ym)
  open.value = false
}

function applyRange() {
  period.setRange(draftFrom.value, draftTo.value)
  open.value = false
}

function fmt(d: string) {
  const [y, m, day] = d.split('-')
  return `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m) - 1]} ${Number(day)}`
}
</script>

<template>
  <div class="relative">
    <div class="flex items-center gap-1">
      <button
        class="btn-ghost !px-2" :disabled="period.mode !== 'month'"
        aria-label="Previous month" @click="period.stepMonth(-1)"
      >‹</button>

      <button
        class="btn-ghost min-w-[13rem] justify-center !py-2"
        aria-haspopup="true" :aria-expanded="open"
        @click="open = !open"
      >
        <span class="font-medium text-ink-100">{{ period.label }}</span>
        <span class="num text-[10px] text-ink-400 ml-1.5">{{ fmt(period.from) }} → {{ fmt(period.to) }}</span>
        <span class="text-ink-400 ml-1">▾</span>
      </button>

      <button
        class="btn-ghost !px-2" :disabled="period.mode !== 'month'"
        aria-label="Next month" @click="period.stepMonth(1)"
      >›</button>
    </div>

    <!-- Dropdown -->
    <div
      v-if="open"
      class="absolute right-0 top-full mt-2 z-30 card w-[22rem] p-4 shadow-2xl"
    >
      <div class="label mb-2">Jump to month</div>
      <div class="grid grid-cols-4 gap-1.5">
        <button
          v-for="m in recentMonths" :key="m.ym"
          class="px-2 py-1.5 rounded text-[11px] border transition-colors"
          :class="period.mode === 'month' && period.month === m.ym
            ? 'border-accent-dim text-accent bg-accent/10'
            : 'border-ink-600 text-ink-300 hover:bg-ink-700/50'"
          @click="pickMonth(m.ym)"
        >{{ m.label }}</button>
      </div>

      <div class="label mt-4 mb-2">Custom range</div>
      <div class="flex items-center gap-2">
        <input v-model="draftFrom" type="date" class="input num flex-1" aria-label="From date" />
        <span class="text-ink-400">→</span>
        <input v-model="draftTo" type="date" class="input num flex-1" aria-label="To date" />
      </div>
      <div class="mt-3 flex items-center justify-between">
        <p class="text-[10px] text-ink-400 pr-3">Window filters by ship date — the MTR month.</p>
        <button class="btn-safe" :disabled="!draftFrom || !draftTo || draftFrom > draftTo" @click="applyRange">Apply range</button>
      </div>
    </div>

    <!-- Click-away -->
    <div v-if="open" class="fixed inset-0 z-20" @click="open = false" />
  </div>
</template>
