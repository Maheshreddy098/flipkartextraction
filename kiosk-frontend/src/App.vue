<template>
  <ErrorBoundary>
    <div id="app" class="min-h-screen bg-gray-50">
      <router-view />

      <!-- Global Loading Overlay -->
      <div v-if="isLoading" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 flex items-center space-x-4">
          <svg class="animate-spin h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span class="text-gray-700">Loading...</span>
        </div>
      </div>

      <!-- Global Error Toast -->
      <div v-if="globalError" class="fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50">
        <div class="flex items-center space-x-2">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <span>{{ globalError }}</span>
          <button @click="globalError = ''" class="ml-2 text-white hover:text-gray-200">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Global Success Toast -->
      <div v-if="globalSuccess" class="fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50">
        <div class="flex items-center space-x-2">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span>{{ globalSuccess }}</span>
          <button @click="globalSuccess = ''" class="ml-2 text-white hover:text-gray-200">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </ErrorBoundary>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useSessionStore } from './core/stores/session.js'
import ErrorBoundary from './shared/components/ErrorBoundary.vue'

// Composables
const sessionStore = useSessionStore()

// Reactive data
const isLoading = ref(false)
const globalError = ref('')
const globalSuccess = ref('')

// Methods
function showError(message) {
  globalError.value = message
  setTimeout(() => {
    globalError.value = ''
  }, 5000)
}

function showSuccess(message) {
  globalSuccess.value = message
  setTimeout(() => {
    globalSuccess.value = ''
  }, 3000)
}

// Global event listeners
function handleGlobalError(event) {
  showError(event.detail.message || 'An error occurred')
}

function handleGlobalSuccess(event) {
  showSuccess(event.detail.message || 'Operation successful')
}

// Lifecycle
onMounted(() => {
  // Add global event listeners
  window.addEventListener('global-error', handleGlobalError)
  window.addEventListener('global-success', handleGlobalSuccess)
})

onUnmounted(() => {
  // Remove global event listeners
  window.removeEventListener('global-error', handleGlobalError)
  window.removeEventListener('global-success', handleGlobalSuccess)
})

// Expose methods globally
window.showGlobalError = showError
window.showGlobalSuccess = showSuccess
</script>

<style>
/* Global styles */
* {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

#app {
  min-height: 100vh;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* Focus styles */
*:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Button focus styles */
button:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Input focus styles */
input:focus, textarea:focus, select:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Animation classes */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from {
  transform: translateX(-100%);
}

.slide-leave-to {
  transform: translateX(100%);
}

/* Mobile optimizations */
@media (max-width: 768px) {
  .fixed.top-4.right-4 {
    top: 1rem;
    right: 1rem;
    left: 1rem;
  }
}

/* Print styles */
@media print {
  .no-print {
    display: none !important;
  }
}
</style>