<template>
  <teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/40" @click="cancel" />
      <div class="relative bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900">{{ title }}</h3>
        <p class="mt-2 text-sm text-gray-600">{{ message }}</p>

        <div v-if="showInput" class="mt-4">
          <textarea
            v-model="inputValue"
            rows="3"
            :placeholder="inputPlaceholder"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button
            @click="cancel"
            class="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition"
          >Cancel</button>
          <button
            @click="confirm"
            :class="confirmBtnClass"
            class="px-4 py-2 text-sm text-white rounded-lg transition"
          >{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  visible: Boolean,
  title: { type: String, default: 'Confirm' },
  message: { type: String, default: 'Are you sure?' },
  confirmText: { type: String, default: 'Confirm' },
  variant: { type: String, default: 'primary' },
  showInput: Boolean,
  inputPlaceholder: { type: String, default: '' },
})

const emit = defineEmits(['confirm', 'cancel'])
const inputValue = ref('')

const confirmBtnClass = computed(() => ({
  'bg-blue-600 hover:bg-blue-700': props.variant === 'primary',
  'bg-red-600 hover:bg-red-700': props.variant === 'danger',
  'bg-green-600 hover:bg-green-700': props.variant === 'success',
}))

function confirm() {
  emit('confirm', inputValue.value)
  inputValue.value = ''
}

function cancel() {
  emit('cancel')
  inputValue.value = ''
}
</script>
