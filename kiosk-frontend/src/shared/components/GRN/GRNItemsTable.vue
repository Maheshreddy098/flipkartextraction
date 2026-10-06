<template>
  <div class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
    <!-- Table Header -->
    <div class="p-4 bg-gray-50 border-b border-gray-200">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-semibold text-gray-900">
          {{ title }}
          <span v-if="items.length > 0" class="text-sm font-normal text-gray-600 ml-2">
            ({{ items.length }} item{{ items.length !== 1 ? 's' : '' }})
          </span>
        </h3>
        
        <!-- Bulk Actions Slot -->
        <div class="flex items-center gap-2">
          <slot name="bulk-actions"></slot>
        </div>
      </div>

      <!-- Search/Filter Slot -->
      <div v-if="$slots.filters" class="mt-3">
        <slot name="filters"></slot>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="p-12 text-center">
      <svg class="animate-spin h-8 w-8 text-purple-600 mx-auto" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="mt-3 text-sm text-gray-600">{{ loadingText }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="items.length === 0" class="p-12 text-center">
      <div class="text-5xl mb-3">📦</div>
      <p class="text-gray-600">{{ emptyText }}</p>
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-gray-100 border-b border-gray-200">
          <tr>
            <th
              v-for="column in columns"
              :key="column.key"
              :class="[
                'px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider',
                column.width || '',
                column.align === 'center' ? 'text-center' : '',
                column.align === 'right' ? 'text-right' : ''
              ]"
            >
              {{ column.label }}
            </th>
            <th v-if="showActions" class="px-4 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <GRNItemsTableRow
            v-for="(item, index) in items"
            :key="getItemKey(item, index)"
            :item="item"
            :index="index"
            :columns="columns"
            :show-actions="showActions"
            @update="(field, value) => $emit('update-item', index, field, value)"
            @delete="$emit('delete-item', index)"
          >
            <!-- Pass through scoped slots -->
            <template v-for="(_, slot) in $slots" #[slot]="slotProps">
              <slot :name="slot" v-bind="slotProps" />
            </template>
          </GRNItemsTableRow>
        </tbody>
      </table>
    </div>

    <!-- Table Footer -->
    <div v-if="$slots.footer" class="p-4 bg-gray-50 border-t border-gray-200">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import GRNItemsTableRow from './GRNItemsTableRow.vue'

export interface TableColumn {
  key: string
  label: string
  width?: string
  align?: 'left' | 'center' | 'right'
  format?: (value: any, item: any) => string
}

interface Props {
  title?: string
  items: any[]
  columns: TableColumn[]
  loading?: boolean
  loadingText?: string
  emptyText?: string
  showActions?: boolean
  itemKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Items',
  loading: false,
  loadingText: 'Loading items...',
  emptyText: 'No items to display',
  showActions: true,
  itemKey: 'id'
})

defineEmits<{
  'update-item': [index: number, field: string, value: any]
  'delete-item': [index: number]
}>()

function getItemKey(item: any, index: number): string | number {
  return item[props.itemKey] || index
}
</script>

