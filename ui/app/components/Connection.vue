<template>
  <div class="message is-warning" v-if="status !== 'connected'">
    <div class="message-body">
      <span class="icon"><i class="fas"
          :class="{ 'fa-info-circle': status === 'disconnected', 'fa-spinner fa-pulse': status === 'connecting' }" /></span>
      <span v-if="status === 'disconnected'">
        Websocket connection lost, <NuxtLink class="is-bold" @click.prevent="() => $emit('reconnect')">Click here
        </NuxtLink> to reconnect.
      </span>
      <span v-else-if="status === 'connecting'">
        Connecting to websocket server...
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { connectionStatus } from '~/stores/SocketStore'
defineProps<{ 'status': connectionStatus }>()
defineEmits<{ (e: "reconnect"): void }>()
</script>
