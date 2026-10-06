<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Tickets</h1>
      <div class="flex items-center gap-3">
        <p class="text-xs text-gray-500">
          Showing tickets raised by all teams. Warehouse tickets are highlighted.
        </p>
        <button
          @click="exportData"
          :disabled="exporting"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50 transition"
        >{{ exporting ? 'Exporting...' : 'Export CSV' }}</button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-3 mb-4">
      <div class="flex gap-2">
        <button
          v-for="f in statusFilters"
          :key="f.value"
          @click="currentStatus = f.value"
          :class="currentStatus === f.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border'"
          class="px-3 py-1.5 text-sm rounded-lg transition"
        >
          {{ f.label }}
        </button>
      </div>
      <div class="flex items-center gap-2 ml-auto">
        <select
          v-model="sectionFilter"
          class="px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs bg-white text-gray-700"
        >
          <option value="">All sections</option>
          <option value="Purchase Order">Purchase Orders</option>
          <option value="Work Order">Work Orders</option>
          <option value="Dispatch Order">Dispatch Orders</option>
          <option value="FBA Transfer">FBA Transfers</option>
          <option value="Other">Other</option>
        </select>
      </div>
    </div>

    <DataTable
      :columns="columns"
      :rows="tickets"
      :total="total"
      :page="page"
      @row-click="openTicket"
      @page-change="onPageChange"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-title="{ row, value }">
        <div class="flex items-center gap-2">
          <span
            v-if="row.raised_team === 'warehouse'"
            class="inline-flex items-center px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-semibold uppercase tracking-wide"
            title="Raised by Warehouse team"
          >
            WH
          </span>
          <span class="truncate">{{ value }}</span>
        </div>
      </template>
      <template #cell-section="{ row }">
        <span class="text-xs text-gray-700">
          {{ row.section }}
        </span>
        <p v-if="row.reference_doctype && row.reference_name" class="text-[11px] text-gray-400">
          {{ row.reference_doctype }} • {{ row.reference_name }}
        </p>
      </template>
      <template #cell-priority="{ value }">
        <span
          class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
          :class="priorityClass(value)"
        >
          {{ value || 'Medium' }}
        </span>
      </template>
    </DataTable>

    <!-- Ticket detail drawer -->
    <Teleport to="body">
      <div
        v-if="showDetail"
        class="fixed inset-0 z-[2100] flex items-stretch justify-end bg-black/40"
        @click.self="closeDetail"
      >
        <div class="w-full max-w-xl bg-white h-full shadow-xl flex flex-col">
          <div class="px-5 py-4 border-b flex items-center justify-between gap-4">
            <div class="min-w-0">
              <p class="text-xs font-mono text-gray-400 truncate">{{ detail?.name }}</p>
              <h2 class="text-lg font-semibold text-gray-900 mt-0.5 truncate">
                {{ detail?.title || 'Ticket' }}
              </h2>
              <p v-if="detail?.section" class="text-xs text-gray-500 mt-0.5 truncate">
                {{ detail.section }}
                <span v-if="detail.reference_doctype && detail.reference_name">
                  • {{ detail.reference_doctype }} / {{ detail.reference_name }}
                </span>
              </p>
            </div>
            <div class="flex items-center gap-2">
              <router-link
                v-if="linkedPath"
                :to="linkedPath"
                class="inline-flex items-center px-3 py-1.5 rounded-lg border border-blue-200 bg-blue-50 text-xs font-medium text-blue-700 hover:bg-blue-100"
              >
                View Related Record
              </router-link>
            </div>
            <button
              type="button"
              class="text-gray-400 hover:text-gray-600 text-xl leading-none"
              @click="closeDetail"
            >
              &times;
            </button>
          </div>

          <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            <div class="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p class="text-xs font-medium text-gray-500 mb-0.5">Status</p>
                <select
                  v-model="editStatus"
                  class="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-sm bg-white"
                >
                  <option value="Open">Open</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Closed">Closed</option>
                </select>
              </div>
              <div>
                <p class="text-xs font-medium text-gray-500 mb-0.5">Priority</p>
                <span
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                  :class="priorityClass(detail?.priority)"
                >
                  {{ detail?.priority || 'Medium' }}
                </span>
              </div>
              <div>
                <p class="text-xs font-medium text-gray-500 mb-0.5">Raised By</p>
                <p class="text-sm text-gray-800">
                  {{ detail?.raised_by || '—' }}
                  <span v-if="detail?.raised_team" class="text-xs text-gray-500">
                    ({{ detail.raised_team }})
                  </span>
                </p>
              </div>
              <div>
                <p class="text-xs font-medium text-gray-500 mb-0.5">Assigned To</p>
                <input
                  v-model="editAssignedTo"
                  class="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-sm"
                  placeholder="user@example.com (optional)"
                />
              </div>
            </div>

            <div>
              <p class="text-xs font-medium text-gray-500 mb-1.5">Description</p>
              <p class="text-sm text-gray-800 whitespace-pre-line bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                {{ detail?.description || '—' }}
              </p>
            </div>

            <div>
              <p class="text-xs font-medium text-gray-500 mb-1.5">Resolution Notes</p>
              <textarea
                v-model="editResolution"
                rows="4"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
                placeholder="Add notes about investigation and resolution..."
              />
            </div>

            <div>
              <p class="text-xs font-medium text-gray-500 mb-1.5">Attachments</p>
              <div v-if="loadingAttachments" class="text-xs text-gray-400">
                Loading attachments...
              </div>
              <div v-else-if="attachments.length === 0" class="text-xs text-gray-400">
                No attachments.
              </div>
              <ul v-else class="space-y-1 text-sm">
                <li
                  v-for="file in attachments"
                  :key="file.file_url"
                  class="flex items-center justify-between gap-2"
                >
                  <span class="truncate">
                    {{ file.file_name }}
                    <span class="text-xs text-gray-400">— {{ file.uploaded_by }}</span>
                  </span>
                  <a
                    :href="file.file_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-xs text-blue-600 hover:underline"
                  >
                    Open
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <p class="text-xs font-medium text-gray-500 mb-1.5">Conversation</p>
              <div class="border border-gray-200 rounded-lg bg-gray-50 max-h-56 overflow-y-auto px-3 py-2 space-y-2 text-sm">
                <p v-if="loadingComments" class="text-xs text-gray-400">Loading comments...</p>
                <p v-else-if="!comments.length" class="text-xs text-gray-400">No comments yet.</p>
                <div
                  v-else
                  v-for="(c, idx) in comments"
                  :key="idx"
                  class="rounded-md bg-white px-3 py-2 border border-gray-200"
                >
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-semibold text-gray-700">
                      {{ c.owner }}
                    </span>
                    <span class="text-[11px] text-gray-400">
                      {{ new Date(c.creation).toLocaleString() }}
                    </span>
                  </div>
                  <p class="text-sm text-gray-800 whitespace-pre-line">
                    {{ c.content }}
                  </p>
                </div>
              </div>
              <div class="mt-2 flex items-end gap-2">
                <textarea
                  v-model="newComment"
                  rows="2"
                  class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
                  placeholder="Write a reply..."
                />
                <button
                  type="button"
                  class="px-3 py-2 text-sm rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                  :disabled="postingComment || !newComment.trim()"
                  @click="postComment"
                >
                  {{ postingComment ? 'Sending...' : 'Send' }}
                </button>
              </div>
            </div>
          </div>

          <div class="px-5 py-3 border-t bg-gray-50 flex items-center justify-end gap-2">
            <button
              type="button"
              class="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-white"
              @click="closeDetail"
            >
              Close
            </button>
            <button
              type="button"
              class="px-4 py-1.5 text-sm rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
              :disabled="savingDetail"
              @click="saveDetail"
            >
              {{ savingDetail ? 'Saving...' : 'Save Changes' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useNotificationStore } from '@/core/stores/notifications.js'
import { useSessionStore } from '@/core/stores/session.js'
import {
  fetchTickets,
  fetchTicket,
  updateTicket,
  listTicketAttachments,
  listTicketComments,
  addTicketComment,
} from '@/core/api/tickets.js'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { downloadCsv } from '@/core/utils/exportCsv.js'

const notify = useNotificationStore()
const session = useSessionStore()

const exporting = ref(false)
const tickets = ref([])
const total = ref(0)
const page = ref(1)
const currentStatus = ref('')
const sectionFilter = ref('')
const showDetail = ref(false)
const detail = ref(null)
const attachments = ref([])
const loadingAttachments = ref(false)
const comments = ref([])
const loadingComments = ref(false)
const newComment = ref('')
const postingComment = ref(false)
const editStatus = ref('Open')
const editResolution = ref('')
const editAssignedTo = ref('')
const savingDetail = ref(false)

const statusFilters = [
  { label: 'All', value: '' },
  { label: 'Open', value: 'Open' },
  { label: 'In Progress', value: 'In Progress' },
  { label: 'Resolved', value: 'Resolved' },
  { label: 'Closed', value: 'Closed' },
]

const columns = [
  { key: 'name', label: 'Ticket #' },
  { key: 'title', label: 'Title' },
  { key: 'section', label: 'Section' },
  { key: 'status', label: 'Status' },
  { key: 'priority', label: 'Priority' },
  { key: 'raised_team', label: 'Raised By' },
  { key: 'modified', label: 'Last Updated' },
]

function priorityClass(p) {
  const val = (p || '').toLowerCase()
  if (val === 'critical') return 'bg-red-100 text-red-700'
  if (val === 'high') return 'bg-amber-100 text-amber-800'
  if (val === 'low') return 'bg-emerald-50 text-emerald-700'
  return 'bg-blue-50 text-blue-700'
}

const linkedPath = computed(() => {
  if (!detail.value?.reference_name) return null
  const name = detail.value.reference_name
  const section = (detail.value.section || '').trim()
  const prefix = session.team === 'warehouse' ? '/warehouse' : '/khanalfoods'

  if (section === 'Dispatch Order') return `${prefix}/dispatch-orders/${name}`
  if (section === 'Purchase Order') return `${prefix}/purchase-orders/${name}`
  if (section === 'Work Order') return `${prefix}/work-orders/${name}`
  if (section === 'FBA Transfer') return `${prefix}/orders/${name}`

  return null
})

async function loadTickets() {
  try {
    const params = { page: page.value }
    if (currentStatus.value) params.status = currentStatus.value
    if (sectionFilter.value) params.section = sectionFilter.value
    const res = await fetchTickets(params)
    tickets.value = res.data || []
    total.value = res.total || 0
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to load tickets')
  }
}

function onPageChange(p) {
  page.value = p
}

async function openTicket(row) {
  try {
    detail.value = null
    attachments.value = []
    comments.value = []
    loadingAttachments.value = true
    loadingComments.value = true
    showDetail.value = true

    const [ticketRes, attachRes, commentRes] = await Promise.all([
      fetchTicket(row.name),
      listTicketAttachments(row.name).catch(() => ({ data: [] })),
      listTicketComments(row.name).catch(() => ({ data: [] })),
    ])

    detail.value = ticketRes
    attachments.value = attachRes?.data || attachRes || []
    comments.value = commentRes?.data || commentRes || []

    editStatus.value = ticketRes.status || 'Open'
    editResolution.value = ticketRes.resolution_notes || ''
    editAssignedTo.value = ticketRes.assigned_to || ''
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to load ticket')
    showDetail.value = false
  } finally {
    loadingAttachments.value = false
    loadingComments.value = false
  }
}

function closeDetail() {
  showDetail.value = false
}

async function saveDetail() {
  if (!detail.value?.name) return
  savingDetail.value = true
  try {
    const payload = {
      status: editStatus.value,
      resolution_notes: editResolution.value,
      assigned_to: editAssignedTo.value || null,
    }
    const updated = await updateTicket(detail.value.name, payload)
    detail.value = updated
    await loadTickets()
    notify.success('Ticket updated')
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to update ticket')
  } finally {
    savingDetail.value = false
  }
}

async function postComment() {
  if (!detail.value?.name || !newComment.value.trim()) return
  postingComment.value = true
  try {
    await addTicketComment(detail.value.name, newComment.value.trim())
    newComment.value = ''
    const res = await listTicketComments(detail.value.name)
    comments.value = res?.data || res || []
  } catch (e) {
    notify.error(e.response?.data?.message || 'Failed to add comment')
  } finally {
    postingComment.value = false
  }
}

async function exportData() {
  exporting.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    if (currentStatus.value) params.status = currentStatus.value
    if (sectionFilter.value) params.section = sectionFilter.value
    const res = await fetchTickets(params)
    const exportColumns = [
      { key: 'name', label: 'Ticket #' },
      { key: 'title', label: 'Title' },
      { key: 'ticket_type', label: 'Type' },
      { key: 'section', label: 'Section' },
      { key: 'reference_doctype', label: 'Reference Doctype' },
      { key: 'reference_name', label: 'Reference Name' },
      { key: 'status', label: 'Status' },
      { key: 'priority', label: 'Priority' },
      { key: 'raised_by', label: 'Raised By' },
      { key: 'raised_team', label: 'Raised Team' },
      { key: 'assigned_to', label: 'Assigned To' },
      { key: 'modified', label: 'Last Updated' },
    ]
    downloadCsv('Tickets', exportColumns, res.data || [])
  } catch {
    notify.error('Export failed')
  } finally {
    exporting.value = false
  }
}

watch([currentStatus, sectionFilter], () => {
  page.value = 1
  loadTickets()
})

onMounted(loadTickets)
</script>

