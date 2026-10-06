<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { call } from '@/api/client'
import { usePeriod } from '@/stores/period'
import StatTile from '@/components/StatTile.vue'
import Sparkline from '@/components/Sparkline.vue'

interface Stats { total: number; shipped: number; fetched: number; ready: number; posting: number; posted: number; failed: number; dead: number }
interface Recon {
  unmapped_skus: { seller_sku: string; orders: number }[]
  failed_errors: { error: string; orders: number }[]
  failed_items: { seller_sku: string; sap_item_code: string; orders: number }[]
}
interface Kpis {
  orders_posted: number; revenue_posted: number; aov: number
  refunded_orders: number; refund_rate: number
  daily: { day: string; orders: number; revenue: number }[]
  settlements: { gross: number; fees: number; refunds: number; reimbursements: number; net_payout: number; periods: number }
}
interface Health {
  last_staged: string | null; last_posted: string | null; last_refunded: string | null
  stuck_posting: number; oldest_failed: string | null
  ship_date_coverage: number; sap_session_cached: boolean
}

const period = usePeriod()
const stats = ref<Stats | null>(null)
const recon = ref<Recon | null>(null)
const kpis = ref<Kpis | null>(null)
const health = ref<Health | null>(null)
const loading = ref(false)

const money = (v?: number) => (v == null ? '—' : `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`)

// Gross → fees → refunds → net deposit waterfall from settlements in window.
const bridge = computed(() => {
  const s = kpis.value?.settlements
  if (!s || !s.periods) return []
  const max = Math.max(Math.abs(s.gross), 1)
  return [
    { label: 'Gross sales', v: s.gross, cls: 'bg-ok-dim text-ok' },
    { label: 'Amazon fees', v: -Math.abs(s.fees), cls: 'bg-bad-dim text-bad' },
    { label: 'Refunds', v: -Math.abs(s.refunds), cls: 'bg-money-dim text-money' },
    { label: 'Reimbursements', v: s.reimbursements, cls: 'bg-accent-dim text-accent' },
    { label: 'Net deposit', v: s.net_payout, cls: 'bg-ink-600 text-ink-100' },
  ].map((x) => ({ ...x, pct: Math.max((Math.abs(x.v) / max) * 100, x.v !== 0 ? 1.5 : 0) }))
})

