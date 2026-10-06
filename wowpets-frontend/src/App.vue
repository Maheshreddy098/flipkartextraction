<template>
  <div id="wowpets-app" class="min-h-screen bg-gray-50">
    <Notifications />
    <router-view />
  </div>
</template>

<script setup>
import Notifications from '@/components/common/Notifications.vue'
</script>
