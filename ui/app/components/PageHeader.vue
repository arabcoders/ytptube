<template>
  <div class="ytp-page-header">
    <div class="ytp-page-heading">
      <span class="ytp-page-icon" :class="{ 'hidden sm:inline-flex': !$slots.icon }">
        <slot name="icon">
          <UIcon :name="icon" class="size-5" aria-hidden="true" />
        </slot>
      </span>

      <div class="min-w-0 space-y-2">
        <p class="text-xs font-medium text-muted">{{ sectionLabel }}</p>
        <h1 class="text-2xl font-semibold tracking-tight text-highlighted sm:text-3xl">
          {{ pageLabel }}
        </h1>
        <p v-if="description" class="max-w-3xl text-sm text-toned">{{ description }}</p>
      </div>
    </div>

    <div
      v-if="$slots.actions"
      class="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:justify-end"
    >
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PageShell } from '~/utils/topLevelNavigation';

defineProps<PageShell>();
</script>
