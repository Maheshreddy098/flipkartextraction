<template>
  <div class="rounded-xl bg-neutral-100 text-neutral-900 p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold">Alert Recipients</h3>
      <button class="text-sm px-3 py-1 border rounded hover:bg-neutral-200" @click="reload" :disabled="loading">
        {{ loading ? 'Loading...' : 'Refresh' }}
      </button>
    </div>

    <div class="text-xs text-neutral-500 mb-2">
      Failure alerts are emailed to enabled recipients. Toggles control which event types each recipient subscribes to. Saved live to Unicommerce Settings.
    </div>

    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-neutral-500 border-b">
            <th class="py-2">On</th>
            <th>Email</th>
            <th>Label</th>
            <th>Orders</th>
            <th>Credit Notes</th>
            <th>Inventory</th>
            <th>GRN</th>
            <th>Recon</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, idx) in recipients" :key="idx" class="border-b border-neutral-200">
            <td class="py-2"><input type="checkbox" v-model="r.enabled" :true-value="1" :false-value="0" /></td>
            <td><input type="email" v-model="r.email" class="border rounded px-2 py-1 text-xs w-48" placeholder="user@example.com" /></td>
            <td><input v-model="r.name_label" class="border rounded px-2 py-1 text-xs w-28" placeholder="Yogesh" /></td>
            <td><input type="checkbox" v-model="r.notify_orders" :true-value="1" :false-value="0" /></td>
            <td><input type="checkbox" v-model="r.notify_credit_notes" :true-value="1" :false-value="0" /></td>
            <td><input type="checkbox" v-model="r.notify_inventory" :true-value="1" :false-value="0" /></td>
            <td><input type="checkbox" v-model="r.notify_grn" :true-value="1" :false-value="0" /></td>
            <td><input type="checkbox" v-model="r.notify_recon" :true-value="1" :false-value="0" /></td>
            <td><button class="text-xs text-red-600 hover:underline" @click="remove(idx)">Remove</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 flex items-center justify-between">
      <button class="text-sm px-3 py-1 border rounded hover:bg-neutral-200" @click="add">+ Add Recipient</button>
      <button
        class="text-sm px-4 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
        :disabled="saving"
        @click="save">
        {{ saving ? 'Saving...' : 'Save' }}
      </button>
    </div>

    <div v-if="message" class="mt-2 text-xs" :class="messageOk ? 'text-emerald-600' : 'text-red-600'">{{ message }}</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({ callMethod: { type: Function, required: true } })

const recipients = ref([])
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const messageOk = ref(true)

const DEFAULT_RECIPIENT = () => ({
  enabled: 1,
  email: '',
  name_label: '',
  notify_orders: 1,
  notify_credit_notes: 1,
  notify_inventory: 1,
  notify_grn: 1,
  notify_recon: 0,
})

async function reload() {
  loading.value = true
  message.value = ''
  try {
    const settings = await props.callMethod('frappe.client.get', {
      doctype: 'Unicommerce Settings',
      name: 'Unicommerce Settings',
    })
    recipients.value = (settings?.alert_recipients || []).map((r) => ({ ...r }))
  } catch (e) {
    message.value = `Load failed: ${e?.message || e}`
    messageOk.value = false
  } finally {
    loading.value = false
  }
}

function add() {
  recipients.value.push(DEFAULT_RECIPIENT())
}

function remove(idx) {
  recipients.value.splice(idx, 1)
}

async function save() {
  saving.value = true
  message.value = ''
  try {
    await props.callMethod('frappe.client.set_value', {
      doctype: 'Unicommerce Settings',
      name: 'Unicommerce Settings',
      fieldname: 'alert_recipients',
      value: recipients.value,
    })
    message.value = 'Saved.'
    messageOk.value = true
    await reload()
  } catch (e) {
    message.value = `Save failed: ${e?.message || e}`
    messageOk.value = false
  } finally {
    saving.value = false
  }
}

onMounted(reload)
</script>
