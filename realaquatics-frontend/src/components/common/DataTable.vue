<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b border-gray-200">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider"
            >
              {{ col.label }}
            </th>
            <th v-if="$slots.actions" class="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-if="!rows.length">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="px-4 py-8 text-center text-gray-400">
              {{ emptyText }}
            </td>
          </tr>
          <tr
            v-for="(row, idx) in rows"
            :key="row.name || idx"
            class="hover:bg-gray-50 cursor-pointer transition"
            @click="$emit('row-click', row)"
          >
            <td v-for="col in columns" :key="col.key" class="px-4 py-3 text-gray-700">
              <slot :name="'cell-' + col.key" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>
            <td v-if="$slots.actions" class="px-4 py-3 text-right">
              <slot name="actions" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="total > rows.length" class="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50 text-sm">
      <span class="text-gray-500">Showing {{ rows.length }} of {{ total }}</span>
      <div class="flex gap-2">
        <button
          :disabled="page <= 1"
          @click="$emit('page-change', page - 1)"
          class="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
        >Prev</button>
        <button
          :disabled="rows.length < pageSize"
          @click="$emit('page-change', page + 1)"
          class="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
        >Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  emptyText: { type: String, default: 'No data found' },
})

defineEmits(['row-click', 'page-change'])
</script>
