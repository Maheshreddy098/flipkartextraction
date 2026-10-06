<template>
  <div class="relative" ref="wrapper">
    <input
      v-model="query"
      @input="onSearch"
      @focus="onFocus"
      type="text"
      :placeholder="placeholder"
      class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
    />
    <div v-if="loading" class="absolute right-3 top-2.5">
      <span class="text-xs text-gray-400">Searching...</span>
    </div>
    <Teleport to="body">
      <div
        v-if="showDropdown && (results.length || noResults || errorMsg)"
        data-item-search-dropdown
        class="fixed z-[9999] mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto min-w-[320px]"
        :style="dropdownStyle"
      >
        <div v-if="errorMsg" class="px-4 py-3 text-sm text-red-600">
          {{ errorMsg }}
        </div>
        <div v-else-if="noResults" class="px-4 py-3 text-sm text-gray-400">
          No items found for "{{ query }}"
        </div>
        <button
          v-for="item in results"
          :key="item.item_code"
          type="button"
          @mousedown.prevent="selectItem(item)"
          class="w-full text-left px-4 py-2 hover:bg-blue-50 text-sm border-b border-gray-100 last:border-0 whitespace-normal break-words min-w-[280px]"
        >
          <span class="font-medium text-gray-900">{{ item.item_code }}</span>
          <span class="text-gray-500 ml-2">{{ item.item_name }}</span>
          <span v-if="item.uom" class="text-gray-400 ml-2 text-xs">({{ item.uom }})</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { searchSAPItems } from '@/core/api/sapMaster.js'

const props = defineProps({
  placeholder: { type: String, default: 'Search items...' },
  clearOnSelect: { type: Boolean, default: false },
  initialValue: { type: String, default: '' },
})
const emit = defineEmits(['select'])

const wrapper = ref(null)
const query = ref(props.initialValue || '')
watch(() => props.initialValue, (v) => { query.value = v || '' })
const results = ref([])
const showDropdown = ref(false)
const loading = ref(false)
const noResults = ref(false)
const errorMsg = ref('')
const dropdownStyle = ref({ top: '0px', left: '0px', width: '200px' })
let debounceTimer = null

function updateDropdownPosition() {
  nextTick(() => {
    if (!wrapper.value) return
    const r = wrapper.value.getBoundingClientRect()
    dropdownStyle.value = {
      top: `${r.bottom + 4}px`,
      left: `${r.left}px`,
      width: `${r.width}px`,
    }
  })
}

function onFocus() {
  if (results.value.length || errorMsg.value) {
    showDropdown.value = true
    updateDropdownPosition()
  }
}

function onSearch() {
  clearTimeout(debounceTimer)
  noResults.value = false
  errorMsg.value = ''
  if (query.value.length < 2) {
    results.value = []
    showDropdown.value = false
    return
  }
  loading.value = true
  debounceTimer = setTimeout(async () => {
    try {
      const res = await searchSAPItems(query.value)
      if (res.error) {
        errorMsg.value = res.error
        results.value = []
      } else {
        results.value = res.data || []
        noResults.value = results.value.length === 0
      }
      showDropdown.value = true
      updateDropdownPosition()
    } catch (err) {
      results.value = []
      errorMsg.value = err.response?.data?.message || err.message || 'Search failed'
      showDropdown.value = true
      updateDropdownPosition()
    }
    loading.value = false
  }, 300)
}

function selectItem(item) {
  query.value = props.clearOnSelect ? '' : item.item_code
  showDropdown.value = false
  noResults.value = false
  errorMsg.value = ''
  results.value = []
  emit('select', item)
}

function onClickOutside(e) {
  if (!wrapper.value) return
  if (wrapper.value.contains(e.target)) return
  if (e.target.closest('[data-item-search-dropdown]')) return
  showDropdown.value = false
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>
