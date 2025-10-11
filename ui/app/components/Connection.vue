<template>
  <Message message_class="p-2 m-2 is-success has-background-warning-90 has-text-dark" v-if="status === 'disconnected'">
    <span class="icon"><i class="fas fa-info-circle" /></span>
    <span>
      Connection lost, <NuxtLink class="is-bold" @click.prevent="() => $emit('reconnect')">Click here</NuxtLink>
      to reconnect.
    </span>
  </Message>
</template>

<script setup lang="ts">
import Message from '~/components/Message.vue'
import type { connectionStatus } from '~/stores/SocketStore'
defineProps<{ 'status': connectionStatus }>()
defineEmits<{ (e: "reconnect"): void }>()
</script>
