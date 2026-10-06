<template>
  <div class="p-6">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Quality Control - Mahadevpura</h1>
      <p class="text-gray-600">Quality management and testing for Mahadevpura plant</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-blue-100 rounded-lg">
            <span class="text-2xl">🔬</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Tests Today</p>
            <p class="text-2xl font-bold text-gray-900">45</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-green-100 rounded-lg">
            <span class="text-2xl">✅</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Passed</p>
            <p class="text-2xl font-bold text-gray-900">42</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-red-100 rounded-lg">
            <span class="text-2xl">❌</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Failed</p>
            <p class="text-2xl font-bold text-gray-900">3</p>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="p-2 bg-yellow-100 rounded-lg">
            <span class="text-2xl">📊</span>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-600">Quality Score</p>
            <p class="text-2xl font-bold text-gray-900">93.3%</p>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900">Quality Tests</h2>
      </div>
      <div class="p-6">
        <div class="flex flex-wrap gap-4 mb-6">
          <button class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
            New Test
          </button>
          <button class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors">
            Generate Report
          </button>
        </div>
        <p class="text-gray-500">Quality control interface will be implemented here.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'

onMounted(() => {
})
</script>
