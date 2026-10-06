<script setup lang="ts">
defineProps<{ open: boolean; title: string; body: string; confirmLabel?: string; money?: boolean }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-40 flex items-center justify-center bg-black/60" @click.self="emit('cancel')">
      <div class="card w-[26rem] p-5 shadow-2xl">
        <div class="text-sm font-semibold" :class="money ? 'text-money' : 'text-ink-100'">{{ title }}</div>
        <p class="mt-2 text-xs text-ink-300 whitespace-pre-line">{{ body }}</p>
        <div class="mt-4 flex justify-end gap-2">
          <button class="btn-ghost" @click="emit('cancel')">Cancel</button>
          <button :class="money ? 'btn-money' : 'btn-safe'" @click="emit('confirm')">
            {{ confirmLabel || 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
