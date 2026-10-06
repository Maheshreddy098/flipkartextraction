<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
    <div class="w-full max-w-md">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <h1 class="text-3xl font-bold text-gray-900">WowPets 3PL</h1>
          <p class="text-gray-500 mt-2">Warehouse Management System</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              v-model="email"
              type="email"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              placeholder="you@company.com"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              v-model="password"
              type="password"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              placeholder="Enter your password"
            />
          </div>

          <div v-if="errorMsg" class="bg-red-50 text-red-700 px-4 py-3 rounded-lg text-sm">
            {{ errorMsg }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <span v-if="loading">Signing in...</span>
            <span v-else>Sign In</span>
          </button>
        </form>

        <p class="text-center text-xs text-gray-400 mt-6">
          Access is role-based. Contact admin for permissions.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { login } from '@/core/auth/authService.js'
import { APP_CONFIG } from '@/config/settings.js'

const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!email.value.trim() || !password.value) {
    errorMsg.value = 'Email and password are required'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const result = await login(email.value, password.value)
    const dest = result.team === 'warehouse' ? '/warehouse/dashboard' : '/khanalfoods/dashboard'
    // Hard reload (not router.push) so the post-login session's rotated CSRF token
    // is re-issued into window.csrf_token by the boot template. Avoids CSRFTokenError
    // on the first write after an in-app login.
    window.location.href = APP_CONFIG.BASE_PATH + dest
  } catch (err) {
    errorMsg.value = err.response?.data?.message || err.message || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>
