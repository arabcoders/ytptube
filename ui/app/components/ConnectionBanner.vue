<template>
  <UAlert
    v-if="sock.connectionStatus !== 'connected'"
    color="warning"
    variant="soft"
    orientation="horizontal"
    :title="title"
  >
    <template #leading>
      <UIcon
        :name="icon"
        :class="[
          'size-4 shrink-0 text-warning',
          sock.connectionStatus === 'connecting' ? 'animate-spin' : '',
        ]"
      />
    </template>

    <template v-if="sock.connectionStatus === 'disconnected'" #actions>
      <UButton color="neutral" variant="link" size="sm" class="px-0" @click="sock.reconnect()">
        {{ t('common.reconnect') }}
      </UButton>
    </template>
  </UAlert>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const { t } = useI18n();

const sock = useAppSocket();

const title = computed(() => {
  if (sock.connectionStatus === 'connecting') {
    return t('app.connection.connectingServer');
  }

  return t('app.connection.lost');
});

const icon = computed(() =>
  sock.connectionStatus === 'connecting' ? 'i-lucide-loader-circle' : 'i-lucide-info',
);
</script>
