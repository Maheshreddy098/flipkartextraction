<template>
  <div class="p-6">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Inventory Transfer - Mahadevpura</h1>
      <p class="text-gray-600">Manage inventory transfers for Mahadevpura plant</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-blue-100 rounded-lg">
            <span class="text-2xl">🔄</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Transfers Today</p>
            <p class="text-2xl font-bold text-gray-900">12</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-green-100 rounded-lg">
            <span class="text-2xl">✅</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Completed</p>
            <p class="text-2xl font-bold text-gray-900">10</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-yellow-100 rounded-lg">
            <span class="text-2xl">⏳</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">In Progress</p>
            <p class="text-2xl font-bold text-gray-900">2</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-purple-100 rounded-lg">
            <span class="text-2xl">📦</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Total Items</p>
            <p class="text-2xl font-bold text-gray-900">1,245</p>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900">Transfer Management</h2>
      </div>
      <div class="p-6">
        <div class="flex flex-wrap gap-4 mb-6">
          <button class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
            New Transfer
          </button>
          <button class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors">
            Bulk Transfer
          </button>
          <button class="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors">
            View History
          </button>
        </div>
        <p class="text-gray-500">Inventory transfer interface will be implemented here.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'

onMounted(() => {
})
</script>
