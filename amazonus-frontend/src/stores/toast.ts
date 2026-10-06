import { reactive } from 'vue'

export interface Toast { id: number; text: string; kind: 'info' | 'ok' | 'error' }

export const toasts = reactive<Toast[]>([])
let seq = 0

export function toast(text: string, kind: Toast['kind'] = 'info', ms = 4500) {
  const t = { id: ++seq, text, kind }
  toasts.push(t)
  setTimeout(() => {
    const i = toasts.findIndex((x) => x.id === t.id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
}
