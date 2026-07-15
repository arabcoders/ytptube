<template>
  <UButton
    color="neutral"
    variant="ghost"
    size="sm"
    :icon="icon"
    :square="square"
    :aria-label="title"
    @click="
      () => {
        color.preference = next;
      }
    "
  >
    <span v-if="showLabel" :class="labelClass">{{ title }}</span>
  </UButton>
</template>

<script setup lang="ts">
import { computed } from 'vue';

withDefaults(
  defineProps<{
    square?: boolean;
    showLabel?: boolean;
    labelClass?: string;
  }>(),
  {
    square: false,
    showLabel: true,
    labelClass: '',
  },
);

const { t } = useI18n();

type Choice = 'system' | 'light' | 'dark';

const opts: Array<Choice> = ['system', 'light', 'dark'];
const color = useColorMode();
const current = computed<Choice>(() =>
  opts.includes(color.preference as Choice) ? (color.preference as Choice) : 'system',
);
const next = computed<Choice>(
  () => opts[(opts.indexOf(current.value) + 1) % opts.length] ?? 'system',
);
const icon = computed(() => {
  if (current.value === 'light') {
    return 'i-lucide-sun';
  }

  if (current.value === 'dark') {
    return 'i-lucide-moon';
  }

  return 'i-lucide-monitor';
});
const title = computed(() => {
  if (current.value === 'light') {
    return t('app.theme.light');
  }

  if (current.value === 'dark') {
    return t('app.theme.dark');
  }

  return t('app.theme.system');
});
</script>
