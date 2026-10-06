<template>
  <span :class="[sizeClass, colorClass]" class="inline-flex items-center rounded-full font-medium border">
    {{ displayLabel }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' },
  size: { type: String, default: 'md' },
})

const STATUS_MAP = {
  // Generic
  'draft':               { label: 'Submitted',                color: 'blue' },
  'cancelled':           { label: 'Cancelled',                color: 'red' },

  // Material Request (CMR)
  'submitted':           { label: 'Awaiting Review',          color: 'blue' },
  'under review':        { label: 'Under Review',             color: 'indigo' },
  'fulfilling':          { label: 'In Fulfillment',           color: 'amber' },
  'partially fulfilled': { label: 'Partially Fulfilled',      color: 'amber' },
  'fully fulfilled':     { label: 'Fulfilled',                color: 'green' },
  'rejected':            { label: 'Rejected',                 color: 'red' },

  // Transfer Request (CTR)
  'approved':            { label: 'Approved',                 color: 'indigo' },
  'dispatched':          { label: 'Dispatched',               color: 'amber' },
  'received':            { label: 'Received',                 color: 'green' },
  'in transit':          { label: 'In Transit',               color: 'amber' },
  'completed':           { label: 'Completed',                color: 'green' },

  // Delivery Note (CDN)
  'pending approval':    { label: 'Awaiting Approval',        color: 'blue' },
  'posted to sap':       { label: 'Posted to SAP',            color: 'green' },
  'posted':              { label: 'Posted to SAP',            color: 'green' },
  'failed':              { label: 'SAP Posting Failed',       color: 'red' },

  // Purchase Request (CPR)
  'po raised':           { label: 'PO Raised',                color: 'indigo' },
  'po posting':          { label: 'Posting PO…',              color: 'amber' },
  'grn done':            { label: 'Goods Received (GRN)',      color: 'green' },
  'transfer pending':    { label: 'Transfer Pending',          color: 'amber' },
  'awaiting warehouse decision': { label: 'Warehouse Review', color: 'indigo' },

  // Item Request (CIR)
  'pending':             { label: 'Pending Review',           color: 'amber' },
  'in progress':         { label: 'In Progress',              color: 'blue' },
  'created':             { label: 'Created in SAP',           color: 'green' },

  // Inventory
  'ok':                  { label: 'OK',                       color: 'green' },
  'expiring_soon':       { label: 'Expiring Soon',            color: 'amber' },
  'expired':             { label: 'Expired',                  color: 'red' },
}

const COLOR_CLASSES = {
  gray:   'bg-gray-50   text-gray-700  border-gray-200',
  blue:   'bg-blue-50   text-blue-700  border-blue-200',
  indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  amber:  'bg-amber-50  text-amber-800 border-amber-200',
  green:  'bg-green-50  text-green-700 border-green-200',
  red:    'bg-red-50    text-red-700   border-red-200',
  teal:   'bg-teal-50   text-teal-700  border-teal-200',
}

const resolved = computed(() => {
  const key = (props.status || '').trim().toLowerCase()
  return STATUS_MAP[key] || { label: props.status || '—', color: 'gray' }
})

const displayLabel = computed(() => resolved.value.label)

const colorClass = computed(() => COLOR_CLASSES[resolved.value.color] || COLOR_CLASSES.gray)

const sizeClass = computed(() =>
  props.size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs',
)
</script>
