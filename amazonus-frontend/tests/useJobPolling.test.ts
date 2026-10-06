import { beforeEach, describe, expect, it, vi } from 'vitest'

const calls: Array<{ method: string; params: any }> = []
let responses: Record<string, any[]> = {}

vi.mock('@/api/client', () => ({
  call: async (method: string, params: any = {}) => {
    calls.push({ method, params })
    const queue = responses[method]
    if (!queue?.length) throw new Error(`no mock response for ${method}`)
    return queue.length > 1 ? queue.shift() : queue[0]
  },
}))

import { useJobPolling } from '@/composables/useJobPolling'

describe('useJobPolling', () => {
  beforeEach(() => {
    calls.length = 0
    responses = {}
    vi.useFakeTimers()
  })

  it('enqueues, streams log lines, resolves on done', async () => {
    responses['enqueue_post'] = [{ job_id: 'j1' }]
    responses['get_post_result'] = [
      { status: 'running', log: [{ msg: 'a', level: 'info' }] },
      { status: 'running', log: [{ msg: 'a', level: 'info' }, { msg: 'b', level: 'warn' }] },
      { status: 'done', posted: 5, log: [{ msg: 'a', level: 'info' }, { msg: 'b', level: 'warn' }] },
    ]
    const job = useJobPolling('get_post_result', 10)
    const p = job.start('enqueue_post', { from_date: 'x', to_date: 'y' })
    expect(job.running.value).toBe(true)
    await vi.advanceTimersByTimeAsync(50)
    const res = await p
    expect(res.status).toBe('done')
    expect(res.posted).toBe(5)
    expect(job.log.value.map((l) => l.msg)).toEqual(['a', 'b']) // no duplicate lines
    expect(job.running.value).toBe(false)
  })

  it('resolves on hana_down and stops polling', async () => {
    responses['enqueue_post'] = [{ job_id: 'j2' }]
    responses['get_post_result'] = [{ status: 'hana_down', log: [] }]
    const job = useJobPolling('get_post_result', 10)
    const p = job.start('enqueue_post', {})
    await vi.advanceTimersByTimeAsync(30)
    const res = await p
    expect(res.status).toBe('hana_down')
    const pollCount = calls.filter((c) => c.method === 'get_post_result').length
    await vi.advanceTimersByTimeAsync(100)
    expect(calls.filter((c) => c.method === 'get_post_result').length).toBe(pollCount)
  })

  it('stops running and rethrows when enqueue fails', async () => {
    responses['enqueue_post'] = [] // forces throw
    const job = useJobPolling('get_post_result', 10)
    await expect(job.start('enqueue_post', {})).rejects.toThrow()
    expect(job.running.value).toBe(false)
  })
})
