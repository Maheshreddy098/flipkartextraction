import { defineStore } from 'pinia'
import { ref } from 'vue'

let _id = 0

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref([])

  function add(message, type = 'info', duration = 4000) {
    const id = ++_id
    items.value.push({ id, message, type })
    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
  }

  function remove(id) {
    items.value = items.value.filter((n) => n.id !== id)
  }

  function success(msg) { add(msg, 'success') }
  function error(msg) { add(msg, 'error', 6000) }
  function info(msg) { add(msg, 'info') }

  return { items, add, remove, success, error, info }
})
