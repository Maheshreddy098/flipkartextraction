<template>
  <div class="flex flex-wrap gap-2">
    <button
      v-for="plant in plants"
      :key="plant.plant_code"
      type="button"
      :class="buttonClasses(plant.plant_code)"
      @click="$emit('update:modelValue', plant.plant_code)"
    >
      {{ plant.plant_code }}
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  plants: {
    type: Array,
    default: () => []
  }
})

defineEmits(['update:modelValue'])

function buttonClasses(plantCode) {
  const isActive = props.modelValue === plantCode
  return [
    'rounded-full px-3 py-1.5 text-sm font-medium border transition-colors',
    isActive
      ? 'bg-teal-600 text-white border-teal-600'
      : 'bg-white text-gray-700 border-gray-300 hover:border-teal-400 hover:text-teal-700'
  ]
}
</script>
