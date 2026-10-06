<template>
  <div class="fixed top-4 right-4 z-50 space-y-2 max-w-sm">
    <transition-group name="notify">
      <div
        v-for="n in store.items"
        :key="n.id"
        :class="classes[n.type]"
        class="px-4 py-3 rounded-lg shadow-lg text-sm flex items-center justify-between"
      >
        <span>{{ n.message }}</span>
        <button @click="store.remove(n.id)" class="ml-3 opacity-70 hover:opacity-100">&times;</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useNotificationStore } from '@/core/stores/notifications.js'

const store = useNotificationStore()

const classes = {
  success: 'bg-green-600 text-white',
  error: 'bg-red-600 text-white',
  info: 'bg-blue-600 text-white',
}
</script>

<style scoped>
.notify-enter-active, .notify-leave-active { transition: all 0.3s ease; }
.notify-enter-from { opacity: 0; transform: translateX(30px); }
.notify-leave-to { opacity: 0; transform: translateX(30px); }
</style>
