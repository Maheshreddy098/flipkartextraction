<template>
  <div class="bg-white rounded-xl shadow-sm border">
    <div class="px-6 py-4 border-b flex items-center justify-between">
      <h2 class="text-base font-semibold text-gray-800">Attachments</h2>
      <span v-if="attachments.length" class="text-xs text-gray-400">{{ attachments.length }} file{{ attachments.length > 1 ? 's' : '' }}</span>
    </div>

    <div class="px-6 py-4 space-y-4">
      <!-- Placeholder shown while the record has not been saved yet -->
      <div v-if="!docname" class="text-sm text-gray-400 py-1 italic">
        Save this record first to add attachments.
      </div>

      <template v-else>
        <!-- Upload section — KhanalFoods only -->
        <div v-if="!readonly" class="flex items-center gap-3">
          <label class="flex-1">
            <input
              ref="fileInput"
              type="file"
              class="hidden"
              @change="onFileSelected"
            />
            <div
              class="flex items-center gap-2 px-4 py-2 border border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition text-sm text-gray-500"
              @click="$refs.fileInput.click()"
            >
              <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
              <span>{{ selectedFile ? selectedFile.name : 'Choose file (max 50 MB)' }}</span>
            </div>
          </label>
          <button
            @click="handleUpload"
            :disabled="!selectedFile || uploading"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium shrink-0"
          >
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
        </div>

        <!-- File list -->
        <div v-if="loading" class="text-sm text-gray-400 py-2">Loading attachments...</div>

        <div v-else-if="attachments.length === 0" class="text-sm text-gray-400 py-2">
          No attachments yet.
        </div>

        <ul v-else class="divide-y divide-gray-100">
          <li
            v-for="att in attachments"
            :key="att.name"
            class="flex items-center justify-between py-2.5 gap-3"
          >
            <div class="flex items-center gap-2 min-w-0">
              <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div class="min-w-0">
                <p class="text-sm font-medium text-gray-800 truncate">{{ att.file_name }}</p>
                <p class="text-xs text-gray-400">{{ att.uploaded_by }} · {{ formatDate(att.uploaded_at) }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <a
                v-if="att.download_url"
                :href="att.download_url"
                target="_blank"
                rel="noopener noreferrer"
                class="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition"
              >
                Download
              </a>
              <button
                v-if="!readonly && canDelete(att)"
                @click="handleDelete(att)"
                :disabled="deleting === att.name"
                class="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition disabled:opacity-50"
              >
                {{ deleting === att.name ? '...' : 'Delete' }}
              </button>
            </div>
          </li>
        </ul>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useSessionStore } from '@/core/stores/session.js'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { uploadKFAttachment, listKFAttachments, deleteKFAttachment } from '@/core/api/kfAttachments.js'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, default: null },
  readonly: { type: Boolean, default: false },
})

const session = useSessionStore()
const notify = useNotificationStore()

const attachments = ref([])
const loading = ref(false)
const uploading = ref(false)
const deleting = ref(null)
const selectedFile = ref(null)
const fileInput = ref(null)

const MAX_SIZE = 50 * 1024 * 1024

function formatDate(val) {
  if (!val) return ''
  const d = new Date(val)
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function canDelete(att) {
  const roles = session.roles || []
  const isManager = roles.includes('Real Aquatics KhanalFoods Manager')
  const isOwner = att.uploaded_by === session.user?.email
  return isManager || isOwner
}

async function loadAttachments() {
  loading.value = true
  try {
    attachments.value = await listKFAttachments(props.doctype, props.docname)
  } catch {
    // silently ignore — attachments section is non-critical
  } finally {
    loading.value = false
  }
}

function onFileSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > MAX_SIZE) {
    notify.error('File is too large. Maximum size is 50 MB.')
    if (fileInput.value) fileInput.value.value = ''
    return
  }
  selectedFile.value = file
}

async function handleUpload() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  try {
    const reader = new FileReader()
    const filedata = await new Promise((resolve, reject) => {
      reader.onload = (e) => resolve(e.target.result.split(',')[1]) // strip base64 prefix
      reader.onerror = reject
      reader.readAsDataURL(selectedFile.value)
    })
    await uploadKFAttachment(props.doctype, props.docname, selectedFile.value.name, filedata)
    notify.success('File uploaded')
    selectedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
    await loadAttachments()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Upload failed')
  } finally {
    uploading.value = false
  }
}

async function handleDelete(att) {
  if (deleting.value) return
  deleting.value = att.name
  try {
    await deleteKFAttachment(att.name)
    notify.success('Attachment deleted')
    await loadAttachments()
  } catch (e) {
    notify.error(e.response?.data?.message || 'Delete failed')
  } finally {
    deleting.value = null
  }
}

// Load when docname first becomes available (handles new-record flow)
watch(() => props.docname, (val) => { if (val) loadAttachments() })

onMounted(() => { if (props.docname) loadAttachments() })
</script>
