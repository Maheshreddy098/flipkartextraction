<template>
  <div class="min-h-screen bg-gray-900 flex items-center justify-center px-4">
    <div class="w-full max-w-sm bg-gray-800 rounded-xl shadow-xl p-8">
      <!-- Header -->
      <div class="text-center mb-8">
        <h1 class="text-2xl font-bold text-white">KFL StoreOps</h1>
        <p class="text-gray-400 text-sm mt-1">Sign in to continue</p>
      </div>

      <!-- Form -->
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">Username</label>
          <input
            v-model="form.usr"
            type="text"
            autocomplete="username"
            required
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            placeholder="Enter username"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">Password</label>
          <input
            v-model="form.pwd"
            type="password"
            autocomplete="current-password"
            required
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            placeholder="Enter password"
          />
        </div>

        <p v-if="errorMsg" class="text-red-400 text-sm">{{ errorMsg }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg text-sm transition-colors"
        >
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login } from '@/core/auth/index.js'
import { useAuthStore } from '@/stores/auth.js'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const form = ref({ usr: '', pwd: '' })
const loading = ref(false)
const errorMsg = ref(
  route.query.error === 'no_role'
    ? 'Your account does not have a StoreOps role assigned. Contact your administrator.'
    : ''
)

async function handleLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    await login(form.value.usr, form.value.pwd)
    await authStore.fetchContext()

    if (!authStore.role) {
      errorMsg.value = 'Your account does not have a StoreOps role assigned. Contact your administrator.'
      authStore.clearAuth()
      return
    }

    const redirect = route.query.redirect || '/dashboard'
    router.push(redirect)
  } catch (e) {
    errorMsg.value = e.message || 'Invalid username or password'
  } finally {
    loading.value = false
  }
}
</script>
