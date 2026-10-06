<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center px-4">
    <div class="max-w-md w-full text-center">
      <div class="mb-8">
        <h1 class="text-9xl font-bold text-gray-300">404</h1>
        <h2 class="text-2xl font-bold text-gray-900 mb-4">Page Not Found</h2>
        <p class="text-gray-600 mb-8">
          The page you're looking for doesn't exist or has been moved.
        </p>
      </div>
      
      <div class="space-y-4">
        <button
          @click="goHome"
          class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
        >
          Go to Login
        </button>
        
        <button
          @click="goBack"
          class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 px-4 rounded-lg transition-colors"
        >
          Go Back
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/login')
}

function goBack() {
  router.back()
}
</script>
