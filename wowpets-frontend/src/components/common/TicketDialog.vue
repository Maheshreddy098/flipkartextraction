<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40">
      <div class="bg-white rounded-xl shadow-lg w-full max-w-lg mx-4">
        <div class="px-5 py-3 border-b flex items-center justify-between">
          <h2 class="text-base font-semibold text-gray-900">{{ title }}</h2>
          <button type="button" class="text-gray-400 hover:text-gray-600" @click="$emit('cancel')">&times;</button>
        </div>
        <div class="px-5 py-4 space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Title *</label>
            <input v-model="local.title" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">Type *</label>
              <select v-model="local.ticket_type" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
                <option value="Operational">Operational</option>
                <option value="Technical">Technical</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">Priority *</label>
              <select v-model="local.priority" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
                <option value="Critical">Critical</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Description *</label>
            <textarea
              v-model="local.description"
              rows="4"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
              placeholder="Describe the issue clearly, including steps to reproduce and expectations."
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Attachment (optional)</label>
            <input ref="fileInput" type="file" class="block w-full text-xs text-gray-500" @change="onFileChange" />
            <p v-if="fileName" class="mt-1 text-xs text-gray-600">Selected: {{ fileName }}</p>
          </div>
        </div>
        <div class="px-5 py-3 border-t bg-gray-50 flex items-center justify-end gap-2">
          <button type="button" class="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-white" @click="$emit('cancel')">
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 text-sm rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            :disabled="submitting"
            @click="handleSubmit"
          >
            {{ submitting ? 'Submitting...' : 'Submit Ticket' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: 'Raise Ticket' },
  section: { type: String, required: true },
  referenceDoctype: { type: String, required: true },
  referenceName: { type: String, required: true },
  submitting: { type: Boolean, default: false },
})

const emit = defineEmits(['submit', 'cancel'])

const local = ref({
  title: '',
  ticket_type: 'Operational',
  priority: 'Medium',
  description: '',
})

const fileInput = ref(null)
const fileName = ref('')
const fileData = ref(null)

watch(
  () => props.visible,
  (v) => {
    if (v) {
      local.value = {
        title: '',
        ticket_type: 'Operational',
        priority: 'Medium',
        description: '',
      }
      fileName.value = ''
      fileData.value = null
      if (fileInput.value) fileInput.value.value = ''
    }
  },
)

function onFileChange(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) {
    fileName.value = ''
    fileData.value = null
    return
  }
  fileName.value = file.name
  const reader = new FileReader()
  reader.onload = () => {
    const result = reader.result
    const base64 = typeof result === 'string' ? result.split(',').pop() : ''
    fileData.value = base64 || null
  }
  reader.readAsDataURL(file)
}

function handleSubmit() {
  if (!local.value.title.trim() || !local.value.description.trim()) {
    // Let parent handle notification
    emit('submit', null)
    return
  }
  const payload = {
    title: local.value.title.trim(),
    ticket_type: local.value.ticket_type,
    priority: local.value.priority,
    description: local.value.description,
    section: props.section,
    reference_doctype: props.referenceDoctype,
    reference_name: props.referenceName,
  }
  emit('submit', { ticket: payload, attachment: fileData.value ? { file_name: fileName.value, filedata: fileData.value } : null })
}
</script>

