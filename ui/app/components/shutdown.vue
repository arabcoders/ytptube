<template>
  <div
    class="relative flex min-h-screen flex-1 items-center justify-center overflow-hidden px-4 py-6 sm:px-6"
  >
    <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        class="absolute top-1/2 left-1/2 size-72 translate-x-[-68%] translate-y-[-70%] rounded-full bg-primary/12 blur-3xl"
      />
      <div
        class="absolute top-1/2 left-1/2 size-64 translate-x-[8%] translate-y-[4%] rounded-full bg-secondary/12 blur-3xl"
      />
    </div>

    <div class="ytp-panel p-0 relative w-full max-w-xl overflow-hidden bg-default/95">
      <div class="space-y-6 px-5 py-6 sm:px-7 sm:py-8" role="status" aria-live="polite">
        <div
          class="inline-flex items-center gap-2 rounded-full border border-default bg-elevated/60 px-3 py-1.5 text-xs font-semibold tracking-[0.22em] text-toned uppercase"
        >
          <UIcon
            name="i-lucide-loader-circle"
            class="size-4 animate-spin text-info"
            aria-hidden="true"
          />
          <span>{{ t('common.shutdownInProgress') }}</span>
        </div>

        <div class="space-y-3">
          <h1 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
            {{ t('common.goodbye') }}
          </h1>

          <p class="text-base leading-7 text-default sm:text-lg">{{ t('common.shuttingDown') }}</p>

          <p v-if="shutdownComplete" class="max-w-lg text-sm leading-6 text-toned sm:text-base">
            {{ t('common.closeWindow') }}
          </p>
        </div>

        <UAlert
          v-if="!shutdownComplete"
          color="info"
          variant="soft"
          icon="i-lucide-power"
          :title="t('common.wrappingUp')"
          :description="t('common.closingServices')"
        />

        <UAlert
          v-else
          color="success"
          variant="soft"
          icon="i-lucide-circle-check"
          :title="t('common.goodbye')"
          :description="t('common.closeWindow')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

const { t } = useI18n();

const shutdownComplete = ref(false);
let shutdownPollTimer: ReturnType<typeof setTimeout> | undefined;
let shutdownPollStopped = false;

const pollShutdown = async () => {
  if (shutdownPollStopped || shutdownComplete.value) {
    return;
  }

  try {
    await request('/api/ping/', { timeout: 2 });
    shutdownPollTimer = setTimeout(pollShutdown, 500);
    return;
  } catch {
    // The server going offline is the completion signal for native shutdown.
  }

  shutdownComplete.value = true;
};

onMounted(() => {
  void pollShutdown();
});

onBeforeUnmount(() => {
  shutdownPollStopped = true;
  if (shutdownPollTimer) {
    clearTimeout(shutdownPollTimer);
  }
});
</script>
