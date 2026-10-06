import { ref } from 'vue'
import { call } from '@/api/client'

export interface JobLogLine { msg: string; level: 'info' | 'warn' | 'error'; at?: string }

export interface JobResult { status: string; [key: string]: any }

const TERMINAL = new Set(['done', 'dry_run', 'error', 'hana_down', 'not_found'])

/**
 * Shared background-job runner: calls an enqueue endpoint, then polls its
 * result endpoint every `intervalMs`, streaming new log lines. All five job
 * families (fetch, post, FBA, settlements, credit notes) use the same
 * cache-payload shape: {status, log: [{msg, level, at}], ...totals}.
 */
export function useJobPolling(resultMethod: string, intervalMs = 2500) {
  const running = ref(false)
  const log = ref<JobLogLine[]>([])
  const result = ref<JobResult | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null
  let cursor = 0

  function stop() {
    if (timer) clearInterval(timer)
    timer = null
    running.value = false
  }

  async function start(enqueueMethod: string, params: Record<string, any>): Promise<JobResult> {
    stop()
    log.value = []
    result.value = null
    cursor = 0
    running.value = true

    let jobId: string
    try {
      const res = await call<{ job_id: string }>(enqueueMethod, params)
      jobId = res.job_id
    } catch (err) {
      running.value = false
      throw err
    }

    return new Promise<JobResult>((resolve) => {
      timer = setInterval(async () => {
        let data: JobResult
        try {
          data = await call<JobResult>(resultMethod, { job_id: jobId })
        } catch {
          return // transient poll failure — keep polling
        }
        const lines = (data.log || []) as JobLogLine[]
        if (lines.length > cursor) {
          log.value.push(...lines.slice(cursor))
          cursor = lines.length
        }
        if (TERMINAL.has(data.status)) {
          result.value = data
          stop()
          resolve(data)
        }
      }, intervalMs)
    })
  }

  return { running, log, result, start, stop }
}
