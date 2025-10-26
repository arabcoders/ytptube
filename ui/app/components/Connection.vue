<template>
  <div class="message is-warning" v-if="status === 'disconnected'">
    <div class="message-body">
      <span class="icon"><i class="fas fa-info-circle" /></span>
      <span>
        Connection lost, <NuxtLink class="is-bold" @click.prevent="() => $emit('reconnect')">Click here</NuxtLink>
        to reconnect.
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { connectionStatus } from '~/stores/SocketStore'
defineProps<{ 'status': connectionStatus }>()
defineEmits<{ (e: "reconnect"): void }>()
</script>
