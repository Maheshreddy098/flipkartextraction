<script setup lang="ts">
import { computed, ref } from 'vue'
import { call } from '@/api/client'
import { usePeriod } from '@/stores/period'
import { useSession } from '@/stores/session'
import { toast } from '@/stores/toast'
import { useJobPolling } from '@/composables/useJobPolling'
import ConfirmModal from '@/components/ConfirmModal.vue'
import LogPanel from '@/components/LogPanel.vue'

const period = usePeriod()
const session = useSession()

// One polling instance per result endpoint; the log panel shows the active one.
const jobs = {
  fetch: useJobPolling('get_report_fetch_result'),
  fba: useJobPolling('get_fba_shipments_result'),
  post: useJobPolling('get_post_result'),
  cn: useJobPolling('get_credit_note_result'),
  recon: useJobPolling('get_reconciliation_result'),
}
const active = ref<keyof typeof jobs>('fetch')
const log = computed(() => jobs[active.value].log.value)
const running = computed(() => Object.values(jobs).some((j) => j.running.value))

const lookback = ref(30)
const cnDryRun = ref(true)
const resetDryRun = ref(true)
const reconCsvPath = ref('')
const reconFileUrl = ref('')

const confirm = ref<null | { title: string; body: string; money?: boolean; run: () => void }>(null)

function summarize(res: any, label: string) {
  if (res.status === 'hana_down') toast(`${label}: HANA down — job aborted safely`, 'error')
  else if (res.status === 'error') toast(`${label}: ${res.message || 'failed'}`, 'error')
  else toast(`${label} done — ${Object.entries(res).filter(([k, v]) => typeof v === 'number').map(([k, v]) => `${k}=${v}`).join(' ')}`, 'ok', 8000)
}

function runFetch() {
  active.value = 'fetch'
  jobs.fetch.start('enqueue_fetch_via_report', {
    from_date: period.from, to_date: period.to, lookback_days: lookback.value,
  }).then((r) => summarize(r, 'Bulk fetch'))
}

function runFba() {
  active.value = 'fba'
  jobs.fba.start('enqueue_fba_shipments_sync', { from_date: period.from, to_date: period.to })
    .then((r) => summarize(r, 'FBA shipments sync'))
}

async function askPost() {
  const stats = await call<{ ready: number }>('get_stats', { from_date: period.from, to_date: period.to })
  confirm.value = {
    title: 'Post to SAP B1',
    money: true,
    body: `Post ${stats.ready.toLocaleString()} ready orders SHIPPED between ${period.from} and ${period.to}?\n\nShip date decides the MTR month — this run reproduces ${period.label}'s MTR membership. Real AR Invoices will be created.`,
    run: () => {
      active.value = 'post'
      jobs.post.start('enqueue_post', { from_date: period.from, to_date: period.to })
        .then((r) => summarize(r, 'SAP post'))
    },
  }
}

function askBulkRetry() {
  confirm.value = {
    title: 'Bulk retry failed orders',
    money: true,
    body: `Reset every FAILED order shipped between ${period.from} and ${period.to} back to ready and re-post to SAP?`,
    run: () => {
      active.value = 'post'
      jobs.post.start('enqueue_bulk_retry', { from_date: period.from, to_date: period.to })
        .then((r) => summarize(r, 'Bulk retry'))
    },
  }
}

function runCreditNotes() {
  const go = () => {
    active.value = 'cn'
    jobs.cn.start('enqueue_credit_notes_live', {
      from_date: period.from, to_date: period.to, dry_run: cnDryRun.value ? 1 : 0,
    }).then((r) => summarize(r, cnDryRun.value ? 'CN dry-run' : 'CN post'))
  }
  if (cnDryRun.value) return go()
  confirm.value = {
    title: 'Post credit notes (LIVE)',
    money: true,
    body: `Fetch refund events ${period.from} → ${period.to} from the Finances API and post real AR Credit Notes (incl. shipping + tax)?`,
    run: go,
  }
}

function runSupplements() {
  const go = () => {
    active.value = 'cn'
    jobs.cn.start('enqueue_shipping_supplements', {
      from_date: period.from, to_date: period.to, dry_run: cnDryRun.value ? 1 : 0,
    }).then((r) => summarize(r, cnDryRun.value ? 'Supplements dry-run' : 'Supplements post'))
  }
  if (cnDryRun.value) return go()
  confirm.value = {
    title: 'Post shipping supplements (LIVE)',
    money: true,
    body: `Post service-only supplement CNs for pre-fix credit notes missing shipping, window ${period.from} → ${period.to}?`,
    run: go,
  }
}

function runResetForRepost() {
  const go = () => {
    active.value = 'post'
    jobs.post.start('enqueue_reset_for_repost', {
      from_date: period.from, to_date: period.to, dry_run: resetDryRun.value ? 1 : 0,
    }).then((r) => summarize(r, resetDryRun.value ? 'Reset dry-run' : 'Reset for repost'))
  }
  if (resetDryRun.value) return go()
  confirm.value = {
    title: 'Reset posted orders back to ready',
    money: true,
    body: `Reset every POSTED order shipped between ${period.from} and ${period.to} back to ready, clearing its SAP invoice/credit-note pointers?\n\nUse this after repointing INC SAP Settings at a different company DB (e.g. a new test replica, or the live cutover) — otherwise these orders stay stuck "posted" against a DB that no longer has their documents.`,
    run: go,
  }
}

