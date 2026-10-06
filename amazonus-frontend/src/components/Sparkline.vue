<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ points: number[]; height?: number }>()

const H = computed(() => props.height ?? 48)
const W = 260

const path = computed(() => {
  const pts = props.points
  if (pts.length < 2) return ''
  const max = Math.max(...pts, 1)
  const step = W / (pts.length - 1)
  return pts
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${(H.value - (v / max) * (H.value - 4) - 2).toFixed(1)}`)
    .join(' ')
})

const area = computed(() => (path.value ? `${path.value} L${W},${H.value} L0,${H.value} Z` : ''))
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" :style="{ height: H + 'px' }" preserveAspectRatio="none" aria-hidden="true">
    <path v-if="area" :d="area" fill="currentColor" opacity="0.12" />
    <path v-if="path" :d="path" fill="none" stroke="currentColor" stroke-width="1.5" />
  </svg>
</template>
