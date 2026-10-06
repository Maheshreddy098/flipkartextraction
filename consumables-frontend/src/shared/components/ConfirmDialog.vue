<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40" @click="$emit('cancel')" />
      <div class="storeops-portal-fields relative w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h3 class="text-base font-semibold text-gray-900">{{ title }}</h3>
        <p class="mt-2 text-sm text-gray-600">{{ message }}</p>

        <div v-if="showInput" class="mt-4">
          <textarea
            v-model="inputValue"
            rows="3"
            :placeholder="inputPlaceholder"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
          />
        </div>

        <div class="mt-6 flex justify-end gap-3">
          <button
            type="button"
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            @click="$emit('cancel')"
          >Cancel</button>
          <button
            type="button"
            :disabled="showInput && !inputValue.trim()"
            class="rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            :class="btnClass"
            @click="handleConfirm"
          >{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  visible:          { type: Boolean, default: false },
  title:            { type: String,  default: 'Confirm' },
  message:          { type: String,  default: 'Are you sure?' },
  confirmText:      { type: String,  default: 'Confirm' },
  variant:          { type: String,  default: 'primary' },   // primary | danger | success
  showInput:        { type: Boolean, default: false },
  inputPlaceholder: { type: String,  default: 'Enter reason…' },
})

const emit = defineEmits(['confirm', 'cancel'])
const inputValue = ref('')

const btnClass = computed(() => {
  if (props.variant === 'danger') return 'bg-red-600 hover:bg-red-700'
  if (props.variant === 'success') return 'bg-green-600 hover:bg-green-700'
  return 'bg-teal-600 hover:bg-teal-700'
})

function handleConfirm() {
  emit('confirm', props.showInput ? inputValue.value : undefined)
  inputValue.value = ''
}
</script>
