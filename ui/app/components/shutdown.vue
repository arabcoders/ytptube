<template>
  <div
    class="relative flex min-h-screen flex-1 items-center justify-center overflow-hidden px-4 py-6 sm:px-6"
  >
    <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        class="absolute top-1/2 left-1/2 size-72 -translate-x-[68%] -translate-y-[70%] rounded-full bg-primary/12 blur-3xl"
      />
      <div
        class="absolute top-1/2 left-1/2 size-64 translate-x-[8%] translate-y-[4%] rounded-full bg-secondary/12 blur-3xl"
      />
    </div>

    <UPageCard
      variant="outline"
      :ui="pageCardUi"
      class="relative w-full max-w-xl overflow-hidden bg-default/95"
    >
      <template #body>
        <div class="space-y-6 px-5 py-6 sm:px-7 sm:py-8" role="status" aria-live="polite">
          <div
            class="inline-flex items-center gap-2 rounded-full border border-default bg-elevated/60 px-3 py-1.5 text-xs font-semibold tracking-[0.22em] text-toned uppercase"
          >
            <UIcon
              name="i-lucide-loader-circle"
              class="size-4 animate-spin text-info"
              aria-hidden="true"
            />
            <span>Shutdown in progress</span>
          </div>

          <div class="space-y-3">
            <h1 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
              Goodbye!
            </h1>

            <p class="text-base leading-7 text-default sm:text-lg">YTPTube is shutting down.</p>

            <p class="max-w-lg text-sm leading-6 text-toned sm:text-base">
              You may now close this window. Thanks for using YTPTube.
            </p>
          </div>

          <UAlert
            color="info"
            variant="soft"
            icon="i-lucide-power"
            title="Wrapping things up"
            description="The native app is closing background services and should exit shortly."
          />
        </div>
      </template>
    </UPageCard>
  </div>
</template>

<script setup lang="ts">
const pageCardUi = {
  root: 'w-full bg-transparent shadow-2xl shadow-primary/5',
  container: 'w-full p-0',
  wrapper: 'w-full items-stretch',
  body: 'w-full p-0',
};
</script>
