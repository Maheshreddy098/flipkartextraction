<template>
  <tr :class="[rowClass, 'hover:bg-gray-50 transition-colors']">
    <td
      v-for="column in columns"
      :key="column.key"
      :class="[
        'px-4 py-3 text-sm',
        column.align === 'center' ? 'text-center' : '',
        column.align === 'right' ? 'text-right' : '',
        getCellClass(column.key)
      ]"
    >
      <!-- Custom Cell Slot -->
      <slot
        v-if="$slots[`cell-${column.key}`]"
        :name="`cell-${column.key}`"
        :item="item"
        :index="index"
        :value="getValue(item, column.key)"
      />
      
      <!-- Default Cell -->
      <template v-else>
        <!-- Editable Input -->
        <input
          v-if="isEditable(column.key)"
          :type="getInputType(column.key)"
          :value="getValue(item, column.key)"
          @input="handleUpdate(column.key, ($event.target as HTMLInputElement).value)"
          @blur="$emit('blur', column.key)"
          :class="[
            'w-full px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-purple-500 focus:border-transparent',
            getInputClass(column.key)
          ]"
          :min="getInputMin(column.key)"
          :max="getInputMax(column.key)"
          :step="getInputStep(column.key)"
        />
        
        <!-- Formatted Display -->
        <template v-else>
          {{ formatValue(column) }}
        </template>
      </template>
    </td>

    <!-- Actions Column -->
    <td v-if="showActions" class="px-4 py-3 text-center">
      <slot name="actions" :item="item" :index="index">
        <button
          @click="$emit('delete')"
          type="button"
          class="text-red-600 hover:text-red-800 hover:bg-red-50 p-1 rounded transition-colors"
          title="Delete"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </slot>
    </td>
  </tr>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TableColumn } from './GRNItemsTable.vue'

interface Props {
  item: any
  index: number
  columns: TableColumn[]
  showActions?: boolean
  editableFields?: string[]
  highlightErrors?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showActions: true,
  editableFields: () => [],
  highlightErrors: false
})

const emit = defineEmits<{
  update: [field: string, value: any]
  delete: []
  blur: [field: string]
}>()

// Get nested value from object using dot notation
function getValue(obj: any, path: string): any {
  return path.split('.').reduce((acc, part) => acc?.[part], obj)
}

// Check if field is editable
function isEditable(field: string): boolean {
  return props.editableFields.includes(field)
}

// Get input type for field
function getInputType(field: string): string {
  if (field.includes('quantity') || field.includes('qty') || field.includes('amount') || field.includes('price')) {
    return 'number'
  }
  if (field.includes('date')) {
    return 'date'
  }
  return 'text'
}

// Get input constraints
function getInputMin(field: string): number | undefined {
  if (getInputType(field) === 'number') {
    return 0
  }
  return undefined
}

function getInputMax(field: string): number | undefined {
  // Can be customized per field
  return undefined
}

function getInputStep(field: string): number | string | undefined {
  if (field.includes('price') || field.includes('amount')) {
    return '0.01'
  }
  if (getInputType(field) === 'number') {
    return '1'
  }
  return undefined
}

// Format value for display
function formatValue(column: TableColumn): string {
  const value = getValue(props.item, column.key)
  
  if (value === null || value === undefined) {
    return '-'
  }
  
  if (column.format) {
    return column.format(value, props.item)
  }
  
  return String(value)
}

// Get cell-specific class
function getCellClass(field: string): string {
  const value = getValue(props.item, field)
  
  // Highlight errors
  if (props.highlightErrors && props.item.errors?.[field]) {
    return 'bg-red-50 border-l-2 border-red-500'
  }
  
  // Highlight warnings
  if (props.item.warnings?.[field]) {
    return 'bg-yellow-50 border-l-2 border-yellow-500'
  }
  
  return 'text-gray-900'
}

// Get input-specific class
function getInputClass(field: string): string {
  if (props.item.errors?.[field]) {
    return 'border-red-500 focus:ring-red-500'
  }
  if (props.item.warnings?.[field]) {
    return 'border-yellow-500 focus:ring-yellow-500'
  }
  return ''
}

// Row class based on item state
const rowClass = computed(() => {
  if (props.item.hasError) {
    return 'bg-red-50'
  }
  if (props.item.hasWarning) {
    return 'bg-yellow-50'
  }
  if (props.item.isNew) {
    return 'bg-green-50'
  }
  return ''
})

// Handle field update
function handleUpdate(field: string, value: string | number) {
  const inputType = getInputType(field)
  let parsedValue: any = value
  
  if (inputType === 'number') {
    parsedValue = value === '' ? 0 : Number(value)
  }
  
  emit('update', field, parsedValue)
}
</script>