function ago(ts: string | null) {
  if (!ts) return 'never'
  const mins = Math.round((Date.now() - new Date(ts.replace(' ', 'T')).getTime()) / 60000)
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`
  return `${Math.round(mins / 1440)}d ago`
}

const pipeline = computed(() => {
  if (!stats.value) return []
  const s = stats.value
  const max = Math.max(s.total, 1)
  return [
    { label: 'fetched', n: s.fetched, cls: 'bg-ink-600' },
    { label: 'ready', n: s.ready, cls: 'bg-accent-dim' },
    { label: 'posted', n: s.posted, cls: 'bg-ok-dim' },
    { label: 'failed', n: s.failed, cls: 'bg-bad-dim' },
  ].map((x) => ({ ...x, pct: Math.max((x.n / max) * 100, x.n > 0 ? 1.5 : 0) }))
})

async function load() {
  loading.value = true
  try {
    const args = { from_date: period.from, to_date: period.to }
    const [s, r, k, h] = await Promise.all([
      call<Stats>('get_stats', args),
      call<Recon>('get_recon_summary', args),
      call<Kpis>('get_kpis', args),
      call<Health>('get_health'),
    ])
    stats.value = s
    recon.value = r
    kpis.value = k
    health.value = h
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => period.key, load)
</script>

<template>
  <div class="space-y-5">
    <!-- Business KPIs (management) -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatTile label="Revenue posted" :value="money(kpis?.revenue_posted)" tone="ok" />
      <StatTile label="Orders posted" :value="kpis?.orders_posted ?? '—'" />
      <StatTile label="Avg order value" :value="money(kpis?.aov)" tone="accent" />
      <StatTile :label="`Refund rate (${kpis?.refunded_orders ?? 0} CNs)`" :value="kpis ? kpis.refund_rate + '%' : '—'" tone="money" />
    </div>

    <div class="grid lg:grid-cols-2 gap-4">
      <!-- Daily revenue trend -->
      <div class="card p-4">
        <div class="flex items-baseline justify-between">
          <div class="label">Daily revenue · {{ period.label }}</div>
          <div class="num text-[11px] text-ink-400">{{ kpis?.daily.length ?? 0 }} days</div>
        </div>
        <div class="mt-3 text-ok">
          <Sparkline :points="kpis?.daily.map((d) => d.revenue) ?? []" :height="56" />
        </div>
        <div class="mt-1 flex justify-between text-[10px] text-ink-400 num">
          <span>{{ kpis?.daily[0]?.day ?? '' }}</span>
          <span>{{ kpis?.daily[kpis.daily.length - 1]?.day ?? '' }}</span>
        </div>
      </div>

      <!-- Settlement payout bridge (finance) -->
      <div class="card p-4">
        <div class="label mb-3">Payout bridge <span class="text-ink-400 normal-case">(settlements overlapping window{{ kpis?.settlements.periods ? ` · ${kpis.settlements.periods}` : '' }})</span></div>
        <div v-if="!bridge.length" class="text-xs text-ink-400">No settlement periods overlap this window — sync settlements from the Actions tab.</div>
        <div v-else class="space-y-1.5">
          <div v-for="b in bridge" :key="b.label" class="flex items-center gap-3">
            <div class="w-28 text-[11px] text-ink-300">{{ b.label }}</div>
            <div class="flex-1 h-4 bg-ink-900 rounded overflow-hidden">
              <div class="h-full rounded" :class="b.cls.split(' ')[0]" :style="{ width: b.pct + '%' }" />
            </div>
            <div class="w-24 num text-right text-xs" :class="b.cls.split(' ')[1]">{{ money(b.v) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pipeline stage tiles -->
    <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
      <StatTile label="Total orders" :value="stats?.total ?? '—'" />
      <StatTile label="Shipped" :value="stats?.shipped ?? '—'" tone="accent" />
      <StatTile label="Posted to SAP" :value="stats?.posted ?? '—'" tone="ok" />
      <StatTile label="Ready to post" :value="stats?.ready ?? '—'" tone="money" />
      <StatTile label="Failed" :value="stats?.failed ?? '—'" tone="bad" />
      <StatTile label="Awaiting mapping" :value="stats?.fetched ?? '—'" tone="muted" />
    </div>

    <!-- Pipeline -->
    <div class="card p-4">
      <div class="label mb-3">Pipeline · {{ period.label }}</div>
      <div class="space-y-2">
        <div v-for="p in pipeline" :key="p.label" class="flex items-center gap-3">
          <div class="w-16 text-[11px] text-ink-300">{{ p.label }}</div>
          <div class="flex-1 h-5 bg-ink-900 rounded overflow-hidden">
            <div class="h-full rounded transition-all duration-500" :class="p.cls" :style="{ width: p.pct + '%' }" />
          </div>
          <div class="w-16 num text-right text-xs">{{ p.n.toLocaleString() }}</div>
        </div>
      </div>
      <p class="mt-3 text-[11px] text-ink-400">
        Window = ship date (MTR month). Orders without a ship date show under their purchase month
        and wait for the FBA shipments sync before posting.
      </p>
    </div>

    <!-- Blockers -->
    <div class="grid md:grid-cols-2 gap-4">
      <div class="card p-4">
        <div class="label mb-2">Unmapped SKUs <span class="text-ink-400 normal-case">(blocking staging → ready)</span></div>
        <div v-if="!recon?.unmapped_skus?.length" class="text-xs text-ink-400">None — all SKUs mapped.</div>
        <table v-else class="w-full text-xs">
          <tbody>
            <tr v-for="u in recon.unmapped_skus" :key="u.seller_sku" class="border-b border-ink-700/50 last:border-0">
              <td class="py-1.5 font-mono">{{ u.seller_sku }}</td>
              <td class="py-1.5 num text-right text-bad">{{ u.orders }} orders</td>
            </tr>
          </tbody>
        </table>
        <p v-if="recon?.unmapped_skus?.length" class="mt-2 text-[11px] text-ink-400">
          Fix: set U_Amz_SKU on the SAP item master — the hourly sync picks it up.
        </p>
      </div>

      <div class="card p-4">
        <div class="label mb-2">Failed postings <span class="text-ink-400 normal-case">(by SAP error)</span></div>
        <div v-if="!recon?.failed_errors?.length" class="text-xs text-ink-400">No failed orders in this window.</div>
        <table v-else class="w-full text-xs">
          <tbody>
            <tr v-for="f in recon.failed_errors" :key="f.error" class="border-b border-ink-700/50 last:border-0">
              <td class="py-1.5 text-ink-300 pr-2">{{ f.error || '(no error text)' }}</td>
              <td class="py-1.5 num text-right text-bad whitespace-nowrap">{{ f.orders }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="recon?.failed_items?.length" class="mt-3">
          <div class="label mb-1">Items involved</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="it in recon.failed_items" :key="it.seller_sku + it.sap_item_code"
                  class="px-1.5 py-0.5 rounded border border-ink-600 font-mono text-[10px] text-ink-300">
              {{ it.sap_item_code }} · {{ it.orders }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Pipeline health (tech) -->
    <div class="card p-4">
      <div class="label mb-3">Pipeline health</div>
      <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 text-xs">
        <div>
          <div class="label">Last order staged</div>
          <div class="mt-1 num">{{ ago(health?.last_staged ?? null) }}</div>
        </div>
        <div>
          <div class="label">Last SAP post</div>
          <div class="mt-1 num">{{ ago(health?.last_posted ?? null) }}</div>
        </div>
        <div>
          <div class="label">Last credit note</div>
          <div class="mt-1 num">{{ ago(health?.last_refunded ?? null) }}</div>
        </div>
        <div>
          <div class="label">Stuck in posting</div>
          <div class="mt-1 num" :class="health?.stuck_posting ? 'text-bad' : 'text-ok'">{{ health?.stuck_posting ?? '—' }}</div>
        </div>
        <div>
          <div class="label">Ship-date coverage</div>
          <div class="mt-1 num" :class="(health?.ship_date_coverage ?? 100) < 99 ? 'text-money' : 'text-ok'">
            {{ health?.ship_date_coverage ?? '—' }}%
          </div>
        </div>
        <div>
          <div class="label">SAP session</div>
          <div class="mt-1" :class="health?.sap_session_cached ? 'text-ok' : 'text-ink-400'">
            {{ health?.sap_session_cached ? '● active' : '○ will re-login' }}
          </div>
        </div>
      </div>
      <p v-if="health?.oldest_failed" class="mt-3 text-[11px] text-ink-400">
        Oldest unresolved failed order: <span class="num">{{ health.oldest_failed.slice(0, 16) }}</span> — clear via Bulk retry once stock/mapping is fixed.
      </p>
    </div>
  </div>
</template>