function runReconciliation() {
  if (!reconCsvPath.value.trim()) { toast('Enter the MTR CSV path first', 'error'); return }
  reconFileUrl.value = ''
  active.value = 'recon'
  jobs.recon.start('enqueue_reconciliation', {
    csv_path: reconCsvPath.value.trim(), from_date: period.from, to_date: period.to,
  }).then((r) => {
    if (r.status === 'done') {
      reconFileUrl.value = r.file_url
      const s = r.summary
      toast(
        `Recon done — Invoices: ${s.invoices.matched} matched, ${s.invoices.mismatched} mismatched, ${s.invoices.missing_in_sap} missing. CNs: ${s.credit_notes.matched} matched, ${s.credit_notes.mismatched} mismatched, ${s.credit_notes.missing_in_sap} missing.`,
        'ok', 12000,
      )
    } else {
      summarize(r, 'Reconciliation')
    }
  })
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="!session.canPost" class="card border-money-dim p-3 text-xs text-money">
      View-only access — actions are disabled. Ask for the “Amazon US Manager” role to run the pipeline.
    </div>

    <div class="grid lg:grid-cols-4 gap-4">
      <!-- Stage 1: data in -->
      <div class="card p-4 space-y-3">
        <div class="label">1 · Bring data in</div>
        <div class="flex items-center gap-2">
          <button class="btn-safe" :disabled="!session.canPost || running" @click="runFetch">⚡ Bulk fetch orders</button>
          <label class="text-[11px] text-ink-400">lookback
            <input v-model.number="lookback" type="number" min="0" max="60" class="input !w-14 ml-1 num" />d
          </label>
        </div>
        <button class="btn-safe" :disabled="!session.canPost || running" @click="runFba">⛟ Sync FBA ship dates</button>
        <p class="text-[11px] text-ink-400">
          Fetch stages orders for {{ period.label }} (+lookback for late-settling purchases).
          Ship-date sync must run before posting — it decides the MTR month.
        </p>
      </div>

      <!-- Stage 2: post invoices -->
      <div class="card p-4 space-y-3">
        <div class="label">2 · Post invoices</div>
        <button class="btn-money" :disabled="!session.canPost || running" @click="askPost">↗ Post ready orders to SAP</button>
        <button class="btn-danger" :disabled="!session.canPost || running" @click="askBulkRetry">↻ Bulk retry failed</button>
        <p class="text-[11px] text-ink-400">
          Posts orders shipped in {{ period.label }}. Duplicate-guarded by Amazon order id — safe to re-run.
        </p>
      </div>

      <!-- Stage 3: credit notes -->
      <div class="card p-4 space-y-3">
        <div class="label">3 · Credit notes</div>
        <label class="flex items-center gap-2 text-xs text-ink-300">
          <input v-model="cnDryRun" type="checkbox" class="accent-cyan-400" />
          Dry run (compute only, never posts)
        </label>
        <button class="btn-money" :disabled="!session.canPost || running" @click="runCreditNotes">↩ Run refund credit notes</button>
        <button class="btn-ghost" :disabled="!session.canPost || running" @click="runSupplements">＋ Shipping supplements (repair)</button>
        <p class="text-[11px] text-ink-400">
          Refund events from the Finances API; CNs include shipping + tax. Run again ~1 week into the
          next month — refund events can lag the MTR by days.
        </p>
      </div>

      <!-- Stage 4: repoint at a different SAP DB -->
      <div class="card p-4 space-y-3">
        <div class="label">4 · Repoint SAP DB</div>
        <label class="flex items-center gap-2 text-xs text-ink-300">
          <input v-model="resetDryRun" type="checkbox" class="accent-cyan-400" />
          Dry run (count only, never resets)
        </label>
        <button class="btn-danger" :disabled="!session.canPost || running" @click="runResetForRepost">⟲ Reset posted → ready</button>
        <p class="text-[11px] text-ink-400">
          After switching INC SAP Settings to a different company DB, resets orders shipped in
          {{ period.label }} that are still "posted" against the old DB back to ready, so
          "Post ready orders" (stage 2) re-creates them in the newly connected DB.
        </p>
      </div>
    </div>

    <div class="card p-4 space-y-3">
      <div class="label">Reconciliation — MTR vs SAP</div>
      <div class="flex items-center gap-2 flex-wrap">
        <input
          v-model="reconCsvPath" type="text" placeholder="CustomUnifiedTransaction.csv (filename only, or full path under private/files)"
          class="input flex-1 min-w-[280px]"
        />
        <button class="btn-safe" :disabled="!session.canPost || running" @click="runReconciliation">⇩ Download reconciliation file</button>
        <a v-if="reconFileUrl" :href="reconFileUrl" target="_blank" class="text-xs text-cyan-400 underline">Download workbook</a>
      </div>
      <p class="text-[11px] text-ink-400">
        Cross-checks the MTR CSV (Order + Refund rows) for {{ period.label }} against SAP Invoices +
        Credit Notes pulled live — same check Finance did by hand, now an XLSX with a Summary sheet
        (matched / amount-mismatched / missing) plus one row per order and refund.
        Place the CSV under the site's <code>private/files</code> directory first — any other path is rejected.
      </p>
    </div>

    <LogPanel :lines="log" :running="running" />

    <ConfirmModal
      :open="!!confirm" :title="confirm?.title || ''" :body="confirm?.body || ''"
      :money="confirm?.money" confirm-label="Run"
      @cancel="confirm = null"
      @confirm="confirm?.run(); confirm = null"
    />
  </div>
</template>
