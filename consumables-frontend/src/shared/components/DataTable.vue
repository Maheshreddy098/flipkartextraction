<template>
  <div class="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-gray-200 bg-gray-50">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-600"
              :class="col.class || ''"
            >
              {{ col.label }}
            </th>
            <th v-if="$slots.actions" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-600">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-if="loading">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="px-4 py-10 text-center">
              <div class="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
            </td>
          </tr>
          <tr v-else-if="!rows.length">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="px-4 py-10 text-center text-gray-400">
              {{ emptyText }}
            </td>
          </tr>
          <tr
            v-for="(row, idx) in rows"
            v-else
            :key="row.name || idx"
            class="cursor-pointer transition hover:bg-gray-50"
            @click="$emit('row-click', row)"
          >
            <td v-for="col in columns" :key="col.key" class="px-4 py-3 text-gray-700" :class="col.cellClass || ''">
              <slot :name="'cell-' + col.key" :row="row" :value="row[col.key]">
                {{ row[col.key] ?? '—' }}
              </slot>
            </td>
            <td v-if="$slots.actions" class="px-4 py-3 text-right" @click.stop>
              <slot name="actions" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="total > pageSize && !loading"
      class="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-4 py-3 text-sm"
    >
      <span class="text-gray-500">Page {{ page }} · {{ total }} total</span>
      <div class="flex gap-2">
        <button
          :disabled="page <= 1"
          class="rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-40 hover:bg-white"
          @click="$emit('page-change', page - 1)"
        >← Prev</button>
        <button
          :disabled="page * pageSize >= total"
          class="rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-40 hover:bg-white"
          @click="$emit('page-change', page + 1)"
        >Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  columns:   { type: Array,  required: true },
  rows:      { type: Array,  default: () => [] },
  total:     { type: Number, default: 0 },
  page:      { type: Number, default: 1 },
  pageSize:  { type: Number, default: 20 },
  loading:   { type: Boolean, default: false },
  emptyText: { type: String, default: 'No records found.' },
})
defineEmits(['row-click', 'page-change'])
</script>
