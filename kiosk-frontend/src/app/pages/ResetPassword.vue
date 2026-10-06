<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-xl shadow p-6 w-full max-w-md">
      <h1 class="text-xl font-semibold text-gray-900 mb-4">Set a New Password</h1>
      <p class="text-sm text-gray-600 mb-6">Enter a new password for your account.</p>

      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 text-red-700 rounded px-3 py-2 text-sm">{{ error }}</div>
      <div v-if="success" class="mb-4 bg-green-50 border border-green-200 text-green-700 rounded px-3 py-2 text-sm">{{ success }}</div>

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="password" class="block text-sm font-medium text-gray-700 mb-1">New Password</label>
          <input id="password" v-model="password" :type="show ? 'text' : 'password'" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder-gray-400 bg-white caret-blue-600 appearance-none" placeholder="Enter new password" />
        </div>
        <div>
          <label for="confirm" class="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
          <input id="confirm" v-model="confirm" :type="show ? 'text' : 'password'" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder-gray-400 bg-white caret-blue-600 appearance-none" placeholder="Confirm new password" />
        </div>
        <div class="flex items-center justify-between">
          <label class="flex items-center text-sm text-gray-600">
            <input type="checkbox" v-model="show" class="mr-2" /> Show passwords
          </label>
          <button type="submit" :disabled="loading" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-60">Set Password</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authService } from '@/core/auth/authService.js'

const route = useRoute()
const router = useRouter()

const token = ref('')
const password = ref('')
const confirm = ref('')
const show = ref(false)
const loading = ref(false)
const error = ref('')
const success = ref('')

onMounted(() => {
  token.value = String(route.query.token || '')
  if (!token.value) {
    error.value = 'Invalid or missing reset token.'
  }
})

async function handleSubmit() {
  error.value = ''
  success.value = ''
  if (!token.value) {
    error.value = 'Invalid or missing reset token.'
    return
  }
  if (!password.value || password.value.length < 8) {
    error.value = 'Password must be at least 8 characters.'
    return
  }
  if (password.value !== confirm.value) {
    error.value = 'Passwords do not match.'
    return
  }
  loading.value = true
  try {
    await authService.resetPasswordWithToken(token.value, password.value)
    success.value = 'Password updated. Redirecting to login…'
    setTimeout(() => router.push('/kiosk/login'), 1200)
  } catch (e) {
    error.value = e.message || 'Failed to reset password.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
</style>


