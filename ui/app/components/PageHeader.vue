<template>
  <div class="ytp-page-header">
    <div class="ytp-page-heading">
      <span class="ytp-page-icon">
        <slot name="icon">
          <UIcon :name="icon" class="size-5" />
        </slot>
      </span>

      <div class="min-w-0" :class="contentClass">
        <div class="ytp-page-kicker">
          <slot name="kicker">
            <span>{{ sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageLabel }}</span>
          </slot>
        </div>
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
import type { YtpPageHeaderProps } from '~/types';

withDefaults(defineProps<YtpPageHeaderProps>(), {
  contentClass: 'space-y-1',
});
</script>
