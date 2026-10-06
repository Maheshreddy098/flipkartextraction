<template>
  <div v-if="hasError" class="error-boundary">
    <div class="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div class="sm:mx-auto sm:w-full sm:max-w-md">
        <div class="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <div class="text-center">
            <!-- Error Icon -->
            <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
              <svg class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L4.35 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>

            <!-- Error Title -->
            <h2 class="mt-4 text-lg font-medium text-gray-900">
              Something went wrong
            </h2>

            <!-- Error Message -->
            <p class="mt-2 text-sm text-gray-600">
              {{ friendlyMessage }}
            </p>

            <!-- Error Details (Development Only) -->
            <div v-if="isDevelopment && errorInfo" class="mt-4 p-3 bg-gray-50 rounded-md text-left">
              <h3 class="text-sm font-medium text-gray-900 mb-2">Error Details:</h3>
              <pre class="text-xs text-red-600 whitespace-pre-wrap">{{ errorInfo }}</pre>
            </div>

            <!-- Action Buttons -->
            <div class="mt-6 space-y-2">
              <button
                @click="retry"
                class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Try Again
              </button>
              
              <button
                @click="goHome"
                class="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Go to Dashboard
              </button>

              <button
                v-if="isDevelopment"
                @click="reportError"
                class="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-500 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Report Error
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/core/stores/session'
import { APP_CONFIG } from '@/config/constants'

const router = useRouter()
const sessionStore = useSessionStore()

const hasError = ref(false)
const error = ref<Error | null>(null)
const errorInfo = ref<string>('')

const isDevelopment = computed(() => APP_CONFIG.IS_DEVELOPMENT)

const friendlyMessage = computed(() => {
  if (!error.value) return 'An unexpected error occurred'
  
  // Map common errors to friendly messages
  const errorMap: Record<string, string> = {
    'ChunkLoadError': 'Failed to load application resources. Please refresh the page.',
    'NetworkError': 'Network connection error. Please check your internet connection.',
    'TypeError': 'A data processing error occurred. Please try refreshing the page.',
    'ReferenceError': 'A component failed to load properly. Please refresh the page.'
  }

  for (const [errorType, message] of Object.entries(errorMap)) {
    if (error.value.name.includes(errorType) || error.value.message.includes(errorType)) {
      return message
    }
  }

  return 'An unexpected error occurred. Please try refreshing the page.'
})

// Capture errors from child components
onErrorCaptured((err: Error, instance, info) => {
  console.error('Error captured by ErrorBoundary:', err)
  console.error('Component info:', info)
  console.error('Component instance:', instance)

  hasError.value = true
  error.value = err
  errorInfo.value = `${err.name}: ${err.message}\n\nStack: ${err.stack}\n\nComponent Info: ${info}`

  // Log error to activity logger if available
  try {
    if (sessionStore.isAuthenticated) {
    }
  } catch (logError) {
    console.error('Failed to log error:', logError)
  }

  // Return false to prevent the error from propagating further
  return false
})

// Handle global unhandled errors
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error)
  hasError.value = true
  error.value = event.error
  errorInfo.value = `${event.error.name}: ${event.error.message}\n\nStack: ${event.error.stack}`
})

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason)
  hasError.value = true
  error.value = new Error(event.reason?.message || 'Unhandled promise rejection')
  errorInfo.value = `Promise Rejection: ${event.reason?.message || 'Unknown error'}\n\nStack: ${event.reason?.stack || 'No stack trace available'}`
})

function retry() {
  const oldName = error.value?.name
  hasError.value = false
  error.value = null
  errorInfo.value = ''
  
  // Force a full page reload for chunk load errors
  if (oldName === 'ChunkLoadError') {
    window.location.reload()
  }
}

function goHome() {
  hasError.value = false
  error.value = null
  errorInfo.value = ''
  
  const session: any = sessionStore.getSession()
  if (session?.plant?.id) {
    router.push(`/plant/${session.plant.id}/dashboard`)
  } else {
    router.push('/login')
  }
}

function reportError() {
  if (!error.value) return

  const err = error.value as any
  const sess: any = sessionStore as any
  const errorReport = {
    error: err.message,
    stack: err.stack,
    userAgent: navigator.userAgent,
    url: window.location.href,
    timestamp: new Date().toISOString(),
    userId: sess.user?.email,
    plantId: sess.plant?.id
  }

  
  // In a real implementation, you'd send this to your error reporting service
  alert('Error report logged to console (development mode)')
}
</script>

<style scoped>
.error-boundary {
  /* Ensure error boundary takes full space */
  min-height: 100vh;
  width: 100%;
}

/* Make sure code blocks are readable */
pre {
  max-height: 200px;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}
</style>