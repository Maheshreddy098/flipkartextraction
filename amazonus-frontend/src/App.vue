<script setup lang="ts">
import { onMounted } from 'vue'
import { useSession } from '@/stores/session'
import { usePeriod } from '@/stores/period'
import { toasts } from '@/stores/toast'
import PeriodPicker from '@/components/PeriodPicker.vue'

const session = useSession()
const period = usePeriod()

const nav = [
  { to: '/', label: 'Overview', icon: '◉' },
  { to: '/orders', label: 'Orders', icon: '▤' },
  { to: '/actions', label: 'Actions', icon: '⚡' },
  { to: '/settlements', label: 'Settlements', icon: '⇄' },
  { to: '/credit-notes', label: 'Credit Notes', icon: '↩' },
  { to: '/inventory', label: 'Inventory', icon: '▦' },
]

onMounted(() => session.load())
</script>

<template>
  <div class="flex min-h-screen">
    <!-- Sidebar -->
    <aside class="w-52 shrink-0 border-r border-ink-700 bg-ink-900 flex flex-col">
      <div class="px-4 py-4 border-b border-ink-700">
        <div class="text-sm font-semibold tracking-tight">Amazon US</div>
        <div class="label mt-0.5">Ops Console</div>
      </div>
      <nav class="flex-1 py-3">
        <RouterLink
          v-for="n in nav" :key="n.to" :to="n.to"
          class="flex items-center gap-2.5 px-4 py-2 text-xs text-ink-300 hover:text-ink-100 hover:bg-ink-800/60 border-l-2 border-transparent"
          exact-active-class="!text-accent !border-accent bg-ink-800/60"
        >
          <span class="opacity-70">{{ n.icon }}</span>{{ n.label }}
        </RouterLink>
      </nav>
      <div class="px-4 py-3 border-t border-ink-700 text-[11px]">
        <div class="text-ink-300 truncate">{{ session.fullName || session.user }}</div>
        <div class="mt-0.5" :class="session.canPost ? 'text-money' : 'text-ink-400'">
          {{ session.canPost ? '● can post to SAP' : '○ view only' }}
        </div>
      </div>
    </aside>

    <!-- Main -->
    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-14 shrink-0 border-b border-ink-700 bg-ink-900/80 backdrop-blur flex items-center justify-between px-5">
        <div class="text-sm text-ink-300">
          <span class="label">Reporting window · ship date = MTR month</span>
        </div>
        <PeriodPicker />
      </header>
      <main class="flex-1 overflow-auto p-5">
        <RouterView />
      </main>
    </div>

    <!-- Toasts -->
    <div class="fixed bottom-4 right-4 z-50 space-y-2 w-80">
      <div
        v-for="t in toasts" :key="t.id"
        class="card px-3 py-2 text-xs shadow-lg"
        :class="{ 'border-bad-dim text-bad': t.kind === 'error', 'border-ok-dim text-ok': t.kind === 'ok', 'text-ink-100': t.kind === 'info' }"
      >{{ t.text }}</div>
    </div>
  </div>
</template>
